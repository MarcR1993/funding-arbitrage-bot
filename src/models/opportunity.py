"""
Opportunity Model - Représente une opportunité d'arbitrage détectée
==================================================================

Modèle pour identifier, évaluer et scorer les opportunités d'arbitrage
de funding rates entre différents exchanges.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid


class OpportunityType(Enum):
    """Types d'opportunités d'arbitrage"""
    FUNDING_RATE = "funding_rate"     # Arbitrage de funding rates
    PRICE_SPREAD = "price_spread"     # Arbitrage de prix spot
    BASIS_SPREAD = "basis_spread"     # Arbitrage futures/spot


class OpportunityPriority(Enum):
    """Priorité de l'opportunité"""
    LOW = "low"         # < 0.05% spread
    MEDIUM = "medium"   # 0.05% - 0.1% spread
    HIGH = "high"       # 0.1% - 0.2% spread
    CRITICAL = "critical"  # > 0.2% spread


@dataclass
class ExchangeData:
    """Données d'un exchange pour l'opportunité"""
    exchange_name: str
    symbol: str
    funding_rate: float
    next_funding_time: Optional[datetime] = None
    funding_frequency_hours: int = 8
    current_price: Optional[float] = None
    volume_24h: Optional[float] = None
    open_interest: Optional[float] = None
    
    # Suggested position
    suggested_side: str = ""  # "long" or "short"
    max_position_size: float = 0.0
    
    @property
    def funding_rate_annual(self) -> float:
        """Funding rate annualisé"""
        periods_per_year = (365 * 24) / self.funding_frequency_hours
        return self.funding_rate * periods_per_year
    
    @property
    def next_funding_in_hours(self) -> Optional[float]:
        """Heures jusqu'au prochain funding"""
        if self.next_funding_time:
            delta = self.next_funding_time - datetime.now()
            return delta.total_seconds() / 3600
        return None


