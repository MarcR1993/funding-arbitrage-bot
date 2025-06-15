
"""
Configuration management system.
Attribution: Inspired by Hummingbot's configuration system (Apache 2.0)
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from decimal import Decimal


def load_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_file: Path to config file. If None, uses default locations.
    
    Returns:
        Dictionary containing configuration
    """
    
    logger = logging.getLogger("config")
    
    # Default config file locations
    default_locations = [
        config_file,
        "config.yaml",
        "conf/config.yaml",
        os.path.expanduser("~/.funding-arbitrage-bot/config.yaml")
    ]
    
    config_path = None
    for location in default_locations:
        if location and os.path.exists(location):
            config_path = location
            break
    
    if not config_path:
        logger.warning("No config file found, using default configuration")
        return get_default_config()
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Loaded configuration from {config_path}")
        
        # Validate and fill in defaults
        config = validate_and_fill_defaults(config)
        
        return config
        
    except Exception as e:
        logger.error(f"Error loading config from {config_path}: {e}")
        logger.info("Using default configuration")
        return get_default_config()


def save_config(config: Dict[str, Any], config_file: str = "config.yaml"):
    """Save configuration to YAML file"""
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(config_file) or ".", exist_ok=True)
        
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
        
        logging.getLogger("config").info(f"Configuration saved to {config_file}")
        
    except Exception as e:
        logging.getLogger("config").error(f"Error saving config: {e}")


def get_default_config() -> Dict[str, Any]:
    """Get default configuration"""
    
    return {
        "exchanges": {
            "binance": {
                "enabled": False,
                "sandbox": True,
                "credentials": {
                    "api_key": "",
                    "api_secret": ""
                }
            },
            "bybit": {
                "enabled": False,
                "sandbox": True,
                "credentials": {
                    "api_key": "",
                    "api_secret": ""
                }
            },
            "hyperliquid": {
                "enabled": False,
                "sandbox": True,
                "credentials": {
                    "api_key": "",
                    "api_secret": ""
                }
            },
            "kucoin": {
                "enabled": False,
                "sandbox": True,
                "credentials": {
                    "api_key": "",
                    "api_secret": "",
                    "passphrase": ""
                }
            }
        },
        "strategy": {
            "min_profit_threshold": "0.0005",  # 0.05%
            "max_position_size_usd": "1000",
            "max_exposure_per_exchange": "5000",
            "max_active_positions": 5,
            "funding_buffer_minutes": 30,
            "enable_auto_trading": False,
            "trading_pairs": [
                "BTC-USDT",
                "ETH-USDT"
            ]
        },
        "logging": {
            "level": "INFO",
            "file": "logs/bot.log"
        },
        "dashboard": {
            "enabled": True,
            "port": 8501,
            "host": "0.0.0.0"
        }
    }


def validate_and_fill_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate configuration and fill in missing defaults"""
    
    default_config = get_default_config()
    
    # Fill in missing sections
    for section, default_section in default_config.items():
        if section not in config:
            config[section] = default_section
        elif isinstance(default_section, dict):
            # Fill in missing keys within sections
            for key, default_value in default_section.items():
                if key not in config[section]:
                    config[section][key] = default_value
                elif isinstance(default_value, dict):
                    # Handle nested dictionaries
                    for nested_key, nested_default in default_value.items():
                        if nested_key not in config[section][key]:
                            config[section][key][nested_key] = nested_default
    
    # Validate strategy configuration
    strategy_config = config.get("strategy", {})
    
    # Convert string numbers to Decimal for precision
    decimal_fields = ["min_profit_threshold", "max_position_size_usd", "max_exposure_per_exchange"]
    for field in decimal_fields:
        if field in strategy_config:
            try:
                strategy_config[field] = str(Decimal(str(strategy_config[field])))
            except:
                logging.getLogger("config").warning(f"Invalid {field}, using default")
                strategy_config[field] = default_config["strategy"][field]
    
    # Validate exchange credentials
    exchanges_config = config.get("exchanges", {})
    for exchange_name, exchange_config in exchanges_config.items():
        if exchange_config.get("enabled", False):
            credentials = exchange_config.get("credentials", {})
            
            # Check required credentials
            required_fields = get_required_credentials(exchange_name)
            for field in required_fields:
                if not credentials.get(field):
                    logging.getLogger("config").warning(
                        f"Missing {field} for {exchange_name}. Exchange will be disabled."
                    )
                    exchange_config["enabled"] = False
    
    return config


def get_required_credentials(exchange: str) -> list:
    """Get required credential fields for an exchange"""
    
    credential_requirements = {
        "binance": ["api_key", "api_secret"],
        "bybit": ["api_key", "api_secret"],
        "hyperliquid": ["api_key", "api_secret"],
        "kucoin": ["api_key", "api_secret", "passphrase"]
    }
    
    return credential_requirements.get(exchange, [])


def create_sample_config(filename: str = "config.sample.yaml"):
    """Create a sample configuration file"""
    
    config = get_default_config()
    
    # Add comments to the sample config
    sample_content = """# Funding Rate Arbitrage Bot Configuration
# Copy this file to config.yaml and update with your settings

# Exchange Configuration
exchanges:
  binance:
    enabled: false  # Set to true to enable
    sandbox: true   # Use testnet for testing
    credentials:
      api_key: "your_binance_api_key"
      api_secret: "your_binance_secret"
  
  bybit:
    enabled: false
    sandbox: true
    credentials:
      api_key: "your_bybit_api_key"
      api_secret: "your_bybit_secret"
  
  hyperliquid:
    enabled: false
    sandbox: true
    credentials:
      api_key: "your_wallet_address"
      api_secret: "your_private_key"
  
  kucoin:
    enabled: false
    sandbox: true
    credentials:
      api_key: "your_kucoin_api_key"
      api_secret: "your_kucoin_secret"
      passphrase: "your_kucoin_passphrase"

