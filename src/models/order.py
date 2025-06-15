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

