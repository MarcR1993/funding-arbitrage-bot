# src/models/__init__.py
"""
Data models for the funding rate arbitrage bot.
Attribution: Structure inspired by Hummingbot's data models (Apache 2.0)
"""

from .order import Order, OrderStatus, OrderType, OrderSide
from .balance import Balance
from .funding_rate import FundingRate
from .position import Position

__all__ = [
    "Order", "OrderStatus", "OrderType", "OrderSide",
    "Balance", 
    "FundingRate",
    "Position"
]

# ========== src/models/order.py ==========
"""
Order data model.
Attribution: Based on Hummingbot's order structure (Apache 2.0)
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "PENDING"
    OPEN = "OPEN" 
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderType(Enum):
    """Order type enumeration"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(Enum):
    """Order side enumeration"""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """
    Order data class.
    Attribution: Structure adapted from Hummingbot's InFlightOrder (Apache 2.0)
    """
    order_id: str
    client_order_id: str
    exchange: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: Decimal
    price: Optional[Decimal]
    status: OrderStatus
    filled_amount: Decimal = Decimal("0")
    remaining_amount: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    fee_amount: Decimal = Decimal("0")
    fee_asset: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.remaining_amount is None:
            self.remaining_amount = self.amount - self.filled_amount
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = self.created_at
    
    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.status == OrderStatus.FILLED
    
    @property
    def is_partially_filled(self) -> bool:
        """Check if order is partially filled"""
        return self.filled_amount > 0 and self.filled_amount < self.amount
    
    @property
    def is_open(self) -> bool:
        """Check if order is open/active"""
        return self.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]
    
    @property
    def is_done(self) -> bool:
        """Check if order is done (filled, canceled, etc.)"""
        return self.status in [
            OrderStatus.FILLED, 
            OrderStatus.CANCELED, 
            OrderStatus.REJECTED, 
            OrderStatus.EXPIRED
        ]


# ========== src/models/balance.py ==========
"""
Balance data model.
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Optional


@dataclass
class Balance:
    """Account balance data class"""
    asset: str
    exchange: str
    total: Decimal
    available: Decimal
    locked: Decimal = Decimal("0")
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        
        # Ensure locked + available = total
        if self.locked == Decimal("0"):
            self.locked = self.total - self.available
    
    @property
    def free(self) -> Decimal:
        """Alias for available balance"""
        return self.available


# ========== src/models/funding_rate.py ==========
"""
Funding rate data model.
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Optional


@dataclass
class FundingRate:
    """Funding rate data class"""
    exchange: str
    symbol: str
    rate: Decimal
    next_funding_time: datetime
    interval_hours: int = 8  # Most exchanges use 8-hour intervals
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    @property
    def annual_rate(self) -> Decimal:
        """Convert to annual rate (365 days * 24 hours / interval_hours)"""
        periods_per_year = Decimal(365 * 24) / Decimal(self.interval_hours)
        return self.rate * periods_per_year
    
    @property
    def daily_rate(self) -> Decimal:
        """Convert to daily rate (24 hours / interval_hours)"""
        periods_per_day = Decimal(24) / Decimal(self.interval_hours)
        return self.rate * periods_per_day


# ========== src/models/position.py ==========
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
