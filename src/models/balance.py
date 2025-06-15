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
