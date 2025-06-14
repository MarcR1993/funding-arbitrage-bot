"""
Hyperliquid Connector - Connecteur pour Hyperliquid DEX
======================================================

Implémentation du connecteur pour Hyperliquid avec support
des funding rates (toutes les heures), trading via vault, et gestion des positions.
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import logging
import aiohttp

from .base_connector import BaseExchangeConnector, ExchangeError, TradingError, ConnectionError
from ..models.exchange import (
    FundingRate, MarketData, Order, Trade, ExchangeBalance, 
    OrderSide, OrderType, OrderStatus
)
from ..models.position import ExchangePosition, PositionSide


class HyperliquidConnector(BaseExchangeConnector):
    """
    Connecteur pour Hyperliquid DEX
    
    Implémente toutes les fonctionnalités nécessaires pour le trading
    d'arbitrage de funding rates sur Hyperliquid avec support vault.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialise le connecteur Hyperliquid
        
        Args:
            config: Configuration contenant private_key, vault_address, testnet, etc.
        """
        super().__init__("hyperliquid", config)
        
        # API credentials
        self.private_key = config.get('private_key') or os.getenv('HYPERLIQUID_PRIVATE_KEY')
        self.vault_address = config.get('vault_address') or os.getenv('HYPERLIQUID_VAULT_ADDRESS')
        self.testnet = config.get('testnet', False) or os.getenv('HYPERLIQUID_TESTNET', 'false').lower() == 'true'
        self.use_vault = config.get('use_vault', True)
        
        if not self.private_key:
            raise ValueError("Hyperliquid private key is required")
        
        if self.use_vault and not self.vault_address:
            raise ValueError("Vault address is required when using vault")
        
        # Hyperliquid clients
        self.info_client = None
        self.exchange_client = None
        self.session = None
        
        # Hyperliquid specific settings
        self.funding_frequency_hours = 1  # Every hour!
        self.base_url = "https://api.hyperliquid-testnet.xyz" if self.testnet else "https://api.hyperliquid.xyz"
        
        # Asset info cache
        self._asset_cache = {}
        self._cache_expiry = None
    
    # =============================================================================
    # CONNECTION MANAGEMENT
    # =============================================================================
    
    async def connect(self) -> bool:
        """Établit la connexion à Hyperliquid"""
        try:
            # Import Hyperliquid SDK
            try:
                from hyperliquid.info import Info
                from hyperliquid.exchange import Exchange
                from hyperliquid.utils.signing import get_timestamp_ms
            except ImportError as e:
                raise ConnectionError(f"Hyperliquid SDK not installed: {e}")
            
            # Initialize HTTP session
            self.session = aiohttp.ClientSession()
            
            # Initialize Hyperliquid clients
            self.info_client = Info(self.testnet)
            
            if self.use_vault:
                self.exchange_client = Exchange(
                    self.private_key, 
                    self.testnet,
                    vault_address=self.vault_address
                )
            else:
                self.exchange_client = Exchange(
                    self.private_key, 
                    self.testnet
                )
            
            # Test connection
            await self._test_connection()
            
            self.is_connected = True
            self.last_ping = datetime.now()
            self.connection_errors = 0
            
            self.logger.info(f"Connected to Hyperliquid {'Testnet' if self.testnet else 'Mainnet'}"
                           f"{' via Vault' if self.use_vault else ''}")
            return True
            
        except Exception as e:
            self.is_connected = False
            self.connection_errors += 1
            self.logger.error(f"Failed to connect to Hyperliquid: {e}")
            raise ConnectionError(f"Hyperliquid connection failed: {e}")
    
    async def disconnect(self) -> None:
        """Ferme la connexion à Hyperliquid"""
        if self.session:
            await self.session.close()
            self.session = None
        
        self.info_client = None
        self.exchange_client = None
        self.is_connected = False
        self.logger.info("Disconnected from Hyperliquid")
    
    async def ping(self) -> bool:
        """Test de connectivité avec Hyperliquid"""
        try:
            await self._enforce_rate_limit()
            
            if not self.info_client:
                return False
            
            # Get meta info as ping
            meta = await self._get_meta_info()
            
            if meta:
                self.last_ping = datetime.now()
                return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Hyperliquid ping failed: {e}")
            return False
    
    async def _test_connection(self) -> None:
        """Test la connexion et les permissions"""
        if not self.info_client or not self.exchange_client:
            raise ConnectionError("Clients not initialized")
        
        # Test info API
        meta = await self._get_meta_info()
        if not meta:
            raise ConnectionError("Unable to fetch meta info")
        
        # Test account access
        user_state = await self._get_user_state()
        if user_state is None:
            raise ConnectionError("Unable to fetch user state")
        
        self.logger.info("Hyperliquid connection test successful")
    
    # =============================================================================
    # HYPERLIQUID API HELPERS
    # =============================================================================
    
    async def _get_meta_info(self) -> Optional[Dict]:
        """Récupère les métadonnées des assets"""
        try:
            # Cache meta info for 5 minutes
            now = datetime.now()
            if self._cache_expiry and now < self._cache_expiry and self._asset_cache:
                return self._asset_cache
            
            if not self.session:
                return None
            
            async with self.session.post(f"{self.base_url}/info", 
                                       json={"type": "meta"}) as response:
                if response.status == 200:
                    data = await response.json()
                    self._asset_cache = data
                    self._cache_expiry = now + timedelta(minutes=5)
                    return data
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting Hyperliquid meta info: {e}")
            return None
    
    async def _get_user_state(self) -> Optional[Dict]:
        """Récupère l'état de l'utilisateur"""
        try:
            if not self.session:
                return None
            
            user_address = self.vault_address if self.use_vault else self._get_wallet_address()
            
            async with self.session.post(f"{self.base_url}/info", 
                                       json={
                                           "type": "clearinghouseState",
                                           "user": user_address
                                       }) as response:
                if response.status == 200:
                    return await response.json()
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting Hyperliquid user state: {e}")
            return None
    
    def _get_wallet_address(self) -> str:
        """Récupère l'adresse du wallet depuis la private key"""
        try:
            from eth_account import Account
            account = Account.from_key(self.private_key)
            return account.address
        except Exception as e:
            self.logger.error(f"Error getting wallet address: {e}")
            return ""
    
    def _get_asset_index(self, symbol: str) -> Optional[int]:
        """Récupère l'index d'un asset"""
        if not self._asset_cache or 'universe' not in self._asset_cache:
            return None
        
        base_token = symbol.split('/')[0] if '/' in symbol else symbol
        
        for i, asset in enumerate(self._asset_cache['universe']):
            if asset['name'] == base_token:
                return i
        
        return None
    
    # =============================================================================
    # MARKET DATA
    # =============================================================================
    
    async def get_funding_rate(self, symbol: str) -> FundingRate:
        """Récupère le funding rate actuel pour un symbol"""
        try:
            await self._enforce_rate_limit()
            
            meta = await self._get_meta_info()
            if not meta:
                raise ExchangeError("Unable to fetch meta info")
            
            base_token = symbol.split('/')[0] if '/' in symbol else symbol
            
            # Find asset in universe
            for asset in meta.get('universe', []):
                if asset['name'] == base_token:
                    funding_rate = float(asset.get('funding', 0))
                    
                    # Calculate next funding time (every hour)
                    next_funding = await self._calculate_next_funding_time()
                    
                    return FundingRate(
                        exchange=self.exchange_name,
                        symbol=symbol,
                        funding_rate=funding_rate,
                        funding_time=datetime.now(),  # Hyperliquid updates continuously
                        next_funding_time=next_funding,
                        timestamp=datetime.now()
                    )
            
            raise ExchangeError(f"Asset {base_token} not found in Hyperliquid universe")
            
        except Exception as e:
            self.logger.error(f"Error getting Hyperliquid funding rate for {symbol}: {e}")
            raise ExchangeError(f"Failed to get funding rate: {e}")
    
    async def get_funding_rates(self, symbols: List[str]) -> Dict[str, FundingRate]:
        """Récupère les funding rates pour plusieurs symbols"""
        try:
            await self._enforce_rate_limit()
            
            meta = await self._get_meta_info()
            if not meta:
                return {}
            
            funding_rates = {}
            next_funding = await self._calculate_next_funding_time()
            
            for symbol in symbols:
                base_token = symbol.split('/')[0] if '/' in symbol else symbol
                
                for asset in meta.get('universe', []):
                    if asset['name'] == base_token:
                        funding_rate = float(asset.get('funding', 0))
                        
                        funding_rates[symbol] = FundingRate(
                            exchange=self.exchange_name,
                            symbol=symbol,
                            funding_rate=funding_rate,
                            funding_time=datetime.now(),
                            next_funding_time=next_funding,
                            timestamp=datetime.now()
                        )
                        break
            
            return funding_rates
            
        except Exception as e:
            self.logger.error(f"Error getting Hyperliquid funding rates: {e}")
            return {}
    
    async def get_next_funding_time(self, symbol: str) -> Optional[datetime]:
        """Récupère l'heure du prochain funding"""
        return await self._calculate_next_funding_time()
    
    async def _calculate_next_funding_time(self) -> datetime:
        """Calcule la prochaine heure de funding Hyperliquid (chaque heure)"""
        now = datetime.utcnow()
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return next_hour
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """Récupère les données de marché"""
        try:
            await self._enforce_rate_limit()
            
            if not self.session:
                raise ConnectionError("Not connected to Hyperliquid")
            
            base_token = symbol.split('/')[0] if '/' in symbol else symbol
            
            # Get all mids (prices)
            async with self.session.post(f"{self.base_url}/info", 
                                       json={"type": "allMids"}) as response:
                if response.status != 200:
                    raise ExchangeError("Failed to get market data")
                
                mids_data = await response.json()
            
            # Get meta info for funding
            meta = await self._get_meta_info()
            
            # Find asset data
            asset_index = self._get_asset_index(symbol)
            if asset_index is None:
                raise ExchangeError(f"Asset {base_token} not found")
            
            current_price = None
            funding_rate = None
            
            # Get price from mids
            if str(asset_index) in mids_data:
                current_price = float(mids_data[str(asset_index)])
            
            # Get funding rate from meta
            if meta and 'universe' in meta:
                for asset in meta['universe']:
                    if asset['name'] == base_token:
                        funding_rate = float(asset.get('funding', 0))
                        break
            
            return MarketData(
                exchange=self.exchange_name,
                symbol=symbol,
                last_price=current_price,
                mark_price=current_price,  # Hyperliquid uses mark price as last price
                funding_rate=funding_rate,
                next_funding_time=await self._calculate_next_funding_time(),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error getting Hyperliquid market data for {symbol}: {e}")
            raise ExchangeError(f"Failed to get market data: {e}")
    
    # =============================================================================
    # TRADING OPERATIONS
    # =============================================================================
    
    async def place_market_order(self, symbol: str, side: OrderSide, 
                                amount: float, **kwargs) -> Order:
        """Place un ordre au marché"""
        try:
            await self._enforce_rate_limit()
            
            if not self.exchange_client:
                raise ConnectionError("Not connected to Hyperliquid exchange")
            
            asset_index = self._get_asset_index(symbol)
            if asset_index is None:
                raise TradingError(f"Asset {symbol} not found")
            
            # Hyperliquid uses positive/negative size for buy/sell
            size = amount if side == OrderSide.BUY else -amount
            
            # Create order
            order_request = {
                "asset": asset_index,
                "isBuy": side == OrderSide.BUY,
                "limitPx": None,  # Market order
                "sz": size,
                "orderType": {"limit": {"tif": "Ioc"}}  # Immediate or Cancel for market behavior
            }
            
            result = await self._execute_order(order_request)
            
            return self._parse_hyperliquid_order(result, symbol, side, amount)
            
        except Exception as e:
            self.logger.error(f"Error placing Hyperliquid market order: {e}")
            raise TradingError(f"Failed to place market order: {e}")
    
    async def place_limit_order(self, symbol: str, side: OrderSide,
                               amount: float, price: float, **kwargs) -> Order:
        """Place un ordre à cours limité"""
        try:
            await self._enforce_rate_limit()
            
            if not self.exchange_client:
                raise ConnectionError("Not connected to Hyperliquid exchange")
            
            asset_index = self._get_asset_index(symbol)
            if asset_index is None:
                raise TradingError(f"Asset {symbol} not found")
            
            # Hyperliquid uses positive/negative size for buy/sell
            size = amount if side == OrderSide.BUY else -amount
            
            # Create order
            order_request = {
                "asset": asset_index,
                "isBuy": side == OrderSide.BUY,
                "limitPx": price,
                "sz": size,
                "orderType": {"limit": {"tif": "Gtc"}}  # Good til Cancel
            }
            
            result = await self._execute_order(order_request)
            
            return self._parse_hyperliquid_order(result, symbol, side, amount, price)
            
        except Exception as e:
            self.logger.error(f"Error placing Hyperliquid limit order: {e}")
            raise TradingError(f"Failed to place limit order: {e}")
    
    async def _execute_order(self, order_request: Dict) -> Dict:
        """Execute un ordre via l'exchange client"""
        try:
            # Use the exchange client to place order
            if hasattr(self.exchange_client, 'order'):
                result = self.exchange_client.order(order_request)
            else:
                # Fallback method
                result = await self._place_order_direct(order_request)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing Hyperliquid order: {e}")
            raise TradingError(f"Order execution failed: {e}")
    
    async def _place_order_direct(self, order_request: Dict) -> Dict:
        """Place ordre directement via API (fallback)"""
        # This would require implementing the signing and API call directly
        # For now, raise an error
        raise TradingError("Direct order placement not implemented")
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Annule un ordre"""
        try:
            await self._enforce_rate_limit()
            
            if not self.exchange_client:
                raise ConnectionError("Not connected to Hyperliquid exchange")
            
            asset_index = self._get_asset_index(symbol)
            if asset_index is None:
                return False
            
            cancel_request = {
                "asset": asset_index,
                "oid": int(order_id)
            }
            
            result = self.exchange_client.cancel(cancel_request)
            
            return result.get('status') == 'ok'
            
        except Exception as e:
            self.logger.error(f"Error canceling Hyperliquid order {order_id}: {e}")
            return False
    
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Récupère les détails d'un ordre"""
        # Hyperliquid doesn't have a direct order query endpoint
        # Would need to get from order history or open orders
        return None
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Récupère les ordres ouverts"""
        try:
            user_state = await self._get_user_state()
            if not user_state:
                return []
            
            orders = []
            for order_data in user_state.get('assetPositions', []):
                # Parse open orders from user state
                # This would need more detailed implementation
                pass
            
            return orders
            
        except Exception as e:
            self.logger.error(f"Error getting Hyperliquid open orders: {e}")
            return []
    
    # =============================================================================
    # POSITION MANAGEMENT
    # =============================================================================
    
    async def get_position(self, symbol: str) -> Optional[ExchangePosition]:
        """Récupère la position actuelle"""
        try:
            user_state = await self._get_user_state()
            if not user_state:
                return None
            
            asset_index = self._get_asset_index(symbol)
            if asset_index is None:
                return None
            
            # Find position in user state
            for position_data in user_state.get('assetPositions', []):
                if position_data.get('position', {}).get('coin') == asset_index:
                    pos_info = position_data['position']
                    size = float(pos_info.get('szi', 0))
                    
                    if size != 0:
                        side = PositionSide.LONG if size > 0 else PositionSide.SHORT
                        
                        return ExchangePosition(
                            exchange=self.exchange_name,
                            symbol=symbol,
                            side=side,
                            size=abs(size),
                            entry_price=float(pos_info.get('entryPx', 0)),
                            current_price=None  # Would need separate call to get current price
                        )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting Hyperliquid position for {symbol}: {e}")
            return None
    
    async def get_all_positions(self) -> List[ExchangePosition]:
        """Récupère toutes les positions"""
        try:
            user_state = await self._get_user_state()
            if not user_state:
                return []
            
            positions = []
            meta = await self._get_meta_info()
            
            for position_data in user_state.get('assetPositions', []):
                pos_info = position_data['position']
                size = float(pos_info.get('szi', 0))
                
                if size != 0:
                    asset_index = pos_info.get('coin')
                    symbol = self._get_symbol_from_index(asset_index, meta)
                    
                    if symbol:
                        side = PositionSide.LONG if size > 0 else PositionSide.SHORT
                        
                        positions.append(ExchangePosition(
                            exchange=self.exchange_name,
                            symbol=symbol,
                            side=side,
                            size=abs(size),
                            entry_price=float(pos_info.get('entryPx', 0))
                        ))
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting Hyperliquid positions: {e}")
            return []
    
    def _get_symbol_from_index(self, asset_index: int, meta: Optional[Dict]) -> Optional[str]:
        """Récupère le symbol depuis l'index d'asset"""
        if not meta or 'universe' not in meta:
            return None
        
        if asset_index < len(meta['universe']):
            asset_name = meta['universe'][asset_index]['name']
            return f"{asset_name}/USDT"
        
        return None
    
    async def close_position(self, symbol: str, **kwargs) -> Order:
        """Ferme une position"""
        try:
            position = await self.get_position(symbol)
            
            if not position:
                raise TradingError(f"No position found for {symbol}")
            
            # Determine opposite side
            opposite_side = OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
            
            # Close with market order
            return await self.place_market_order(
                symbol=symbol,
                side=opposite_side,
                amount=position.size,
                **kwargs
            )
            
        except Exception as e:
            self.logger.error(f"Error closing Hyperliquid position for {symbol}: {e}")
            raise TradingError(f"Failed to close position: {e}")
    
    # =============================================================================
    # ACCOUNT INFORMATION
    # =============================================================================
    
    async def get_balance(self, asset: str = "USDT") -> ExchangeBalance:
        """Récupère la balance d'un asset"""
        try:
            user_state = await self._get_user_state()
            if not user_state:
                raise ExchangeError("Unable to get user state")
            
            # Hyperliquid uses USDC as base currency, but we'll treat as USDT
            margin_summary = user_state.get('marginSummary', {})
            
            if asset.upper() in ['USDT', 'USDC', 'USD']:
                account_value = float(margin_summary.get('accountValue', 0))
                
                return ExchangeBalance(
                    exchange=self.exchange_name,
                    asset=asset,
                    total=account_value,
                    available=account_value,  # Simplified - would need more detailed calculation
                    locked=0.0,
                    last_updated=datetime.now()
                )
            
            # For other assets, return zero
            return ExchangeBalance(
                exchange=self.exchange_name,
                asset=asset,
                total=0.0,
                available=0.0,
                locked=0.0,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error getting Hyperliquid balance for {asset}: {e}")
            raise ExchangeError(f"Failed to get balance: {e}")
    
    async def get_all_balances(self) -> Dict[str, ExchangeBalance]:
        """Récupère toutes les balances"""
        try:
            # Hyperliquid primarily uses USDC
            usdt_balance = await self.get_balance("USDT")
            return {"USDT": usdt_balance}
            
        except Exception as e:
            self.logger.error(f"Error getting Hyperliquid balances: {e}")
            return {}
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def _parse_hyperliquid_order(self, order_result: Dict, symbol: str, 
                                side: OrderSide, amount: float, price: Optional[float] = None) -> Order:
        """Parse une réponse d'ordre Hyperliquid vers notre modèle Order"""
        
        return Order(
            exchange_order_id=str(order_result.get('status', {}).get('resting', {}).get('oid', 'unknown')),
            exchange=self.exchange_name,
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET if price is None else OrderType.LIMIT,
            size=amount,
            price=price,
            filled_size=0.0,  # Would need to be updated based on fills
            status=OrderStatus.PENDING,  # Would need proper status mapping
            created_at=datetime.now()
        )
