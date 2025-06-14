"""
Position Model - Représente une position d'arbitrage active
============================================================

Modèle pour tracker les positions d'arbitrage entre deux exchanges,
avec toutes les métriques nécessaires pour la gestion et l'optimisation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from enum import Enum
import uuid


class PositionStatus(Enum):
    """Status possibles d'une position"""
    OPENING = "opening"      # En cours d'ouverture
    ACTIVE = "active"        # Position active et profitable
    MONITORING = "monitoring" # Sous surveillance (profit faible)
    CLOSING = "closing"      # En cours de fermeture
    CLOSED = "closed"        # Position fermée
    ERROR = "error"          # Erreur technique


class PositionSide(Enum):
    """Côté de la position sur un exchange"""
    LONG = "long"
    SHORT = "short"


@dataclass
class ExchangePosition:
    """Position sur un exchange spécifique"""
    exchange: str
    symbol: str
    side: PositionSide
    size: float
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    order_id: Optional[str] = None
    position_id: Optional[str] = None
    
    @property
    def pnl(self) -> float:
        """Calculate PnL for this exchange position"""
        if not self.entry_price or not self.current_price:
            return 0.0
            
        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) * self.size
        else:  # SHORT
            return (self.entry_price - self.current_price) * self.size


@dataclass
class FundingMetrics:
    """Métriques liées aux funding rates"""
    initial_spread: float
    current_spread: float
    funding_collected_exchange_a: float = 0.0
    funding_collected_exchange_b: float = 0.0
    funding_rate_a: float = 0.0
    funding_rate_b: float = 0.0
    next_funding_time_a: Optional[datetime] = None
    next_funding_time_b: Optional[datetime] = None
    
    @property
    def total_funding_collected(self) -> float:
        """Total funding collecté des deux exchanges"""
        return self.funding_collected_exchange_a + self.funding_collected_exchange_b
    
    @property
    def spread_decay(self) -> float:
        """Détérioration du spread depuis l'ouverture"""
        return self.initial_spread - self.current_spread


