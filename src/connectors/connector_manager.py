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
                return True
            
            # Create connector instance
            connector_class = self._connector_classes[exchange]
            connector = connector_class(api_key, api_secret, sandbox)
            
            # Set up event handlers
            connector.add_event_handler("funding_rate_update", self._on_funding_rate_update)
            connector.add_event_handler("balance_update", self._on_balance_update)
            
            # Start connector
            success = await connector.start()
            if success:
                self._connectors[exchange] = connector
                self.logger.info(f"Successfully added connector for {exchange}")
                return True
            else:
                self.logger.error(f"Failed to start connector for {exchange}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error adding connector for {exchange}: {e}")
            return False
    
    async def remove_connector(self, exchange: str) -> bool:
        """Remove and stop a connector"""
        try:
            if exchange in self._connectors:
                await self._connectors[exchange].stop()
                del self._connectors[exchange]
                
                # Clean up aggregated data
                if exchange in self._all_funding_rates:
                    del self._all_funding_rates[exchange]
                if exchange in self._all_balances:
                    del self._all_balances[exchange]
                
                self.logger.info(f"Removed connector for {exchange}")
                return True
            else:
                self.logger.warning(f"Connector for {exchange} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error removing connector for {exchange}: {e}")
            return False
    
    async def stop_all(self):
        """Stop all connectors"""
        for exchange in list(self._connectors.keys()):
            await self.remove_connector(exchange)
        
        self.logger.info("All connectors stopped")
    
    def get_connector(self, exchange: str) -> Optional[BaseConnector]:
        """Get a specific connector"""
        return self._connectors.get(exchange)
    
    def get_all_connectors(self) -> Dict[str, BaseConnector]:
        """Get all active connectors"""
        return self._connectors.copy()
    
    def get_connected_exchanges(self) -> List[str]:
        """Get list of connected exchange names"""
        return [name for name, conn in self._connectors.items() if conn.is_connected]
    
    async def _on_funding_rate_update(self, data: dict):
        """Handle funding rate updates from connectors"""
        try:
            symbol = data["symbol"]
            funding_rate = data["funding_rate"]
            exchange = funding_rate.exchange
            
            if exchange not in self._all_funding_rates:
                self._all_funding_rates[exchange] = {}
            
            self._all_funding_rates[exchange][symbol] = funding_rate
            
        except Exception as e:
            self.logger.error(f"Error handling funding rate update: {e}")
    
    async def _on_balance_update(self, data: dict):
        """Handle balance updates from connectors"""
        try:
            asset = data["asset"]
            balance = data["balance"]
            exchange = balance.exchange
            
            if exchange not in self._all_balances:
                self._all_balances[exchange] = {}
            
            self._all_balances[exchange][asset] = balance
            
        except Exception as e:
            self.logger.error(f"Error handling balance update: {e}")
    
    # ====== Data Access Methods ======
    
    def get_funding_rates(self, symbol: str) -> Dict[str, FundingRate]:
        """Get funding rates for a symbol from all exchanges"""
        rates = {}
        for exchange, symbols in self._all_funding_rates.items():
            if symbol in symbols:
                rates[exchange] = symbols[symbol]
        return rates
    
    def get_all_funding_rates(self) -> Dict[str, Dict[str, FundingRate]]:
        """Get all funding rates from all exchanges"""
        return self._all_funding_rates.copy()
    
    def get_balances(self, asset: str) -> Dict[str, Balance]:
        """Get balances for an asset from all exchanges"""
        balances = {}
        for exchange, assets in self._all_balances.items():
            if asset in assets:
                balances[exchange] = assets[asset]
        return balances
    
    def get_all_balances(self) -> Dict[str, Dict[str, Balance]]:
        """Get all balances from all exchanges"""
        return self._all_balances.copy()
    
    async def get_arbitrage_opportunities(self, symbol: str, min_profit_threshold: Decimal) -> List[dict]:
        """Find arbitrage opportunities for a symbol"""
        opportunities = []
        rates = self.get_funding_rates(symbol)
        
        if len(rates) < 2:
            return opportunities
        
        # Compare all exchange pairs
        exchanges = list(rates.keys())
        for i in range(len(exchanges)):
            for j in range(i + 1, len(exchanges)):
                exchange1, exchange2 = exchanges[i], exchanges[j]
                rate1 = rates[exchange1].rate
                rate2 = rates[exchange2].rate
                
                # Calculate profit potential
                profit_diff = abs(rate1 - rate2)
                
                if profit_diff > min_profit_threshold:
                    # Determine which direction is more profitable
                    if rate1 < rate2:
                        long_exchange, short_exchange = exchange1, exchange2
                        long_rate, short_rate = rate1, rate2
                    else:
                        long_exchange, short_exchange = exchange2, exchange1
                        long_rate, short_rate = rate2, rate1
                    
                    opportunity = {
                        "symbol": symbol,
                        "long_exchange": long_exchange,
                        "short_exchange": short_exchange,
                        "long_rate": long_rate,
                        "short_rate": short_rate,
                        "rate_difference": profit_diff,
                        "profit_potential": profit_diff  # Simplified calculation
                    }
                    
                    opportunities.append(opportunity)
        
        # Sort by profit potential (highest first)
        opportunities.sort(key=lambda x: x["profit_potential"], reverse=True)
        
        return opportunities


