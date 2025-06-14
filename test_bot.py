# Tests rapides pour vérifier les composants

# Test 1: Structure et imports
echo "🧪 Test 1: Structure et imports"
python test_bot.py

# Test 2: Configuration
echo -e "\n🧪 Test 2: Configuration"
python -c "
from src.models.config import FundingBotConfig
config = FundingBotConfig()
print(f'✅ Tokens: {config.trading.tokens}')
print(f'✅ Position size: ${config.trading.position_size_usd}')
print(f'✅ Exchanges: {config.get_enabled_exchanges()}')
"

# Test 3: Models
echo -e "\n🧪 Test 3: Models"
python -c "
from src.models.position import Position
from src.models.opportunity import create_opportunity
from datetime import datetime

# Test Position
pos = Position(pair_name='test', token='BTC', exchange_a='binance', exchange_b='kucoin', size_usd=1000)
print(f'✅ Position created: {pos.id}')

# Test Opportunity  
opp = create_opportunity('BTC', 
    {'exchange_name': 'binance', 'funding_rate': 0.001, 'funding_frequency_hours': 8},
    {'exchange_name': 'kucoin', 'funding_rate': -0.0005, 'funding_frequency_hours': 8}
)
print(f'✅ Opportunity created: {opp.spread:.4f} spread')
"

# Test 4: Engine (sans connexions)
echo -e "\n🧪 Test 4: Engine"
python -c "
from src.bot.arbitrage_engine import ArbitrageEngine, EngineState
from src.models.config import FundingBotConfig

config = FundingBotConfig()
# Désactiver les exchanges pour le test
config.exchanges.binance.enabled = False
config.exchanges.kucoin.enabled = False  
config.exchanges.hyperliquid.enabled = False

engine = ArbitrageEngine(config)
print(f'✅ Engine created: {engine.state.value}')

status = engine.get_engine_status()
print(f'✅ Status: {status[\"engine\"][\"state\"]}')
"

# Test 5: CLI (création seulement)
echo -e "\n🧪 Test 5: CLI Interface"
python -c "
from src.ui.cli_interface import FundingBotCLI
cli = FundingBotCLI()
print('✅ CLI interface created successfully')
"

# Test 6: Point d'entrée principal
echo -e "\n🧪 Test 6: Main Entry Point"
python src/main.py --version
python src/main.py --help | head -5

# Test 7: Validation de configuration
echo -e "\n🧪 Test 7: Configuration Validation"
python src/main.py --validate-config --config config/config.example.yaml

echo -e "\n🎉 Tests terminés!"
echo "💡 Si tous les tests passent, le bot est prêt à être configuré et utilisé"
