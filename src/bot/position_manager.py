"""
Position Manager - Gestionnaire des positions d'arbitrage
========================================================

Gestionnaire responsable de l'ouverture, fermeture et monitoring
des positions d'arbitrage selon la stratégie 3 paires optimale.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import asdict

from ..models.position import Position, PositionStatus, ExchangePosition, FundingMetrics
from ..models.opportunity import ArbitrageOpportunity
from ..models.config import FundingBotConfig
from ..exchanges import BaseExchangeConnector, TradingError, OrderSide


class PositionManager:
    """
    Gestionnaire des positions d'arbitrage
    
    Responsabilités:
    - Ouvrir des positions selon les opportunités détectées
    - Monitoring continu des positions actives
    - Fermeture automatique selon les critères de profit/risque
    - Gestion des 3 paires simultanées maximum
    - Replacement intelligent des positions sous-performantes
    """
    
    def __init__(self, config: FundingBotConfig, connectors: Dict[str, BaseExchangeConnector]):
        """
        Initialise le gestionnaire de positions
        
        Args:
            config: Configuration du bot
            connectors: Connecteurs des exchanges {name: connector}
        """
        self.config = config
        self.connectors = connectors
        self.logger = logging.getLogger(__name__)
        
        # État des positions
        self.active_positions: Dict[str, Position] = {}
        self.position_history: List[Position] = []
        
        # Limites de trading
        self.max_positions = config.trading.max_concurrent_positions
        self.position_size_usd = config.trading.position_size_usd
        self.max_leverage = config.trading.max_leverage
        
        # Paramètres de gestion des risques
        self.min_profit_threshold = config.risk_management.min_profit_threshold
        self.stop_loss_threshold = config.risk_management.stop_loss_threshold
        self.max_position_age_hours = config.risk_management.max_position_age_hours
        
        # Monitoring
        self.is_running = False
        self.monitoring_interval = 30  # 30 secondes
        self.last_evaluation = None
        
        # Métriques
        self.total_positions_opened = 0
        self.total_positions_closed = 0
        self.total_realized_pnl = 0.0
        self.total_fees_paid = 0.0
    
    # =============================================================================
    # LIFECYCLE MANAGEMENT
    # =============================================================================
    
    async def start(self) -> None:
        """Démarre le gestionnaire de positions"""
        if self.is_running:
            self.logger.warning("Position manager already running")
            return
        
        self.logger.info(f"Starting position manager (max {self.max_positions} positions)")
        self.is_running = True
        
        # Démarrer le monitoring en arrière-plan
        asyncio.create_task(self._monitoring_loop())
    
    async def stop(self) -> None:
        """Arrête le gestionnaire et ferme toutes les positions"""
        self.logger.info("Stopping position manager")
        self.is_running = False
        
        # Fermer toutes les positions actives
        await self.close_all_positions(reason="Bot stopping")
    
    async def _monitoring_loop(self) -> None:
        """Boucle de monitoring des positions"""
        while self.is_running:
            try:
                await self.evaluate_all_positions()
                await asyncio.sleep(self.monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in position monitoring: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    # =============================================================================
    # POSITION OPENING
    # =============================================================================
    
    async def try_open_position(self, opportunity: ArbitrageOpportunity) -> Optional[Position]:
        """
        Tente d'ouvrir une position basée sur une opportunité
        
        Args:
            opportunity: Opportunité d'arbitrage détectée
            
        Returns:
            Position créée ou None si échec
        """
        try:
            # Vérifier si on peut ouvrir une nouvelle position
            if not self._can_open_position(opportunity):
                return None
            
            # Vérifier les prérequis de trading
            if not await self._validate_trading_requirements(opportunity):
                return None
            
            # Ouvrir la position
            position = await self._open_arbitrage_position(opportunity)
            
            if position:
                self.active_positions[position.id] = position
                self.total_positions_opened += 1
                
                self.logger.info(f"✅ Opened position {position.id}: "
                               f"{opportunity.token} {opportunity.pair_name} "
                               f"spread={opportunity.spread*100:.3f}%")
            
            return position
            
        except Exception as e:
            self.logger.error(f"Failed to open position for {opportunity.token} {opportunity.pair_name}: {e}")
            return None
    
    def _can_open_position(self, opportunity: ArbitrageOpportunity) -> bool:
        """Vérifie si on peut ouvrir une nouvelle position"""
        
        # Vérifier le nombre maximum de positions
        if len(self.active_positions) >= self.max_positions:
            self.logger.debug("Maximum positions reached")
            return False
        
        # Vérifier qu'on n'a pas déjà cette paire/token
        for position in self.active_positions.values():
            if (position.pair_name == opportunity.pair_name and 
                position.token == opportunity.token):
                self.logger.debug(f"Position already exists for {opportunity.token} {opportunity.pair_name}")
                return False
        
        # Vérifier que l'opportunité est exécutable
        if not opportunity.should_execute(
            min_spread=self.config.trading.min_spread_threshold,
            min_score=30.0
        ):
            self.logger.debug(f"Opportunity not executable: score={opportunity.score:.1f}")
            return False
        
        return True
    
    async def _validate_trading_requirements(self, opportunity: ArbitrageOpportunity) -> bool:
        """Valide les prérequis pour ouvrir la position"""
        
        if not opportunity.exchange_a or not opportunity.exchange_b:
            return False
        
        exchange_a_name = opportunity.exchange_a.exchange_name
        exchange_b_name = opportunity.exchange_b.exchange_name
        
        # Vérifier que les connecteurs sont disponibles et connectés
        connector_a = self.connectors.get(exchange_a_name)
        connector_b = self.connectors.get(exchange_b_name)
        
        if not connector_a or not connector_b:
            self.logger.warning(f"Missing connectors for {exchange_a_name} or {exchange_b_name}")
            return False
        
        if not connector_a.is_connected or not connector_b.is_connected:
            self.logger.warning(f"Exchanges not connected: {exchange_a_name}={connector_a.is_connected}, "
                              f"{exchange_b_name}={connector_b.is_connected}")
            return False
        
        # Vérifier les balances
        symbol = f"{opportunity.token}/USDT"
        
        try:
            balance_checks = await asyncio.gather(
                connector_a.validate_trading_requirements(symbol, OrderSide.BUY, self.position_size_usd),
                connector_b.validate_trading_requirements(symbol, OrderSide.SELL, self.position_size_usd),
                return_exceptions=True
            )
            
            if not all(check for check in balance_checks if not isinstance(check, Exception)):
                self.logger.warning(f"Trading requirements not met for {opportunity.token}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error validating trading requirements: {e}")
            return False
        
        return True
    
    async def _open_arbitrage_position(self, opportunity: ArbitrageOpportunity) -> Optional[Position]:
        """Ouvre une position d'arbitrage"""
        
        # Déterminer les côtés de trading
        long_exchange = opportunity.exchange_a.exchange_name if opportunity.exchange_a.suggested_side == "long" else opportunity.exchange_b.exchange_name
        short_exchange = opportunity.exchange_b.exchange_name if opportunity.exchange_b.suggested_side == "short" else opportunity.exchange_a.exchange_name
        
        connector_long = self.connectors[long_exchange]
        connector_short = self.connectors[short_exchange]
        
        symbol = f"{opportunity.token}/USDT"
        
        try:
            # Calculer la taille en tokens (pas en USD)
            # On utilise le prix moyen pour convertir
            avg_price = (opportunity.exchange_a.current_price + opportunity.exchange_b.current_price) / 2 if \
                       (opportunity.exchange_a.current_price and opportunity.exchange_b.current_price) else None
            
            if not avg_price:
                # Fallback: récupérer le prix actuel
                market_data = await connector_long.get_market_data(symbol)
                avg_price = market_data.last_price
            
            if not avg_price:
                raise TradingError("Cannot determine current price")
            
            position_size_tokens = self.position_size_usd / avg_price
            
            # Placer les ordres simultanément
            self.logger.info(f"Placing simultaneous orders: "
                           f"LONG {position_size_tokens:.6f} {opportunity.token} on {long_exchange}, "
                           f"SHORT {position_size_tokens:.6f} {opportunity.token} on {short_exchange}")
            
            long_order, short_order = await asyncio.gather(
                connector_long.place_market_order(symbol, OrderSide.BUY, position_size_tokens),
                connector_short.place_market_order(symbol, OrderSide.SELL, position_size_tokens)
            )
            
            # Créer les positions d'exchange
            long_exchange_pos = ExchangePosition(
                exchange=long_exchange,
                symbol=symbol,
                side="long",
                size=position_size_tokens,
                entry_price=long_order.average_fill_price,
                order_id=long_order.exchange_order_id
            )
            
            short_exchange_pos = ExchangePosition(
                exchange=short_exchange,
                symbol=symbol,
                side="short", 
                size=position_size_tokens,
                entry_price=short_order.average_fill_price,
                order_id=short_order.exchange_order_id
            )
            
            # Créer les métriques de funding
            funding_metrics = FundingMetrics(
                initial_spread=opportunity.spread,
                current_spread=opportunity.spread,
                funding_rate_a=opportunity.exchange_a.funding_rate,
                funding_rate_b=opportunity.exchange_b.funding_rate,
                next_funding_time_a=opportunity.exchange_a.next_funding_time,
                next_funding_time_b=opportunity.exchange_b.next_funding_time
            )
            
            # Créer la position
            position = Position(
                pair_name=opportunity.pair_name,
                token=opportunity.token,
                exchange_a=long_exchange,
                exchange_b=short_exchange,
                position_a=long_exchange_pos,
                position_b=short_exchange_pos,
                size_usd=self.position_size_usd,
                leverage=1,  # Pas de leverage pour l'arbitrage
                funding_metrics=funding_metrics,
                total_fees_paid=long_order.fees_paid + short_order.fees_paid,
                status=PositionStatus.ACTIVE,
                opened_at=datetime.now()
            )
            
            return position
            
        except Exception as e:
            self.logger.error(f"Failed to open arbitrage position: {e}")
            # TODO: Cleanup partial orders if needed
            raise TradingError(f"Position opening failed: {e}")
    
    # =============================================================================
    # POSITION MONITORING & EVALUATION
    # =============================================================================
    
    async def evaluate_all_positions(self) -> None:
        """Évalue toutes les positions actives"""
        if not self.active_positions:
            return
        
        self.logger.debug(f"Evaluating {len(self.active_positions)} active positions")
        
        # Évaluer chaque position
        positions_to_close = []
        
        for position_id, position in self.active_positions.items():
            try:
                await self._evaluate_position(position)
                
                # Vérifier les critères de fermeture
                if position.should_close(self.min_profit_threshold, self.stop_loss_threshold):
                    positions_to_close.append(position_id)
                    
            except Exception as e:
                self.logger.error(f"Error evaluating position {position_id}: {e}")
                # Marquer pour fermeture en cas d'erreur persistante
                positions_to_close.append(position_id)
        
        # Fermer les positions marquées
        for position_id in positions_to_close:
            position = self.active_positions[position_id]
            reason = "Auto-close criteria met"
            
            if position.is_expired:
                reason = "Position expired"
            elif position.roi_percentage <= self.stop_loss_threshold * 100:
                reason = "Stop loss triggered"
            elif not position.is_profitable:
                reason = "No longer profitable"
            
            await self.close_position(position_id, reason=reason)
        
        self.last_evaluation = datetime.now()
    
    async def _evaluate_position(self, position: Position) -> None:
        """Évalue une position spécifique"""
        
        # Mettre à jour les prix actuels
        await self._update_position_prices(position)
        
        # Mettre à jour les métriques de funding
        await self._update_funding_metrics(position)
        
        # Recalculer les PnL
        self._calculate_position_pnl(position)
        
        position.last_updated = datetime.now()
    
    async def _update_position_prices(self, position: Position) -> None:
        """Met à jour les prix actuels de la position"""
        try:
            symbol = f"{position.token}/USDT"
            
            # Récupérer les prix actuels des deux exchanges
            connector_a = self.connectors[position.exchange_a]
            connector_b = self.connectors[position.exchange_b]
            
            market_data_a, market_data_b = await asyncio.gather(
                connector_a.get_market_data(symbol),
                connector_b.get_market_data(symbol),
                return_exceptions=True
            )
            
            # Mettre à jour les prix
            if not isinstance(market_data_a, Exception) and position.position_a:
                position.position_a.current_price = market_data_a.last_price
            
            if not isinstance(market_data_b, Exception) and position.position_b:
                position.position_b.current_price = market_data_b.last_price
                
        except Exception as e:
            self.logger.error(f"Error updating prices for position {position.id}: {e}")
    
    async def _update_funding_metrics(self, position: Position) -> None:
        """Met à jour les métriques de funding"""
        try:
            symbol = f"{position.token}/USDT"
            
            # Récupérer les funding rates actuels
            connector_a = self.connectors[position.exchange_a]
            connector_b = self.connectors[position.exchange_b]
            
            funding_a, funding_b = await asyncio.gather(
                connector_a.get_funding_rate(symbol),
                connector_b.get_funding_rate(symbol),
                return_exceptions=True
            )
            
            if position.funding_metrics:
                # Mettre à jour les rates actuels
                if not isinstance(funding_a, Exception):
                    position.funding_metrics.funding_rate_a = funding_a.funding_rate
                    position.funding_metrics.next_funding_time_a = funding_a.next_funding_time
                
                if not isinstance(funding_b, Exception):
                    position.funding_metrics.funding_rate_b = funding_b.funding_rate
                    position.funding_metrics.next_funding_time_b = funding_b.next_funding_time
                
                # Recalculer le spread actuel
                position.funding_metrics.current_spread = abs(
                    position.funding_metrics.funding_rate_a - position.funding_metrics.funding_rate_b
                )
                
        except Exception as e:
            self.logger.error(f"Error updating funding metrics for position {position.id}: {e}")
    
    def _calculate_position_pnl(self, position: Position) -> None:
        """Calcule le PnL de la position"""
        try:
            total_unrealized = 0.0
            
            # PnL des positions individuelles
            if position.position_a:
                total_unrealized += position.position_a.pnl
            
            if position.position_b:
                total_unrealized += position.position_b.pnl
            
            # Ajouter les funding collectés
            if position.funding_metrics:
                total_unrealized += position.funding_metrics.total_funding_collected
            
            position.unrealized_pnl = total_unrealized
            
        except Exception as e:
            self.logger.error(f"Error calculating PnL for position {position.id}: {e}")
    
    # =============================================================================
    # POSITION CLOSING
    # =============================================================================
    
    async def close_position(self, position_id: str, reason: str = "Manual close") -> bool:
        """
        Ferme une position spécifique
        
        Args:
            position_id: ID de la position à fermer
            reason: Raison de la fermeture
            
        Returns:
            bool: True si fermée avec succès
        """
        
        if position_id not in self.active_positions:
            self.logger.warning(f"Position {position_id} not found in active positions")
            return False
        
        position = self.active_positions[position_id]
        
        try:
            self.logger.info(f"🔄 Closing position {position_id}: {reason}")
            position.status = PositionStatus.CLOSING
            
            # Fermer les positions sur les deux exchanges
            final_pnl, total_fees = await self._close_exchange_positions(position)
            
            # Finaliser la position
            position.close_position(final_pnl, total_fees)
            
            # Déplacer vers l'historique
            del self.active_positions[position_id]
            self.position_history.append(position)
            
            # Mettre à jour les métriques
            self.total_positions_closed += 1
            self.total_realized_pnl += final_pnl
            self.total_fees_paid += total_fees
            
            self.logger.info(f"✅ Closed position {position_id}: "
                           f"PnL=${final_pnl:.2f}, ROI={position.roi_percentage:.2f}%")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to close position {position_id}: {e}")
            position.status = PositionStatus.ERROR
            return False
    
    async def _close_exchange_positions(self, position: Position) -> Tuple[float, float]:
        """Ferme les positions sur les exchanges"""
        
        symbol = f"{position.token}/USDT"
        total_pnl = 0.0
        total_fees = 0.0
        
        try:
            # Fermer les positions simultanément
            connector_a = self.connectors[position.exchange_a]
            connector_b = self.connectors[position.exchange_b]
            
            close_orders = await asyncio.gather(
                connector_a.close_position(symbol),
                connector_b.close_position(symbol),
                return_exceptions=True
            )
            
            # Traiter les résultats
            for i, order_result in enumerate(close_orders):
                if isinstance(order_result, Exception):
                    self.logger.error(f"Failed to close position on exchange {i}: {order_result}")
                else:
                    total_fees += order_result.fees_paid
            
            # Calculer le PnL final
            total_pnl = position.net_pnl  # Utiliser le PnL calculé
            
            return total_pnl, total_fees
            
        except Exception as e:
            self.logger.error(f"Error closing exchange positions: {e}")
            return position.net_pnl, position.total_fees_paid
    
    async def close_all_positions(self, reason: str = "Close all requested") -> List[str]:
        """
        Ferme toutes les positions actives
        
        Args:
            reason: Raison de la fermeture
            
        Returns:
            List des IDs des positions fermées
        """
        
        if not self.active_positions:
            return []
        
        self.logger.info(f"Closing all {len(self.active_positions)} active positions: {reason}")
        
        closed_positions = []
        
        # Fermer toutes les positions en parallèle
        close_tasks = []
        for position_id in list(self.active_positions.keys()):
            task = self.close_position(position_id, reason)
            close_tasks.append((position_id, task))
        
        # Attendre tous les résultats
        for position_id, task in close_tasks:
            try:
                success = await task
                if success:
                    closed_positions.append(position_id)
            except Exception as e:
                self.logger.error(f"Error closing position {position_id}: {e}")
        
        return closed_positions
    
    # =============================================================================
    # POSITION REPLACEMENT STRATEGY
    # =============================================================================
    
    async def consider_position_replacement(self, new_opportunity: ArbitrageOpportunity) -> Optional[Position]:
        """
        Considère remplacer une position existante par une meilleure opportunité
        
        Args:
            new_opportunity: Nouvelle opportunité détectée
            
        Returns:
            Position ouverte si remplacement effectué
        """
        
        if len(self.active_positions) < self.max_positions:
            # On a de la place, pas besoin de remplacer
            return await self.try_open_position(new_opportunity)
        
        # Trouver la position la moins performante
        worst_position = self._find_worst_position()
        
        if not worst_position:
            return None
        
        # Comparer avec la nouvelle opportunité
        replacement_score = self._calculate_replacement_score(new_opportunity, worst_position)
        
        if replacement_score > 1.5:  # Nouvelle opportunité 50% meilleure
            self.logger.info(f"Replacing position {worst_position.id} with better opportunity "
                           f"(score improvement: {replacement_score:.2f}x)")
            
            # Fermer l'ancienne position
            await self.close_position(worst_position.id, "Replaced by better opportunity")
            
            # Ouvrir la nouvelle
            return await self.try_open_position(new_opportunity)
        
        return None
    
    def _find_worst_position(self) -> Optional[Position]:
        """Trouve la position la moins performante"""
        if not self.active_positions:
            return None
        
        # Trier par score de santé (le plus bas en premier)
        sorted_positions = sorted(
            self.active_positions.values(),
            key=lambda p: p.health_score
        )
        
        return sorted_positions[0]
    
    def _calculate_replacement_score(self, new_opportunity: ArbitrageOpportunity, 
                                   existing_position: Position) -> float:
        """Calcule le score de remplacement"""
        
        # Score de la nouvelle opportunité
        new_score = new_opportunity.risk_adjusted_score
        
        # Score de la position existante (basé sur performance actuelle)
        existing_score = existing_position.health_score
        
        # Ratio d'amélioration
        if existing_score > 0:
            return new_score / existing_score
        else:
            return new_score / 10  # Éviter division par zéro
    
    # =============================================================================
    # DATA ACCESS & STATISTICS
    # =============================================================================
    
    def get_active_positions(self) -> List[Position]:
        """Récupère toutes les positions actives"""
        return list(self.active_positions.values())
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Récupère une position spécifique"""
        return self.active_positions.get(position_id)
    
    def get_positions_for_pair(self, pair_name: str) -> List[Position]:
        """Récupère les positions pour une paire spécifique"""
        return [pos for pos in self.active_positions.values() if pos.pair_name == pair_name]
    
    def get_manager_stats(self) -> Dict:
        """Récupère les statistiques du gestionnaire"""
        active_positions = list(self.active_positions.values())
        
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in active_positions)
        total_size_usd = sum(pos.size_usd for pos in active_positions)
        
        avg_age_hours = 0.0
        if active_positions:
            avg_age_hours = sum(pos.age_hours for pos in active_positions) / len(active_positions)
        
        win_rate = 0.0
        if self.total_positions_closed > 0:
            profitable_positions = len([pos for pos in self.position_history if pos.net_pnl > 0])
            win_rate = profitable_positions / self.total_positions_closed
        
        return {
            'is_running': self.is_running,
            'active_positions': len(self.active_positions),
            'max_positions': self.max_positions,
            'total_positions_opened': self.total_positions_opened,
            'total_positions_closed': self.total_positions_closed,
            'total_realized_pnl': self.total_realized_pnl,
            'total_unrealized_pnl': total_unrealized_pnl,
            'total_size_usd': total_size_usd,
            'total_fees_paid': self.total_fees_paid,
            'win_rate': win_rate,
            'avg_position_age_hours': avg_age_hours,
            'last_evaluation': self.last_evaluation
        }
    
    def get_performance_summary(self) -> Dict:
        """Récupère un résumé de performance"""
        stats = self.get_manager_stats()
        
        total_pnl = stats['total_realized_pnl'] + stats['total_unrealized_pnl']
        net_pnl = total_pnl - stats['total_fees_paid']
        
        roi_percentage = 0.0
        if stats['total_positions_opened'] > 0:
            total_invested = stats['total_positions_opened'] * self.position_size_usd
            roi_percentage = (net_pnl / total_invested) * 100
        
        return {
            'total_pnl': total_pnl,
            'net_pnl': net_pnl,
            'roi_percentage': roi_percentage,
            'win_rate': stats['win_rate'],
            'avg_position_age_hours': stats['avg_position_age_hours'],
            'positions_summary': f"{stats['active_positions']}/{stats['max_positions']} active"
        }
    
    def __repr__(self) -> str:
        return (f"PositionManager(active={len(self.active_positions)}/{self.max_positions}, "
                f"total_pnl=${self.total_realized_pnl:.2f}, "
                f"running={self.is_running})")