# Trading Strategy Configuration
strategy:
  min_profit_threshold: "0.0005"    # Minimum profit threshold (0.05%)
  max_position_size_usd: "1000"     # Maximum position size in USD
  max_exposure_per_exchange: "5000" # Maximum total exposure per exchange
  max_active_positions: 5           # Maximum simultaneous arbitrage positions
  funding_buffer_minutes: 30        # Minutes before funding to close positions
  enable_auto_trading: false        # Enable automatic trading (start false for safety)
  trading_pairs:                    # Symbols to monitor for arbitrage
    - "BTC-USDT"
    - "ETH-USDT"

# Logging Configuration
logging:
  level: "INFO"           # DEBUG, INFO, WARNING, ERROR
  file: "logs/bot.log"    # Log file location

# Dashboard Configuration
dashboard:
  enabled: true     # Enable web dashboard
  port: 8501       # Dashboard port
  host: "0.0.0.0"  # Dashboard host (0.0.0.0 for all interfaces)

# Risk Management (Advanced)
risk_management:
  max_daily_loss: "500"           # Maximum daily loss in USD
  position_timeout_hours: 7       # Auto-close positions after X hours
  emergency_stop_loss: "0.02"     # Emergency stop loss (2%)
  min_account_balance: "1000"     # Minimum account balance to trade
"""
    
    try:
        with open(filename, 'w') as f:
            f.write(sample_content)
        
        print(f"✅ Sample configuration created: {filename}")
        print("📝 Edit this file and rename to config.yaml to get started")
        
    except Exception as e:
        print(f"❌ Error creating sample config: {e}")


# ========== Environment Variable Support ==========

def load_config_from_env() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    
    config = get_default_config()
    
    # Exchange credentials from environment
    exchanges = {
        "binance": {
            "api_key": "BINANCE_API_KEY",
            "api_secret": "BINANCE_API_SECRET"
        },
        "bybit": {
            "api_key": "BYBIT_API_KEY", 
            "api_secret": "BYBIT_API_SECRET"
        },
        "hyperliquid": {
            "api_key": "HYPERLIQUID_API_KEY",
            "api_secret": "HYPERLIQUID_API_SECRET"
        },
        "kucoin": {
            "api_key": "KUCOIN_API_KEY",
            "api_secret": "KUCOIN_API_SECRET",
            "passphrase": "KUCOIN_PASSPHRASE"
        }
    }
    
    for exchange, env_vars in exchanges.items():
        if exchange in config["exchanges"]:
            for cred_key, env_key in env_vars.items():
                env_value = os.getenv(env_key)
                if env_value:
                    config["exchanges"][exchange]["credentials"][cred_key] = env_value
                    config["exchanges"][exchange]["enabled"] = True
    
    # Strategy settings from environment
    strategy_env_vars = {
        "MIN_PROFIT_THRESHOLD": "min_profit_threshold",
        "MAX_POSITION_SIZE": "max_position_size_usd",
        "MAX_EXPOSURE": "max_exposure_per_exchange",
        "AUTO_TRADING": "enable_auto_trading"
    }
    
    for env_key, config_key in strategy_env_vars.items():
        env_value = os.getenv(env_key)
        if env_value:
            if config_key == "enable_auto_trading":
                config["strategy"][config_key] = env_value.lower() in ("true", "1", "yes")
            else:
                config["strategy"][config_key] = env_value
    
    return config


def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two configuration dictionaries"""
    
    result = base_config.copy()
    
    for key, value in override_config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result


# ========== Configuration Validation ==========

def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate configuration and return validation result.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    
    errors = []
    
    # Check that at least 2 exchanges are enabled
    enabled_exchanges = []
    for exchange, exchange_config in config.get("exchanges", {}).items():
        if exchange_config.get("enabled", False):
            enabled_exchanges.append(exchange)
    
    if len(enabled_exchanges) < 2:
        errors.append("At least 2 exchanges must be enabled for arbitrage")
    
    # Validate strategy parameters
    strategy = config.get("strategy", {})
    
    try:
        min_profit = Decimal(str(strategy.get("min_profit_threshold", "0")))
        if min_profit <= 0:
            errors.append("min_profit_threshold must be greater than 0")
    except:
        errors.append("min_profit_threshold must be a valid number")
    
    try:
        max_position = Decimal(str(strategy.get("max_position_size_usd", "0")))
        if max_position <= 0:
            errors.append("max_position_size_usd must be greater than 0")
    except:
        errors.append("max_position_size_usd must be a valid number")
    
    # Validate trading pairs
    trading_pairs = strategy.get("trading_pairs", [])
    if not trading_pairs:
        errors.append("At least one trading pair must be specified")
    
    for pair in trading_pairs:
        if not isinstance(pair, str) or "-" not in pair:
            errors.append(f"Invalid trading pair format: {pair}")
    
    return len(errors) == 0, errors


if __name__ == "__main__":
    """CLI for configuration management"""
    
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "create-sample":
            create_sample_config()
        elif command == "validate":
            config_file = sys.argv[2] if len(sys.argv) > 2 else "config.yaml"
            config = load_config(config_file)
            is_valid, errors = validate_config(config)
            
            if is_valid:
                print("✅ Configuration is valid")
            else:
                print("❌ Configuration errors:")
                for error in errors:
                    print(f"   - {error}")
        else:
            print("Usage: python settings.py [create-sample|validate] [config-file]")
    else:
        print("Available commands:")
        print("  create-sample  - Create a sample configuration file")
        print("  validate       - Validate configuration file")
