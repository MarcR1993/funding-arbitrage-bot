"""
Configuration Models - Modèles de configuration avec validation Pydantic
========================================================================

Modèles pour gérer la configuration du bot avec validation automatique,
valeurs par défaut et documentation intégrée.
"""

from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum
import os


class BotMode(str, Enum):
    """Modes de fonctionnement du bot"""
    PRODUCTION = "production"
    SANDBOX = "sandbox"
    PAPER_TRADING = "paper_trading"
    BACKTEST = "backtest"
    DEVELOPMENT = "development"


class LogLevel(str, Enum):
    """Niveaux de logging"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ExchangeName(str, Enum):
    """Exchanges supportés"""
    BINANCE = "binance"
    KUCOIN = "kucoin"
    HYPERLIQUID = "hyperliquid"


# =============================================================================
# BOT CONFIGURATION
# =============================================================================

class BotConfig(BaseModel):
    """Configuration générale du bot"""
    
    name: str = Field(default="FundingArbitrageBot", description="Nom du bot")
    version: str = Field(default="1.0.0", description="Version du bot")
    mode: BotMode = Field(default=BotMode.PRODUCTION, description="Mode de fonctionnement")
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Niveau de logging")
    
    evaluation_interval_seconds: int = Field(
        default=300, 
        ge=30, 
        le=3600,
        description="Intervalle d'évaluation en secondes (30s-1h)"
    )
    
    health_check_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Intervalle de health check en secondes"
    )
    
    metrics_update_interval_seconds: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Intervalle de mise à jour des métriques"
    )
    
    class Config:
        use_enum_values = True


# =============================================================================
# TRADING CONFIGURATION
# =============================================================================

class TradingPair(BaseModel):
    """Configuration d'une paire de trading"""
    
    name: str = Field(..., description="Nom de la paire (ex: binance_kucoin)")
    priority: int = Field(default=1, ge=1, le=10, description="Priorité (1=max)")
    description: str = Field(default="", description="Description de la paire")
    enabled: bool = Field(default=True, description="Paire activée")
    
    @validator('name')
    def validate_pair_name(cls, v):
        """Valide le format du nom de paire"""
        valid_exchanges = ["binance", "kucoin", "hyperliquid"]
        parts = v.lower().split('_')
        
        if len(parts) != 2:
            raise ValueError("Format: exchange1_exchange2")
        
        if not all(part in valid_exchanges for part in parts):
            raise ValueError(f"Exchanges supportés: {valid_exchanges}")
        
        if parts[0] == parts[1]:
            raise ValueError("Les deux exchanges doivent être différents")
        
        return v.lower()


class TradingConfig(BaseModel):
    """Configuration du trading"""
    
    tokens: List[str] = Field(
        default=["BTC", "ETH", "SOL", "AVAX", "ATOM"],
        min_items=1,
        max_items=20,
        description="Liste des tokens à trader"
    )
    
    position_size_usd: float = Field(
        default=1000.0,
        gt=0,
        le=100000,
        description="Taille des positions en USD"
    )
    
    max_concurrent_positions: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Nombre maximum de positions simultanées"
    )
    
    min_spread_threshold: float = Field(
        default=0.0005,
        gt=0,
        le=0.01,
        description="Seuil minimum de spread (0.05% par défaut)"
    )
    
    max_leverage: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Leverage maximum autorisé"
    )
    
    supported_pairs: List[TradingPair] = Field(
        default_factory=lambda: [
            TradingPair(name="binance_kucoin", priority=1, description="8h vs 8h décalés"),
            TradingPair(name="binance_hyperliquid", priority=2, description="8h vs 1h"),
            TradingPair(name="kucoin_hyperliquid", priority=3, description="8h vs 1h")
        ],
        description="Paires de trading supportées"
    )
    
    @validator('tokens')
    def validate_tokens(cls, v):
        """Valide la liste des tokens"""
        # Convert to uppercase
        v = [token.upper() for token in v]
        
        # Remove duplicates
        v = list(set(v))
        
        # Validate format (basic check)
        for token in v:
            if not token.isalpha() or len(token) < 2 or len(token) > 10:
                raise ValueError(f"Token invalide: {token}")
        
        return v


# =============================================================================
# RISK MANAGEMENT
# =============================================================================

