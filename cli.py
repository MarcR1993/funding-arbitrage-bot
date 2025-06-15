
"""
Command-line interface for the funding rate arbitrage bot.
Allows control and monitoring of the bot without the dashboard.
"""

import asyncio
import click
import json
import logging
import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.main import FundingArbitrageBot
from src.config.settings import (
    create_sample_config, 
    load_config, 
    validate_config,
    load_config_from_env
)
from src.connectors.connector_manager import ConnectorManager


@click.group()
@click.option('--config', '-c', help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
@click.pass_context
def cli(ctx, config, verbose):
    """Funding Rate Arbitrage Bot CLI"""
    
    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj['config_file'] = config
    ctx.obj['verbose'] = verbose


@cli.command()
@click.pass_context
def start(ctx):
    """Start the arbitrage bot"""
    
    click.echo("🚀 Starting Funding Rate Arbitrage Bot...")
    
    try:
        config_file = ctx.obj.get('config_file')
        bot = FundingArbitrageBot(config_file)
        
        # Run the bot
        asyncio.run(bot.start())
        
    except KeyboardInterrupt:
        click.echo("\n👋 Bot stopped by user")
    except Exception as e:
        click.echo(f"❌ Error starting bot: {e}")
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', default='config.sample.yaml', help='Output file name')
def init(output):
    """Create a sample configuration file"""
    
    click.echo(f"📝 Creating sample configuration: {output}")
    create_sample_config(output)
    
    click.echo("\n📋 Next steps:")
    click.echo(f"1. Edit {output} with your exchange API keys")
    click.echo("2. Rename to config.yaml")
    click.echo("3. Run: python cli.py validate")
    click.echo("4. Run: python cli.py start")


@cli.command()
@click.option('--config', '-c', help='Configuration file to validate')
def validate(config):
    """Validate configuration file"""
    
    config_file = config or "config.yaml"
    
    click.echo(f"🔍 Validating configuration: {config_file}")
    
    if not os.path.exists(config_file):
        click.echo(f"❌ Configuration file not found: {config_file}")
        click.echo("💡 Run 'python cli.py init' to create a sample config")
        sys.exit(1)
    
    try:
        config_data = load_config(config_file)
        is_valid, errors = validate_config(config_data)
        
        if is_valid:
            click.echo("✅ Configuration is valid!")
            
            # Show enabled exchanges
            enabled_exchanges = []
            for exchange, exchange_config in config_data.get("exchanges", {}).items():
                if exchange_config.get("enabled", False):
                    enabled_exchanges.append(exchange)
            
            if enabled_exchanges:
                click.echo(f"📊 Enabled exchanges: {', '.join(enabled_exchanges)}")
            else:
                click.echo("⚠️  No exchanges enabled - update credentials and set enabled: true")
            
            # Show strategy settings
            strategy = config_data.get("strategy", {})
            click.echo(f"💰 Min profit threshold: {strategy.get('min_profit_threshold')}%")
            click.echo(f"💵 Max position size: ${strategy.get('max_position_size_usd')}")
            click.echo(f"🤖 Auto trading: {'ON' if strategy.get('enable_auto_trading') else 'OFF'}")
            
        else:
            click.echo("❌ Configuration has errors:")
            for error in errors:
                click.echo(f"   • {error}")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Error validating config: {e}")
        sys.exit(1)


@cli.command()
@click.option('--exchange', '-e', help='Test specific exchange only')
@click.option('--sandbox', is_flag=True, help='Use sandbox/testnet')
def test(exchange, sandbox):
    """Test exchange connections"""
    
    click.echo("🧪 Testing exchange connections...")
    
    async def run_test():
        try:
            # Load config
            config_data = load_config()
            
            # Create connector manager
            manager = ConnectorManager()
            
            # Filter exchanges if specified
            exchanges_to_test = config_data.get("exchanges", {})
            if exchange:
                if exchange in exchanges_to_test:
                    exchanges_to_test = {exchange: exchanges_to_test[exchange]}
                else:
                    click.echo(f"❌ Exchange '{exchange}' not found in config")
                    return
            
            # Test each exchange
            test_results = {}
            
            for exchange_name, exchange_config in exchanges_to_test.items():
                if not exchange_config.get("enabled", False):
                    click.echo(f"⏭️  Skipping {exchange_name} - disabled")
                    continue
                
                click.echo(f"🔌 Testing {exchange_name}...")
                
                try:
                    credentials = exchange_config.get("credentials", {})
                    use_sandbox = sandbox or exchange_config.get("sandbox", True)
                    
                    success = await manager.add_connector(
                        exchange=exchange_name,
                        credentials=credentials,
                        sandbox=use_sandbox
                    )
                    
                    if success:
                        click.echo(f"✅ {exchange_name}: Connected successfully")
                        test_results[exchange_name] = False
                    
                except Exception as e:
                    click.echo(f"❌ {exchange_name}: Error - {e}")
                    test_results[exchange_name] = False
            
            # Test funding rate retrieval
            if any(test_results.values()):
                click.echo("\n📊 Testing funding rate retrieval...")
                await asyncio.sleep(2)  # Wait for connections to stabilize
                
                test_symbols = ["BTC-USDT", "ETH-USDT"]
                for symbol in test_symbols:
                    rates = manager.get_funding_rates(symbol)
                    if rates:
                        click.echo(f"  {symbol}:")
                        for ex, rate in rates.items():
                            click.echo(f"    {ex}: {rate.rate:.6f} ({rate.rate * 100:.4f}%)")
                    else:
                        click.echo(f"  {symbol}: No rates available")
            
            # Health check
            click.echo("\n🏥 Running health check...")
            health = await manager.health_check()
            
            healthy_count = sum(1 for h in health.values() if h)
            total_count = len(health)
            
            click.echo(f"📈 Health check: {healthy_count}/{total_count} exchanges healthy")
            
            for exchange_name, is_healthy in health.items():
                status = "✅ Healthy" if is_healthy else "❌ Unhealthy"
                click.echo(f"  {exchange_name}: {status}")
            
            # Cleanup
            await manager.stop_all()
            
        except Exception as e:
            click.echo(f"❌ Test failed: {e}")
    
    asyncio.run(run_test())


@cli.command()
@click.option('--duration', '-d', default=60, help='Duration in seconds')
@click.option('--symbol', '-s', default='BTC-USDT', help='Symbol to monitor')
def monitor(duration, symbol):
    """Monitor funding rates and opportunities"""
    
    click.echo(f"📡 Monitoring {symbol} for {duration} seconds...")
    
    async def run_monitor():
        try:
            # Load config and setup
            config_data = load_config()
            manager = ConnectorManager()
            
            # Setup exchanges
            exchanges_config = config_data.get("exchanges", {})
            connected_count = 0
            
            for exchange_name, exchange_config in exchanges_config.items():
                if exchange_config.get("enabled", False):
                    credentials = exchange_config.get("credentials", {})
                    sandbox = exchange_config.get("sandbox", True)
                    
                    success = await manager.add_connector(
                        exchange=exchange_name,
                        credentials=credentials,
                        sandbox=sandbox
                    )
                    
                    if success:
                        connected_count += 1
            
            if connected_count < 2:
                click.echo("❌ Need at least 2 exchanges connected for monitoring")
                return
            
            click.echo(f"✅ Connected to {connected_count} exchanges")
            
            # Wait for initial data
            await asyncio.sleep(3)
            
            # Monitor loop
            start_time = asyncio.get_event_loop().time()
            update_count = 0
            
            while (asyncio.get_event_loop().time() - start_time) < duration:
                # Get current rates
                rates = manager.get_funding_rates(symbol)
                
                if rates and len(rates) >= 2:
                    # Display rates
                    rate_info = []
                    for exchange, rate in rates.items():
                        rate_info.append(f"{exchange}: {rate.rate:.6f}")
                    
                    click.echo(f"📊 {symbol}: {' | '.join(rate_info)}")
                    
                    # Check for arbitrage opportunities
                    min_threshold = Decimal("0.0001")
                    opportunities = await manager.get_arbitrage_opportunities(symbol, min_threshold)
                    
                    if opportunities:
                        best = opportunities[0]
                        profit_pct = best['profit_potential'] * 100
                        click.echo(f"🎯 Best opportunity: {profit_pct:.4f}% "
                                 f"(Long {best['long_exchange']}, Short {best['short_exchange']})")
                    
                    update_count += 1
                
                await asyncio.sleep(5)
            
            click.echo(f"\n📈 Monitoring complete. Received {update_count} updates.")
            
            # Cleanup
            await manager.stop_all()
            
        except Exception as e:
            click.echo(f"❌ Monitoring failed: {e}")
    
    asyncio.run(run_monitor())


@cli.command()
@click.option('--symbol', '-s', help='Filter by symbol')
@click.option('--min-profit', '-p', default=0.01, help='Minimum profit threshold (%)')
def opportunities(symbol, min_profit):
    """Find current arbitrage opportunities"""
    
    click.echo("🔍 Scanning for arbitrage opportunities...")
    
    async def find_opportunities():
        try:
            # Setup
            config_data = load_config()
            manager = ConnectorManager()
            
            # Connect exchanges
            connected = 0
            for exchange_name, exchange_config in config_data.get("exchanges", {}).items():
                if exchange_config.get("enabled", False):
                    credentials = exchange_config.get("credentials", {})
                    sandbox = exchange_config.get("sandbox", True)
                    
                    success = await manager.add_connector(exchange_name, credentials, sandbox)
                    if success:
                        connected += 1
            
            if connected < 2:
                click.echo("❌ Need at least 2 exchanges connected")
                return
            
            # Wait for data
            await asyncio.sleep(3)
            
            # Get opportunities
            symbols_to_check = [symbol] if symbol else ["BTC-USDT", "ETH-USDT"]
            min_threshold = Decimal(str(min_profit / 100))
            
            total_opportunities = 0
            
            for check_symbol in symbols_to_check:
                opportunities = await manager.get_arbitrage_opportunities(check_symbol, min_threshold)
                
                if opportunities:
                    click.echo(f"\n💰 {check_symbol} Opportunities (min {min_profit}%):")
                    
                    for i, opp in enumerate(opportunities[:5], 1):
                        profit_pct = opp['profit_potential'] * 100
                        annual_est = opp['annual_profit_estimate'] * 100
                        
                        click.echo(f"  {i}. 📈 Long {opp['long_exchange']:12} ({opp['long_rate']:>8.6f})")
                        click.echo(f"     📉 Short {opp['short_exchange']:12} ({opp['short_rate']:>8.6f})")
                        click.echo(f"     💵 Profit: {profit_pct:>6.4f}% | Annual est: {annual_est:>6.2f}%")
                    
                    total_opportunities += len(opportunities)
                else:
                    click.echo(f"\n{check_symbol}: No opportunities above {min_profit}% threshold")
            
            click.echo(f"\n📊 Total opportunities found: {total_opportunities}")
            
            # Cleanup
            await manager.stop_all()
            
        except Exception as e:
            click.echo(f"❌ Error finding opportunities: {e}")
    
    asyncio.run(find_opportunities())


@cli.command()
def status():
    """Show bot status and performance"""
    
    # Check if performance data exists
    performance_file = "logs/performance.json"
    
    if not os.path.exists(performance_file):
        click.echo("📊 No performance data found")
        click.echo("💡 Start the bot to generate performance data")
        return
    
    try:
        with open(performance_file, 'r') as f:
            performance_data = json.load(f)
        
        if not performance_data:
            click.echo("📊 No performance data available")
            return
        
        # Get latest data
        latest = performance_data[-1]
        
        click.echo("📊 Bot Performance Summary")
        click.echo("=" * 40)
        click.echo(f"Last Update: {latest.get('timestamp', 'Unknown')}")
        click.echo(f"Total Funding Collected: ${latest.get('total_funding_collected', 0):.2f}")
        click.echo(f"Net Profit: ${latest.get('net_profit', 0):.2f}")
        click.echo(f"Successful Arbitrages: {latest.get('successful_arbitrages', 0)}")
        click.echo(f"Failed Arbitrages: {latest.get('failed_arbitrages', 0)}")
        click.echo(f"Success Rate: {latest.get('success_rate_percent', 0):.1f}%")
        click.echo(f"Active Positions: {latest.get('active_positions', 0)}")
        
        # Show trend if we have historical data
        if len(performance_data) > 1:
            previous = performance_data[-2]
            profit_change = latest.get('net_profit', 0) - previous.get('net_profit', 0)
            
            if profit_change > 0:
                click.echo(f"📈 Profit change: +${profit_change:.2f}")
            elif profit_change < 0:
                click.echo(f"📉 Profit change: ${profit_change:.2f}")
            else:
                click.echo("➡️  No profit change")
        
    except Exception as e:
        click.echo(f"❌ Error reading performance data: {e}")


@cli.command()
@click.option('--days', '-d', default=7, help='Number of days of logs to show')
def logs(days):
    """Show bot logs"""
    
    log_file = "logs/bot.log"
    
    if not os.path.exists(log_file):
        click.echo(f"📄 Log file not found: {log_file}")
        return
    
    try:
        # Show last N lines of log file
        lines_to_show = days * 100  # Approximate lines per day
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Show last lines
        recent_lines = lines[-lines_to_show:] if len(lines) > lines_to_show else lines
        
        click.echo(f"📄 Recent logs (last {len(recent_lines)} lines):")
        click.echo("=" * 50)
        
        for line in recent_lines:
            click.echo(line.rstrip())
    
    except Exception as e:
        click.echo(f"❌ Error reading logs: {e}")


@cli.command()
def info():
    """Show system information"""
    
    click.echo("ℹ️  Funding Rate Arbitrage Bot Information")
    click.echo("=" * 50)
    
    # Bot version and info
    click.echo("📦 Version: 1.0.0")
    click.echo("🏗️  Architecture: Multi-exchange arbitrage")
    click.echo("📜 License: Apache 2.0")
    click.echo("🔗 Based on: Hummingbot framework")
    
    # Supported exchanges
    click.echo("\n🏦 Supported Exchanges:")
    exchanges_info = {
        "Binance": "World's largest crypto futures exchange",
        "Bybit": "Popular derivatives trading platform", 
        "Hyperliquid": "Leading decentralized perpetual exchange",
        "KuCoin": "Global crypto exchange with futures"
    }
    
    for exchange, description in exchanges_info.items():
        click.echo(f"  • {exchange}: {description}")
    
    # Files and directories
    click.echo("\n📁 Important Files:")
    files_info = [
        ("config.yaml", "Main configuration file"),
        ("logs/bot.log", "Application logs"),
        ("logs/performance.json", "Performance data"),
        ("cli.py", "Command line interface")
    ]
    
    for filename, description in files_info:
        exists = "✅" if os.path.exists(filename) else "❌"
        click.echo(f"  {exists} {filename}: {description}")
    
    # Quick start guide
    click.echo("\n🚀 Quick Start:")
    click.echo("  1. python cli.py init")
    click.echo("  2. Edit config.sample.yaml with your API keys")
    click.echo("  3. Rename to config.yaml")
    click.echo("  4. python cli.py validate")
    click.echo("  5. python cli.py test")
    click.echo("  6. python cli.py start")


if __name__ == '__main__':
    cli()


# ========== Setup Script for CLI ==========

"""
Create setup.py for easy installation:

from setuptools import setup, find_packages

setup(
    name="funding-arbitrage-bot",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "pyyaml>=6.0",
        "ccxt>=4.0.0",
        "aiohttp>=3.8.0",
        "pandas>=1.5.0",
        "numpy>=1.24.0",
        "streamlit>=1.28.0",
        "plotly>=5.0.0"
    ],
    entry_points={
        'console_scripts': [
            'funding-arb=cli:cli',
        ],
    },
    author="Your Name",
    description="Multi-exchange funding rate arbitrage bot",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/MarcR1993/funding-arbitrage-bot",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
""" = True
                    else:
                        click.echo(f"❌ {exchange_name}: Connection failed")
                        test_results[exchange_name]
