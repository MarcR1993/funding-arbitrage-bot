python"""
Funding rate arbitrage strategy.
"""

import asyncio
from decimal import Decimal
from typing import Dict, Optional, Tuple

from .base_strategy import BaseStrategy
from src.connectors.base_connector import BaseConnector
from src.models.funding_rate import FundingRate
from src.models.order import OrderType, OrderSide
from src.utils.math_utils import calculate_funding_arbitrage_profit


class FundingRateArbitrage(BaseStrategy):
    """
    Main funding rate arbitrage strategy.
    
    Logic:
    1. Monitor funding rates across exchanges
    2. Find opportunities where rate differences > threshold
    3. Go long on exchange with lower rate
    4. Go short on exchange with higher rate
    5. Profit from the rate difference
    """
    
    def __init__(self, connectors: Dict[str, BaseConnector], config: dict):
        super().__init__(connectors, config)
        
        # Strategy parameters
        self.min_profit_threshold = Decimal(str(config.get("min_profit_threshold", 0.01)))
        self.max_position_size = Decimal(str(config.get("max_position_size", 1000)))
        self.trading_pairs = config.get("trading_pairs", ["BTC-USDT", "ETH-USDT"])
        
        # Current positions tracking
        self._positions: Dict[str, Dict[str, Decimal]] = {}
        
        # Latest funding rates
        self._funding_rates: Dict[str, Dict[str, FundingRate]] = {}
    
    async def on_tick(self):
        """Main strategy logic - called every tick"""
        if not self.is_active:
            return
        
        # Check for arbitrage opportunities
        for symbol in self.trading_pairs:
            await self._check_arbitrage_opportunity(symbol)
    
    async def on_funding_rate_update(self, exchange: str, symbol: str, funding_rate: FundingRate):
        """Handle funding rate updates"""
        if exchange not in self._funding_rates:
            self._funding_rates[exchange] = {}
        
        self._funding_rates[exchange][symbol] = funding_rate
        self.logger.debug(f"Updated funding rate for {exchange}:{symbol} = {funding_rate.rate}")
    
    async def _check_arbitrage_opportunity(self, symbol: str):
        """Check for arbitrage opportunities for a specific symbol"""
        try:
            # Get funding rates from all exchanges
            rates = self._get_funding_rates_for_symbol(symbol)
            
            if len(rates) < 2:
                return  # Need at least 2 exchanges
            
            # Find best arbitrage opportunity
            opportunity = self._find_best_opportunity(rates, symbol)
            
            if opportunity:
                await self._execute_arbitrage(opportunity)
                
        except Exception as e:
            self.logger.error(f"Error checking arbitrage for {symbol}: {e}")
    
    def _get_funding_rates_for_symbol(self, symbol: str) -> Dict[str, FundingRate]:
        """Get funding rates for a symbol from all exchanges"""
        rates = {}
        for exchange, symbols in self._funding_rates.items():
            if symbol in symbols:
                rates[exchange] = symbols[symbol]
        return rates
    
    def _find_best_opportunity(self, rates: Dict[str, FundingRate], symbol: str) -> Optional[dict]:
        """Find the best arbitrage opportunity"""
        if len(rates) < 2:
            return None
        
        best_opportunity = None
        max_profit = Decimal("0")
        
        # Compare all exchange pairs
        exchanges = list(rates.keys())
        for i in range(len(exchanges)):
            for j in range(i + 1, len(exchanges)):
                exchange1, exchange2 = exchanges[i], exchanges[j]
                rate1 = rates[exchange1].rate
                rate2 = rates[exchange2].rate
                
                # Calculate potential profit for both directions
                profit1 = calculate_funding_arbitrage_profit(rate1, rate2, self.max_position_size)
                profit2 = calculate_funding_arbitrage_profit(rate2, rate1, self.max_position_size)
                
                # Choose the more profitable direction
                if profit1 > profit2 and profit1 > max_profit and profit1 > self.min_profit_threshold:
                    max_profit = profit1
                    best_opportunity = {
                        "symbol": symbol,
                        "long_exchange": exchange1,
                        "short_exchange": exchange2,
                        "long_rate": rate1,
                        "short_rate": rate2,
                        "expected_profit": profit1,
                        "position_size": self.max_position_size
                    }
                elif profit2 > max_profit and profit2 > self.min_profit_threshold:
                    max_profit = profit2
                    best_opportunity = {
                        "symbol": symbol,
                        "long_exchange": exchange2,
                        "short_exchange": exchange1,
                        "long_rate": rate2,
                        "short_rate": rate1,
                        "expected_profit": profit2,
                        "position_size": self.max_position_size
                    }
        
        return best_opportunity
    
    async def _execute_arbitrage(self, opportunity: dict):
        """Execute the arbitrage trade"""
        try:
            symbol = opportunity["symbol"]
            long_exchange = opportunity["long_exchange"]
            short_exchange = opportunity["short_exchange"]
            position_size = opportunity["position_size"]
            
            self.logger.info(f"Executing arbitrage for {symbol}:")
            self.logger.info(f"  Long on {long_exchange}, Short on {short_exchange}")
            self.logger.info(f"  Expected profit: ${opportunity['expected_profit']}")
            
            # Place long order
            long_connector = self.connectors[long_exchange]
            long_order = await long_connector.place_order(
                symbol=symbol,
                side="BUY",
                order_type=OrderType.MARKET,
                amount=position_size
            )
            
            # Place short order
            short_connector = self.connectors[short_exchange]
            short_order = await short_connector.place_order(
                symbol=symbol,
                side="SELL",
                order_type=OrderType.MARKET,
                amount=position_size
            )
            
            if long_order and short_order:
                self._trade_count += 1
                self.logger.info(f"Arbitrage executed successfully for {symbol}")
                
                # Track positions
                if symbol not in self._positions:
                    self._positions[symbol] = {}
                
                self._positions[symbol][long_exchange] = position_size
                self._positions[symbol][short_exchange] = -position_size
            else:
                self.logger.error(f"Failed to execute arbitrage for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Error executing arbitrage: {e}")
