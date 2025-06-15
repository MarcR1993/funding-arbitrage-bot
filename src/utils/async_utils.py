"""
Async utilities adapted from Hummingbot.
Attribution: Based on Hummingbot's async utilities (Apache 2.0)
"""

import asyncio
import logging
from typing import Any, Awaitable, Optional
from functools import wraps


def safe_ensure_future(coro: Awaitable) -> asyncio.Task:
    """
    Safely create a future from a coroutine.
    Attribution: Adapted from Hummingbot's safe_ensure_future (Apache 2.0)
    """
    try:
        return asyncio.ensure_future(coro)
    except Exception as e:
        logging.error(f"Error creating future: {e}")
        # Create a dummy completed future
        future = asyncio.Future()
        future.set_exception(e)
        return future


def async_ttl_cache(ttl_seconds: int = 300):
    """
    TTL cache decorator for async functions.
    """
    def decorator(func):
        cache = {}
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import time
            key = str(args) + str(sorted(kwargs.items()))
            now = time.time()
            
            if key in cache:
                result, timestamp = cache[key]
                if now - timestamp < ttl_seconds:
                    return result
            
            result = await func(*args, **kwargs)
            cache[key] = (result, now)
            
            # Cleanup old entries
            expired_keys = [
                k for k, (_, ts) in cache.items() 
                if now - ts >= ttl_seconds
            ]
            for k in expired_keys:
                del cache[k]
                
            return result
        return wrapper
    return decorator


class AsyncQueue:
    """
    Async queue wrapper with error handling.
    Attribution: Pattern from Hummingbot's queue handling (Apache 2.0)
    """
    
    def __init__(self, maxsize: int = 0):
        self._queue = asyncio.Queue(maxsize=maxsize)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def put(self, item: Any, timeout: Optional[float] = None):
        """Put item in queue with timeout"""
        try:
            if timeout:
                await asyncio.wait_for(self._queue.put(item), timeout=timeout)
            else:
                await self._queue.put(item)
        except asyncio.TimeoutError:
            self.logger.warning(f"Queue put timeout after {timeout}s")
            raise
        except Exception as e:
            self.logger.error(f"Error putting item in queue: {e}")
            raise
    
    async def get(self, timeout: Optional[float] = None):
        """Get item from queue with timeout"""
        try:
            if timeout:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            else:
                return await self._queue.get()
        except asyncio.TimeoutError:
            self.logger.warning(f"Queue get timeout after {timeout}s")
            raise
        except Exception as e:
            self.logger.error(f"Error getting item from queue: {e}")
            raise
    
    def qsize(self) -> int:
        """Get queue size"""
        return self._queue.qsize()
    
    def empty(self) -> bool:
        """Check if queue is empty"""
        return self._queue.empty()
