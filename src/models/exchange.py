"""
Exchange Models - Modèles pour les données d'exchanges
=====================================================

Modèles pour représenter les données des exchanges, funding rates,
order books, et autres informations de marché.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid


class ExchangeType(Enum):
    """Types d'exchanges"""
    CENTRALIZED = "centralized"
    DECENTRALIZED = "decentralized"
    HYBRID = "hybrid"


class OrderSide(Enum):
    """Côtés d'ordre"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Types d'ordres"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    """Status des ordres"""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


# =============================================================================
# MARKET DATA MODELS
# =============================================================================

@dataclass
class FundingRate:
    """Funding rate d'un token sur un exchange"""
    
    exchange: str
    symbol: str
    funding_rate: float
    funding_time: datetime
    next_funding_time: Optional[datetime] = None
    
    # Additional data
    predicted_rate: Optional[float] = None
    index_price: Optional[float] = None
    mark_price: Optional[float] = None
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def funding_rate_annual(self) -> float:
        """Funding rate annualisé (approximation)"""
        # Assume 8h funding frequency by default
        return self.funding_rate * 3 * 365
    
    @property
    def hours_to_next_funding(self) -> Optional[float]:
        """Heures jusqu'au prochain funding"""
        if self.next_funding_time:
            delta = self.next_funding_time - datetime.now()
            return max(0, delta.total_seconds() / 3600)
        return None
    
    @property
    def is_positive(self) -> bool:
        """Funding rate positif (longs paient shorts)"""
        return self.funding_rate > 0
    
    @property
    def is_extreme(self) -> bool:
        """Funding rate extrême (>0.1% ou <-0.1%)"""
        return abs(self.funding_rate) > 0.001


@dataclass
class MarketData:
    """Données de marché pour un symbol"""
    
    exchange: str
    symbol: str
    
    # Price data
    bid: Optional[float] = None
    ask: Optional[float] = None
    last_price: Optional[float] = None
    mark_price: Optional[float] = None
    index_price: Optional[float] = None
    
    # Volume data
    volume_24h: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    
    # Open interest
    open_interest: Optional[float] = None
    open_interest_usd: Optional[float] = None
    
    # Funding
    funding_rate: Optional[float] = None
    next_funding_time: Optional[datetime] = None
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def spread(self) -> Optional[float]:
        """Spread bid-ask"""
        if self.bid and self.ask:
            return self.ask - self.bid
        return None
    
    @property
    def spread_percentage(self) -> Optional[float]:
        """Spread en pourcentage"""
        if self.spread and self.last_price:
            return (self.spread / self.last_price) * 100
        return None
    
    @property
    def mid_price(self) -> Optional[float]:
        """Prix moyen bid-ask"""
        if self.bid and self.ask:
            return (self.bid + self.ask) / 2
        return self.last_price


@dataclass
class OrderBookLevel:
    """Niveau du carnet d'ordres"""
    price: float
    size: float
    
    @property
    def notional(self) -> float:
        """Valeur notionnelle"""
        return self.price * self.size


