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
