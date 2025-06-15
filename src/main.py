# src/main.py
"""
Main entry point for the funding rate arbitrage bot.
Attribution: Structure adapted from Hummingbot (Apache 2.0)
"""

import asyncio
import logging
import signal
import sys
import os
from typing import Optional
from decimal import Decimal

from src.config.settings import load_config, save_config
from src.core.clock import ArbitrageClock, TimeIterator
from src.core.event_bus import EventBus
from src.strategies.funding_arbitrage import FundingRateArbitrage
from src.connectors.connector_manager import ConnectorManager
from src.utils.time_utils import get_utc_datetime


class FundingArbitrageBot(TimeIterator):
    """
    Main bot application that coordinates all components.
    Attribution: Based on Hummingbot's main application structure (Apache 2.0)
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Load configuration
        self.config = load_config(config_file)
        
        # Core components
        self.clock: Optional[ArbitrageClock] = None
        self.event_bus: Optional[EventBus] = None
        self.connector_manager: Optional[ConnectorManager] = None
        self.strategy: Optional[FundingRateArbitrage] = None
        
        # Bot state
        self._running = False
        self._shutdown_requested = False
        
    async def initialize(self) -> bool:
        """Initialize all bot components"""
        try:
            self.logger.info("🚀 Initializing Funding Arbitrage Bot...")
            
            # Initialize core components
            self.event_bus = EventBus()
            await self.event_bus.start()
            
            self.connector_manager = ConnectorManager()
            
            # Initialize clock
            self.clock = ArbitrageClock(tick_interval=1.0)
            
            # Add bot to clock for periodic updates
            self.clock.add_iterator(self)
            
            # Setup exchange connectors
            await self._setup_connectors()
            
            # Initialize strategy
            await self._setup_strategy()
            
            # Add strategy to clock
            if self.strategy:
                self.clock.add_iterator(self.strategy)
            
            self.logger.info("✅ Bot initialization completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize bot: {e}")
            return False
    
    async def _setup_connectors(self):
        """Setup exchange connectors based on configuration"""
        
        exchanges_config = self.config.get("exchanges", {})
        
        for exchange_name, exchange_config in exchanges_config.items():
            if not exchange_config.get("enabled", False):
                self.logger.info(f"⏭️  Skipping {exchange_name} - disabled in config")
                continue
            
            self.logger.info(f"🔌 Setting up {exchange_name} connector...")
            
            try:
                credentials = exchange_config.get("credentials", {})
                sandbox = exchange_config.get("sandbox", True)
                
                success = await self.connector_manager.add_connector(
                    exchange=exchange_name,
                    credentials=credentials,
                    sandbox=sandbox
                )
                
                if success:
                    self.logger.info(f"✅ {exchange_name} connector ready")
                else:
                    self.logger.error(f"❌ Failed to setup {exchange_name} connector")
                    
            except Exception as e:
                self.logger.error(f"❌ Error setting up {exchange_name}: {e}")
        
        # Verify we have at least 2 exchanges connected
        connected_exchanges = self.connector_manager.get_connected_exchanges()
        if len(connected_exchanges) < 2:
            raise Exception(f"Need at least 2 exchanges for arbitrage. Connected: {connected_exchanges}")
        
        self.logger.info(f"📊 Connected to {len(connected_exchanges)} exchanges: {', '.join(connected_exchanges)}")
    
    async def _setup_strategy(self):
        """Setup the funding arbitrage strategy"""
        
        strategy_config = self.config.get("strategy", {})
        
        self.strategy = FundingRateArbitrage(
            connector_manager=self.connector_manager,
            config=strategy_config,
            event_bus=self.event_bus
        )
        
        # Subscribe to strategy events
        if self.event_bus:
            self.event_bus.subscribe("arbitrage_opened", self._on_arbitrage_opened)
            self.event_bus.subscribe("arbitrage_closed", self._on_arbitrage_closed)
            self.event_bus.subscribe("funding_rate_update", self._on_funding_rate_update)
        
        self.logger.info("📈 Strategy initialized")
    
    async def start(self):
        """Start the bot"""
        if self._running:
            self.logger.warning("Bot is already running")
            return
        
        try:
            # Initialize if not already done
            if not self.clock:
                success = await self.initialize()
                if not success:
                    raise Exception("Failed to initialize bot")
            
            self._running = True
            
            # Start strategy
            if self.strategy:
                await self.strategy.start()
            
            # Start the main clock
            await self.clock.start()
            
            self.logger.info("🟢 Bot started successfully")
            
            # Keep running until shutdown
            while self._running and not self._shutdown_requested:
                await asyncio.sleep(1)
            
        except Exception as e:
            self.logger.error(f"Error running bot: {e}")
            raise
        
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the bot gracefully"""
        if not self._running:
            return
        
        self.logger.info("🔴 Stopping bot...")
        self._running = False
        
        try:
            # Stop strategy
            if self.strategy:
                # Close all positions before stopping
                await self.strategy.close_all_positions()
                await self.strategy.stop()
            
            # Stop clock
            if self.clock:
                await self.clock.stop()
            
            # Stop connectors
            if self.connector_manager:
                await self.connector_manager.stop_all()
            
            # Stop event bus
            if self.event_bus:
                await self.event_bus.stop()
            
            self.logger.info("✅ Bot stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping bot: {e}")
    
    async def tick(self, timestamp: float):
        """Called by clock every tick for bot-level operations"""
        
        # Perform periodic bot-level tasks
        current_time = get_utc_datetime()
        
        # Log status every 5 minutes
        if int(timestamp) % 300 == 0:
            await self._log_status()
        
        # Save performance data every hour
        if int(timestamp) % 3600 == 0:
            await self._save_performance_data()
    
    async def _log_status(self):
        """Log current bot status"""
        
        if not self.strategy:
            return
        
        try:
            # Get strategy performance
            performance = self.
