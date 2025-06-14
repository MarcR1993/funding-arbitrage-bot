#!/usr/bin/env python3
"""
Funding Rate Arbitrage Bot - Main Entry Point
=============================================

Point d'entrée principal du bot d'arbitrage de funding rates.
Supporte plusieurs modes d'exécution et options de ligne de commande.
"""

import sys
import os
import asyncio
import argparse
import logging
from pathlib import Path
from typing import Optional

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot.arbitrage_engine import ArbitrageEngine, EngineState
from src.models.config import FundingBotConfig, create_config, BotMode
from src.ui.cli_interface import FundingBotCLI


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configure le système de logging
    
    Args:
        log_level: Niveau de log (DEBUG, INFO, WARNING, ERROR)
        log_file: Fichier de log (optionnel)
    """
    
    # Format des logs
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Configuration de base
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[]
    )
    
    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Handler fichier si spécifié
    if log_file:
        # Créer le dossier logs s'il n'existe pas
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)
    
    # Ajouter le handler console
    logging.getLogger().addHandler(console_handler)
    
    # Réduire le niveau de log pour les librairies externes
    logging.getLogger("ccxt").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def parse_arguments() -> argparse.Namespace:
    """Parse les arguments de ligne de commande"""
    
    parser = argparse.ArgumentParser(
        description="Funding Rate Arbitrage Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Launch interactive CLI
  %(prog)s --mode cli               # Launch interactive CLI  
  %(prog)s --mode headless          # Run bot in headless mode
  %(prog)s --mode paper-trading     # Run in paper trading mode
  %(prog)s --config my_config.yaml  # Use custom config file
  %(prog)s --log-level DEBUG        # Enable debug logging
        """
    )
    
    # Mode d'exécution
    parser.add_argument(
        "--mode",
        choices=["cli", "headless", "paper-trading", "backtest"],
        default="cli",
        help="Execution mode (default: cli)"
    )
    
    # Configuration
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Configuration file path (default: config/config.yaml)"
    )
    
    # Logging
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--log-file",
        type=str,
        help="Log file path (default: logs to console)"
    )
    
    # Bot parameters
    parser.add_argument(
        "--position-size",
        type=float,
        help="Override position size in USD"
    )
    
    parser.add_argument(
        "--max-positions",
        type=int,
        help="Override maximum concurrent positions"
    )
    
    parser.add_argument(
        "--tokens",
        type=str,
        nargs="+",
        help="Override trading tokens (e.g., --tokens BTC ETH SOL)"
    )
    
    # Actions
    parser.add_argument(
        "--test-connections",
        action="store_true",
        help="Test exchange connections and exit"
    )
    
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate configuration and exit"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Funding Arbitrage Bot v1.0.0"
    )
    
    return parser.parse_args()


def load_and_validate_config(config_path: str, args: argparse.Namespace) -> FundingBotConfig:
    """
    Charge et valide la configuration
    
    Args:
        config_path: Chemin vers le fichier de configuration
        args: Arguments de ligne de commande
        
    Returns:
        Configuration validée
    """
    
    try:
        # Charger la configuration
        config = create_config(config_path, env_override=True)
        
        # Appliquer les overrides de ligne de commande
        if args.position_size:
            config.trading.position_size_usd = args.position_size
            
        if args.max_positions:
            config.trading.max_concurrent_positions = args.max_positions
            
        if args.tokens:
            config.trading.tokens = [token.upper() for token in args.tokens]
        
        # Ajuster le mode selon les arguments
        if args.mode == "paper-trading":
            config.bot.mode = BotMode.PAPER_TRADING
        elif args.mode == "backtest":
            config.bot.mode = BotMode.BACKTEST
        
        # Ajuster le niveau de log
        config.bot.log_level = args.log_level
        
        print(f"✅ Configuration loaded from {config_path}")
        
        return config
        
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        print(f"💡 Make sure {config_path} exists and is valid")
        sys.exit(1)


async def test_connections_mode(config: FundingBotConfig) -> None:
    """Mode test des connexions"""
    
    print("🔗 Testing exchange connections...")
    
    try:
        engine = ArbitrageEngine(config)
        
        # Initialiser
        success = await engine.initialize()
        
        if not success:
            print("❌ Failed to initialize engine")
            return
        
        # Tester les connexions
        connected = await engine._test_all_connections()
        
        print(f"\n📊 Connection Results:")
        for exchange_name, connector in engine.connectors.items():
            status = "✅ Connected" if exchange_name in connected else "❌ Failed"
            print(f"  {exchange_name.title()}: {status}")
        
        # Nettoyer
        await engine.stop()
        
        if len(connected) >= 2:
            print(f"\n✅ Connection test successful ({len(connected)} exchanges connected)")
        else:
            print(f"\n❌ Connection test failed (need at least 2 exchanges)")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Connection test error: {e}")
        sys.exit(1)