@dataclass
class ArbitrageOpportunity:
    """
    Opportunité d'arbitrage entre deux exchanges
    
    Contient toutes les informations nécessaires pour évaluer
    et exécuter une stratégie d'arbitrage de funding rates.
    """
    
    # Identification
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    token: str = ""
    pair_name: str = ""  # "binance_kucoin"
    opportunity_type: OpportunityType = OpportunityType.FUNDING_RATE
    
    # Exchanges data
    exchange_a: ExchangeData = None
    exchange_b: ExchangeData = None
    
    # Métriques principales
    spread: float = 0.0  # Différence entre les funding rates
    spread_percentage: float = 0.0
    expected_daily_profit: float = 0.0
    expected_hourly_profit: float = 0.0
    
    # Timing et durée
    detected_at: datetime = field(default_factory=datetime.now)
    valid_until: Optional[datetime] = None
    estimated_duration_hours: float = 24.0
    
    # Scoring et priorité
    score: float = 0.0  # Score global 0-100
    priority: OpportunityPriority = OpportunityPriority.LOW
    confidence: float = 0.0  # Confiance 0-1
    
    # Risk metrics
    liquidity_score: float = 0.0
    volatility_risk: float = 0.0
    execution_risk: float = 0.0
    
    # Execution parameters
    recommended_size_usd: float = 1000.0
    max_leverage: int = 1
    suggested_duration_hours: float = 24.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization calculations"""
        if self.exchange_a and self.exchange_b:
            self._calculate_metrics()
            self._calculate_score()
            self._set_priority()
    
    # =============================================================================
    # PROPERTIES - Métriques Calculées
    # =============================================================================
    
    @property
    def age_minutes(self) -> float:
        """Âge de l'opportunité en minutes"""
        return (datetime.now() - self.detected_at).total_seconds() / 60
    
    @property
    def is_valid(self) -> bool:
        """Opportunité encore valide"""
        if self.valid_until:
            return datetime.now() < self.valid_until
        return self.age_minutes < 30  # 30 minutes par défaut
    
    @property
    def is_stale(self) -> bool:
        """Opportunité trop ancienne"""
        return self.age_minutes > 10  # 10 minutes max
    
    @property
    def annual_return_estimate(self) -> float:
        """Estimation du retour annuel si maintenu"""
        if self.recommended_size_usd == 0:
            return 0.0
        daily_return = self.expected_daily_profit / self.recommended_size_usd
        return daily_return * 365 * 100  # Pourcentage annuel
    
    @property
    def risk_adjusted_score(self) -> float:
        """Score ajusté du risque"""
        risk_factor = 1 - (self.volatility_risk + self.execution_risk) / 2
        return self.score * risk_factor * self.confidence
    
    @property
    def execution_complexity(self) -> str:
        """Complexité d'exécution"""
        if self.execution_risk < 0.2:
            return "Simple"
        elif self.execution_risk < 0.5:
            return "Moderate"
        else:
            return "Complex"
    
    # =============================================================================
    # METHODS - Calculs et Évaluations
    # =============================================================================
    
    def _calculate_metrics(self) -> None:
        """Calcule les métriques principales"""
        if not self.exchange_a or not self.exchange_b:
            return
            
        # Spread calculation
        self.spread = abs(self.exchange_a.funding_rate - self.exchange_b.funding_rate)
        self.spread_percentage = self.spread * 100
        
        # Determine which exchange pays better
        if self.exchange_a.funding_rate > self.exchange_b.funding_rate:
            self.exchange_a.suggested_side = "short"
            self.exchange_b.suggested_side = "long"
            profit_rate = self.exchange_a.funding_rate + abs(self.exchange_b.funding_rate) if self.exchange_b.funding_rate < 0 else self.spread
        else:
            self.exchange_a.suggested_side = "long"
            self.exchange_b.suggested_side = "short"
            profit_rate = self.exchange_b.funding_rate + abs(self.exchange_a.funding_rate) if self.exchange_a.funding_rate < 0 else self.spread
        
        # Profit calculations
        freq_a = self.exchange_a.funding_frequency_hours
        freq_b = self.exchange_b.funding_frequency_hours
        
        # Calculate weighted average frequency
        avg_frequency = (freq_a + freq_b) / 2
        funding_periods_per_day = 24 / avg_frequency
        
        self.expected_hourly_profit = profit_rate * self.recommended_size_usd
        self.expected_daily_profit = self.expected_hourly_profit * funding_periods_per_day
        
        # Adjust for different frequencies (Hyperliquid advantage)
        if "hyperliquid" in self.pair_name.lower():
            # Hyperliquid funds every hour vs 8h for others
            hyperliquid_multiplier = 8 if freq_a != freq_b else 1
            self.expected_daily_profit *= hyperliquid_multiplier
    
    def _calculate_score(self) -> None:
        """Calcule le score global de l'opportunité"""
        if not self.exchange_a or not self.exchange_b:
            self.score = 0.0
            return
            
        score = 0.0
        
        # Spread score (0-40 points)
        spread_score = min(self.spread * 8000, 40)  # 0.5% spread = 40 points
        score += spread_score
        
        # Frequency advantage (0-20 points)
        freq_a = self.exchange_a.funding_frequency_hours
        freq_b = self.exchange_b.funding_frequency_hours
        if min(freq_a, freq_b) == 1:  # Hyperliquid
            score += 20
        elif max(freq_a, freq_b) <= 8:
            score += 10
        
        # Liquidity score (0-15 points)
        score += self.liquidity_score * 15
        
        # Confidence score (0-15 points)
        score += self.confidence * 15
        
        # Pair bonus (0-10 points)
        pair_bonuses = {
            "binance_hyperliquid": 10,  # Best pair
            "kucoin_hyperliquid": 8,
            "binance_kucoin": 6
        }
        score += pair_bonuses.get(self.pair_name, 0)
        
        self.score = min(100, max(0, score))
    
    def _set_priority(self) -> None:
        """Définit la priorité basée sur le spread"""
        if self.spread >= 0.002:  # 0.2%
            self.priority = OpportunityPriority.CRITICAL
        elif self.spread >= 0.001:  # 0.1%
            self.priority = OpportunityPriority.HIGH
        elif self.spread >= 0.0005:  # 0.05%
            self.priority = OpportunityPriority.MEDIUM
        else:
            self.priority = OpportunityPriority.LOW
    
    def update_market_data(self, exchange_a_data: Dict, exchange_b_data: Dict) -> None:
        """Met à jour les données de marché"""
        if self.exchange_a:
            self.exchange_a.funding_rate = exchange_a_data.get('funding_rate', self.exchange_a.funding_rate)
            self.exchange_a.current_price = exchange_a_data.get('current_price')
            self.exchange_a.volume_24h = exchange_a_data.get('volume_24h')
            
        if self.exchange_b:
            self.exchange_b.funding_rate = exchange_b_data.get('funding_rate', self.exchange_b.funding_rate)
            self.exchange_b.current_price = exchange_b_data.get('current_price')
            self.exchange_b.volume_24h = exchange_b_data.get('volume_24h')
        
        # Recalculate metrics
        self._calculate_metrics()
        self._calculate_score()
        self._set_priority()
    
    def calculate_liquidity_score(self) -> float:
        """Calcule le score de liquidité basé sur volume et open interest"""
        if not self.exchange_a or not self.exchange_b:
            return 0.0
            
        # Minimum volume threshold (24h volume in USD)
        min_volume_threshold = 1_000_000  # $1M
        
        vol_a = self.exchange_a.volume_24h or 0
        vol_b = self.exchange_b.volume_24h or 0
        
        min_volume = min(vol_a, vol_b)
        
        if min_volume >= min_volume_threshold * 10:  # $10M+
            return 1.0
        elif min_volume >= min_volume_threshold * 5:  # $5M+
            return 0.8
        elif min_volume >= min_volume_threshold:  # $1M+
            return 0.6
        elif min_volume >= min_volume_threshold * 0.5:  # $500K+
            return 0.4
        else:
            return 0.2
    
    def calculate_execution_risk(self) -> float:
        """Calcule le risque d'exécution"""
        risk = 0.0
        
        # Age risk
        if self.age_minutes > 5:
            risk += 0.2
        elif self.age_minutes > 2:
            risk += 0.1
            
        # Spread size risk (very large spreads might be errors)
        if self.spread > 0.005:  # 0.5%
            risk += 0.3
            
        # Market hours risk (weekend/holidays)
        now = datetime.now()
        if now.weekday() >= 5:  # Weekend
            risk += 0.1
            
        return min(1.0, risk)
    
    def estimate_confidence(self, historical_data: Optional[List] = None) -> float:
        """Estime la confiance dans l'opportunité"""
        confidence = 0.5  # Base confidence
        
        # Spread consistency
        if 0.0002 <= self.spread <= 0.002:  # Reasonable range
            confidence += 0.3
        elif self.spread > 0.002:  # Very high spread (suspicious)
            confidence -= 0.2
            
        # Exchange reputation
        reputable_exchanges = ["binance", "kucoin", "hyperliquid"]
        if (self.exchange_a.exchange_name.lower() in reputable_exchanges and 
            self.exchange_b.exchange_name.lower() in reputable_exchanges):
            confidence += 0.2
            
        return min(1.0, max(0.0, confidence))
    
    def is_better_than(self, other: 'ArbitrageOpportunity') -> bool:
        """Compare si cette opportunité est meilleure qu'une autre"""
        # Compare d'abord par risk-adjusted score
        if abs(self.risk_adjusted_score - other.risk_adjusted_score) > 5:
            return self.risk_adjusted_score > other.risk_adjusted_score
            
        # Puis par spread
        if abs(self.spread - other.spread) > 0.0001:  # 0.01%
            return self.spread > other.spread
            
        # Finalement par freshness
        return self.age_minutes < other.age_minutes
    
    def should_execute(self, min_spread: float = 0.0005, min_score: float = 30.0) -> bool:
        """Détermine si l'opportunité devrait être exécutée"""
        checks = [
            self.is_valid,
            not self.is_stale,
            self.spread >= min_spread,
            self.score >= min_score,
            self.confidence > 0.3,
            self.execution_risk < 0.7
        ]
        
        return all(checks)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'opportunité en dictionnaire"""
        return {
            'id': self.id,
            'token': self.token,
            'pair_name': self.pair_name,
            'opportunity_type': self.opportunity_type.value,
            'spread': self.spread,
            'spread_percentage': self.spread_percentage,
            'expected_daily_profit': self.expected_daily_profit,
            'expected_hourly_profit': self.expected_hourly_profit,
            'detected_at': self.detected_at.isoformat(),
            'age_minutes': self.age_minutes,
            'score': self.score,
            'priority': self.priority.value,
            'confidence': self.confidence,
            'liquidity_score': self.liquidity_score,
            'execution_risk': self.execution_risk,
            'recommended_size_usd': self.recommended_size_usd,
            'annual_return_estimate': self.annual_return_estimate,
            'risk_adjusted_score': self.risk_adjusted_score,
            'is_valid': self.is_valid,
            'should_execute': self.should_execute(),
            'exchange_a': {
                'name': self.exchange_a.exchange_name if self.exchange_a else None,
                'funding_rate': self.exchange_a.funding_rate if self.exchange_a else None,
                'suggested_side': self.exchange_a.suggested_side if self.exchange_a else None
            } if self.exchange_a else None,
            'exchange_b': {
                'name': self.exchange_b.exchange_name if self.exchange_b else None,
                'funding_rate': self.exchange_b.funding_rate if self.exchange_b else None,
                'suggested_side': self.exchange_b.suggested_side if self.exchange_b else None
            } if self.exchange_b else None,
            'metadata': self.metadata
        }
    
    def __str__(self) -> str:
        """String representation pour logging"""
        return (f"Opportunity {self.id}: {self.token} {self.pair_name} "
                f"| Spread: {self.spread_percentage:.3f}% "
                f"| Daily Profit: ${self.expected_daily_profit:.2f} "
                f"| Score: {self.score:.1f} | Priority: {self.priority.value}")
    
    def __repr__(self) -> str:
        return f"ArbitrageOpportunity(id='{self.id}', token='{self.token}', spread={self.spread:.4f})"


