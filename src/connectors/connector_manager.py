# src/connectors/connector_manager.py
"""
Updated connector manager for handling multiple exchange connections.
Attribution: Inspired by Hummingbot's connector management (Apache 2.0)
"""

import asyncio
import logging
from typing import Dict, List, Optional, Type, Union
from decimal import Decimal

from .base_connector import BaseConnector
from .binance_connector import BinanceConnector
from .bybit_connector import BybitConnector
from .hyperliquid_connector import HyperliquidConnector
from .kucoin_connector import KuCoinConnector
from src.models.funding_rate import FundingRate
from src.models.balance import Balance


class ConnectorManager:
    """
    Manages multiple exchange connectors including Binance, Bybit, Hyperliquid, and KuCoin.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Available connector classes
        self._connector_classes: Dict[str, Type[BaseConnector]] = {
            'binance': BinanceConnector,
            'bybit': BybitConnector,
            'hyperliquid': HyperliquidConnector,
            'kucoin': KuCoinConnector,
        }
        
        # Active connectors
        self._connectors: Dict[str, BaseConnector] = {}
        
        # Aggregated data
        self._all_funding_rates: Dict[str, Dict[str, FundingRate]] = {}
        self._all_balances: Dict[str, Dict[str, Balance]] = {}
        
        # Exchange-specific configuration requirements
        self._exchange_configs = {
            'binance': {'required_fields': ['api_key', 'api_secret']},
            'bybit': {'required_fields': ['api_key', 'api_secret']},
            'hyperliquid': {'required_fields': ['api_key', 'api_secret']},
            'kucoin': {'required_fields': ['api_key', 'api_secret', 'passphrase']},
        }
    
    async def add_connector(self, 
                           exchange: str, 
                           credentials: Dict[str, str],
                           sandbox: bool = False) -> bool:
        """
        Add and start a new connector with exchange-specific credentials.
        
        Args:
            exchange: Exchange name ('binance', 'bybit', 'hyperliquid', 'kucoin')
            credentials: Dict with exchange-specific credentials
            sandbox: Whether to use sandbox/testnet
        """
        try:
            if exchange not in self._connector_classes:
                self.logger.error(f"Unsupported exchange: {exchange}")
                self.logger.info(f"Supported exchanges: {list(self._connector_classes.keys())}")
                return False
            
            if exchange in self._connectors:
                self.logger.warning(f"Connector for {exchange} already exists")
                return True
            
            # Validate required credentials
            required_fields = self._exchange_configs[exchange]['required_fields']
            for field in required_fields:
                if field not in credentials:
                    self.logger.error(f"Missing required credential '{field}' for {exchange}")
                    return False
            
            # Create connector instance with exchange-specific parameters
            connector_class = self._connector_classes[exchange]
            
            if exchange == 'kucoin':
                connector = connector_class(
                    api_key=credentials['api_key'],
                    api_secret=credentials['api_secret'],
                    passphrase=credentials['passphrase'],
                    sandbox=sandbox
                )
            else:
                connector = connector_class(
                    api_key=credentials['api_key'],
                    api_secret=credentials['api_secret'],
                    sandbox=sandbox
                )
            
            # Set up event handlers
            connector.add_event_handler("funding_rate_update", self._on_funding_rate_update)
            connector.add_event_handler("balance_update", self._on_balance_update)
            
            # Start connector
            success = await connector.start()
            if success:
                self._connectors[exchange] = connector
                self.logger.info(f"✅ Successfully added connector for {exchange}")
                return True
            else:
                self.logger.error(f"❌ Failed to start connector for {exchange}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error adding connector for {exchange}: {e}")
            return False
    
    async def add_binance(self, api_key: str, api_secret: str, sandbox: bool = False) -> bool:
        """Convenience method to add Binance connector"""
        return await self.add_connector('binance', {
            'api_key': api_key,
            'api_secret': api_secret
        }, sandbox)
    
    async def add_bybit(self, api_key: str, api_secret: str, sandbox: bool = False) -> bool:
        """Convenience method to add Bybit connector"""
        return await self.add_connector('bybit', {
            'api_key': api_key,
            'api_secret': api_secret
        }, sandbox)
    
    async def add_hyperliquid(self, api_key: str, api_secret: str, sandbox: bool = False) -> bool:
        """Convenience method to add Hyperliquid connector"""
        return await self.add_connector('hyperliquid', {
            'api_key': api_key,
            'api_secret': api_secret
        }, sandbox)
    
    async def add_kucoin(self, api_key: str, api_secret: str, passphrase: str, sandbox: bool = False) -> bool:
        """Convenience method to add KuCoin connector"""
        return await self.add_connector('kucoin', {
            'api_key': api_key,
            'api_secret': api_secret,
            'passphrase': passphrase
        }, sandbox)
    
    async def remove_connector(self, exchange: str) -> bool:
        """Remove and stop a connector"""
        try:
            if exchange in self._connectors:
                await self._connectors[exchange].stop()
                del self._connectors[exchange]
                
                # Clean up aggregated data
                if exchange in self._all_funding_rates:
                    del self._all_funding_rates[exchange]
                if exchange in self._all_balances:
                    del self._all_balances[exchange]
                
                self.logger.info(f"Removed connector for {exchange}")
                return True
            else:
                self.logger.warning(f"Connector for {exchange} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error removing connector for {exchange}: {e}")
            return False
    
    async def stop_all(self):
        """Stop all connectors"""
        for exchange in list(self._connectors.keys()):
            await self.remove_connector(exchange)
        
        self.logger.info("All connectors stopped")
    
    def get_connector(self, exchange: str) -> Optional[BaseConnector]:
        """Get a specific connector"""
        return self._connectors.get(exchange)
    
    def get_all_connectors(self) -> Dict[str, BaseConnector]:
        """Get all active connectors"""
        return self._connectors.copy()
    
    def get_connected_exchanges(self) -> List[str]:
        """Get list of connected exchange names"""
        return [name for name, conn in self._connectors.items() if conn.is_connected]
    
    def get_exchange_info(self) -> Dict[str, dict]:
        """Get information about all supported exchanges"""
        return {
            'binance': {
                'name': 'Binance Futures',
                'type': 'CEX',
                'funding_interval': 8,
                'supported_pairs': ['BTC-USDT', 'ETH-USDT', 'BNB-USDT', 'ADA-USDT'],
                'credentials': ['api_key', 'api_secret']
            },
            'bybit': {
                'name': 'Bybit',
                'type': 'CEX',
                'funding_interval': 8,
                'supported_pairs': ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'DOGE-USDT'],
                'credentials': ['api_key', 'api_secret']
            },
            'hyperliquid': {
                'name': 'Hyperliquid',
                'type': 'DEX',
                'funding_interval': 8,
                'supported_pairs': ['BTC-USDT', 'ETH-USDT', 'SOL-USDT'],
                'credentials': ['api_key', 'api_secret'],
                'note': 'Decentralized perpetual exchange'
            },
            'kucoin': {
                'name': 'KuCoin Futures',
                'type': 'CEX',
                'funding_interval': 8,
                'supported_pairs': ['BTC-USDT', 'ETH-USDT', 'KCS-USDT'],
                'credentials': ['api_key', 'api_secret', 'passphrase']
            }
        }
    
    async def _on_funding_rate_update(self, data: dict):
        """Handle funding rate updates from connectors"""
        try:
            symbol = data["symbol"]
            funding_rate = data["funding_rate"]
            exchange = funding_rate.exchange
            
            if exchange not in self._all_funding_rates:
                self._all_funding_rates[exchange] = {}
            
            self._all_funding_rates[exchange][symbol] = funding_rate
            
        except Exception as e:
            self.logger.error(f"Error handling funding rate update: {e}")
    
    async def _on_balance_update(self, data: dict):
        """Handle balance updates from connectors"""
        try:
            asset = data["asset"]
            balance = data["balance"]
            exchange = balance.exchange
            
            if exchange not in self._all_balances:
                self._all_balances[exchange] = {}
            
            self._all_balances[exchange][asset] = balance
            
        except Exception as e:
            self.logger.error(f"Error handling balance update: {e}")
    
    # ====== Data Access Methods ======
    
    def get_funding_rates(self, symbol: str) -> Dict[str, FundingRate]:
        """Get funding rates for a symbol from all exchanges"""
        rates = {}
        for exchange, symbols in self._all_funding_rates.items():
            if symbol in symbols:
                rates[exchange] = symbols[symbol]
        return rates
    
    def get_all_funding_rates(self) -> Dict[str, Dict[str, FundingRate]]:
        """Get all funding rates from all exchanges"""
        return self._all_funding_rates.copy()
    
    def get_balances(self, asset: str) -> Dict[str, Balance]:
        """Get balances for an asset from all exchanges"""
        balances = {}
        for exchange, assets in self._all_balances.items():
            if asset in assets:
                balances[exchange] = assets[asset]
        return balances
    
    def get_all_balances(self) -> Dict[str, Dict[str, Balance]]:
        """Get all balances from all exchanges"""
        return self._all_balances.copy()
    
    async def get_arbitrage_opportunities(self, 
                                        symbol: str, 
                                        min_profit_threshold: Decimal) -> List[dict]:
        """Find arbitrage opportunities for a symbol across all connected exchanges"""
        opportunities = []
        rates = self.get_funding_rates(symbol)
        
        if len(rates) < 2:
            return opportunities
        
        # Compare all exchange pairs
        exchanges = list(rates.keys())
        for i in range(len(exchanges)):
            for j in range(i + 1, len(exchanges)):
                exchange1, exchange2 = exchanges[i], exchanges[j]
                rate1 = rates[exchange1].rate
                rate2 = rates[exchange2].rate
                
                # Calculate profit potential (rate difference)
                profit_diff = abs(rate1 - rate2)
                
                if profit_diff > min_profit_threshold:
                    # Determine which direction is more profitable
                    if rate1 < rate2:
                        long_exchange, short_exchange = exchange1, exchange2
                        long_rate, short_rate = rate1, rate2
                    else:
                        long_exchange, short_exchange = exchange2, exchange1
                        long_rate, short_rate = rate2, rate1
                    
                    opportunity = {
                        "symbol": symbol,
                        "long_exchange": long_exchange,
                        "short_exchange": short_exchange,
                        "long_rate": long_rate,
                        "short_rate": short_rate,
                        "rate_difference": profit_diff,
                        "profit_potential": profit_diff,
                        "next_funding_long": rates[long_exchange].next_funding_time,
                        "next_funding_short": rates[short_exchange].next_funding_time,
                        "annual_profit_estimate": profit_diff * Decimal("365") * Decimal("3")  # ~3 times per day
                    }
                    
                    opportunities.append(opportunity)
        
        # Sort by profit potential (highest first)
        opportunities.sort(key=lambda x: x["profit_potential"], reverse=True)
        
        return opportunities
    
    def get_status_summary(self) -> dict:
        """Get a summary of all connector statuses"""
        summary = {
            "total_connectors": len(self._connectors),
            "connected_exchanges": self.get_connected_exchanges(),
            "total_symbols_tracked": 0,
            "exchanges": {}
        }
        
        for exchange, connector in self._connectors.items():
            exchange_info = {
                "status": "connected" if connector.is_connected else "disconnected",
                "symbols_tracked": len(self._all_funding_rates.get(exchange, {})),
                "last_update": None
            }
            
            # Get latest update time
            if exchange in self._all_funding_rates:
                latest_time = None
                for symbol, rate in self._all_funding_rates[exchange].items():
                    if latest_time is None or rate.updated_at > latest_time:
                        latest_time = rate.updated_at
                exchange_info["last_update"] = latest_time
            
            summary["exchanges"][exchange] = exchange_info
            summary["total_symbols_tracked"] += exchange_info["symbols_tracked"]
        
        return summary
    
    async def health_check(self) -> Dict[str, bool]:
        """Perform health check on all connectors"""
        health = {}
        
        for exchange, connector in self._connectors.items():
            try:
                # Try to get a funding rate as a health check
                test_result = await connector.get_funding_rate("BTC-USDT")
                health[exchange] = test_result is not None
            except Exception as e:
                self.logger.error(f"Health check failed for {exchange}: {e}")
                health[exchange] = False
        
        return health


# ========== Update src/connectors/__init__.py ==========

"""
Exchange connectors for funding rate arbitrage.
Attribution: Based on Hummingbot connector architecture (Apache 2.0)
"""

from .base_connector import BaseConnector, ConnectorStatus
from .binance_connector import BinanceConnector
from .bybit_connector import BybitConnector
from .hyperliquid_connector import HyperliquidConnector
from .kucoin_connector import KuCoinConnector
from .connector_manager import ConnectorManager

__all__ = [
    "BaseConnector", "ConnectorStatus",
    "BinanceConnector", "BybitConnector", 
    "HyperliquidConnector", "KuCoinConnector",
    "ConnectorManager"
]
