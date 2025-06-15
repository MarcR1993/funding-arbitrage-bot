python"""
Trading strategies for funding rate arbitrage.
Attribution: Based on Hummingbot's strategy framework (Apache 2.0)
"""

from .base_strategy import BaseStrategy
from .funding_arbitrage import FundingRateArbitrage

__all__ = ["BaseStrategy", "FundingRateArbitrage"]
