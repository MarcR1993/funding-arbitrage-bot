"""
Arbitrage Engine - Moteur principal du bot d'arbitrage
=====================================================

Moteur central qui coordonne tous les composants :
- Oracle des funding rates
- Gestionnaire de positions
- Connecteurs d'exchanges
- Stratégie d'arbitrage

Implémente la logique de trading automatique avec la stratégie 3 paires optimale.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

from .funding_oracle import FundingRateOracle
from .position_manager import PositionManager
from ..models.config import FundingBotConfig, BotMode
from ..models.opportunity import ArbitrageOpportunity
from ..models.position import Position
from ..exchanges import (
    BaseExchangeConnector, BinanceConnector, KuCoinConnector, 
    HyperliquidConnector, ConnectionError
)


class EngineState(Enum):
    """États possibles du moteur"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class ArbitrageEngine:
    """
    Moteur principal d'arbitrage de funding rates
    
    Responsabilités:
    - Coordination de tous les composants
    - Logique de trading automatique
    - Gestion des états et erreurs
    - Monitoring et métriques globales
    - Emergency stop et recovery
    """
    
    def __init__(self, config: FundingBotConfig):
        """
        Initialise le moteur d'arbitrage
        
        Args:
            config: Configuration complète du bot
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # État du moteur
        self.state = EngineState.STOPPED
        self.start_time = None
        self.last_cycle_time = None
        self.error_count = 0
        self.emergency_stop_triggered = False
        
        # Composants principaux
        self.connectors: Dict[str, BaseExchangeConnector] = {}
        self.funding_oracle: Optional[FundingRateOracle] = None
        self.position_manager: Optional[PositionManager] = None
        
        # Configuration de trading
        self.trading_cycle_interval = config.bot.evaluation_interval_seconds
        self.max_daily_loss = config.risk_management.max_daily_loss
        self.emergency_close_threshold = config.risk_management.emergency_close_threshold
        
        # Métriques globales
        self.total_cycles = 0
        self.successful_cycles = 0
        self.opportunities_evaluated = 0
        self.positions_opened_today = 0
        self.daily_pnl = 0.0
        self.daily_start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # =============================================================================
    # LIFECYCLE MANAGEMENT
    # =============================================================================
    
    async def initialize(self) -> bool:
        """
        Initialise tous les composants du moteur
        
        Returns:
            bool: True si l'initialisation réussit
        """
        try:
            self.logger.info("🚀 Initializing Funding Arbitrage Engine...")
            self.state = EngineState.STARTING
            
            # 1. Initialiser les connecteurs d'exchanges
            await self._initialize_connectors()
            
            # 2. Vérifier les connexions
            connected_exchanges = await self._test_all_connections()
            
            if len(connected_exchanges) < 2:
                raise ConnectionError(f"Need at least 2 exchanges, got {len(connected_exchanges)}")
            
            # 3. Initialiser l'oracle des funding rates
            self.funding_oracle = FundingRateOracle(self.config, self.connectors)
            
            # 4. Initialiser le gestionnaire de positions
            self.position_manager = PositionManager(self.config, self.connectors)
            
            self.logger.info(f"✅ Engine initialized with {len(connected_exchanges)} exchanges: "
                           f"{', '.join(connected_exchanges)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Engine initialization failed: {e}")
            self.state = EngineState.ERROR
            return False
    
    async def _initialize_connectors(self) -> None:
        """Initialise et connecte tous les exchanges"""
        
        enabled_exchanges = self.config.get_enabled_exchanges()
        self.logger.info(f"Initializing connectors for: {enabled_exchanges}")
        
        # Créer les connecteurs selon la configuration
        for exchange_name in enabled_exchanges:
            try:
                connector = await self._create_connector(exchange_name)
                if connector:
                    self.connectors[exchange_name] = connector
                    
            except Exception as e:
                self.logger.error(f"Failed to initialize {exchange_name} connector: {e}")
                continue
    
    async def _create_connector(self, exchange_name: str) -> Optional[BaseExchangeConnector]:
        """Crée un connecteur pour un exchange spécifique"""
        
        exchange_config = self.config.get_exchange_config(exchange_name)
        if not exchange_config:
            self.logger.warning(f"No configuration found for {exchange_name}")
            return None
        
        try:
            # Créer le connecteur selon le type d'exchange
            if exchange_name == "binance":
                connector = BinanceConnector({
                    'testnet': exchange_config.testnet,
                    'rate_limit_per_minute': exchange_config.rate_limit_requests_per_minute
                })
            
            elif exchange_name == "kucoin":
                connector = KuCoinConnector({
                    'sandbox': exchange_config.sandbox,
                    'rate_limit_per_minute': exchange_config.rate_limit_requests_per_minute
                })
            
            elif exchange_name == "hyperliquid":
                connector = HyperliquidConnector({
                    'testnet': exchange_config.testnet,
                    'use_vault': getattr(exchange_config, 'use_vault', True),
                    'rate_limit_per_minute': exchange_config.rate_limit_requests_per_minute
                })
            
            else:
                self.logger.error(f"Unknown exchange: {exchange_name}")
                return None
            
            # Connecter
            success = await connector.connect()
            if success:
                self.logger.info(f"✅ Connected to {exchange_name}")
                return connector
            else:
                self.logger.error(f"❌ Failed to connect to {exchange_name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating {exchange_name} connector: {e}")
            return None
    
    async def _test_all_connections(self) -> List[str]:
        """Test toutes les connexions et retourne les exchanges connectés"""
        
        connected = []
        
        for exchange_name, connector in self.connectors.items():
            try:
                if await connector.ping():
                    connected.append(exchange_name)
                    self.logger.info(f"✅ {exchange_name} connection verified")
                else:
                    self.logger.warning(f"❌ {exchange_name} ping failed")
                    
            except Exception as e:
                self.logger.error(f"❌ {exchange_name} connection test failed: {e}")
        
        return connected
    
    async def start(self) -> bool:
        """
        Démarre le moteur d'arbitrage
        
        Returns:
            bool: True si le démarrage réussit
        """
        
        if self.state == EngineState.RUNNING:
            self.logger.warning("Engine already running")
            return True
        
        try:
            # Initialiser si pas déjà fait
            if self.state == EngineState.STOPPED:
                if not await self.initialize():
                    return False
            
            self.logger.info("🚀 Starting Funding Arbitrage Engine...")
            
            # Démarrer les composants
            await self.funding_oracle.start()
            await self.position_manager.start()
            
            # Marquer comme running
            self.state = EngineState.RUNNING
            self.start_time = datetime.now()
            self.emergency_stop_triggered = False
            
            # Démarrer la boucle principale
            asyncio.create_task(self._main_trading_loop())
            
            self.logger.info("✅ Funding Arbitrage Engine started successfully!")
            self._log_engine_status()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start engine: {e}")
            self.state = EngineState.ERROR
            return False
    
    async def stop(self, emergency: bool = False) -> None:
        """
        Arrête le moteur d'arbitrage
        
        Args:
            emergency: Si True, arrêt d'urgence (ferme toutes les positions)
        """
        
        if emergency:
            self.logger.warning("🚨 EMERGENCY STOP triggered!")
            self.state = EngineState.EMERGENCY_STOP
            self.emergency_stop_triggered = True
        else:
            self.logger.info("🛑 Stopping Funding Arbitrage Engine...")
            self.state = EngineState.STOPPING
        
        try:
            # Arrêter les composants
            if self.funding_oracle:
                await self.funding_oracle.stop()
            
            if self.position_manager:
                if emergency:
                    # Fermer toutes les positions immédiatement
                    await self.position_manager.close_all_positions("Emergency stop")
                
                await self.position_manager.stop()
            
            # Fermer les connexions
            for connector in self.connectors.values():
                await connector.disconnect()
            
            self.state = EngineState.STOPPED
            
            stop_type = "Emergency stop" if emergency else "Normal stop"
            self.logger.info(f"✅ Engine stopped ({stop_type})")
            
        except Exception as e:
            self.logger.error(f"Error during engine stop: {e}")
            self.state = EngineState.ERROR
    
    # =============================================================================
    # MAIN TRADING LOOP
    # =============================================================================
    
    async def _main_trading_loop(self) -> None:
        """Boucle principale de trading"""
        
        self.logger.info("Starting main trading loop...")
        
        while self.state == EngineState.RUNNING:
            cycle_start = datetime.now()
            
            try:
                # Exécuter un cycle de trading
                await self._execute_trading_cycle()
                
                # Vérifier les conditions d'arrêt d'urgence
                if await self._should_emergency_stop():
                    await self.stop(emergency=True)
                    break
                
                # Attendre avant le prochain cycle
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                sleep_time = max(0, self.trading_cycle_interval - cycle_duration)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
                self.last_cycle_time = datetime.now()
                self.successful_cycles += 1
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in trading cycle: {e}")
                self.error_count += 1
                
                # Si trop d'erreurs, arrêter
                if self.error_count >= 10:
                    self.logger.error("Too many errors, stopping engine")
                    await self.stop(emergency=True)
                    break
                
                # Attendre avant de réessayer
                await asyncio.sleep(60)
            
            finally:
                self.total_cycles += 1
    
    async def _execute_trading_cycle(self) -> None:
        """Exécute un cycle de trading complet"""
        
        self.logger.debug("Executing trading cycle...")
        
        # 1. Vérifier l'état des composants
        if not self._verify_components_health():
            raise RuntimeError("Components not healthy")
        
        # 2. Récupérer les meilleures opportunités
        opportunities = self._get_best_opportunities()
        self.opportunities_evaluated += len(opportunities)
        
        if not opportunities:
            self.logger.debug("No opportunities found in this cycle")
            return
        
        # 3. Évaluer les opportunités pour ouverture/remplacement
        for opportunity in opportunities:
            try:
                await self._evaluate_opportunity(opportunity)
            except Exception as e:
                self.logger.error(f"Error evaluating opportunity {opportunity.id}: {e}")
                continue
        
        # 4. Mettre à jour les métriques quotidiennes
        self._update_daily_metrics()
        
        # 5. Log du statut (moins fréquent)
        if self.total_cycles % 20 == 0:  # Tous les 20 cycles
            self._log_engine_status()
    
    def _verify_components_health(self) -> bool:
        """Vérifie la santé des composants"""
        
        checks = [
            self.funding_oracle and self.funding_oracle.is_healthy(),
            self.position_manager and self.position_manager.is_running,
            len([c for c in self.connectors.values() if c.is_connected]) >= 2
        ]
        
        return all(checks)
    
    def _get_best_opportunities(self) -> List[ArbitrageOpportunity]:
        """Récupère les meilleures opportunités actuelles"""
        
        if not self.funding_oracle:
            return []
        
        # Récupérer toutes les opportunités
        all_opportunities = self.funding_oracle.get_current_opportunities()
        
        # Filtrer par qualité
        min_score = 30.0  # Score minimum
        min_spread = self.config.trading.min_spread_threshold
        
        filtered = [
            opp for opp in all_opportunities
            if opp.score >= min_score and opp.spread >= min_spread and opp.should_execute()
        ]
        
        # Retourner les 5 meilleures
        return filtered[:5]
    
    async def _evaluate_opportunity(self, opportunity: ArbitrageOpportunity) -> None:
        """Évalue une opportunité pour ouverture ou remplacement"""
        
        if not self.position_manager:
            return
        
        # Si on peut ouvrir directement
        if len(self.position_manager.active_positions) < self.config.trading.max_concurrent_positions:
            position = await self.position_manager.try_open_position(opportunity)
            if position:
                self.positions_opened_today += 1
                self.logger.info(f"📈 Opened new position: {position}")
        
        # Sinon, considérer le remplacement
        else:
            position = await self.position_manager.consider_position_replacement(opportunity)
            if position:
                self.positions_opened_today += 1
                self.logger.info(f"🔄 Replaced position with: {position}")
    
    # =============================================================================
    # SAFETY & MONITORING
    # =============================================================================
    
    async def _should_emergency_stop(self) -> bool:
        """Vérifie si un arrêt d'urgence est nécessaire"""
        
        # Vérifier les pertes quotidiennes
        current_daily_pnl = self._calculate_current_daily_pnl()
        
        if current_daily_pnl <= self.max_daily_loss:
            self.logger.warning(f"Daily loss limit reached: {current_daily_pnl:.2%} <= {self.max_daily_loss:.2%}")
            return True
        
        # Vérifier le seuil d'urgence
        if current_daily_pnl <= self.emergency_close_threshold:
            self.logger.error(f"Emergency threshold reached: {current_daily_pnl:.2%}")
            return True
        
        # Vérifier l'état des connexions
        connected_exchanges = len([c for c in self.connectors.values() if c.is_connected])
        if connected_exchanges < 2:
            self.logger.error(f"Too few exchanges connected: {connected_exchanges}")
            return True
        
        return False
    
    def _calculate_current_daily_pnl(self) -> float:
        """Calcule le PnL quotidien actuel"""
        
        if not self.position_manager:
            return 0.0
        
        # PnL réalisé aujourd'hui + PnL non réalisé des positions actives
        stats = self.position_manager.get_manager_stats()
        
        # Filtrer les positions fermées aujourd'hui
        today_realized = 0.0
        for position in self.position_manager.position_history:
            if (position.closed_at and 
                position.closed_at >= self.daily_start_time):
                today_realized += position.net_pnl
        
        total_daily_pnl = today_realized + stats['total_unrealized_pnl']
        
        # Convertir en pourcentage du capital total
        total_capital = self.positions_opened_today * self.config.trading.position_size_usd
        if total_capital > 0:
            return total_daily_pnl / total_capital
        
        return 0.0
    
    def _update_daily_metrics(self) -> None:
        """Met à jour les métriques quotidiennes"""
        
        now = datetime.now()
        
        # Reset quotidien à minuit
        if now.date() > self.daily_start_time.date():
            self.daily_start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self.positions_opened_today = 0
            self.daily_pnl = 0.0
        
        # Mettre à jour le PnL quotidien
        self.daily_pnl = self._calculate_current_daily_pnl()
    
    # =============================================================================
    # STATUS & METRICS
    # =============================================================================
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Récupère le statut complet du moteur"""
        
        uptime_seconds = 0
        if self.start_time:
            uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        
        # Statistiques des composants
        oracle_stats = self.funding_oracle.get_oracle_stats() if self.funding_oracle else {}
        position_stats = self.position_manager.get_manager_stats() if self.position_manager else {}
        
        # Statut des exchanges
        exchange_status = {}
        for name, connector in self.connectors.items():
            exchange_status[name] = {
                'connected': connector.is_connected,
                'last_ping': connector.last_ping,
                'errors': connector.connection_errors
            }
        
        return {
            'engine': {
                'state': self.state.value,
                'uptime_seconds': uptime_seconds,
                'start_time': self.start_time,
                'last_cycle': self.last_cycle_time,
                'total_cycles': self.total_cycles,
                'successful_cycles': self.successful_cycles,
                'error_count': self.error_count,
                'emergency_stop_triggered': self.emergency_stop_triggered
            },
            'trading': {
                'opportunities_evaluated': self.opportunities_evaluated,
                'positions_opened_today': self.positions_opened_today,
                'daily_pnl': self.daily_pnl,
                'daily_pnl_percentage': self.daily_pnl * 100
            },
            'oracle': oracle_stats,
            'positions': position_stats,
            'exchanges': exchange_status
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Récupère un résumé de performance"""
        
        if not self.position_manager:
            return {}
        
        perf = self.position_manager.get_performance_summary()
        
        # Ajouter des métriques du moteur
        perf.update({
            'engine_uptime_hours': (datetime.now() - self.start_time).total_seconds() / 3600 if self.start_time else 0,
            'cycles_per_hour': self.total_cycles / max(1, (datetime.now() - self.start_time).total_seconds() / 3600) if self.start_time else 0,
            'daily_positions': self.positions_opened_today,
            'opportunities_per_cycle': self.opportunities_evaluated / max(1, self.total_cycles)
        })
        
        return perf
    
    def _log_engine_status(self) -> None:
        """Log le statut du moteur"""
        
        status = self.get_engine_status()
        perf = self.get_performance_summary()
        
        self.logger.info(
            f"🤖 Engine Status: {status['engine']['state']} | "
            f"Positions: {status['positions'].get('active_positions', 0)}/{self.config.trading.max_concurrent_positions} | "
            f"Daily PnL: {status['trading']['daily_pnl_percentage']:.2f}% | "
            f"Exchanges: {len([e for e in status['exchanges'].values() if e['connected']])}/{len(self.connectors)} | "
            f"Opportunities: {status['oracle'].get('current_opportunities', 0)}"
        )
    
    def is_healthy(self) -> bool:
        """Vérifie si le moteur est en bonne santé"""
        
        if self.state != EngineState.RUNNING:
            return False
        
        return self._verify_components_health()
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check complet pour monitoring externe"""
        
        health = {
            'status': 'healthy' if self.is_healthy() else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'components': {
                'engine': self.state.value,
                'oracle': 'healthy' if (self.funding_oracle and self.funding_oracle.is_healthy()) else 'unhealthy',
                'position_manager': 'running' if (self.position_manager and self.position_manager.is_running) else 'stopped',
                'exchanges': {
                    name: 'connected' if connector.is_connected else 'disconnected'
                    for name, connector in self.connectors.items()
                }
            },
            'metrics': self.get_performance_summary()
        }
        
        return health
    
    def __repr__(self) -> str:
        active_positions = len(self.position_manager.active_positions) if self.position_manager else 0
        
        return (f"ArbitrageEngine(state={self.state.value}, "
                f"positions={active_positions}/{self.config.trading.max_concurrent_positions}, "
                f"exchanges={len([c for c in self.connectors.values() if c.is_connected])}, "
                f"cycles={self.total_cycles})")