@dataclass
class Position:
    """
    Position d'arbitrage entre deux exchanges
    
    Représente une position d'arbitrage complète avec:
    - Positions sur les deux exchanges
    - Métriques de performance
    - Gestion du timing et des risques
    """
    
    # Identification
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    pair_name: str = ""  # "binance_kucoin", "binance_hyperliquid", etc.
    token: str = ""      # "BTC", "ETH", etc.
    
    # Exchanges et positions
    exchange_a: str = ""
    exchange_b: str = ""
    position_a: Optional[ExchangePosition] = None
    position_b: Optional[ExchangePosition] = None
    
    # Paramètres de trading
    size_usd: float = 0.0
    leverage: int = 1
    
    # Métriques financières
    funding_metrics: Optional[FundingMetrics] = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_fees_paid: float = 0.0
    
    # Timing
    opened_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    expected_close_time: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Status et gestion
    status: PositionStatus = PositionStatus.OPENING
    auto_close_enabled: bool = True
    emergency_close: bool = False
    
    # Métadonnées
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization setup"""
        if not self.pair_name and self.exchange_a and self.exchange_b:
            self.pair_name = f"{self.exchange_a}_{self.exchange_b}"
            
        # Set expected close time (4 weeks by default)
        if not self.expected_close_time:
            self.expected_close_time = self.opened_at + timedelta(weeks=4)
    
    # =============================================================================
    # PROPERTIES - Métriques Calculées
    # =============================================================================
    
    @property
    def age_hours(self) -> float:
        """Âge de la position en heures"""
        return (datetime.now() - self.opened_at).total_seconds() / 3600
    
    @property
    def age_days(self) -> float:
        """Âge de la position en jours"""
        return self.age_hours / 24
    
    @property
    def is_expired(self) -> bool:
        """Position expirée (au-delà de la durée max)"""
        if self.expected_close_time:
            return datetime.now() > self.expected_close_time
        return self.age_hours > 672  # 4 weeks default
    
    @property
    def total_pnl(self) -> float:
        """PnL total (réalisé + non réalisé + funding)"""
        funding_pnl = 0.0
        if self.funding_metrics:
            funding_pnl = self.funding_metrics.total_funding_collected
            
        return self.realized_pnl + self.unrealized_pnl + funding_pnl
    
    @property
    def net_pnl(self) -> float:
        """PnL net après fees"""
        return self.total_pnl - self.total_fees_paid
    
    @property
    def roi_percentage(self) -> float:
        """Return on Investment en pourcentage"""
        if self.size_usd == 0:
            return 0.0
        return (self.net_pnl / self.size_usd) * 100
    
    @property
    def hourly_profit_rate(self) -> float:
        """Taux de profit horaire"""
        if self.age_hours == 0:
            return 0.0
        return self.net_pnl / self.age_hours
    
    @property
    def daily_profit_rate(self) -> float:
        """Taux de profit quotidien"""
        return self.hourly_profit_rate * 24
    
    @property
    def is_profitable(self) -> bool:
        """Position actuellement profitable"""
        return self.net_pnl > 0
    
    @property
    def health_score(self) -> float:
        """Score de santé de la position (0-100)"""
        score = 50  # Base score
        
        # Profit factor
        if self.net_pnl > 0:
            score += min(self.roi_percentage * 10, 30)  # Max +30
        else:
            score += max(self.roi_percentage * 10, -30)  # Max -30
            
        # Spread factor
        if self.funding_metrics:
            if self.funding_metrics.current_spread > 0.0002:  # 0.02%
                score += 10
            elif self.funding_metrics.current_spread < 0:
                score -= 20
                
        # Age factor
        if self.age_hours < 24:
            score += 5  # Recent position bonus
        elif self.age_hours > 168:  # 1 week
            score -= 5  # Old position penalty
            
        return max(0, min(100, score))
    
    # =============================================================================
    # METHODS - Actions et Mises à Jour
    # =============================================================================
    
    def update_positions(self, position_a_data: Dict, position_b_data: Dict) -> None:
        """Met à jour les données des positions"""
        if self.position_a:
            self.position_a.current_price = position_a_data.get('current_price')
            
        if self.position_b:
            self.position_b.current_price = position_b_data.get('current_price')
            
        self.last_updated = datetime.now()
        self._calculate_unrealized_pnl()
    
    def update_funding_metrics(self, rate_a: float, rate_b: float, 
                             collected_a: float = 0.0, collected_b: float = 0.0) -> None:
        """Met à jour les métriques de funding"""
        if not self.funding_metrics:
            # Initialize with current rates as initial spread
            initial_spread = abs(rate_a - rate_b)
            self.funding_metrics = FundingMetrics(
                initial_spread=initial_spread,
                current_spread=abs(rate_a - rate_b)
            )
        
        self.funding_metrics.funding_rate_a = rate_a
        self.funding_metrics.funding_rate_b = rate_b
        self.funding_metrics.current_spread = abs(rate_a - rate_b)
        
        # Add newly collected funding
        self.funding_metrics.funding_collected_exchange_a += collected_a
        self.funding_metrics.funding_collected_exchange_b += collected_b
        
        self.last_updated = datetime.now()
    
    def _calculate_unrealized_pnl(self) -> None:
        """Calcule le PnL non réalisé"""
        total_unrealized = 0.0
        
        if self.position_a:
            total_unrealized += self.position_a.pnl
            
        if self.position_b:
            total_unrealized += self.position_b.pnl
            
        self.unrealized_pnl = total_unrealized
    
    def should_close(self, min_profit_threshold: float = 0.0002,
                    stop_loss_threshold: float = -0.005) -> bool:
        """
        Détermine si la position devrait être fermée
        
        Args:
            min_profit_threshold: Seuil minimum de profit (0.02% par défaut)
            stop_loss_threshold: Seuil de stop loss (-0.5% par défaut)
        """
        roi_decimal = self.roi_percentage / 100
        
        # Stop loss
        if roi_decimal <= stop_loss_threshold:
            return True
            
        # Position expirée
        if self.is_expired:
            return True
            
        # Spread devenu défavorable
        if self.funding_metrics and self.funding_metrics.current_spread < 0:
            return True
            
        # Profit trop faible depuis trop longtemps
        if (self.age_hours > 24 and 
            roi_decimal < min_profit_threshold and 
            self.daily_profit_rate < min_profit_threshold):
            return True
            
        # Emergency close flag
        if self.emergency_close:
            return True
            
        return False
    
    def mark_for_closure(self, reason: str = "") -> None:
        """Marque la position pour fermeture"""
        self.status = PositionStatus.CLOSING
        self.metadata['close_reason'] = reason
        self.metadata['close_marked_at'] = datetime.now().isoformat()
    
    def close_position(self, final_pnl: float, fees_paid: float = 0.0) -> None:
        """Ferme la position avec le PnL final"""
        self.status = PositionStatus.CLOSED
        self.closed_at = datetime.now()
        self.realized_pnl = final_pnl
        self.total_fees_paid += fees_paid
        self.unrealized_pnl = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la position en dictionnaire pour sauvegarde"""
        return {
            'id': self.id,
            'pair_name': self.pair_name,
            'token': self.token,
            'exchange_a': self.exchange_a,
            'exchange_b': self.exchange_b,
            'size_usd': self.size_usd,
            'leverage': self.leverage,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'total_fees_paid': self.total_fees_paid,
            'opened_at': self.opened_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'status': self.status.value,
            'total_pnl': self.total_pnl,
            'net_pnl': self.net_pnl,
            'roi_percentage': self.roi_percentage,
            'age_hours': self.age_hours,
            'health_score': self.health_score,
            'metadata': self.metadata
        }
    
    def __str__(self) -> str:
        """String representation for logging"""
        return (f"Position {self.id}: {self.token} {self.pair_name} "
                f"| Size: ${self.size_usd} | PnL: ${self.net_pnl:.2f} "
                f"| ROI: {self.roi_percentage:.2f}% | Age: {self.age_hours:.1f}h "
                f"| Status: {self.status.value}")
    
    def __repr__(self) -> str:
        return f"Position(id='{self.id}', token='{self.token}', pair='{self.pair_name}')"
