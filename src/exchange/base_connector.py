"""
Base Exchange Connector - Interface commune pour tous les exchanges
==================================================================

Interface abstraite définissant les méthodes que tous les connecteurs
d'exchange doivent implémenter pour le bot d'arbitrage.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import asyncio
import logging

from ..models.exchange import (
    FundingRate, MarketData, OrderBook, Order, Trade,
    ExchangeStatus, ExchangeBalance, OrderSide, OrderType
)
from ..models.position import ExchangePosition


class ExchangeError(Exception):
    """Exception de base pour les erreurs d'exchange"""
    pass


class ConnectionError(ExchangeError):
    """Erreur de connexion à l'exchange"""
    pass


class TradingError(ExchangeError):
    """Erreur lors du trading"""
    pass


class InsufficientBalanceError(TradingError):
    """Balance insuffisante"""
    pass


class RateLimitError(ExchangeError):
    """Limite de taux d'API atteinte"""
    pass


class BaseExchangeConnector(ABC):
    """
    Interface de base pour tous les connecteurs d'exchange
    
    Définit toutes les méthodes nécessaires pour interagir avec un exchange
    dans le contexte de l'arbitrage de funding rates.
    """
    
    def __init__(self, exchange_name: str, config: Dict[str, Any]):
        """
        Initialise le connecteur
        
        Args:
            exchange_name: Nom de l'exchange (binance, kucoin, hyperliquid)
            config: Configuration spécifique à l'exchange
        """
        self.exchange_name = exchange_name.lower()
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{exchange_name}")
        
        # Status tracking
        self.is_connected = False
        self.last_ping = None
        self.connection_errors = 0
        self.rate_limit_remaining = None
        
        # Client instance (will be set by subclasses)
        self.client = None
        
        # Rate limiting
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = None
        self._request_count = 0
        self._request_window_start = datetime.now()
    
    # =============================================================================
    # CONNECTION MANAGEMENT
    # =============================================================================
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Établit la connexion à l'exchange
        
        Returns:
            bool: True si connecté avec succès
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Ferme la connexion à l'exchange"""
        pass
    
    @abstractmethod
    async def ping(self) -> bool:
        """
        Test de connectivité
        
        Returns:
            bool: True si l'exchange répond
        """
        pass
    
    async def get_status(self) -> ExchangeStatus:
        """
        Récupère le status de connexion
        
        Returns:
            ExchangeStatus: Status actuel de l'exchange
        """
        from ..models.exchange import ExchangeStatus
        
        return ExchangeStatus(
            exchange=self.exchange_name,
            is_connected=self.is_connected,
            is_trading_enabled=await self._is_trading_enabled(),
            last_ping=self.last_ping,
            connection_age_minutes=self._get_connection_age()
        )
    
    async def _is_trading_enabled(self) -> bool:
        """Vérifie si le trading est activé"""
        try:
            # Basic implementation - can be overridden
            return self.is_connected
        except Exception:
            return False
    
    def _get_connection_age(self) -> Optional[float]:
        """Calcule l'âge de la connexion en minutes"""
        if self.last_ping:
            return (datetime.now() - self.last_ping).total_seconds() / 60
        return None
    
    # =============================================================================
    # RATE LIMITING
    # =============================================================================
    
    async def _enforce_rate_limit(self) -> None:
        """Applique les limites de taux d'API"""
        async with self._rate_limit_lock:
            now = datetime.now()
            
            # Reset counter every minute
            if (now - self._request_window_start).seconds >= 60:
                self._request_count = 0
                self._request_window_start = now
            
            # Check if we're hitting the limit
            max_requests = self.config.get('rate_limit_per_minute', 60)
            if self._request_count >= max_requests:
                sleep_time = 60 - (now - self._request_window_start).seconds
                if sleep_time > 0:
                    self.logger.warning(f"Rate limit reached, sleeping {sleep_time}s")
                    await asyncio.sleep(sleep_time)
                    self._request_count = 0
                    self._request_window_start = datetime.now()
            
            self._request_count += 1
            self._last_request_time = now
    
    # =============================================================================
    # MARKET DATA
    # =============================================================================
    
    @abstractmethod
    async def get_funding_rate(self, symbol: str) -> FundingRate:
        """
        Récupère le funding rate actuel
        
        Args:
            symbol: Symbol du token (ex: "BTC/USDT")
            
        Returns:
            FundingRate: Funding rate actuel
        """
        pass
    
    @abstractmethod
    async def get_funding_rates(self, symbols: List[str]) -> Dict[str, FundingRate]:
        """
        Récupère les funding rates pour plusieurs symbols
        
        Args:
            symbols: Liste des symbols
            
        Returns:
            Dict mapping symbol -> FundingRate
        """
        pass
    
    @abstractmethod
    async def get_next_funding_time(self, symbol: str) -> Optional[datetime]:
        """
        Récupère l'heure du prochain funding
        
        Args:
            symbol: Symbol du token
            
        Returns:
            datetime ou None si pas disponible
        """
        pass
    
    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketData:
        """
        Récupère les données de marché
        
        Args:
            symbol: Symbol du token
            
        Returns:
            MarketData: Données de marché actuelles
        """
        pass
    
    async def get_order_book(self, symbol: str, limit: int = 20) -> Optional[OrderBook]:
        """
        Récupère le carnet d'ordres (optionnel)
        
        Args:
            symbol: Symbol du token
            limit: Nombre de niveaux à récupérer
            
        Returns:
            OrderBook ou None si pas supporté
        """
        # Default implementation returns None
        # Can be overridden by exchanges that support it
        return None
    
    # =============================================================================
    # TRADING OPERATIONS
    # =============================================================================
    
    @abstractmethod
    async def place_market_order(self, symbol: str, side: OrderSide, 
                                amount: float, **kwargs) -> Order:
        """
        Place un ordre au marché
        
        Args:
            symbol: Symbol du token
            side: BUY ou SELL
            amount: Quantité à trader
            **kwargs: Paramètres supplémentaires
            
        Returns:
            Order: Ordre créé
        """
        pass
    
    @abstractmethod
    async def place_limit_order(self, symbol: str, side: OrderSide,
                               amount: float, price: float, **kwargs) -> Order:
        """
        Place un ordre à cours limité
        
        Args:
            symbol: Symbol du token
            side: BUY ou SELL
            amount: Quantité à trader
            price: Prix limite
            **kwargs: Paramètres supplémentaires
            
        Returns:
            Order: Ordre créé
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Annule un ordre
        
        Args:
            order_id: ID de l'ordre
            symbol: Symbol du token
            
        Returns:
            bool: True si annulé avec succès
        """
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """
        Récupère les détails d'un ordre
        
        Args:
            order_id: ID de l'ordre
            symbol: Symbol du token
            
        Returns:
            Order ou None si pas trouvé
        """
        pass
    
    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Récupère les ordres ouverts
        
        Args:
            symbol: Symbol spécifique ou None pour tous
            
        Returns:
            List[Order]: Liste des ordres ouverts
        """
        pass
    
    # =============================================================================
    # POSITION MANAGEMENT
    # =============================================================================
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[ExchangePosition]:
        """
        Récupère la position actuelle
        
        Args:
            symbol: Symbol du token
            
        Returns:
            ExchangePosition ou None si pas de position
        """
        pass
    
    @abstractmethod
    async def get_all_positions(self) -> List[ExchangePosition]:
        """
        Récupère toutes les positions
        
        Returns:
            List[ExchangePosition]: Liste des positions
        """
        pass
    
    @abstractmethod
    async def close_position(self, symbol: str, **kwargs) -> Order:
        """
        Ferme une position
        
        Args:
            symbol: Symbol du token
            **kwargs: Paramètres supplémentaires
            
        Returns:
            Order: Ordre de fermeture
        """
        pass
    
    # =============================================================================
    # ACCOUNT INFORMATION
    # =============================================================================
    
    @abstractmethod
    async def get_balance(self, asset: str = "USDT") -> ExchangeBalance:
        """
        Récupère la balance d'un asset
        
        Args:
            asset: Asset à vérifier (défaut: USDT)
            
        Returns:
            ExchangeBalance: Balance de l'asset
        """
        pass
    
    @abstractmethod
    async def get_all_balances(self) -> Dict[str, ExchangeBalance]:
        """
        Récupère toutes les balances
        
        Returns:
            Dict mapping asset -> ExchangeBalance
        """
        pass
    
    async def get_available_balance_usd(self) -> float:
        """
        Récupère la balance disponible en USD
        
        Returns:
            float: Balance disponible en USD
        """
        try:
            usdt_balance = await self.get_balance("USDT")
            return usdt_balance.available
        except Exception as e:
            self.logger.error(f"Error getting USD balance: {e}")
            return 0.0
    
    # =============================================================================
    # TRADE HISTORY
    # =============================================================================
    
    async def get_recent_trades(self, symbol: str, limit: int = 50) -> List[Trade]:
        """
        Récupère l'historique des trades récents (optionnel)
        
        Args:
            symbol: Symbol du token
            limit: Nombre de trades à récupérer
            
        Returns:
            List[Trade]: Liste des trades récents
        """
        # Default implementation returns empty list
        # Can be overridden by exchanges that support it
        return []
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def format_symbol(self, token: str, quote: str = "USDT") -> str:
        """
        Formate un symbol selon les conventions de l'exchange
        
        Args:
            token: Token de base (ex: "BTC")
            quote: Token de quote (défaut: "USDT")
            
        Returns:
            str: Symbol formaté
        """
        # Default format: TOKEN/QUOTE
        # Can be overridden by exchanges with different formats
        return f"{token.upper()}/{quote.upper()}"
    
    def parse_symbol(self, symbol: str) -> tuple[str, str]:
        """
        Parse un symbol en token de base et quote
        
        Args:
            symbol: Symbol à parser (ex: "BTC/USDT")
            
        Returns:
            tuple: (base_token, quote_token)
        """
        if '/' in symbol:
            return tuple(symbol.split('/'))
        else:
            # Assume USDT if no separator
            return symbol, "USDT"
    
    async def validate_trading_requirements(self, symbol: str, 
                                          side: OrderSide, amount: float) -> bool:
        """
        Valide les prérequis pour un trade
        
        Args:
            symbol: Symbol du token
            side: Côté de l'ordre
            amount: Quantité
            
        Returns:
            bool: True si le trade peut être exécuté
        """
        try:
            # Check connection
            if not self.is_connected:
                return False
            
            # Check balance (simplified)
            balance = await self.get_available_balance_usd()
            market_data = await self.get_market_data(symbol)
            
            if market_data.last_price:
                required_balance = amount * market_data.last_price
                if balance < required_balance:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating trading requirements: {e}")
            return False
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(exchange='{self.exchange_name}', connected={self.is_connected})"
    
    # =============================================================================
    # CONTEXT MANAGER SUPPORT
    # =============================================================================
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