class RiskManagementConfig(BaseModel):
    """Configuration de la gestion des risques"""
    
    # Profit/Loss limits
    stop_loss_threshold: float = Field(
        default=-0.005,
        ge=-0.1,
        le=0,
        description="Seuil de stop loss (-0.5% par défaut)"
    )
    
    min_profit_threshold: float = Field(
        default=0.0002,
        gt=0,
        le=0.01,
        description="Seuil minimum de profit pour maintenir ouvert"
    )
    
    target_daily_profit: float = Field(
        default=0.02,
        gt=0,
        le=0.5,
        description="Objectif de profit quotidien (2% par défaut)"
    )
    
    max_daily_loss: float = Field(
        default=-0.01,
        ge=-0.1,
        le=0,
        description="Perte quotidienne maximum (-1% par défaut)"
    )
    
    # Position limits
    max_position_age_hours: int = Field(
        default=672,  # 4 weeks
        ge=1,
        le=8760,  # 1 year
        description="Âge maximum des positions en heures"
    )
    
    emergency_close_threshold: float = Field(
        default=-0.02,
        ge=-0.1,
        le=0,
        description="Seuil de fermeture d'urgence totale"
    )
    
    max_positions_per_exchange: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Positions maximum par exchange"
    )
    
    # Spread monitoring
    spread_warning_threshold: float = Field(
        default=0.0001,
        gt=0,
        le=0.001,
        description="Seuil d'alerte pour spread faible"
    )
    
    spread_critical_threshold: float = Field(
        default=-0.0001,
        ge=-0.001,
        le=0,
        description="Seuil critique pour spread négatif"
    )
    
    @root_validator
    def validate_thresholds(cls, values):
        """Valide la cohérence des seuils"""
        stop_loss = values.get('stop_loss_threshold', -0.005)
        emergency = values.get('emergency_close_threshold', -0.02)
        
        if stop_loss <= emergency:
            raise ValueError("Stop loss doit être > emergency threshold")
        
        min_profit = values.get('min_profit_threshold', 0.0002)
        target_profit = values.get('target_daily_profit', 0.02)
        
        if min_profit >= target_profit:
            raise ValueError("Min profit doit être < target daily profit")
        
        return values


# =============================================================================
# EXCHANGE CONFIGURATION
# =============================================================================

class ExchangeConfig(BaseModel):
    """Configuration d'un exchange"""
    
    enabled: bool = Field(default=True, description="Exchange activé")
    name: str = Field(..., description="Nom de l'exchange")
    testnet: bool = Field(default=False, description="Mode testnet")
    sandbox: bool = Field(default=False, description="Mode sandbox")
    max_positions: int = Field(default=2, ge=0, le=10, description="Positions max sur cet exchange")
    
    # Funding specific
    funding_frequency_hours: int = Field(
        default=8, 
        ge=1, 
        le=24,
        description="Fréquence des funding en heures"
    )
    
    funding_times_utc: List[str] = Field(
        default_factory=list,
        description="Heures de funding UTC (format HH:MM)"
    )
    
    # API limits
    rate_limit_requests_per_minute: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Limite de requêtes par minute"
    )
    
    max_order_size_usd: float = Field(
        default=10000,
        gt=0,
        le=1000000,
        description="Taille d'ordre maximum en USD"
    )
    
    # Configuration CCXT
    ccxt_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration spécifique CCXT"
    )
    
    @validator('funding_times_utc')
    def validate_funding_times(cls, v):
        """Valide le format des heures de funding"""
        for time_str in v:
            try:
                parts = time_str.split(':')
                if len(parts) != 2:
                    raise ValueError()
                hour, minute = int(parts[0]), int(parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError()
            except (ValueError, IndexError):
                raise ValueError(f"Format invalide pour {time_str}, utilisez HH:MM")
        return v


class HyperliquidConfig(ExchangeConfig):
    """Configuration spécifique pour Hyperliquid"""
    
    use_vault: bool = Field(default=True, description="Utiliser un vault")
    vault_config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "auto_approve_orders": True,
            "max_slippage_bps": 10
        },
        description="Configuration du vault"
    )


class ExchangesConfig(BaseModel):
    """Configuration de tous les exchanges"""
    
    binance: ExchangeConfig = Field(
        default_factory=lambda: ExchangeConfig(
            name="Binance Futures",
            funding_frequency_hours=8,
            funding_times_utc=["00:00", "08:00", "16:00"],
            ccxt_config={"defaultType": "future"}
        )
    )
    
    kucoin: ExchangeConfig = Field(
        default_factory=lambda: ExchangeConfig(
            name="KuCoin Futures",
            funding_frequency_hours=8,
            funding_times_utc=["04:00", "12:00", "20:00"],
            ccxt_config={"defaultType": "future"}
        )
    )
    
    hyperliquid: HyperliquidConfig = Field(
        default_factory=lambda: HyperliquidConfig(
            name="Hyperliquid",
            funding_frequency_hours=1
        )
    )


