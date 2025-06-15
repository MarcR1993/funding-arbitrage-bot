
"""
Hyperliquid connector for funding rate arbitrage.
Attribution: Based on Hummingbot's connector patterns (Apache 2.0)
Note: Hyperliquid has unique API patterns compared to traditional exchanges
"""

import asyncio
import logging
import time
import json
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime

import aiohttp
import ccxt.async_support as ccxt
from ccxt.base.errors import NetworkError, ExchangeError

from .base_connector import BaseConnector
from src.models.order import Order, OrderStatus, OrderType, OrderSide
from src.models.balance import Balance
from src.models.funding_rate import FundingRate
from src.models.position import Position, PositionSide
from src.utils.async_utils import safe_ensure_future
from src.utils.time_utils import get_utc_datetime


class HyperliquidConnector(BaseConnector):
    """
    Hyperliquid exchange connector for perpetual futures trading.
    
    Note: Hyperliquid uses a unique API structure different from traditional exchanges.
    It's a decentralized perp DEX with on-chain settlement but centralized matching.
    """
    
    def __init__(self, api_key: str, api_secret: str, sandbox: bool = False):
        super().__init__("hyperliquid", api_key, api_secret, sandbox)
        
        # Hyperliquid API endpoints
        self.base_url = "https://api.hyperliquid-testnet.xyz" if sandbox else "https://api.hyperliquid.xyz"
        self.info_url = f"{self.base_url}/info"
        self.exchange_url = f"{self.base_url}/exchange"
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 0.2  # 200ms between requests
        
        # Symbol mapping (Hyperliquid uses different notation)
        self._symbol_map = {}
        
        # Asset info cache
        self._asset_info = {}
        
    async def connect(self) -> bool:
        """Connect to Hyperliquid API"""
        try:
            # Create HTTP session
            self._session = aiohttp.ClientSession()
            
            # Test connection by getting asset info
            await self._load_asset_info()
            
            # Load symbol mappings
            await self._load_symbol_mappings()
            
            self.logger.info("Connected to Hyperliquid successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Hyperliquid: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Hyperliquid"""
        if self._session:
            await self._session.close()
            self._session = None
        self.logger.info("Disconnected from Hyperliquid")
    
    async def _load_asset_info(self):
        """Load asset information from Hyperliquid"""
        try:
            data = {"type": "meta"}
            async with self._session.post(self.info_url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    self._asset_info = {asset['name']: asset for asset in result.get('universe', [])}
                else:
                    raise Exception(f"Failed to load asset info: {response.status}")
                    
        except Exception as e:
            self.logger.error(f"Error loading asset info: {e}")
            raise
    
    async def _load_symbol_mappings(self):
        """Load symbol mappings from Hyperliquid"""
        try:
            # Hyperliquid uses asset names like "BTC", "ETH" for perpetuals
            for asset_name, asset_info in self._asset_info.items():
                if asset_info.get('onlyIsolated') is False:  # Cross margin available
                    # Map our format (BTC-USDT) to Hyperliquid format (BTC)
                    our_symbol = f"{asset_name}-USDT"
                    self._symbol_map[our_symbol] = asset_name
                    
        except Exception as e:
            self.logger.error(f"Error loading symbol mappings: {e}")
    
    def _convert_symbol(self, symbol: str) -> str:
        """Convert our symbol format to Hyperliquid format"""
        return self._symbol_map.get(symbol, symbol.split('-')[0])
    
    async def _rate_limit(self):
        """Apply rate limiting"""
        now = time.time()
        time_since_last = now - self._last_request_time
        if time_since_last < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - time_since_last)
        self._last_request_time = time.time()
    
    async def _make_request(self, url: str, data: dict) -> dict:
        """Make authenticated request to Hyperliquid"""
        await self._rate_limit()
        
        try:
            async with self._session.post(url, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"HTTP {response.status}: {await response.text()}")
                    
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            raise
    
    async def get_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """Get current funding rate for a symbol"""
        try:
            hl_symbol = self._convert_symbol(symbol)
            
            # Get funding rate from Hyperliquid
            data = {
                "type": "fundingHistory",
                "coin": hl_symbol,
                "startTime": int((datetime.utcnow().timestamp() - 3600) * 1000)  # Last hour
            }
            
            response = await self._make_request(self.info_url, data)
            
            if response and len(response) > 0:
                # Get the most recent funding rate
                latest_funding = response[-1]
                rate = Decimal(str(latest_funding['fundingRate']))
                
                # Hyperliquid funding happens every 8 hours at 00:00, 08:00, 16:00 UTC
                # Calculate next funding time
                current_time = datetime.utcnow()
                current_hour = current_time.hour
                
                if current_hour < 8:
                    next_hour = 8
                elif current_hour < 16:
                    next_hour = 16
                else:
                    next_hour = 24  # Next day 00:00
                
                next_funding_time = current_time.replace(
                    hour=next_hour % 24, 
                    minute=0, 
                    second=0, 
                    microsecond=0
                )
                
                if next_hour == 24:
                    next_funding_time = next_funding_time.replace(hour=0)
                    next_funding_time = next_funding_time.replace(day=next_funding_time.day + 1)
                
                funding_rate = FundingRate(
                    exchange=self._exchange_name,
                    symbol=symbol,
                    rate=rate,
                    next_funding_time=next_funding_time,
                    interval_hours=8
                )
                
                # Update cache and emit event
                self.update_funding_rate(symbol, funding_rate)
                
                return funding_rate
                
        except Exception as e:
            self.logger.error(f"Error getting funding rate for {symbol}: {e}")
            return None
    
    async def get_balance(self, asset: str) -> Optional[Balance]:
        """Get balance for an asset"""
        try:
            data = {
                "type": "clearinghouseState",
                "user": self._api_key  # In Hyperliquid, user address is used
            }
            
            response = await self._make_request(self.info_url, data)
            
            if response and 'marginSummary' in response:
                margin_summary = response['marginSummary']
                
                if asset == 'USDT':
                    # USDT is the base currency in Hyperliquid
                    total_value = Decimal(str(margin_summary['accountValue']))
                    available = total_value  # Simplified - should account for margin requirements
                    
                    balance = Balance(
                        asset=asset,
                        exchange=self._exchange_name,
                        total=total_value,
                        available=available,
                        locked=Decimal("0")
                    )
                    
                    # Update cache and emit event
                    self.update_balance(asset, balance)
                    
                    return balance
                
        except Exception as e:
            self.logger.error(f"Error getting balance for {asset}: {e}")
            return None
    
    async def place_order(self, 
                         symbol: str,
                         side: str,
                         order_type: OrderType,
                         amount: Decimal,
                         price: Optional[Decimal] = None) -> Optional[Order]:
        """Place an order on Hyperliquid"""
        try:
            hl_symbol = self._convert_symbol(symbol)
            
            # Get asset index
            if hl_symbol not in self._asset_info:
                self.logger.error(f"Unknown symbol: {hl_symbol}")
                return None
                
            asset_info = self._asset_info[hl_symbol]
            asset_index = asset_info['assetId']
            
            # Prepare order data
            order_data = {
                "coin": hl_symbol,
                "is_buy": side.upper() == "BUY",
                "sz": str(amount),
                "limit_px": str(price) if order_type == OrderType.LIMIT and price else None,
                "order_type": {
                    OrderType.MARKET: "Market",
                    OrderType.LIMIT: "Limit"
                }.get(order_type, "Limit"),
                "reduce_only": False
            }
            
            # Create the exchange request
            exchange_data = {
                "type": "order",
                "orders": [order_data],
                "grouping": "na"
            }
            
            response = await self._make_request(self.exchange_url, exchange_data)
            
            if response and 'status' in response and response['status'] == 'ok':
                # Hyperliquid returns transaction hash instead of order ID
                tx_hash = response.get('response', {}).get('data', {}).get('statuses', [{}])[0].get('resting', {}).get('oid')
                
                if tx_hash:
                    order = Order(
                        order_id=str(tx_hash),
                        client_order_id=str(tx_hash),
                        exchange=self._exchange_name,
                        symbol=symbol,
                        side=OrderSide.BUY if side.upper() == 'BUY' else OrderSide.SELL,
                        order_type=order_type,
                        amount=amount,
                        price=price,
                        status=OrderStatus.PENDING,
                        filled_amount=Decimal("0")
                    )
                    
                    # Update cache and emit event
                    self.update_order(order)
                    
                    return order
                
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            # Get the order to find the symbol
            cached_order = self.get_cached_order(order_id)
            if not cached_order:
                self.logger.error(f"Order {order_id} not found in cache")
                return False
            
            hl_symbol = self._convert_symbol(cached_order.symbol)
            
            cancel_data = {
                "type": "cancel",
                "cancels": [{
                    "coin": hl_symbol,
                    "oid": int(order_id)
                }]
            }
            
            response = await self._make_request(self.exchange_url, cancel_data)
            
            if response and response.get('status') == 'ok':
                # Update order status
                cached_order.status = OrderStatus.CANCELED
                self.update_order(cached_order)
                return True
                
        except Exception as e:
            self.logger.error(f"Error canceling order {order_id}: {e}")
            return False
    
    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get order status"""
        try:
            # Get cached order
            cached_order = self.get_cached_order(order_id)
            if not cached_order:
                return None
            
            # Get open orders to check status
            data = {
                "type": "openOrders",
                "user": self._api_key
            }
            
            response = await self._make_request(self.info_url, data)
            
            if response:
                # Check if order is still open
                order_found = False
                for open_order in response:
                    if str(open_order.get('oid')) == order_id:
                        order_found = True
                        # Update with current info
                        cached_order.filled_amount = Decimal(str(open_order.get('sz', 0))) - Decimal(str(open_order.get('szOpen', 0)))
                        cached_order.status = OrderStatus.OPEN if open_order.get('szOpen', 0) > 0 else OrderStatus.FILLED
                        break
                
                if not order_found:
                    # Order not in open orders, likely filled or canceled
                    cached_order.status = OrderStatus.FILLED
                
                self.update_order(cached_order)
                return cached_order
                
        except Exception as e:
            self.logger.error(f"Error getting order status for {order_id}: {e}")
            return None
    
    async def get_position_size(self, symbol: str) -> Decimal:
        """Get current position size for a symbol"""
        try:
            hl_symbol = self._convert_symbol(symbol)
            
            data = {
                "type": "clearinghouseState",
                "user": self._api_key
            }
            
            response = await self._make_request(self.info_url, data)
            
            if response and 'assetPositions' in response:
                for pos in response['assetPositions']:
                    if pos['position']['coin'] == hl_symbol:
                        return Decimal(str(pos['position']['szi']))
            
            return Decimal("0")
            
        except Exception as e:
            self.logger.error(f"Error getting position size for {symbol}: {e}")
            return Decimal("0")
    
    async def get_positions(self) -> List[Position]:
        """Get all current positions"""
        try:
            data = {
                "type": "clearinghouseState",
                "user": self._api_key
            }
            
            response = await self._make_request(self.info_url, data)
            positions = []
            
            if response and 'assetPositions' in response:
                for pos in response['assetPositions']:
                    position_data = pos['position']
                    size = Decimal(str(position_data['szi']))
                    
                    if size != 0:  # Only include non-zero positions
                        position = Position(
                            exchange=self._exchange_name,
                            symbol=position_data['coin'],
                            side=PositionSide.LONG if size > 0 else PositionSide.SHORT,
                            size=abs(size),
                            entry_price=Decimal(str(position_data.get('entryPx', 0))) if position_data.get('entryPx') else None,
                            unrealized_pnl=Decimal(str(position_data.get('unrealizedPnl', 0))) if position_data.get('unrealizedPnl') else None
                        )
                        positions.append(position)
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []
    
    async def _funding_rate_monitor(self):
        """Monitor funding rates for all trading pairs"""
        while self.is_connected:
            try:
                # Get funding rates for all perpetual symbols
                for our_symbol in self._symbol_map.keys():
                    await self.get_funding_rate(our_symbol)
                    await asyncio.sleep(2)  # Longer delay for Hyperliquid
                
                # Wait before next update cycle
                await asyncio.sleep(120)  # Update every 2 minutes (less frequent than CEX)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in funding rate monitor: {e}")
                await asyncio.sleep(60)
    
    async def _balance_monitor(self):
        """Monitor account balances"""
        while self.is_connected:
            try:
                await self.get_balance('USDT')  # Main currency
                await asyncio.sleep(60)  # Update every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in balance monitor: {e}")
                await asyncio.sleep(60)
    
    async def _order_monitor(self):
        """Monitor order status updates"""
        while self.is_connected:
            try:
                # Check status of all tracked orders
                for order_id in list(self._orders.keys()):
                    order = await self.get_order_status(order_id)
                    if order and order.is_done:
                        # Remove completed orders from tracking
                        del self._orders[order_id]
                    
                    await asyncio.sleep(1)
                
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in order monitor: {e}")
                await asyncio.sleep(30)
