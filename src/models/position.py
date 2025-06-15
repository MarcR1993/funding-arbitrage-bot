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
