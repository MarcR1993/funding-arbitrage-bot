"""
Binance Futures Connector - Connecteur pour Binance Futures
==========================================================

Implémentation du connecteur pour Binance Futures avec support
des funding rates, trading, et gestion des positions.
"""

import os
import ccxt
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import logging

from .base_connector import BaseExchangeConnector, ExchangeError, TradingError, ConnectionError
from ..models.exchange import (
    FundingRate, MarketData, Order, Trade, ExchangeBalance, 
    OrderSide, OrderType, OrderStatus
)
from ..models.position import ExchangePosition, PositionSide


class BinanceConnector(BaseExchangeConnector):
    """
    Connecteur pour Binance Futures
    
    Implémente toutes les fonctionnalités nécessaires pour le trading
    d'arbitrage de funding rates sur Binance Futures.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialise le connecteur Binance
        
        Args:
            config: Configuration contenant api_key, secret, testnet, etc.
        """
        super().__init__("binance", config)
        
        # API credentials
        self.api_key = config.get('api_key') or os.getenv('BINANCE_API_KEY')
        self.secret = config.get('secret') or os.getenv('BINANCE_SECRET')
        self.testnet = config.get('testnet', False) or os.getenv('BINANCE_TESTNET', 'false').lower() == 'true'
        
        if not self.api_key or not self.secret:
            raise ValueError("Binance API key and secret are required")
        
        # CCXT client will be initialized in connect()
        self.client: Optional[ccxt.binance] = None
        
        # Binance specific settings
        self.funding_times_utc = ["00:00", "08:00", "16:00"]
        self.funding_frequency_hours = 8
    
    # =============================================================================
    # CONNECTION MANAGEMENT
    # =============================================================================
    
    async def connect(self) -> bool:
        """Établit la connexion à Binance Futures"""
        try:
            self.client = ccxt.binance({
                'apiKey': self.api_key,
                'secret': self.secret,
                'sandbox': self.testnet,
                'options': {
                    'defaultType': 'future',  # Use futures by default
                    'adjustForTimeDifference': True,
                    'recvWindow': 10000,
                },
                'enableRateLimit': True,
                'rateLimit': 1200,  # 50 requests per second
            })
            
            # Test connection
            await self._test_connection()
            
            self.is_connected = True
            self.last_ping = datetime.now()
            self.connection_errors = 0
            
            self.logger.info(f"Connected to Binance {'Testnet' if self.testnet else 'Mainnet'}")
            return True
            
        except Exception as e:
            self.is_connected = False
            self.connection_errors += 1
            self.logger.error(f"Failed to connect to Binance: {e}")
            raise ConnectionError(f"Binance connection failed: {e}")
    
    async def disconnect(self) -> None:
        """Ferme la connexion à Binance"""
        if self.client:
            await self.client.close()
            self.client = None
        
        self.is_connected = False
        self.logger.info("Disconnected from Binance")
    
    async def ping(self) -> bool:
        """Test de connectivité avec Binance"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                return False
            
            # Use exchange time endpoint for ping
            response = await self.client.fetch_time()
            
            if response:
                self.last_ping = datetime.now()
                return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Binance ping failed: {e}")
            return False
    
    async def _test_connection(self) -> None:
        """Test la connexion et les permissions"""
        if not self.client:
            raise ConnectionError("Client not initialized")
        
        # Test API connectivity
        server_time = await self.client.fetch_time()
        if not server_time:
            raise ConnectionError("Unable to fetch server time")
        
        # Test account access
        account_info = await self.client.fetch_balance()
        if not account_info:
            raise ConnectionError("Unable to fetch account info")
        
        self.logger.info("Binance connection test successful")
    
    # =============================================================================
    # MARKET DATA
    # =============================================================================
    
    async def get_funding_rate(self, symbol: str) -> FundingRate:
        """Récupère le funding rate actuel pour un symbol"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            # Binance uses different symbol format
            binance_symbol = self._format_binance_symbol(symbol)
            
            # Get funding rate
            funding_info = await self.client.fetch_funding_rate(binance_symbol)
            
            if not funding_info:
                raise ExchangeError(f"No funding rate data for {symbol}")
            
            # Get next funding time
            next_funding = await self._calculate_next_funding_time()
            
            return FundingRate(
                exchange=self.exchange_name,
                symbol=symbol,
                funding_rate=float(funding_info['fundingRate']),
                funding_time=datetime.fromtimestamp(funding_info['fundingTimestamp'] / 1000),
                next_funding_time=next_funding,
                index_price=funding_info.get('indexPrice'),
                mark_price=funding_info.get('markPrice'),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error getting Binance funding rate for {symbol}: {e}")
            raise ExchangeError(f"Failed to get funding rate: {e}")
    
    async def get_funding_rates(self, symbols: List[str]) -> Dict[str, FundingRate]:
        """Récupère les funding rates pour plusieurs symbols"""
        funding_rates = {}
        
        # Binance allows batch requests for funding rates
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            # Get all funding rates at once
            all_funding_rates = await self.client.fetch_funding_rates()
            
            for symbol in symbols:
                binance_symbol = self._format_binance_symbol(symbol)
                
                if binance_symbol in all_funding_rates:
                    funding_info = all_funding_rates[binance_symbol]
                    next_funding = await self._calculate_next_funding_time()
                    
                    funding_rates[symbol] = FundingRate(
                        exchange=self.exchange_name,
                        symbol=symbol,
                        funding_rate=float(funding_info['fundingRate']),
                        funding_time=datetime.fromtimestamp(funding_info['fundingTimestamp'] / 1000),
                        next_funding_time=next_funding,
                        index_price=funding_info.get('indexPrice'),
                        mark_price=funding_info.get('markPrice'),
                        timestamp=datetime.now()
                    )
                else:
                    self.logger.warning(f"No funding rate data for {symbol} on Binance")
            
            return funding_rates
            
        except Exception as e:
            self.logger.error(f"Error getting Binance funding rates: {e}")
            # Fallback to individual requests
            for symbol in symbols:
                try:
                    funding_rates[symbol] = await self.get_funding_rate(symbol)
                except Exception:
                    continue
            
            return funding_rates
    
    async def get_next_funding_time(self, symbol: str) -> Optional[datetime]:
        """Récupère l'heure du prochain funding"""
        return await self._calculate_next_funding_time()
    
    async def _calculate_next_funding_time(self) -> datetime:
        """Calcule la prochaine heure de funding Binance"""
        now = datetime.utcnow()
        today = now.date()
        
        # Binance funding times: 00:00, 08:00, 16:00 UTC
        funding_hours = [0, 8, 16]
        
        for hour in funding_hours:
            funding_time = datetime.combine(today, datetime.min.time().replace(hour=hour))
            if funding_time > now:
                return funding_time
        
        # Next day first funding (00:00)
        next_day = today + timedelta(days=1)
        return datetime.combine(next_day, datetime.min.time())
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """Récupère les données de marché"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            binance_symbol = self._format_binance_symbol(symbol)
            
            # Get ticker data
            ticker = await self.client.fetch_ticker(binance_symbol)
            
            # Get funding rate
            funding_info = await self.client.fetch_funding_rate(binance_symbol)
            
            return MarketData(
                exchange=self.exchange_name,
                symbol=symbol,
                bid=ticker.get('bid'),
                ask=ticker.get('ask'),
                last_price=ticker.get('last'),
                mark_price=funding_info.get('markPrice'),
                index_price=funding_info.get('indexPrice'),
                volume_24h=ticker.get('baseVolume'),
                volume_24h_usd=ticker.get('quoteVolume'),
                funding_rate=float(funding_info['fundingRate']),
                next_funding_time=await self._calculate_next_funding_time(),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error getting Binance market data for {symbol}: {e}")
            raise ExchangeError(f"Failed to get market data: {e}")
    
    # =============================================================================
    # TRADING OPERATIONS
    # =============================================================================
    
    async def place_market_order(self, symbol: str, side: OrderSide, 
                                amount: float, **kwargs) -> Order:
        """Place un ordre au marché"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            binance_symbol = self._format_binance_symbol(symbol)
            side_str = side.value.lower()
            
            # Place market order
            result = await self.client.create_market_order(
                symbol=binance_symbol,
                side=side_str,
                amount=amount,
                params=kwargs
            )
            
            return self._parse_order_response(result, symbol)
            
        except Exception as e:
            self.logger.error(f"Error placing Binance market order: {e}")
            raise TradingError(f"Failed to place market order: {e}")
    
    async def place_limit_order(self, symbol: str, side: OrderSide,
                               amount: float, price: float, **kwargs) -> Order:
        """Place un ordre à cours limité"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            binance_symbol = self._format_binance_symbol(symbol)
            side_str = side.value.lower()
            
            # Place limit order
            result = await self.client.create_limit_order(
                symbol=binance_symbol,
                side=side_str,
                amount=amount,
                price=price,
                params=kwargs
            )
            
            return self._parse_order_response(result, symbol)
            
        except Exception as e:
            self.logger.error(f"Error placing Binance limit order: {e}")
            raise TradingError(f"Failed to place limit order: {e}")
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Annule un ordre"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            binance_symbol = self._format_binance_symbol(symbol)
            
            result = await self.client.cancel_order(order_id, binance_symbol)
            
            return result.get('status') == 'canceled'
            
        except Exception as e:
            self.logger.error(f"Error canceling Binance order {order_id}: {e}")
            return False
    
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Récupère les détails d'un ordre"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            binance_symbol = self._format_binance_symbol(symbol)
            
            result = await self.client.fetch_order(order_id, binance_symbol)
            
            if result:
                return self._parse_order_response(result, symbol)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting Binance order {order_id}: {e}")
            return None
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Récupère les ordres ouverts"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            binance_symbol = self._format_binance_symbol(symbol) if symbol else None
            
            orders = await self.client.fetch_open_orders(binance_symbol)
            
            return [self._parse_order_response(order, symbol or self._parse_binance_symbol(order['symbol'])) 
                   for order in orders]
            
        except Exception as e:
            self.logger.error(f"Error getting Binance open orders: {e}")
            return []
    
    # =============================================================================
    # POSITION MANAGEMENT
    # =============================================================================
    
    async def get_position(self, symbol: str) -> Optional[ExchangePosition]:
        """Récupère la position actuelle"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            binance_symbol = self._format_binance_symbol(symbol)
            
            positions = await self.client.fetch_positions([binance_symbol])
            
            for pos in positions:
                if pos['symbol'] == binance_symbol and float(pos['size']) != 0:
                    side = PositionSide.LONG if float(pos['size']) > 0 else PositionSide.SHORT
                    
                    return ExchangePosition(
                        exchange=self.exchange_name,
                        symbol=symbol,
                        side=side,
                        size=abs(float(pos['size'])),
                        entry_price=float(pos['entryPrice']) if pos['entryPrice'] else None,
                        current_price=float(pos['markPrice']) if pos['markPrice'] else None
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting Binance position for {symbol}: {e}")
            return None
    
    async def get_all_positions(self) -> List[ExchangePosition]:
        """Récupère toutes les positions"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            positions = await self.client.fetch_positions()
            
            result = []
            for pos in positions:
                if float(pos['size']) != 0:
                    side = PositionSide.LONG if float(pos['size']) > 0 else PositionSide.SHORT
                    symbol = self._parse_binance_symbol(pos['symbol'])
                    
                    result.append(ExchangePosition(
                        exchange=self.exchange_name,
                        symbol=symbol,
                        side=side,
                        size=abs(float(pos['size'])),
                        entry_price=float(pos['entryPrice']) if pos['entryPrice'] else None,
                        current_price=float(pos['markPrice']) if pos['markPrice'] else None
                    ))
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting Binance positions: {e}")
            return []
    
    async def close_position(self, symbol: str, **kwargs) -> Order:
        """Ferme une position"""
        try:
            # Get current position
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
            self.logger.error(f"Error closing Binance position for {symbol}: {e}")
            raise TradingError(f"Failed to close position: {e}")
    
    # =============================================================================
    # ACCOUNT INFORMATION
    # =============================================================================
    
    async def get_balance(self, asset: str = "USDT") -> ExchangeBalance:
        """Récupère la balance d'un asset"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            balance = await self.client.fetch_balance()
            
            if asset in balance:
                asset_balance = balance[asset]
                
                return ExchangeBalance(
                    exchange=self.exchange_name,
                    asset=asset,
                    total=float(asset_balance.get('total', 0)),
                    available=float(asset_balance.get('free', 0)),
                    locked=float(asset_balance.get('used', 0)),
                    last_updated=datetime.now()
                )
            
            # Asset not found, return zero balance
            return ExchangeBalance(
                exchange=self.exchange_name,
                asset=asset,
                total=0.0,
                available=0.0,
                locked=0.0,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error getting Binance balance for {asset}: {e}")
            raise ExchangeError(f"Failed to get balance: {e}")
    
    async def get_all_balances(self) -> Dict[str, ExchangeBalance]:
        """Récupère toutes les balances"""
        try:
            await self._enforce_rate_limit()
            
            if not self.client:
                raise ConnectionError("Not connected to Binance")
            
            balance = await self.client.fetch_balance()
            
            result = {}
            for asset, asset_balance in balance.items():
                if isinstance(asset_balance, dict) and 'total' in asset_balance:
                    total = float(asset_balance.get('total', 0))
                    if total > 0:  # Only include non-zero balances
                        result[asset] = ExchangeBalance(
                            exchange=self.exchange_name,
                            asset=asset,
                            total=total,
                            available=float(asset_balance.get('free', 0)),
                            locked=float(asset_balance.get('used', 0)),
                            last_updated=datetime.now()
                        )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting Binance balances: {e}")
            return {}
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def _format_binance_symbol(self, symbol: str) -> str:
        """Formate un symbol pour Binance (BTC/USDT -> BTCUSDT)"""
        if '/' in symbol:
            base, quote = symbol.split('/')
            return f"{base.upper()}{quote.upper()}"
        else:
            return f"{symbol.upper()}USDT"
    
    def _parse_binance_symbol(self, binance_symbol: str) -> str:
        """Parse un symbol Binance vers format standard (BTCUSDT -> BTC/USDT)"""
        if binance_symbol.endswith('USDT'):
            base = binance_symbol[:-4]
            return f"{base}/USDT"
        elif binance_symbol.endswith('BUSD'):
            base = binance_symbol[:-4]
            return f"{base}/BUSD"
        else:
            # Fallback
            return binance_symbol
    
    def _parse_order_response(self, order_data: Dict, symbol: str) -> Order:
        """Parse une réponse d'ordre Binance vers notre modèle Order"""
        
        # Map Binance status to our status
        status_mapping = {
            'NEW': OrderStatus.OPEN,
            'PARTIALLY_FILLED': OrderStatus.PARTIALLY_FILLED,
            'FILLED': OrderStatus.FILLED,
            'CANCELED': OrderStatus.CANCELED,
            'REJECTED': OrderStatus.REJECTED,
            'EXPIRED': OrderStatus.EXPIRED
        }
        
        # Map side
        side = OrderSide.BUY if order_data['side'].upper() == 'BUY' else OrderSide.SELL
        
        # Map type
        order_type = OrderType.MARKET if order_data['type'].upper() == 'MARKET' else OrderType.LIMIT
        
        return Order(
            exchange_order_id=str(order_data['id']),
            exchange=self.exchange_name,
            symbol=symbol,
            side=side,
            order_type=order_type,
            size=float(order_data['amount']),
            price=float(order_data['price']) if order_data['price'] else None,
            filled_size=float(order_data['filled']),
            average_fill_price=float(order_data['average']) if order_data['average'] else None,
            fees_paid=float(order_data.get('fee', {}).get('cost', 0)),
            status=status_mapping.get(order_data['status'], OrderStatus.PENDING),
            created_at=datetime.fromtimestamp(order_data['timestamp'] / 1000),
            updated_at=datetime.fromtimestamp(order_data['lastTradeTimestamp'] / 1000) if order_data['lastTradeTimestamp'] else datetime.now()
        )
