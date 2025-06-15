"""
Base connector class adapted from Hummingbot's ConnectorBase.
Attribution: Based on Hummingbot's connector architecture (Apache 2.0)
Original: https://github.com/hummingbot/hummingbot/blob/master/hummingbot/connector/connector_base.py
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional, Set
from enum import Enum

from src.models.order import Order, OrderStatus, OrderType
from src.models.balance import Balance
from src.models.funding_rate import FundingRate
from src.utils.async_utils import safe_ensure_future


class ConnectorStatus(Enum):
    """Connection status enumeration"""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"


class BaseConnector(ABC):
    """
    Base connector class for all exchange connections.
    Attribution: Adapted from Hummingbot's ConnectorBase (Apache 2.0)
    """
    
    def __init__(self, 
                 exchange_name: str,
                 api_key: str,
                 api_secret: str,
                 sandbox: bool = False):
        self._exchange_name = exchange_name
        self._api_key = api_key
        self._api_secret = api_secret
        self._sandbox = sandbox
        
        # Connection status
        self._status = ConnectorStatus.DISCONNECTED
        self._last_timestamp = 0
        
        # Data storage
        self._balances: Dict[str, Balance] = {}
        self._orders: Dict[str, Order] = {}
        self._funding_rates: Dict[str, FundingRate] = {}
        
        # WebSocket connections
        self._ws_connections: Dict[str, object] = {}
        
        # Event handlers
        self._event_handlers: Dict[str, List] = {}
        
        # Logger
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{exchange_name}")
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        
    @property
    def exchange_name(self) -> str:
        return self._exchange_name
    
    @property
    def status(self) -> ConnectorStatus:
        return self._status
    
    @property
    def is_connected(self) -> bool:
        return self._status == ConnectorStatus.CONNECTED
        
    # ====== Abstract Methods (Must be implemented by subclasses) ======
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the exchange"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the exchange"""
        pass
    
    @abstractmethod
    async def get_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """Get current funding rate for a symbol"""
        pass
    
    @abstractmethod
    async def get_balance(self, asset: str) -> Optional[Balance]:
        """Get balance for an asset"""
        pass
    
    @abstractmethod
    async def place_order(self, 
                         symbol: str,
                         side: str,
                         order_type: OrderType,
                         amount: Decimal,
                         price: Optional[Decimal] = None) -> Optional[Order]:
        """Place an order"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get order status"""
        pass
    
    @abstractmethod
    async def get_position_size(self, symbol: str) -> Decimal:
        """Get current position size for a symbol"""
        pass
    
    # ====== Common Methods ======
    
    async def start(self):
        """Start the connector and background tasks"""
        try:
            self._status = ConnectorStatus.CONNECTING
            
            # Connect to exchange
            connected = await self.connect()
            if not connected:
                self._status = ConnectorStatus.ERROR
                return False
                
            self._status = ConnectorStatus.CONNECTED
            
            # Start background tasks
            await self._start_background_tasks()
            
            self.logger.info(f"Connector started for {self._exchange_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting connector: {e}")
            self._status = ConnectorStatus.ERROR
            return False
    
    async def stop(self):
        """Stop the connector and cleanup"""
        try:
            # Cancel all background tasks
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
                
            # Disconnect
            await self.disconnect()
            
            self._status = ConnectorStatus.DISCONNECTED
            self.logger.info(f"Connector stopped for {self._exchange_name}")
            
        except Exception as e:
            self.logger.error(f"Error stopping connector: {e}")
    
    async def _start_background_tasks(self):
        """Start background monitoring tasks"""
        # Funding rate monitoring
        task = safe_ensure_future(self._funding_rate_monitor())
        self._background_tasks.add(task)
        
        # Balance monitoring  
        task = safe_ensure_future(self._balance_monitor())
        self._background_tasks.add(task)
        
        # Order monitoring
        task = safe_ensure_future(self._order_monitor())
        self._background_tasks.add(task)
    
    async def _funding_rate_monitor(self):
        """Monitor funding rates (to be overridden)"""
        while self.is_connected:
            try:
                # Subclasses should implement specific monitoring logic
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in funding rate monitor: {e}")
                await asyncio.sleep(30)
    
    async def _balance_monitor(self):
        """Monitor account balances (to be overridden)"""
        while self.is_connected:
            try:
                # Subclasses should implement specific monitoring logic
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in balance monitor: {e}")
                await asyncio.sleep(30)
    
    async def _order_monitor(self):
        """Monitor order status (to be overridden)"""
        while self.is_connected:
            try:
                # Subclasses should implement specific monitoring logic
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in order monitor: {e}")
                await asyncio.sleep(30)
    
    # ====== Event System ======
    
    def add_event_handler(self, event_type: str, handler):
        """Add an event handler"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def _emit_event(self, event_type: str, data: dict):
        """Emit an event to all handlers"""
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        safe_ensure_future(handler(data))
                    else:
                        handler(data)
                except Exception as e:
                    self.logger.error(f"Error in event handler: {e}")
    
    # ====== Utility Methods ======
    
    def update_funding_rate(self, symbol: str, funding_rate: FundingRate):
        """Update funding rate data"""
        self._funding_rates[symbol] = funding_rate
        self._emit_event("funding_rate_update", {
            "symbol": symbol,
            "funding_rate": funding_rate
        })
    
    def update_balance(self, asset: str, balance: Balance):
        """Update balance data"""
        self._balances[asset] = balance
        self._emit_event("balance_update", {
            "asset": asset,
            "balance": balance
        })
    
    def update_order(self, order: Order):
        """Update order data"""
        self._orders[order.order_id] = order
        self._emit_event("order_update", {
            "order": order
        })
    
    def get_cached_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """Get cached funding rate"""
        return self._funding_rates.get(symbol)
    
    def get_cached_balance(self, asset: str) -> Optional[Balance]:
        """Get cached balance"""
        return self._balances.get(asset)
    
    def get_cached_order(self, order_id: str) -> Optional[Order]:
        """Get cached order"""
        return self._orders.get(order_id)
    
    def __str__(self):
        return f"{self.__class__.__name__}({self._exchange_name})"
    
    def __repr__(self):
        return self.__str__()