@dataclass
class OrderBook:
    """Carnet d'ordres"""
    
    exchange: str
    symbol: str
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        """Meilleur bid"""
        return self.bids[0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        """Meilleur ask"""
        return self.asks[0] if self.asks else None
    
    @property
    def spread(self) -> Optional[float]:
        """Spread"""
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None
    
    @property
    def mid_price(self) -> Optional[float]:
        """Prix moyen"""
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return None
    
    def get_depth(self, side: str, max_levels: int = 10) -> List[OrderBookLevel]:
        """Récupère la profondeur du carnet"""
        if side.lower() == 'bid':
            return self.bids[:max_levels]
        else:
            return self.asks[:max_levels]
    
    def get_liquidity(self, side: str, price_range: float = 0.01) -> float:
        """Calcule la liquidité dans une fourchette de prix"""
        if not self.mid_price:
            return 0.0
        
        levels = self.get_depth(side, 50)
        total_liquidity = 0.0
        
        for level in levels:
            price_diff = abs(level.price - self.mid_price) / self.mid_price
            if price_diff <= price_range:
                total_liquidity += level.notional
            else:
                break
        
        return total_liquidity


# =============================================================================
# ORDER MODELS
# =============================================================================

@dataclass
class Order:
    """Ordre de trading"""
    
    # Identification
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    client_order_id: Optional[str] = None
    exchange_order_id: Optional[str] = None
    
    # Order details
    exchange: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    
    # Quantities and prices
    size: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    
    # Execution
    filled_size: float = 0.0
    average_fill_price: Optional[float] = None
    fees_paid: float = 0.0
    
    # Status and timing
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def remaining_size(self) -> float:
        """Quantité restante à exécuter"""
        return max(0, self.size - self.filled_size)
    
    @property
    def fill_percentage(self) -> float:
        """Pourcentage exécuté"""
        if self.size == 0:
            return 0.0
        return (self.filled_size / self.size) * 100
    
    @property
    def is_filled(self) -> bool:
        """Ordre complètement exécuté"""
        return self.status == OrderStatus.FILLED or self.remaining_size == 0
    
    @property
    def is_active(self) -> bool:
        """Ordre actif (peut encore être exécuté)"""
        return self.status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]
    
    @property
    def notional_value(self) -> Optional[float]:
        """Valeur notionnelle de l'ordre"""
        price = self.price or self.average_fill_price
        if price:
            return price * self.size
        return None
    
    @property
    def executed_notional(self) -> Optional[float]:
        """Valeur notionnelle exécutée"""
        if self.average_fill_price:
            return self.average_fill_price * self.filled_size
        return None
    
    def update_fill(self, filled_size: float, fill_price: float, fee: float = 0.0) -> None:
        """Met à jour l'exécution de l'ordre"""
        self.filled_size += filled_size
        self.fees_paid += fee
        
        # Update average fill price
        if self.average_fill_price is None:
            self.average_fill_price = fill_price
        else:
            total_notional = (self.average_fill_price * (self.filled_size - filled_size) + 
                            fill_price * filled_size)
            self.average_fill_price = total_notional / self.filled_size
        
        # Update status
        if self.filled_size >= self.size:
            self.status = OrderStatus.FILLED
            self.filled_at = datetime.now()
        elif self.filled_size > 0:
            self.status = OrderStatus.PARTIALLY_FILLED
        
        self.updated_at = datetime.now()


# =============================================================================
# EXCHANGE MODELS
# =============================================================================

@dataclass
class ExchangeInfo:
    """Informations sur un exchange"""
    
    name: str
    display_name: str
    exchange_type: ExchangeType
    
    # Capabilities
    supports_futures: bool = True
    supports_spot: bool = True
    supports_funding_rates: bool = True
    
    # Funding specifics
    funding_frequency_hours: int = 8
    funding_times_utc: List[str] = field(default_factory=list)
    
    # Limits
    min_order_size: Optional[float] = None
    max_order_size: Optional[float] = None
    min_notional: Optional[float] = None
    
    # Fees
    maker_fee: Optional[float] = None
    taker_fee: Optional[float] = None
    funding_fee: Optional[float] = None
    
    # API limits
    rate_limit_per_minute: int = 60
    
    # Status
    is_operational: bool = True
    last_status_check: datetime = field(default_factory=datetime.now)
    
    @property
    def funding_periods_per_day(self) -> float:
        """Nombre de périodes de funding par jour"""
        return 24 / self.funding_frequency_hours
    
    @property
    def next_funding_time(self) -> Optional[datetime]:
        """Prochaine heure de funding"""
        if not self.funding_times_utc:
            return None
        
        now = datetime.now()
        today = now.date()
        
        for time_str in self.funding_times_utc:
            hour, minute = map(int, time_str.split(':'))
            funding_time = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
            
            if funding_time > now:
                return funding_time
        
        # Next day first funding
        hour, minute = map(int, self.funding_times_utc[0].split(':'))
        next_day = today + timedelta(days=1)
        return datetime.combine(next_day, datetime.min.time().replace(hour=hour, minute=minute))


@dataclass
class ExchangeStatus:
    """Status d'un exchange"""
    
    exchange: str
    is_connected: bool = False
    is_trading_enabled: bool = False
    last_ping: Optional[datetime] = None
    last_error: Optional[str] = None
    
    # Performance metrics
    avg_response_time_ms: Optional[float] = None
    success_rate_24h: Optional[float] = None
    
    # Market data freshness
    last_market_data_update: Optional[datetime] = None
    last_funding_rate_update: Optional[datetime] = None
    
    @property
    def is_healthy(self) -> bool:
        """Exchange en bonne santé"""
        checks = [
            self.is_connected,
            self.is_trading_enabled,
            self.last_ping and (datetime.now() - self.last_ping).seconds < 300,  # 5 min
            not self.last_error or (datetime.now() - self.last_ping).seconds < 3600  # 1h
        ]
        return all(check for check in checks if check is not None)
    
    @property
    def connection_age_minutes(self) -> Optional[float]:
        """Âge de la connexion en minutes"""
        if self.last_ping:
            return (datetime.now() - self.last_ping).total_seconds() / 60
        return None