async def headless_mode(config: FundingBotConfig) -> None:
    """Mode headless (sans interface)"""
    
    print("🤖 Starting Funding Arbitrage Bot in headless mode...")
    
    try:
        # Créer et initialiser le moteur
        engine = ArbitrageEngine(config)
        
        print("🔧 Initializing engine...")
        success = await engine.initialize()
        
        if not success:
            print("❌ Failed to initialize engine")
            sys.exit(1)
        
        print("🚀 Starting trading engine...")
        success = await engine.start()
        
        if not success:
            print("❌ Failed to start engine")
            sys.exit(1)
        
        print("✅ Bot started successfully!")
        print("💡 Press Ctrl+C to stop the bot")
        
        # Boucle principale - attendre indéfiniment
        try:
            while engine.state == EngineState.RUNNING:
                await asyncio.sleep(10)
                
                # Log périodique du statut
                if engine.total_cycles % 60 == 0:  # Toutes les 10 minutes environ
                    status = engine.get_engine_status()
                    print(f"📊 Status: {status['positions'].get('active_positions', 0)} positions, "
                          f"{status['oracle'].get('current_opportunities', 0)} opportunities, "
                          f"{status['engine']['total_cycles']} cycles")
        
        except KeyboardInterrupt:
            print("\n🛑 Stopping bot...")
            await engine.stop()
            print("✅ Bot stopped successfully")
            
    except Exception as e:
        print(f"❌ Error in headless mode: {e}")
        sys.exit(1)


async def paper_trading_mode(config: FundingBotConfig) -> None:
    """Mode paper trading"""
    
    print("📄 Starting in Paper Trading mode...")
    print("💡 No real trades will be executed")
    
    # Modifier la config pour paper trading
    config.bot.mode = BotMode.PAPER_TRADING
    
    # Lancer en mode headless
    await headless_mode(config)


async def cli_mode(config: FundingBotConfig) -> None:
    """Mode interface CLI interactive"""
    
    print("🎮 Starting interactive CLI...")
    
    try:
        cli = FundingBotCLI()
        cli.config = config  # Passer la config préchargée
        await cli.run()
        
    except Exception as e:
        print(f"❌ CLI error: {e}")
        sys.exit(1)


def validate_config_mode(config: FundingBotConfig) -> None:
    """Mode validation de configuration"""
    
    print("✅ Configuration validation passed!")
    print(f"📊 Trading tokens: {', '.join(config.trading.tokens)}")
    print(f"💰 Position size: ${config.trading.position_size_usd}")
    print(f"📈 Max positions: {config.trading.max_concurrent_positions}")
    print(f"🏛️ Enabled exchanges: {', '.join(config.get_enabled_exchanges())}")


def check_prerequisites() -> None:
    """Vérifie les prérequis avant le démarrage"""
    
    # Vérifier Python version
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required")
        sys.exit(1)
    
    # Créer les dossiers nécessaires
    directories = ["data/logs", "data/backtest_results", "data/positions_history", "config"]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Vérifier les variables d'environnement critiques
    required_env_vars = []
    missing_vars = []
    
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️ Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("💡 Set these in your .env file or environment")


async def main() -> None:
    """Point d'entrée principal"""
    
    # Parser les arguments
    args = parse_arguments()
    
    # Vérifier les prérequis
    check_prerequisites()
    
    # Configurer le logging
    log_file = args.log_file or f"data/logs/bot_{args.mode}.log"
    setup_logging(args.log_level, log_file)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting Funding Arbitrage Bot in {args.mode} mode")
    
    # Charger la configuration
    config = load_and_validate_config(args.config, args)
    
    # Mode validation seulement
    if args.validate_config:
        validate_config_mode(config)
        return
    
    # Mode test connexions seulement
    if args.test_connections:
        await test_connections_mode(config)
        return
    
    # Exécuter selon le mode
    try:
        if args.mode == "cli":
            await cli_mode(config)
        elif args.mode == "headless":
            await headless_mode(config)
        elif args.mode == "paper-trading":
            await paper_trading_mode(config)
        elif args.mode == "backtest":
            print("🔄 Backtest mode not yet implemented")
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"💥 Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Configuration pour Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Lancer le main
    asyncio.run(main())