# =============================================================================
# MONITORING & NOTIFICATIONS
# =============================================================================

class AlertConfig(BaseModel):
    """Configuration des alertes"""
    
    position_opened: bool = Field(default=True, description="Alerte ouverture position")
    position_closed: bool = Field(default=True, description="Alerte fermeture position")
    profit_target_reached: bool = Field(default=True, description="Objectif de profit atteint")
    stop_loss_triggered: bool = Field(default=True, description="Stop loss déclenché")
    daily_summary: bool = Field(default=True, description="Résumé quotidien")
    error_alerts: bool = Field(default=True, description="Alertes d'erreur")


class TelegramConfig(BaseModel):
    """Configuration Telegram"""
    
    enabled: bool = Field(default=False, description="Notifications Telegram activées")
    alerts: AlertConfig = Field(default_factory=AlertConfig)
    daily_report_time_utc: str = Field(
        default="09:00",
        description="Heure du rapport quotidien UTC"
    )
    
    @validator('daily_report_time_utc')
    def validate_report_time(cls, v):
        """Valide l'heure du rapport"""
        try:
            parts = v.split(':')
            if len(parts) != 2:
                raise ValueError()
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError()
        except (ValueError, IndexError):
            raise ValueError(f"Format invalide: {v}, utilisez HH:MM")
        return v


class MonitoringConfig(BaseModel):
    """Configuration du monitoring"""
    
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    
    discord: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": False,
            "alerts": {"position_opened": True, "daily_summary": True}
        }
    )
    
    email: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": False,
            "smtp_config": {
                "server": "smtp.gmail.com",
                "port": 587,
                "use_tls": True
            },
            "alerts": {"daily_summary": True, "emergency_stop": True}
        }
    )
    
    prometheus: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": False,
            "port": 8000,
            "metrics_prefix": "funding_bot"
        }
    )
    
    health_check: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": True,
            "port": 8080,
            "endpoint": "/health"
        }
    )


# =============================================================================
# CONFIGURATION PRINCIPALE
# =============================================================================

class FundingBotConfig(BaseModel):
    """Configuration complète du bot"""
    
    bot: BotConfig = Field(default_factory=BotConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    risk_management: RiskManagementConfig = Field(default_factory=RiskManagementConfig)
    exchanges: ExchangesConfig = Field(default_factory=ExchangesConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    # Additional configs
    logging: Dict[str, Any] = Field(
        default_factory=lambda: {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "files": {
                "main_log": "data/logs/bot.log",
                "error_log": "data/logs/error.log",
                "trading_log": "data/logs/trading.log"
            },
            "rotation": {"max_size_mb": 100, "backup_count": 10},
            "structured_logging": True
        }
    )
    
    database: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "sqlite",
            "sqlite": {"path": "data/bot_database.db"},
            "tables": {
                "positions": True,
                "trades": True,
                "funding_rates": True,
                "performance_metrics": True
            }
        }
    )
    
    security: Dict[str, Any] = Field(
        default_factory=lambda: {
            "encryption": {"enabled": True},
            "audit_logging": True,
            "max_daily_trades": 100,
            "max_position_size_usd": 50000
        }
    )
    
    @root_validator
    def validate_config_consistency(cls, values):
        """Valide la cohérence globale de la configuration"""
        trading = values.get('trading')
        risk = values.get('risk_management')
        
        if trading and risk:
            # Vérifier que position_size <= max_position_size
            pos_size = trading.position_size_usd
            max_size = values.get('security', {}).get('max_position_size_usd', 50000)
            
            if pos_size > max_size:
                raise ValueError(f"Position size ({pos_size}) > max allowed ({max_size})")
        
        return values
    
    def get_exchange_config(self, exchange_name: str) -> Optional[ExchangeConfig]:
        """Récupère la configuration d'un exchange"""
        return getattr(self.exchanges, exchange_name.lower(), None)
    
    def is_exchange_enabled(self, exchange_name: str) -> bool:
        """Vérifie si un exchange est activé"""
        config = self.get_exchange_config(exchange_name)
        return config.enabled if config else False
    
    def get_enabled_exchanges(self) -> List[str]:
        """Retourne la liste des exchanges activés"""
        enabled = []
        for exchange_name in ['binance', 'kucoin', 'hyperliquid']:
            if self.is_exchange_enabled(exchange_name):
                enabled.append(exchange_name)
        return enabled
    
    def get_trading_pairs(self) -> List[TradingPair]:
        """Retourne les paires de trading activées et triées par priorité"""
        enabled_exchanges = set(self.get_enabled_exchanges())
        
        valid_pairs = []
        for pair in self.trading.supported_pairs:
            if not pair.enabled:
                continue
                
            # Check if both exchanges in pair are enabled
            exchanges = pair.name.split('_')
            if all(ex in enabled_exchanges for ex in exchanges):
                valid_pairs.append(pair)
        
        # Sort by priority
        return sorted(valid_pairs, key=lambda x: x.priority)


