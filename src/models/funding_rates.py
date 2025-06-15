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
