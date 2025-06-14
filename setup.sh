#!/usr/bin/env python3
"""
Setup script for Funding Arbitrage Bot
Professional funding rate arbitrage bot for Binance, KuCoin & Hyperliquid
"""

from setuptools import setup, find_packages
import os
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
def read_requirements(filename):
    """Read requirements from file and return as list"""
    req_path = Path(__file__).parent / filename
    if req_path.exists():
        with open(req_path, 'r', encoding='utf-8') as f:
            return [
                line.strip() 
                for line in f 
                if line.strip() and not line.startswith('#')
            ]
    return []

# Core requirements
install_requires = [
    "cryptography>=41.0.0,<43.0.0",
    "pydantic>=2.5.0,<3.0.0",
    "pyyaml>=6.0.1,<7.0.0",
    "python-dotenv>=1.0.0,<2.0.0",
    "rich>=13.7.0,<14.0.0",
    "questionary>=2.0.1,<3.0.0",
    "click>=8.1.7,<9.0.0",
    "python-telegram-bot>=20.7,<21.0.0",
    "structlog>=23.2.0,<24.0.0",
    "sqlalchemy>=2.0.23,<3.0.0",
    "ccxt>=4.2.0,<5.0.0",
    "pandas>=2.1.0,<3.0.0",
    "numpy>=1.24.0,<2.0.0",
    "aiohttp>=3.9.0,<4.0.0",
    "aiofiles>=23.2.1,<24.0.0",
    "websockets>=12.0,<13.0.0",
    "httpx>=0.25.0,<1.0.0",
    "typer>=0.9.0,<1.0.0",
    "colorama>=0.4.6,<1.0.0",
    "tabulate>=0.9.0,<1.0.0",
]

# Optional dependencies
extras_require = {
    'monitoring': [
        'prometheus-client>=0.19.0,<1.0.0',
        'psutil>=5.9.6,<6.0.0',
        'grafana-api>=1.0.3',
    ],
    'technical-analysis': [
        'TA-Lib>=0.4.25',
        'quantlib>=1.31',
    ],
    'production': [
        'gunicorn>=21.2.0,<22.0.0',
        'uvicorn>=0.24.0,<1.0.0',
    ],
    'testing': [
        'pytest>=7.4.0,<8.0.0',
        'pytest-asyncio>=0.21.0,<1.0.0',
        'pytest-cov>=4.1.0,<5.0.0',
        'pytest-mock>=3.12.0,<4.0.0',
    ],
    'development': [
        'black>=23.10.0',
        'isort>=5.12.0',
        'flake8>=6.1.0',
        'mypy>=1.7.0',
        'pre-commit>=3.5.0',
    ]
}

# All extras combined
extras_require['all'] = list(set(sum(extras_require.values(), [])))

setup(
    name="funding-arbitrage-bot",
    version="1.0.0",
    author="MarcR1993",
    author_email="marc@example.com",  # Update with your email
    description="Professional funding rate arbitrage bot for Binance, KuCoin & Hyperliquid",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MarcR1993/funding-arbitrage-bot",
    project_urls={
        "Bug Reports": "https://github.com/MarcR1993/funding-arbitrage-bot/issues",
        "Documentation": "https://github.com/MarcR1993/funding-arbitrage-bot/blob/main/docs/",
        "Source": "https://github.com/MarcR1993/funding-arbitrage-bot",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.9,<3.13",
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "funding-bot=funding_arbitrage_bot.cli:main",
            "arbitrage-bot=funding_arbitrage_bot.main:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "funding_arbitrage_bot": [
            "config/*.yaml",
            "config/*.yml",
            "templates/*.html",
            "static/*",
        ],
    },
    zip_safe=False,
    keywords=[
        "arbitrage", "funding-rate", "cryptocurrency", "trading-bot", 
        "binance", "kucoin", "hyperliquid", "quantitative-finance",
        "algorithmic-trading", "defi", "crypto-trading"
    ],
)
