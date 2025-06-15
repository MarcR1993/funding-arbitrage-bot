ython"""
Clock system adapted from Hummingbot's Clock.
Attribution: Based on Hummingbot's clock architecture (Apache 2.0)
Original: https://github.com/hummingbot/hummingbot/blob/master/hummingbot/core/clock.pyx
"""

import asyncio
import logging
import time
from typing import List, Set
from abc import ABC, abstractmethod


class TimeIterator(ABC):
    """
    Base class for objects that need to be called on each clock tick.
    Attribution: Adapted from Hummingbot's TimeIterator (Apache 2.0)
    """
    
    @abstractmethod
    async def tick(self, timestamp: float):
        """Called on each clock tick"""
        pass


class ArbitrageClock:
    """
    Clock system that coordinates all time-based operations.
    Attribution: Adapted from Hummingbot's Clock (Apache 2.0)
    """
    
    def __init__(self, tick_interval: float = 1.0):
        self.tick_interval = tick_interval
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Registered iterators
        self._iterators: List[TimeIterator] = []
        
        # Clock state
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
    def add_iterator(self, iterator: TimeIterator):
        """Add an iterator to be called on each tick"""
        if iterator not in self._iterators:
            self._iterators.append(iterator)
            self.logger.info(f"Added iterator: {iterator.__class__.__name__}")
    
    def remove_iterator(self, iterator: TimeIterator):
        """Remove an iterator"""
        if iterator in self._iterators:
            self._iterators.remove(iterator)
            self.logger.info(f"Removed iterator: {iterator.__class__.__name__}")
    
    async def start(self):
        """Start the clock"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._clock_loop())
        self.logger.info("Clock started")
    
    async def stop(self):
        """Stop the clock"""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Clock stopped")
    
    async def _clock_loop(self):
        """Main clock loop"""
        while self._running:
            try:
                start_time = time.time()
                
                # Call all iterators
                for iterator in self._iterators:
                    try:
                        await iterator.tick(start_time)
                    except Exception as e:
                        self.logger.error(f"Error in iterator {iterator.__class__.__name__}: {e}")
                
                # Sleep for the remaining time
                elapsed = time.time() - start_time
                sleep_time = max(0, self.tick_interval - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in clock loop: {e}")
                await asyncio.sleep(1)  # Prevent rapid error loops
