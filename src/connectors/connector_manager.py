
"""
Connector manager for handling multiple exchange connections.
Attribution: Inspired by Hummingbot's connector management (Apache 2.0)
"""

import asyncio
import logging
from typing import Dict, List, Optional, Type
from decimal import Decimal

from .base_connector import BaseConnector
from .binance_connector import BinanceConnector
from .bybit_connector import BybitConnector
from src.models.funding_rate import FundingRate
from src.models.balance import Balance


class ConnectorManager:
    """
    Manages multiple exchange connectors.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Available connector classes
        self._connector_classes: Dict[str, Type[BaseConnector]] = {
            'binance': BinanceConnector,
            'bybit': BybitConnector,
            # Add more exchanges here: 'okx': OKXConnector, etc.
        }
        
        # Active connectors
        self._connectors: Dict[str, BaseConnector] = {}
        
        # Aggregated data
        self._all_funding_rates: Dict[str, Dict[str, FundingRate]] = {}
        self._all_balances: Dict[str, Dict[str, Balance]] = {}
    
    async def add_connector(self, 
                           exchange: str, 
                           api_key: str, 
                           api_secret: str, 
                           sandbox: bool = False) -> bool:
        """Add and start a new connector"""
        try:
            if exchange not in self._connector_classes:
                self.logger.error(f"Unsupported exchange: {exchange}")
                return False
            
            if exchange in self._connectors:
                self.logger.warning(f"Connector for {exchange} already exists")
