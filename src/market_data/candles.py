"""
Candlestick data provider for V2 strategies.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional


@dataclass
class CandleData:
    """Single candlestick data point"""
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.timestamp(),
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume)
        }


class CandleDataProvider:
    """
    Provides candlestick data for technical analysis.
    Attribution: Based on Hummingbot's Candle data system (Apache 2.0)
    """
    
    def __init__(self, connector_manager):
        self.connector_manager = connector_manager
        self._candle_cache: Dict[str, List[CandleData]] = {}
    
    async def get_candles(self, 
                         exchange: str,
                         symbol: str,
                         interval: str = "1m",
                         limit: int = 100) -> List[CandleData]:
        """Get candlestick data for a trading pair"""
        
        cache_key = f"{exchange}:{symbol}:{interval}"
        
        # Return cached data for now (in production, fetch from exchange)
        if cache_key not in self._candle_cache:
            # Generate sample candle data for testing
            self._candle_cache[cache_key] = self._generate_sample_candles(limit)
        
        return self._candle_cache[cache_key][-limit:]
    
    def _generate_sample_candles(self, count: int) -> List[CandleData]:
        """Generate sample candle data for testing"""
        import random
        from datetime import timedelta
        
        candles = []
        base_price = Decimal("50000")  # Sample BTC price
        current_time = datetime.utcnow()
        
        for i in range(count):
            timestamp = current_time - timedelta(minutes=count - i)
            
            # Generate realistic OHLCV data
            open_price = base_price + Decimal(random.randint(-1000, 1000))
            close_price = open_price + Decimal(random.randint(-500, 500))
            high_price = max(open_price, close_price) + Decimal(random.randint(0, 200))
            low_price = min(open_price, close_price) - Decimal(random.randint(0, 200))
            volume = Decimal(random.randint(100, 1000))
            
            candle = CandleData(
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume
            )
            candles.append(candle)
            base_price = close_price  # Next candle starts where this one ended
        
        return candles
