python"""
Event bus system for inter-component communication.
"""

import asyncio
import logging
from typing import Dict, List, Callable, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    """Event data structure"""
    type: str
    data: Any
    timestamp: datetime
    source: str


class EventBus:
    """
    Central event bus for component communication.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._handlers: Dict[str, List[Callable]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to an event type"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        self._handlers[event_type].append(handler)
        self.logger.debug(f"Handler subscribed to {event_type}")
    
    def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe from an event type"""
        if event_type in self._handlers:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
                self.logger.debug(f"Handler unsubscribed from {event_type}")
    
    async def publish(self, event_type: str, data: Any, source: str = "unknown"):
        """Publish an event"""
        event = Event(
            type=event_type,
            data=data,
            timestamp=datetime.utcnow(),
            source=source
        )
        
        await self._event_queue.put(event)
    
    async def start(self):
        """Start the event processor"""
        if self._running:
            return
        
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        self.logger.info("Event bus started")
    
    async def stop(self):
        """Stop the event processor"""
        if not self._running:
            return
        
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Event bus stopped")
    
    async def _process_events(self):
        """Process events from the queue"""
        while self._running:
            try:
                # Get event with timeout
                event = await asyncio.wait_for(
                    self._event_queue.get(), 
                    timeout=1.0
                )
                
                # Call all handlers for this event type
                if event.type in self._handlers:
                    for handler in self._handlers[event.type]:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(event)
                            else:
                                handler(event)
                        except Exception as e:
                            self.logger.error(f"Error in event handler: {e}")
                
            except asyncio.TimeoutError:
                continue  # No events, continue loop
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error processing events: {e}")
