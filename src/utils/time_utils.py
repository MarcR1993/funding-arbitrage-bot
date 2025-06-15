"""
Time utilities for trading operations.
"""

from datetime import datetime, timezone, timedelta
import time


def get_utc_timestamp() -> float:
    """Get current UTC timestamp"""
    return time.time()


def get_utc_datetime() -> datetime:
    """Get current UTC datetime"""
    return datetime.now(timezone.utc)


def timestamp_to_datetime(timestamp: float) -> datetime:
    """Convert timestamp to datetime"""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def datetime_to_timestamp(dt: datetime) -> float:
    """Convert datetime to timestamp"""
    return dt.timestamp()


def get_next_funding_time(interval_hours: int = 8) -> datetime:
    """
    Calculate next funding time based on interval.
    Most exchanges use 8-hour intervals: 00:00, 08:00, 16:00 UTC
    """
    now = get_utc_datetime()
    
    # Calculate hours since midnight
    hours_since_midnight = now.hour + now.minute / 60 + now.second / 3600
    
    # Find next funding time
    funding_times = [i * interval_hours for i in range(24 // interval_hours)]
    
    next_funding_hour = None
    for funding_hour in funding_times:
        if funding_hour > hours_since_midnight:
            next_funding_hour = funding_hour
            break
    
    # If no funding time today, use first funding time tomorrow
    if next_funding_hour is None:
        next_funding_hour = funding_times[0] + 24
    
    # Create datetime for next funding
    next_funding = now.replace(hour=0, minute=0, second=0, microsecond=0)
    next_funding += timedelta(hours=next_funding_hour)
    
    return next_funding


def time_until_next_funding(interval_hours: int = 8) -> timedelta:
    """Calculate time until next funding"""
    next_funding = get_next_funding_time(interval_hours)
    now = get_utc_datetime()
    return next_funding - now
