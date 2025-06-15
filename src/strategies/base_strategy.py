python"""
Base strategy class adapted from Hummingbot's StrategyPyBase.
Attribution: Based on Hummingbot's strategy architecture (Apache 2.0)
Original: https://github.com/hummingbot/hummingbot/blob/master/hummingbot/strategy/strategy_py_base.py
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from decimal import Decimal

from src.connectors.base_connector import BaseConnector
from src.models.order import Order
from src.models.funding_rate import FundingRate


class BaseStrategy(ABC):
    """
    Base strategy class for all trading strategies.
    Attribution: Adapted from Hummingbot's StrategyPyBase (Apache 2.0)
    """
    
    def __init__(self, 
                 connectors: Dict[str, BaseConnector],
                 config: dict):
        self.connectors = connectors
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Strategy state
        self._active = False
        self._orders: Dict[str, Order] = {}
        
        # Performance tracking
        self._total_profit = Decimal("0")
        self._trade_count = 0
        
    @abstractmethod
    async def on_tick(self):
        """
        Called every tick (usually every second).
        Main strategy logic goes here.
        """
        pass
    
    @abstractmethod
    async def on_funding_rate_update(self, exchange: str, symbol: str, funding_rate: FundingRate):
        """Called when funding rate is updated"""
        pass
    
    async def start(self):
        """Start the strategy"""
        self._active = True
        self.logger.info(f"Strategy {self.__class__.__name__} started")
        
        # Subscribe to events from connectors
        for connector in self.connectors.values():
            connector.add_event_handler("funding_rate_update", self._handle_funding_rate_update)
    
    async def stop(self):
        """Stop the strategy"""
        self._active = False
        self.logger.info(f"Strategy {self.__class__.__name__} stopped")
    
    async def _handle_funding_rate_update(self, data: dict):
        """Handle funding rate update events"""
        await self.on_funding_rate_update(
            data["symbol"].split("-")[0],  # exchange from symbol
            data["symbol"], 
            data["funding_rate"]
        )
    
    @property
    def is_active(self) -> bool:
        return self._active
    
    @property
    def total_profit(self) -> Decimal:
        return self._total_profit
    
    @property
    def trade_count(self) -> int:
        return self._trade_count
