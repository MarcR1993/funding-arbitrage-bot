"""
Funding Rate Arbitrage Bot
"""

__version__ = "1.0.0"
__author__ = "Funding Bot Team"
__description__ = "Professional funding rate arbitrage bot for crypto exchanges"

from .bot.arbitrage_engine import ArbitrageEngine
from .models.config import FundingBotConfig

__all__ = [
    'ArbitrageEngine',
    'FundingBotConfig'
]