# ========== Update src/connectors/__init__.py ==========

"""
Exchange connectors for funding rate arbitrage.
Attribution: Based on Hummingbot connector architecture (Apache 2.0)
"""

from .base_connector import BaseConnector, ConnectorStatus
from .binance_connector import BinanceConnector
from .bybit_connector import BybitConnector
from .connector_manager import ConnectorManager

__all__ = [
    "BaseConnector", "ConnectorStatus",
    "BinanceConnector", "BybitConnector",
    "ConnectorManager"
]


# ========== Update src/models/position.py ==========

"""
Position data model.
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Optional
from enum import Enum


class PositionSide(Enum):
    """Position side enumeration"""
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


@dataclass
class Position:
    """Trading position data class"""
    exchange: str
    symbol: str
    side: PositionSide
    size: Decimal
    entry_price: Optional[Decimal] = None
    mark_price: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    margin: Optional[Decimal] = None
    leverage: Optional[Decimal] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    @property
    def is_long(self) -> bool:
        """Check if position is long"""
        return self.side == PositionSide.LONG and self.size > 0
    
    @property
    def is_short(self) -> bool:
        """Check if position is short"""
        return self.side == PositionSide.SHORT and self.size > 0
    
    @property
    def is_flat(self) -> bool:
        """Check if position is flat (no position)"""
        return self.size == 0 or self.side == PositionSide.NONE


# ========== Update src/utils/math_utils.py ==========

"""
Mathematical utilities for trading calculations.
"""

from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import Union


def safe_decimal(value: Union[str, int, float, Decimal]) -> Decimal:
    """Safely convert value to Decimal"""
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (ValueError, TypeError):
        return Decimal("0")


def round_down(value: Decimal, decimals: int) -> Decimal:
    """Round down to specified decimal places"""
    if decimals <= 0:
        return value.quantize(Decimal("1"), rounding=ROUND_DOWN)
    
    quantizer = Decimal("0.1") ** decimals
    return value.quantize(quantizer, rounding=ROUND_DOWN)


def round_up(value: Decimal, decimals: int) -> Decimal:
    """Round up to specified decimal places"""
    if decimals <= 0:
        return value.quantize(Decimal("1"), rounding=ROUND_UP)
    
    quantizer = Decimal("0.1") ** decimals
    return value.quantize(quantizer, rounding=ROUND_UP)


def calculate_profit_percentage(entry_price: Decimal, exit_price: Decimal, side: str) -> Decimal:
    """Calculate profit percentage for a trade"""
    if entry_price <= 0:
        return Decimal("0")
    
    if side.upper() == "LONG":
        return (exit_price - entry_price) / entry_price * Decimal("100")
    else:  # SHORT
        return (entry_price - exit_price) / entry_price * Decimal("100")


def calculate_funding_arbitrage_profit(
    funding_rate_1: Decimal,
    funding_rate_2: Decimal, 
    position_size: Decimal,
    hours: int = 8
) -> Decimal:
    """
    Calculate potential profit from funding rate arbitrage.
    
    Args:
        funding_rate_1: Funding rate on exchange 1 (where we go long)
        funding_rate_2: Funding rate on exchange 2 (where we go short)
        position_size: Position size in USD
        hours: Hours until next funding (usually 8)
    
    Returns:
        Expected profit in USD
    """
    # If funding_rate_1 < funding_rate_2, we profit by:
    # - Going long on exchange 1 (receive funding if rate is negative)
    # - Going short on exchange 2 (pay funding if rate is positive)
    
    profit_rate = funding_rate_2 - funding_rate_1
    return profit_rate * position_size
