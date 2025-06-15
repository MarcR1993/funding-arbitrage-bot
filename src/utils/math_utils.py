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
