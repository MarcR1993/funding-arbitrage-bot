
"""
KuCoin connector for funding rate arbitrage.
Attribution: Based on Hummingbot's connector patterns (Apache 2.0)
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


class KuCoinConnector(BaseConnector):
    """
    KuCoin exchange connector for perpetual futures trading.
    """
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str, sandbox: bool = False):
        super().__init__("kucoin", api_key, api_secret, sandbox)
        
        # KuCoin requires a passphrase
        self._passphrase = passphrase
        
        # CCXT exchange instance
        self._exchange: Optional[ccxt.kucoinfutures] = None
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 0.1  # 100ms between requests
        
        # Symbol mapping
        self._symbol_map = {}
        
    async def connect(self) -> bool:
        """Connect to KuCoin API"""
        try:
            # Initialize CCXT exchange for KuCoin Futures
            exchange_config = {
                'apiKey': self._api_key,
                'secret': self._api_secret,
                'password': self._passphrase,
                'sandbox': self._sandbox,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',  # Use futures API
                }
            }
            
            self._exchange = ccxt.kucoinfutures(exchange_config)
            
            # Test connection
            await self._exchange.load_markets()
            
            # Load symbol mappings
            await self._load_symbol_mappings()
            
            self.logger.info("Connected to KuCoin successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to KuCoin: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from KuCoin"""
        if self._exchange:
            await self._exchange.close()
            self._exchange = None
        self.logger.info("Disconnected from KuCoin")
    
    async def _load_symbol_mappings(self):
        """Load symbol mappings from KuCoin"""
        try:
            markets = await self._exchange.load_markets()
            for symbol, market in markets.items():
                if market['type'] == 'future' and market['settle'] == 'USDT':
                    # Map our format (BTC-USDT) to KuCoin format (BTC/USDT:USDT)
                    our_symbol = f"{market['base']}-{market['quote']}"
                    self._symbol_map[our_symbol] = symbol
                    
        except Exception as e:
            self.logger.error(f"Error loading symbol mappings: {e}")
    
    def _convert_symbol(self, symbol: str) -> str:
        """Convert our symbol format to KuCoin format"""
        return self._symbol_map.get(symbol, symbol.replace('-', '/') + ':USDT')
    
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
            
            kucoin_symbol = self._convert_symbol(symbol)
            
            # Get funding rate from KuCoin
            # KuCoin uses a different endpoint structure
            response = await self._exchange.publicGetContractsActive()
            
            if response and 'data' in response:
                for contract in response['data']:
                    if contract['symbol'] == kucoin_symbol.replace('/', '').replace(':USDT', 'M'):
                        rate = Decimal(str(contract.get('fundingFeeRate', 0)))
                        
                        # Calculate next funding time (KuCoin uses 8-hour intervals)
                        next_funding_timestamp = int(contract.get('nextFundingRateTime', 0))
                        if next_funding_timestamp:
                            next_funding_time = datetime.fromtimestamp(next_funding_timestamp / 1000)
                        else:
                            # Fallback calculation
                            current_time = datetime.utcnow()
                            current_hour = current_time.hour
                            
                            if current_hour < 8:
                                next_hour = 8
                            elif current_hour < 16:
                                next_hour = 16
                            else:
                                next_hour = 24
                            
                            next_funding_time = current_time.replace(
                                hour=next_hour % 24, 
                                minute=0, 
                                second=0, 
                                microsecond=0
                            )
                            
                            if next_hour == 24:
                                next_funding_time = next_funding_time.replace(hour=0)
                                from datetime import timedelta
                                next_funding_time += timedelta(days=1)
                        
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
        """Place an order on KuCoin"""
        try:
            await self._rate_limit()
            
            kucoin_symbol = self._convert_symbol(symbol)
            
            # Convert order type
            ccxt_type = 'market' if order_type == OrderType.MARKET else 'limit'
            
            # Place order
            order_params = {}
            if order_type == OrderType.LIMIT and price:
                order_params['price'] = float(price)
            
            # KuCoin futures require leverage setting
            order_params['leverage'] = 1  # Start with 1x leverage
            
            response = await self._exchange.create_order(
                symbol=kucoin_symbol,
                type=ccxt_type,
                side=side.lower(),
                amount=float(amount),
                **order_params
            )
            
            if response:
                order = Order(
                    order_id=str(response['id']),
                    client_order_id=str(response.get('clientOrderId', response['id'])),
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
            
            response = await self._exchange.cancel_order(order_id)
            
            if response:
                # Update order status
                cached_order = self.get_cached_order(order_id)
                if cached_order:
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
            
            kucoin_symbol = self._convert_symbol(cached_order.symbol)
            
            response = await self._exchange.fetch_order(order_id, kucoin_symbol)
            
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
            
            kucoin_symbol = self._convert_symbol(symbol)
            
            positions = await self._exchange.privateGetPositions()
            
            if positions and 'data' in positions:
                for pos in positions['data']:
                    if pos['symbol'] == kucoin_symbol.replace('/', '').replace(':USDT', 'M'):
                        return Decimal(str(pos.get('currentQty', 0)))
            
            return Decimal("0")
            
        except Exception as e:
            self.logger.error(f"Error getting position size for {symbol}: {e}")
            return Decimal("0")
    
    async def get_positions(self) -> List[Position]:
        """Get all current positions"""
        try:
            await self._rate_limit()
            
            positions_data = await self._exchange.privateGetPositions()
            positions = []
            
            if positions_data and 'data' in positions_data:
                for pos in positions_data['data']:
                    size = Decimal(str(pos.get('currentQty', 0)))
