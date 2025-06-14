"""
Models package for Funding Arbitrage Bot
"""

# Position models
from .position import (
    Position, 
    PositionStatus, 
    PositionSide,
    ExchangePosition, 
    FundingMetrics
)

# Opportunity models
from .opportunity import (
    ArbitrageOpportunity,
    OpportunityType,
    OpportunityPriority,
    ExchangeData,
    OpportunityFilter,
    create_opportunity
)

# Configuration models
from .config import (
    FundingBotConfig,
    BotConfig,
    TradingConfig,
    RiskManagementConfig,
    ExchangesConfig,
    MonitoringConfig,
    BotMode,
    LogLevel,
    create_config,
    load_config_from_env
)

# Exchange models
from .exchange import (
    FundingRate,
    MarketData,
    OrderBook,
    Order,
    Trade,
    ExchangeInfo,
    ExchangeStatus,
    ExchangeBalance,
    OrderSide,
    OrderType,
    OrderStatus,
    create_exchange_info,
    calculate_funding_arbitrage_spread
)

__all__ = [
    # Position
    'Position', 'PositionStatus', 'PositionSide', 'ExchangePosition', 'FundingMetrics',
    
    # Opportunity
    'ArbitrageOpportunity', 'OpportunityType', 'OpportunityPriority', 
    'ExchangeData', 'OpportunityFilter', 'create_opportunity',
    
    # Config
    'FundingBotConfig', 'BotConfig', 'TradingConfig', 'RiskManagementConfig',
    'ExchangesConfig', 'MonitoringConfig', 'BotMode', 'LogLevel', 
    'create_config', 'load_config_from_env',
    
    # Exchange
    'FundingRate', 'MarketData', 'OrderBook', 'Order', 'Trade',
    'ExchangeInfo', 'ExchangeStatus', 'ExchangeBalance',
    'OrderSide', 'OrderType', 'OrderStatus',
    'create_exchange_info', 'calculate_funding_arbitrage_spread'
]