# =============================================================================
# OPPORTUNITY MANAGER UTILITIES
# =============================================================================

class OpportunityFilter:
    """Filtre pour les opportunités"""
    
    @staticmethod
    def filter_by_spread(opportunities: List[ArbitrageOpportunity], 
                        min_spread: float = 0.0005) -> List[ArbitrageOpportunity]:
        """Filtre par spread minimum"""
        return [opp for opp in opportunities if opp.spread >= min_spread]
    
    @staticmethod
    def filter_by_score(opportunities: List[ArbitrageOpportunity], 
                       min_score: float = 30.0) -> List[ArbitrageOpportunity]:
        """Filtre par score minimum"""
        return [opp for opp in opportunities if opp.score >= min_score]
    
    @staticmethod
    def filter_executable(opportunities: List[ArbitrageOpportunity]) -> List[ArbitrageOpportunity]:
        """Filtre les opportunités exécutables"""
        return [opp for opp in opportunities if opp.should_execute()]
    
    @staticmethod
    def sort_by_priority(opportunities: List[ArbitrageOpportunity]) -> List[ArbitrageOpportunity]:
        """Trie par priorité et score"""
        priority_order = {
            OpportunityPriority.CRITICAL: 4,
            OpportunityPriority.HIGH: 3,
            OpportunityPriority.MEDIUM: 2,
            OpportunityPriority.LOW: 1
        }
        
        return sorted(opportunities, 
                     key=lambda x: (priority_order[x.priority], x.risk_adjusted_score), 
                     reverse=True)


