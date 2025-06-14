"""
Funding Rate Oracle - Collecte et analyse des funding rates
==========================================================

Oracle responsable de collecter les funding rates de tous les exchanges,
détecter les opportunités d'arbitrage et calculer les spreads.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..models.exchange import FundingRate
from ..models.opportunity import ArbitrageOpportunity, ExchangeData, create_opportunity
from ..models.config import FundingBotConfig
from ..exchanges import BaseExchangeConnector


@dataclass
class FundingSnapshot:
    """Snapshot des funding rates à un moment donné"""
    timestamp: datetime
    rates: Dict[str, Dict[str, FundingRate]]  # {exchange: {token: FundingRate}}
    opportunities: List[ArbitrageOpportunity]
    
    @property
    def age_seconds(self) -> float:
        """Âge du snapshot en secondes"""
        return (datetime.now() - self.timestamp).total_seconds()
    
    @property
    def is_stale(self, max_age_seconds: int = 300) -> bool:
        """Snapshot trop ancien (5 minutes par défaut)"""
        return self.age_seconds > max_age_seconds


class FundingRateOracle:
    """
    Oracle pour la collecte et l'analyse des funding rates
    
    Responsabilités:
    - Collecter les funding rates de tous les exchanges
    - Détecter les opportunités d'arbitrage
    - Maintenir un historique des rates
    - Calculer les spreads et scores
    """
    
    def __init__(self, config: FundingBotConfig, connectors: Dict[str, BaseExchangeConnector]):
        """
        Initialise l'oracle
        
        Args:
            config: Configuration du bot
            connectors: Connecteurs des exchanges {name: connector}
        """
        self.config = config
        self.connectors = connectors
        self.logger = logging.getLogger(__name__)
        
        # État de l'oracle
        self.is_running = False
        self.last_update = None
        self.update_interval = config.bot.evaluation_interval_seconds
        
        # Cache des données
        self.current_snapshot: Optional[FundingSnapshot] = None
        self.rate_history: List[FundingSnapshot] = []
        self.max_history_size = 1000  # Garder 1000 snapshots max
        
        # Tokens à surveiller
        self.tokens = config.trading.tokens
        self.supported_pairs = [pair.name for pair in config.trading.supported_pairs if pair.enabled]
        
        # Métriques
        self.total_updates = 0
        self.failed_updates = 0
        self.opportunities_detected = 0
    
    # =============================================================================
    # LIFECYCLE MANAGEMENT
    # =============================================================================
    
    async def start(self) -> None:
        """Démarre l'oracle"""
        if self.is_running:
            self.logger.warning("Oracle already running")
            return
        
        self.logger.info(f"Starting funding rate oracle for {len(self.tokens)} tokens")
        self.is_running = True
        
        # Première collecte immédiate
        await self.update_funding_rates()
        
        # Démarrer la boucle de mise à jour
        asyncio.create_task(self._update_loop())
    
    async def stop(self) -> None:
        """Arrête l'oracle"""
        self.logger.info("Stopping funding rate oracle")
        self.is_running = False
    
    async def _update_loop(self) -> None:
        """Boucle principale de mise à jour"""
        while self.is_running:
            try:
                await asyncio.sleep(self.update_interval)
                if self.is_running:  # Check again after sleep
                    await self.update_funding_rates()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in oracle update loop: {e}")
                self.failed_updates += 1
                await asyncio.sleep(30)  # Wait before retrying
    
    # =============================================================================
    # DATA COLLECTION
    # =============================================================================
    
    async def update_funding_rates(self) -> FundingSnapshot:
        """
        Met à jour tous les funding rates et détecte les opportunités
        
        Returns:
            FundingSnapshot: Nouveau snapshot des données
        """
        start_time = datetime.now()
        
        try:
            # Collecter les rates de tous les exchanges
            all_rates = await self._collect_all_rates()
            
            # Détecter les opportunités
            opportunities = await self._detect_opportunities(all_rates)
            
            # Créer le snapshot
            snapshot = FundingSnapshot(
                timestamp=start_time,
                rates=all_rates,
                opportunities=opportunities
            )
            
            # Mettre à jour le cache
            self.current_snapshot = snapshot
            self._add_to_history(snapshot)
            
            self.last_update = start_time
            self.total_updates += 1
            self.opportunities_detected += len(opportunities)
            
            self.logger.debug(f"Updated funding rates: {len(opportunities)} opportunities found")
            
            return snapshot
            
        except Exception as e:
            self.logger.error(f"Failed to update funding rates: {e}")
            self.failed_updates += 1
            raise
    
    async def _collect_all_rates(self) -> Dict[str, Dict[str, FundingRate]]:
        """Collecte les funding rates de tous les exchanges"""
        all_rates = {}
        
        # Collecter en parallèle pour tous les exchanges actifs
        tasks = []
        for exchange_name, connector in self.connectors.items():
            if connector.is_connected:
                task = self._collect_exchange_rates(exchange_name, connector)
                tasks.append(task)
        
        if not tasks:
            self.logger.warning("No connected exchanges for rate collection")
            return all_rates
        
        # Attendre tous les résultats
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Traiter les résultats
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                exchange_name = list(self.connectors.keys())[i]
                self.logger.error(f"Failed to collect rates from {exchange_name}: {result}")
            else:
                exchange_name, rates = result
                all_rates[exchange_name] = rates
        
        return all_rates
    
    async def _collect_exchange_rates(self, exchange_name: str, 
                                    connector: BaseExchangeConnector) -> Tuple[str, Dict[str, FundingRate]]:
        """Collecte les rates d'un exchange spécifique"""
        try:
            # Utiliser la méthode batch si possible
            rates = await connector.get_funding_rates(self.tokens)
            
            self.logger.debug(f"Collected {len(rates)} rates from {exchange_name}")
            return exchange_name, rates
            
        except Exception as e:
            self.logger.error(f"Error collecting rates from {exchange_name}: {e}")
            # Fallback: collecter individuellement
            rates = {}
            for token in self.tokens:
                try:
                    rate = await connector.get_funding_rate(f"{token}/USDT")
                    rates[token] = rate
                    await asyncio.sleep(0.1)  # Petit délai entre requêtes
                except Exception:
                    continue
            
            return exchange_name, rates
    
    def _add_to_history(self, snapshot: FundingSnapshot) -> None:
        """Ajoute un snapshot à l'historique"""
        self.rate_history.append(snapshot)
        
        # Limiter la taille de l'historique
        if len(self.rate_history) > self.max_history_size:
            self.rate_history = self.rate_history[-self.max_history_size:]
    
    # =============================================================================
    # OPPORTUNITY DETECTION
    # =============================================================================
    
    async def _detect_opportunities(self, all_rates: Dict[str, Dict[str, FundingRate]]) -> List[ArbitrageOpportunity]:
        """Détecte les opportunités d'arbitrage"""
        opportunities = []
        
        # Vérifier toutes les paires supportées
        for pair_name in self.supported_pairs:
            try:
                exchange_a, exchange_b = pair_name.split('_')
                
                # Vérifier que les deux exchanges ont des données
                if exchange_a not in all_rates or exchange_b not in all_rates:
                    continue
                
                # Détecter les opportunités pour cette paire
                pair_opportunities = await self._detect_pair_opportunities(
                    exchange_a, exchange_b, all_rates[exchange_a], all_rates[exchange_b]
                )
                
                opportunities.extend(pair_opportunities)
                
            except Exception as e:
                self.logger.error(f"Error detecting opportunities for {pair_name}: {e}")
                continue
        
        # Trier par score décroissant
        opportunities.sort(key=lambda x: x.risk_adjusted_score, reverse=True)
        
        return opportunities
    
    async def _detect_pair_opportunities(self, exchange_a: str, exchange_b: str,
                                       rates_a: Dict[str, FundingRate], 
                                       rates_b: Dict[str, FundingRate]) -> List[ArbitrageOpportunity]:
        """Détecte les opportunités pour une paire d'exchanges"""
        opportunities = []
        
        # Tokens communs aux deux exchanges
        common_tokens = set(rates_a.keys()) & set(rates_b.keys())
        
        for token in common_tokens:
            try:
                rate_a = rates_a[token]
                rate_b = rates_b[token]
                
                # Calculer le spread
                spread = abs(rate_a.funding_rate - rate_b.funding_rate)
                
                # Vérifier le seuil minimum
                if spread < self.config.trading.min_spread_threshold:
                    continue
                
                # Créer les données d'exchange
                exchange_data_a = ExchangeData(
                    exchange_name=exchange_a,
                    symbol=f"{token}/USDT",
                    funding_rate=rate_a.funding_rate,
                    next_funding_time=rate_a.next_funding_time,
                    funding_frequency_hours=self._get_exchange_frequency(exchange_a)
                )
                
                exchange_data_b = ExchangeData(
                    exchange_name=exchange_b,
                    symbol=f"{token}/USDT",
                    funding_rate=rate_b.funding_rate,
                    next_funding_time=rate_b.next_funding_time,
                    funding_frequency_hours=self._get_exchange_frequency(exchange_b)
                )
                
                # Créer l'opportunité
                opportunity = create_opportunity(token, 
                                              self._exchange_data_to_dict(exchange_data_a),
                                              self._exchange_data_to_dict(exchange_data_b))
                
                # Appliquer la taille de position configurée
                opportunity.recommended_size_usd = self.config.trading.position_size_usd
                
                opportunities.append(opportunity)
                
            except Exception as e:
                self.logger.error(f"Error creating opportunity for {token} {exchange_a}-{exchange_b}: {e}")
                continue
        
        return opportunities
    
    def _get_exchange_frequency(self, exchange_name: str) -> int:
        """Récupère la fréquence de funding d'un exchange"""
        frequencies = {
            'binance': 8,
            'kucoin': 8,
            'hyperliquid': 1
        }
        return frequencies.get(exchange_name.lower(), 8)
    
    def _exchange_data_to_dict(self, exchange_data: ExchangeData) -> Dict:
        """Convertit ExchangeData en dict pour create_opportunity"""
        return {
            'exchange_name': exchange_data.exchange_name,
            'funding_rate': exchange_data.funding_rate,
            'funding_frequency_hours': exchange_data.funding_frequency_hours,
            'current_price': exchange_data.current_price,
            'volume_24h': exchange_data.volume_24h
        }
    
    # =============================================================================
    # DATA ACCESS
    # =============================================================================
    
    def get_current_rates(self, exchange: Optional[str] = None) -> Optional[Dict]:
        """
        Récupère les rates actuels
        
        Args:
            exchange: Exchange spécifique ou None pour tous
            
        Returns:
            Dict des rates ou None si pas de données
        """
        if not self.current_snapshot:
            return None
        
        if exchange:
            return self.current_snapshot.rates.get(exchange)
        else:
            return self.current_snapshot.rates
    
    def get_current_opportunities(self, min_score: Optional[float] = None) -> List[ArbitrageOpportunity]:
        """
        Récupère les opportunités actuelles
        
        Args:
            min_score: Score minimum (optionnel)
            
        Returns:
            Liste des opportunités filtrées
        """
        if not self.current_snapshot:
            return []
        
        opportunities = self.current_snapshot.opportunities
        
        if min_score is not None:
            opportunities = [opp for opp in opportunities if opp.score >= min_score]
        
        return opportunities
    
    def get_best_opportunities(self, count: int = 5) -> List[ArbitrageOpportunity]:
        """
        Récupère les meilleures opportunités
        
        Args:
            count: Nombre d'opportunités à retourner
            
        Returns:
            Liste des meilleures opportunités
        """
        opportunities = self.get_current_opportunities()
        return opportunities[:count]
    
    def get_opportunity_for_pair(self, pair_name: str, token: str) -> Optional[ArbitrageOpportunity]:
        """
        Récupère l'opportunité pour une paire et token spécifiques
        
        Args:
            pair_name: Nom de la paire (ex: "binance_kucoin")
            token: Token (ex: "BTC")
            
        Returns:
            Opportunité ou None si pas trouvée
        """
        opportunities = self.get_current_opportunities()
        
        for opp in opportunities:
            if opp.pair_name == pair_name and opp.token == token:
                return opp
        
        return None
    
    def get_funding_rate(self, exchange: str, token: str) -> Optional[FundingRate]:
        """
        Récupère un funding rate spécifique
        
        Args:
            exchange: Nom de l'exchange
            token: Token
            
        Returns:
            FundingRate ou None si pas trouvé
        """
        if not self.current_snapshot:
            return None
        
        exchange_rates = self.current_snapshot.rates.get(exchange, {})
        return exchange_rates.get(token)
    
    # =============================================================================
    # STATISTICS & ANALYSIS
    # =============================================================================
    
    def get_oracle_stats(self) -> Dict:
        """Récupère les statistiques de l'oracle"""
        uptime_seconds = 0
        if self.last_update:
            uptime_seconds = (datetime.now() - self.last_update).total_seconds()
        
        success_rate = 0.0
        if self.total_updates > 0:
            success_rate = (self.total_updates - self.failed_updates) / self.total_updates
        
        return {
            'is_running': self.is_running,
            'last_update': self.last_update,
            'uptime_seconds': uptime_seconds,
            'total_updates': self.total_updates,
            'failed_updates': self.failed_updates,
            'success_rate': success_rate,
            'opportunities_detected': self.opportunities_detected,
            'current_opportunities': len(self.get_current_opportunities()),
            'exchanges_connected': len([c for c in self.connectors.values() if c.is_connected]),
            'history_size': len(self.rate_history)
        }
    
    def get_spread_statistics(self, hours_back: int = 24) -> Dict[str, Dict]:
        """
        Analyse les spreads historiques
        
        Args:
            hours_back: Nombre d'heures à analyser
            
        Returns:
            Statistiques par paire
        """
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        # Filtrer l'historique
        recent_snapshots = [s for s in self.rate_history if s.timestamp >= cutoff_time]
        
        if not recent_snapshots:
            return {}
        
        # Analyser par paire
        pair_stats = {}
        
        for pair_name in self.supported_pairs:
            spreads = []
            
            for snapshot in recent_snapshots:
                for opp in snapshot.opportunities:
                    if opp.pair_name == pair_name:
                        spreads.append(opp.spread)
            
            if spreads:
                pair_stats[pair_name] = {
                    'count': len(spreads),
                    'avg_spread': sum(spreads) / len(spreads),
                    'min_spread': min(spreads),
                    'max_spread': max(spreads),
                    'median_spread': sorted(spreads)[len(spreads)//2] if spreads else 0
                }
        
        return pair_stats
    
    def is_healthy(self) -> bool:
        """Vérifie si l'oracle est en bonne santé"""
        checks = [
            self.is_running,
            self.current_snapshot is not None,
            not (self.current_snapshot and self.current_snapshot.is_stale()),
            len([c for c in self.connectors.values() if c.is_connected]) >= 2,
            self.total_updates > 0
        ]
        
        return all(checks)
    
    def __repr__(self) -> str:
        status = "running" if self.is_running else "stopped"
        connected_exchanges = len([c for c in self.connectors.values() if c.is_connected])
        
        return (f"FundingRateOracle(status={status}, "
                f"exchanges={connected_exchanges}/{len(self.connectors)}, "
                f"opportunities={len(self.get_current_opportunities())})")
