# 🤖 Funding Rate Arbitrage Bot

> **Professional automated funding rate arbitrage between Binance, KuCoin & Hyperliquid**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![GitHub Actions](https://github.com/[USERNAME]/funding-arbitrage-bot/workflows/CI/badge.svg)](https://github.com/[USERNAME]/funding-arbitrage-bot/actions)

## ✨ Fonctionnalités

🔄 **Arbitrage Multi-Exchange Automatique**
- Surveillance continue des funding rates sur 3 exchanges
- Ouverture/fermeture automatique des positions
- Stratégie optimisée 3 paires simultanées maximum

📊 **Gestion Intelligente des Positions**
- Durées variables (quelques heures à plusieurs semaines)
- Optimisation continue basée sur la profitabilité
- Remplacement dynamique des positions sous-performantes

🛡️ **Gestion des Risques Intégrée**
- Stop-loss automatique et limites de pertes
- Position sizing intelligent
- Surveillance 24/7 avec alertes

📱 **Interface & Monitoring**
- CLI interactive style Hummingbot
- Alertes Telegram/Discord en temps réel
- Dashboard Grafana pour métriques avancées

🐳 **Production Ready**
- Déploiement Docker
- CI/CD avec GitHub Actions
- Logging et monitoring professionnel

## 🎯 Stratégie - 3 Paires Optimales

| Paire | Exchange A | Exchange B | Avantage |
|-------|------------|------------|----------|
| **Paire 1** | Binance | KuCoin | Cycles décalés = revenus quasi-continus |
| **Paire 2** | Binance | Hyperliquid | 8h vs 1h = 8x plus d'opportunités |
| **Paire 3** | KuCoin | Hyperliquid | Coverage complémentaire |

**Exemple de Performance :**
- **Objectif :** 10-30% de profit annualisé
- **Positions Max :** 3 simultanées  
- **Win Rate :** ~85%+ (backtests)
- **Max Drawdown :** <2%

## 🚀 Quick Start

### Prérequis
- Python 3.9+
- API Keys pour Binance Futures, KuCoin Futures, Hyperliquid
- Capital minimum recommandé : $1,000+ par exchange

### Installation

```bash
# 1. Clone le repository
git clone https://github.com/[USERNAME]/funding-arbitrage-bot.git
cd funding-arbitrage-bot

# 2. Créer environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# 3. Installer dependencies
pip install -r requirements.txt

# 4. Configuration
cp .env.example .env
cp config/config.example.yaml config/config.yaml

# Édite .env avec tes API keys
nano .env

# 5. Test de connexion
python scripts/test_connections.py

# 6. Lancer le bot
python src/main.py
```

### Configuration Rapide

```bash
# Mode paper trading (recommandé pour débuter)
export BOT_MODE=paper_trading
export LOG_LEVEL=DEBUG

# ou mode production avec petites positions
export BOT_MODE=production
export MAX_POSITION_SIZE_USD=100
```

## 📊 Interface CLI

```bash
funding-bot start         # Démarre le bot
funding-bot config        # Configuration interactive
funding-bot status        # Status des positions
funding-bot stop          # Arrête le bot
funding-bot backtest      # Lance un backtest
```

**Interface Interactive :**
```
╔══════════════════════════════════════════════════════════════╗
║              🤖 FUNDING RATE ARBITRAGE BOT 🤖               ║
║                     Interactive Interface                     ║
╚══════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────┐
│                        🎛️ Main Menu                         │
├─────┬───────────────────────────────────┬─────────────────────┤
│  1  │ Configure Trading Parameters      │ ✅ Ready           │
│  2  │ Setup Exchanges & API Keys        │ 2/3 configured     │
│  3  │ Risk Management Settings          │ ⚙️ Configure       │
│  4  │ Start/Stop Bot                    │ 🟢 RUNNING         │
│  5  │ View Active Positions             │ 2 active           │
│  6  │ Monitoring & Alerts               │ 📱 Telegram ON     │
└─────┴───────────────────────────────────┴─────────────────────┘
```

## 📈 Monitoring & Alertes

### Telegram Bot
```bash
# Messages automatiques :
🚀 Position ouverte: BTC Binance↔KuCoin, spread 0.08%
💰 Profit réalisé: +$23.45 sur ETH (12h de holding)
⚠️ Spread diminué: SOL position marquée pour fermeture
📊 Rapport quotidien: +2.1% profit, 3/3 positions actives
```

### Dashboard Grafana
- Profits en temps réel
- Spreads par paire
- Performance par exchange
- Métriques de risque

## 🛡️ Sécurité

**✅ Best Practices Intégrées :**
- API keys via variables d'environnement
- Jamais de secrets dans le code
- Permissions API minimales (trading uniquement)
- Rate limiting automatique
- Logs sécurisés (pas de données sensibles)

**🔐 Permissions API Requises :**
- **Binance :** Futures Trading (pas de withdrawal)
- **KuCoin :** Futures Trading (pas de withdrawal)  
- **Hyperliquid :** Trading via vault (sécurité maximum)

## 📚 Documentation

- [📖 Setup Détaillé](docs/SETUP.md) - Installation et configuration complète
- [🎯 Stratégie](docs/STRATEGY.md) - Explication de la stratégie 3 paires
- [🔧 API Reference](docs/API_REFERENCE.md) - Documentation technique
- [🚀 Deployment](docs/DEPLOYMENT.md) - Guide de déploiement production
- [🔍 Troubleshooting](docs/TROUBLESHOOTING.md) - Résolution de problèmes

## 🧪 Testing

```bash
# Tests unitaires
pytest tests/unit/ -v

# Tests d'intégration
pytest tests/integration/ -v

# Tests avec coverage
pytest --cov=src --cov-report=html

# Backtest sur données historiques
python scripts/backtest.py --start=2024-01-01 --end=2024-12-31
```

## 🐳 Déploiement Docker

```bash
# Build image
docker build -t funding-arbitrage-bot .

# Run container
docker-compose up -d

# Monitoring
docker-compose logs -f bot
```

## ⚖️ Disclaimer

**Ce bot est fourni à des fins éducatives et de recherche. Le trading de cryptomonnaies comportent des risques financiers importants. Utilisez uniquement des fonds que vous pouvez vous permettre de perdre.**

- ✅ Testé en paper trading
- ✅ Backtests sur données historiques  
- ✅ Gestion des risques intégrée
- ⚠️ Performances passées ne garantissent pas les résultats futurs
- ⚠️ Utilisez d'abord en mode testnet/paper trading

## 🤝 Contributing

Les contributions sont les bienvenues ! Voir [CONTRIBUTING.md](docs/CONTRIBUTING.md) pour les guidelines.

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/amazing-feature`)
3. Commit les changements (`git commit -m 'Add amazing feature'`)
4. Push la branche (`git push origin feature/amazing-feature`)
5. Ouvrir une Pull Request

## 📄 License

Ce projet est sous licence MIT. Voir [LICENSE](LICENSE) pour plus de détails.

## 📞 Support

- 📧 **Email :** [your.email@example.com]
- 💬 **Telegram :** [@your_telegram]
- 🐛 **Issues :** [GitHub Issues](https://github.com/[USERNAME]/funding-arbitrage-bot/issues)
- 📖 **Wiki :** [Documentation Complète](https://github.com/[USERNAME]/funding-arbitrage-bot/wiki)

---

⭐ **Si ce projet t'aide, n'hésite pas à lui donner une étoile !** ⭐
