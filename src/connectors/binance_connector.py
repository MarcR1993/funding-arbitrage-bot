"""
Binance connector for funding rate arbitrage.
Attribution: Based on Hummingbot's Binance connector (Apache 2.0)
Original: https://github.com/hummingbot/hummingbot/tree/master/hummingbot/connector/exchange/binance
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime

import ccxt.async_support as ccxt
from ccxt.base.errors import NetworkError, ExchangeError

from .base_connector import BaseConnector
from src.models.order import Order, OrderStatus, OrderType, OrderSide
from src.models.balance import Balance
from src.models.funding_rate import FundingRate
from src.models.position import Position, PositionSide
from src.utils.async_utils import safe_ensure_future
from src.utils.time_utils import get_utc_datetime


class BinanceConnector(BaseConnector):
    """
    Binance exchange connector for perpetual futures trading.
    Attribution: Adapted from Hummingbot's Binance connector (Apache 2.0)
    """
    
    def __init__(self, api_key: str, api_secret: str, sandbox: bool = False):
        super().__init__("binance", api_key, api_secret, sandbox)
        
        # CCXT exchange instance
        self._exchange: Optional[ccxt.binance] = None
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 0.1  # 100ms between requests
        
        # Symbol mapping (Binance uses different notation)
        self._symbol_map = {}
        
    async def connect(self) -> bool:
        """Connect to Binance API"""
        try:
            # Initialize CCXT exchange
            exchange_config = {
                'apiKey': self._api_key,
                'secret': self._api_secret,
                'sandbox': self._sandbox,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',  # Use futures API
                }
            }
            
            self._exchange = ccxt.binance(exchange_config)
            
            # Test connection
            await self._exchange.load_markets()
            
            # Load symbol mappings
            await self._load_symbol_mappings()
            
            self.logger.info("Connected to Binance successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Binance: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Binance"""
        if self._exchange:
            await self._exchange.close()
            self._exchange = None
        self.logger.info("Disconnected from Binance")
    
    async def _load_symbol_mappings(self):
        """Load symbol mappings from Binance"""
        try:
            markets = await self._exchange.load_markets()
            for symbol, market in markets.items():
                if market['type'] == 'future' and market['settle'] == 'USDT':
                    # Map our format (BTC-USDT) to Binance format (BTC/USDT)
                    our_symbol = f"{market['base']}-{market['quote']}"
                    self._symbol_map[our_symbol] = symbol
                    
        except Exception as e:
            self.logger.error(f"Error loading symbol mappings: {e}")
    
    def _convert_symbol(self, symbol: str) -> str:
        """Convert our symbol format to Binance format"""
        return self._symbol_map.get(symbol, symbol.replace('-', '/'))
    
    async def _rate_limit(self):
        """Apply rate limiting"""
        now = time.time()
        time_since_last = now - self._last_request_time
        if time_since_last < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - time_since_last)
        self._last_request_time = time.time()
    
    async def get_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """Get current funding rate for a symbol"""
        try:
            await self._rate_limit()
            
            binance_symbol = self._convert_symbol(symbol)
            
            # Get funding rate from Binance
            response = await self._exchange.fapiPublic_get_premiumindex({
                'symbol': binance_symbol.replace('/', '')
            })
            
            if response:
                rate = Decimal(str(response['lastFundingRate']))
                
                # Get next funding time
                next_funding_timestamp = int(response['nextFundingTime']) / 1000
                next_funding_time = datetime.fromtimestamp(next_funding_timestamp)
                
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
            await self._rate_limit()
            
            balance_data = await self._exchange.fetch_balance()
            
            if asset in balance_data:
                asset_balance = balance_data[asset]
                
                balance = Balance(
                    asset=asset,
                    exchange=self._exchange_name,
                    total=Decimal(str(asset_balance['total'])),
                    available=Decimal(str(asset_balance['free'])),
                    locked=Decimal(str(asset_balance['used']))
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
        """Place an order on Binance"""
        try:
            await self._rate_limit()
            
            binance_symbol = self._convert_symbol(symbol)
            
            # Convert order type
            ccxt_type = 'market' if order_type == OrderType.MARKET else 'limit'
            
            # Place order
            order_params = {}
            if order_type == OrderType.LIMIT and price:
                order_params['price'] = float(price)
            
            response = await self._exchange.create_order(
                symbol=binance_symbol,
                type=ccxt_type,
                side=side.lower(),
                amount=float(amount),
                **order_params
            )
            
            if response:
                order = Order(
                    order_id=str(response['id']),
                    client_order_id=str(response['clientOrderId']),
                    exchange=self._exchange_name,
                    symbol=symbol,
                    side=OrderSide.BUY if side.upper() == 'BUY' else OrderSide.SELL,
                    order_type=order_type,
                    amount=amount,
                    price=price,
                    status=OrderStatus.PENDING,
                    filled_amount=Decimal(str(response.get('filled', 0)))
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
            await self._rate_limit()
            
            # Get the order to find the symbol
            cached_order = self.get_cached_order(order_id)
            if not cached_order:
                self.logger.error(f"Order {order_id} not found in cache")
                return False
            
            binance_symbol = self._convert_symbol(cached_order.symbol)
            
            response = await self._exchange.cancel_order(order_id, binance_symbol)
            
            if response:
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
            await self._rate_limit()
            
            # Get cached order for symbol
            cached_order = self.get_cached_order(order_id)
            if not cached_order:
                return None
            
            binance_symbol = self._convert_symbol(cached_order.symbol)
            
            response = await self._exchange.fetch_order(order_id, binance_symbol)
            
            if response:
                # Update order status
                status_map = {
                    'open': OrderStatus.OPEN,
                    'closed': OrderStatus.FILLED,
                    'canceled': OrderStatus.CANCELED,
                    'rejected': OrderStatus.REJECTED
                }
                
                cached_order.status = status_map.get(response['status'], OrderStatus.PENDING)
                cached_order.filled_amount = Decimal(str(response['filled']))
                
                self.update_order(cached_order)
                
                return cached_order
                
        except Exception as e:
            self.logger.error(f"Error getting order status for {order_id}: {e}")
            return None
    
    async def get_position_size(self, symbol: str) -> Decimal:
        """Get current position size for a symbol"""
        try:
            await self._rate_limit()
            
            binance_symbol = self._convert_symbol(symbol)
            
            positions = await self._exchange.fapiPrivate_get_positionrisk()
            
            for pos in positions:
                if pos['symbol'] == binance_symbol.replace('/', ''):
                    return Decimal(str(pos['positionAmt']))
            
            return Decimal("0")
            
        except Exception as e:
            self.logger.error(f"Error getting position size for {symbol}: {e}")
            return Decimal("0")
    
    async def get_positions(self) -> List[Position]:
        """Get all current positions"""
        try:
            await self._rate_limit()
            
            positions_data = await self._exchange.fapiPrivate_get_positionrisk()
            positions = []
            
            for pos in positions_data:
                size = Decimal(str(pos['positionAmt']))
                if size != 0:  # Only include non-zero positions
                    position = Position(
                        exchange=self._exchange_name,
                        symbol=pos['symbol'],
                        side=PositionSide.LONG if size > 0 else PositionSide.SHORT,
                        size=abs(size),
                        entry_price=Decimal(str(pos['entryPrice'])) if pos['entryPrice'] else None,
                        mark_price=Decimal(str(pos['markPrice'])) if pos['markPrice'] else None,
                        unrealized_pnl=Decimal(str(pos['unRealizedProfit'])) if pos['unRealizedProfit'] else None
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
                    await asyncio.sleep(1)  # Small delay between symbols
                
                # Wait before next update cycle
                await asyncio.sleep(60)  # Update every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in funding rate monitor: {e}")
                await asyncio.sleep(30)
    
    async def _balance_monitor(self):
        """Monitor account balances"""
        assets_to_monitor = ['USDT', 'BTC', 'ETH', 'BNB']  # Common assets
        
        while self.is_connected:
            try:
                for asset in assets_to_monitor:
                    await self.get_balance(asset)
                    await asyncio.sleep(0.5)
                
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in balance monitor: {e}")
                await asyncio.sleep(30)
    
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
                    
                    await asyncio.sleep(0.5)
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in order monitor: {e}")
                await asyncio.sleep(30)