# =============================================================================
# CONFIGURATION LOADER
# =============================================================================

def load_config_from_env() -> Dict[str, Any]:
    """Charge la configuration depuis les variables d'environnement"""
    config = {}
    
    # Bot config
    if os.getenv('BOT_MODE'):
        config['bot'] = {'mode': os.getenv('BOT_MODE')}
    
    if os.getenv('LOG_LEVEL'):
        config.setdefault('bot', {})['log_level'] = os.getenv('LOG_LEVEL')
    
    # Trading config
    if os.getenv('MAX_POSITION_SIZE_USD'):
        config['trading'] = {
            'position_size_usd': float(os.getenv('MAX_POSITION_SIZE_USD'))
        }
    
    if os.getenv('TRADING_TOKENS'):
        tokens = os.getenv('TRADING_TOKENS').split(',')
        config.setdefault('trading', {})['tokens'] = [t.strip() for t in tokens]
    
    # Risk management
    risk_vars = {
        'STOP_LOSS_THRESHOLD': 'stop_loss_threshold',
        'MIN_PROFIT_THRESHOLD': 'min_profit_threshold',
        'TARGET_DAILY_PROFIT': 'target_daily_profit',
        'MAX_POSITION_AGE_HOURS': 'max_position_age_hours'
    }
    
    risk_config = {}
    for env_var, config_key in risk_vars.items():
        if os.getenv(env_var):
            value = os.getenv(env_var)
            risk_config[config_key] = float(value) if '.' in value else int(value)
    
    if risk_config:
        config['risk_management'] = risk_config
    
    # Exchanges
    exchanges_config = {}
    
    # Binance
    if os.getenv('BINANCE_API_KEY'):
        exchanges_config['binance'] = {
            'testnet': os.getenv('BINANCE_TESTNET', 'false').lower() == 'true'
        }
    
    # KuCoin
    if os.getenv('KUCOIN_API_KEY'):
        exchanges_config['kucoin'] = {
            'sandbox': os.getenv('KUCOIN_SANDBOX', 'false').lower() == 'true'
        }
    
    # Hyperliquid
    if os.getenv('HYPERLIQUID_PRIVATE_KEY'):
        exchanges_config['hyperliquid'] = {
            'testnet': os.getenv('HYPERLIQUID_TESTNET', 'false').lower() == 'true'
        }
    
    if exchanges_config:
        config['exchanges'] = exchanges_config
    
    # Monitoring
    if os.getenv('TELEGRAM_ENABLED'):
        config['monitoring'] = {
            'telegram': {
                'enabled': os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true'
            }
        }
    
    return config


def create_config(config_file: Optional[str] = None, 
                 env_override: bool = True) -> FundingBotConfig:
    """
    Crée une configuration complète
    
    Args:
        config_file: Chemin vers le fichier YAML de configuration
        env_override: Si True, les variables d'env surchargent le fichier
    """
    import yaml
    
    # Start with defaults
    config_dict = {}
    
    # Load from file if provided
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            file_config = yaml.safe_load(f)
            if file_config:
                config_dict.update(file_config)
    
    # Override with environment variables
    if env_override:
        env_config = load_config_from_env()
        # Deep merge env config
        for key, value in env_config.items():
            if key in config_dict and isinstance(config_dict[key], dict) and isinstance(value, dict):
                config_dict[key].update(value)
            else:
                config_dict[key] = value
    
    # Create and validate config
    return FundingBotConfig(**config_dict)
