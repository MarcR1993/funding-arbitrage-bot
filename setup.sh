#!/bin/bash
# Script de setup initial pour funding-arbitrage-bot

echo "🚀 Setting up Funding Arbitrage Bot repository..."

# Cloner le repository (remplace [USERNAME] par ton nom d'utilisateur GitHub)
git clone https://github.com/[USERNAME]/funding-arbitrage-bot.git
cd funding-arbitrage-bot

echo "📁 Creating directory structure..."

# Créer structure des dossiers
mkdir -p src/{bot,exchanges,models,utils,ui}
mkdir -p tests/{unit,integration,fixtures}
mkdir -p config scripts docs docker 
mkdir -p monitoring/{grafana/dashboards,prometheus,alerts}
mkdir -p data/{logs,backtest_results,positions_history}
mkdir -p .github/{workflows,ISSUE_TEMPLATE}

# Créer fichiers __init__.py pour les packages Python
find src tests -type d -exec touch {}/__init__.py \;

# Créer fichiers de base
touch .env.example .pre-commit-config.yaml
touch requirements.txt requirements-dev.txt pyproject.toml setup.py
touch Makefile CHANGELOG.md
touch src/main.py

# Créer fichiers GitHub
touch .github/workflows/{ci.yml,security-scan.yml,release.yml}
touch .github/ISSUE_TEMPLATE/{bug_report.md,feature_request.md}
touch .github/pull_request_template.md

# Créer fichiers de documentation
touch docs/{SETUP.md,STRATEGY.md,API_REFERENCE.md,DEPLOYMENT.md,TROUBLESHOOTING.md,CONTRIBUTING.md}

# Créer fichiers de configuration
touch config/{config.example.yaml,trading_pairs.yaml,risk_limits.yaml,exchanges.yaml}

# Créer scripts utiles
touch scripts/{setup.sh,run_bot.py,backtest.py,monitor_positions.py,emergency_close.py}

# Créer fichiers Docker
touch docker/{Dockerfile,Dockerfile.dev,docker-compose.yml,docker-compose.dev.yml,.dockerignore}

# Créer .gitkeep pour dossiers vides
touch data/{logs,backtest_results,positions_history}/.gitkeep

echo "✅ Directory structure created successfully!"
echo ""
echo "📂 Project structure:"
tree -L 3 -a

echo ""
echo "🎯 Next steps:"
echo "1. Run: chmod +x setup.sh && ./setup.sh"
echo "2. Configure your .env file" 
echo "3. Install dependencies: pip install -r requirements.txt"
echo "4. Start coding! 🚀"