def create_opportunity(token: str, exchange_a_data: Dict, exchange_b_data: Dict) -> ArbitrageOpportunity:
    """
    Factory function pour créer une opportunité
    
    Args:
        token: Token symbol (e.g., "BTC")
        exchange_a_data: Dict with exchange_name, funding_rate, etc.
        exchange_b_data: Dict with exchange_name, funding_rate, etc.
    """
    exchange_a = ExchangeData(
        exchange_name=exchange_a_data['exchange_name'],
        symbol=f"{token}/USDT",
        funding_rate=exchange_a_data['funding_rate'],
        funding_frequency_hours=exchange_a_data.get('funding_frequency_hours', 8),
        current_price=exchange_a_data.get('current_price'),
        volume_24h=exchange_a_data.get('volume_24h')
    )
    
    exchange_b = ExchangeData(
        exchange_name=exchange_b_data['exchange_name'],
        symbol=f"{token}/USDT",
        funding_rate=exchange_b_data['funding_rate'],
        funding_frequency_hours=exchange_b_data.get('funding_frequency_hours', 8),
        current_price=exchange_b_data.get('current_price'),
        volume_24h=exchange_b_data.get('volume_24h')
    )
    
    pair_name = f"{exchange_a.exchange_name.lower()}_{exchange_b.exchange_name.lower()}"
    
    opportunity = ArbitrageOpportunity(
        token=token,
        pair_name=pair_name,
        exchange_a=exchange_a,
        exchange_b=exchange_b
    )
    
    # Calculate risk metrics
    opportunity.liquidity_score = opportunity.calculate_liquidity_score()
    opportunity.execution_risk = opportunity.calculate_execution_risk()
    opportunity.confidence = opportunity.estimate_confidence()
    
    return opportunity