@dataclass
class ExchangeBalance:
    """Balance sur un exchange"""
    
    exchange: str
    asset: str
    
    # Balances
    total: float = 0.0
    available: float = 0.0
    locked: float = 0.0
    
    # USD equivalent
    usd_value: Optional[float] = None
    
    # Update info
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def locked_percentage(self) -> float:
        """Pourcentage de balance verrouillée"""
        if self.total == 0:
            return 0.0
        return (self.locked / self.total) * 100
    
    @property
    def is_sufficient(self, required_amount: float) -> bool:
        """Balance suffisante pour le montant requis"""
        return self.available >= required_amount


# =============================================================================
# TRADE MODELS
# =============================================================================

@dataclass
class Trade:
    """Trade exécuté"""
    
    # Identification
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    exchange_trade_id: Optional[str] = None
    order_id: Optional[str] = None
    
    # Trade details
    exchange: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    
    # Execution
    size: float = 0.0
    price: float = 0.0
    fee: float = 0.0
    fee_asset: str = "USDT"
    
    # Timing
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Metadata
    is_maker: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def notional_value(self) -> float:
        """Valeur notionnelle du trade"""
        return self.price * self.size
    
    @property
    def fee_percentage(self) -> float:
        """Fee en pourcentage"""
        if self.notional_value == 0:
            return 0.0
        return (self.fee / self.notional_value) * 100


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_exchange_info(exchange_name: str) -> ExchangeInfo:
    """Factory pour créer ExchangeInfo selon l'exchange"""
    
    configs = {
        'binance': ExchangeInfo(
            name='binance',
            display_name='Binance Futures',
            exchange_type=ExchangeType.CENTRALIZED,
            funding_frequency_hours=8,
            funding_times_utc=['00:00', '08:00', '16:00'],
            maker_fee=0.0002,
            taker_fee=0.0004,
            rate_limit_per_minute=60
        ),
        
        'kucoin': ExchangeInfo(
            name='kucoin',
            display_name='KuCoin Futures',
            exchange_type=ExchangeType.CENTRALIZED,
            funding_frequency_hours=8,
            funding_times_utc=['04:00', '12:00', '20:00'],
            maker_fee=0.0002,
            taker_fee=0.0006,
            rate_limit_per_minute=45
        ),
        
        'hyperliquid': ExchangeInfo(
            name='hyperliquid',
            display_name='Hyperliquid',
            exchange_type=ExchangeType.DECENTRALIZED,
            funding_frequency_hours=1,
            funding_times_utc=[f"{h:02d}:00" for h in range(24)],
            maker_fee=0.0002,
            taker_fee=0.0005,
            rate_limit_per_minute=120
        )
    }
    
    return configs.get(exchange_name.lower(), ExchangeInfo(
        name=exchange_name,
        display_name=exchange_name.title(),
        exchange_type=ExchangeType.CENTRALIZED
    ))


def calculate_funding_arbitrage_spread(funding_a: FundingRate, funding_b: FundingRate) -> Dict[str, Any]:
    """Calcule le spread d'arbitrage entre deux funding rates"""
    
    spread = abs(funding_a.funding_rate - funding_b.funding_rate)
    
    # Determine direction
    if funding_a.funding_rate > funding_b.funding_rate:
        long_exchange = funding_b.exchange
        short_exchange = funding_a.exchange
        expected_profit_rate = funding_a.funding_rate + abs(funding_b.funding_rate) if funding_b.funding_rate < 0 else spread
    else:
        long_exchange = funding_a.exchange
        short_exchange = funding_b.exchange
        expected_profit_rate = funding_b.funding_rate + abs(funding_a.funding_rate) if funding_a.funding_rate < 0 else spread
    
    return {
        'spread': spread,
        'spread_percentage': spread * 100,
        'long_exchange': long_exchange,
        'short_exchange': short_exchange,
        'expected_profit_rate': expected_profit_rate,
        'funding_a': funding_a.funding_rate,
        'funding_b': funding_b.funding_rate,
        'timestamp': datetime.now()
    }


def get_market_data_freshness(market_data: MarketData, max_age_minutes: int = 5) -> bool:
    """Vérifie si les données de marché sont fraîches"""
    age_minutes = (datetime.now() - market_data.timestamp).total_seconds() / 60
    return age_minutes <= max_age_minutes
