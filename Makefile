# =============================================================================
# FUNDING ARBITRAGE BOT - Makefile
# =============================================================================

.PHONY: help install install-dev test lint format clean setup

# Variables
PYTHON := python3
PIP := pip3
PYTEST := pytest

# =============================================================================
# HELP
# =============================================================================
help: ## Affiche l'aide
	@echo "🤖 Funding Arbitrage Bot - Commandes Disponibles"
	@echo ""
	@echo "📦 Installation & Setup:"
	@echo "  install      - Installe les dépendances de production"
	@echo "  install-dev  - Installe toutes les dépendances (dev + prod)"
	@echo "  setup        - Setup complet du projet (première fois)"
	@echo "  clean        - Nettoie les fichiers temporaires"
	@echo ""
	@echo "🧪 Développement & Tests:"
	@echo "  format       - Formate le code avec Black et isort"
	@echo "  lint         - Vérifie la qualité du code"
	@echo "  test         - Lance tous les tests"
	@echo "  check        - Vérifie tout (lint + tests)"
	@echo ""
	@echo "🚀 Bot Operations:"
	@echo "  run          - Lance le bot en mode production"
	@echo "  run-paper    - Lance le bot en mode paper trading"
	@echo "  config       - Aide à la configuration"

# =============================================================================
# INSTALLATION & SETUP
# =============================================================================
install: ## Installe les dépendances de production
	@echo "📦 Installation des dépendances de production..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: ## Installe toutes les dépendances (dev + prod)
	@echo "📦 Installation des dépendances de développement..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

setup: install-dev ## Setup complet du projet (première fois)
	@echo "🔧 Setup initial du projet..."
	# Créer les dossiers nécessaires
	mkdir -p data/{logs,backtest_results,positions_history}
	# Copier les fichiers de configuration
	cp .env.example .env || true
	cp config/config.example.yaml config/config.yaml || true
	@echo "✅ Setup terminé! Édite .env et config/config.yaml avec tes paramètres"

clean: ## Nettoie les fichiers temporaires
	@echo "🧹 Nettoyage des fichiers temporaires..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/

# =============================================================================
# DÉVELOPPEMENT & TESTS
# =============================================================================
format: ## Formate le code avec Black et isort
	@echo "🎨 Formatage du code..."
	black src tests --line-length=100
	isort src tests

lint: ## Vérifie la qualité du code
	@echo "🔍 Vérification de la qualité du code..."
	flake8 src tests --max-line-length=100
	black --check src tests
	isort --check-only src tests

test: ## Lance tous les tests
	@echo "🧪 Lancement des tests..."
	$(PYTEST) tests/ -v

check: lint test ## Vérifie tout (lint + tests)

# =============================================================================
# BOT OPERATIONS
# =============================================================================
run: ## Lance le bot en mode production
	@echo "🚀 Lancement du bot en mode production..."
	$(PYTHON) src/main.py

run-paper: ## Lance le bot en mode paper trading
	@echo "📄 Lancement en mode paper trading..."
	BOT_MODE=paper_trading $(PYTHON) src/main.py

config: ## Aide à la configuration
	@echo "⚙️ Configuration du bot"
	@echo "1. Édite .env avec tes API keys"
	@echo "2. Édite config/config.yaml selon tes besoins"
	@echo "3. Test connexions: python scripts/test_connections.py"

# Cible par défaut
.DEFAULT_GOAL := help
