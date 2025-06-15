
"""
Comprehensive test script for all exchange connectors.
Tests Binance, Bybit, Hyperliquid, and KuCoin connectors.
"""

import asyncio
import logging
import os
from decimal import Decimal
from datetime import datetime

from src.connectors.connector_manager import ConnectorManager
from src.utils.time_utils import get_utc_datetime


class ConnectorTester:
    """Test suite for all exchange connectors"""
    
    def __init__(self):
        self.logger = logging.getLogger("ConnectorTester")
        self.manager = ConnectorManager()
        
        # Test symbols to check across all exchanges
        self.test_symbols = ['BTC-USDT', 'ETH-USDT']
        
        # Exchange credentials configuration
        self.exchange_configs = {
            'binance': {
                'enabled': False,  # Set to True when you have credentials
                'credentials': {
                    'api_key': os.getenv('BINANCE_API_KEY', 'your_binance_testnet_api_key'),
                    'api_secret': os.getenv('BINANCE_API_SECRET', 'your_binance_testnet_secret'),
                },
                'sandbox': True
            },
            'bybit': {
                'enabled': False,  # Set to True when you have credentials
                'credentials': {
                    'api_key': os.getenv('BYBIT_API_KEY', 'your_bybit_testnet_api_key'),
                    'api_secret': os.getenv('BYBIT_API_SECRET', 'your_bybit_testnet_secret'),
                },
                'sandbox': True
            },
            'hyperliquid': {
                'enabled': False,  # Set to True when you have credentials
                'credentials': {
                    'api_key': os.getenv('HYPERLIQUID_API_KEY', 'your_hyperliquid_wallet_address'),
                    'api_secret': os.getenv('HYPERLIQUID_API_SECRET', 'your_hyperliquid_private_key'),
                },
                'sandbox': True
            },
            'kucoin': {
                'enabled': False,  # Set to True when you have credentials
                'credentials': {
                    'api_key': os.getenv('KUCOIN_API_KEY', 'your_kucoin_api_key'),
                    'api_secret': os.getenv('KUCOIN_API_SECRET', 'your_kucoin_secret'),
                    'passphrase': os.getenv('KUCOIN_PASSPHRASE', 'your_kucoin_passphrase'),
                },
                'sandbox': True
            }
        }
    
    async def setup_connectors(self) -> Dict[str, bool]:
        """Set up all available connectors"""
        self.logger.info("🔌 Setting up exchange connectors...")
        
        setup_results = {}
        
        for exchange, config in self.exchange_configs.items():
            if not config['enabled']:
                self.logger.info(f"⏭️  Skipping {exchange} - not enabled (update credentials to enable)")
                setup_results[exchange] = False
                continue
            
            # Check if credentials look real (not placeholder)
            creds = config['credentials']
            if any(str(v).startswith('your_') for v in creds.values()):
                self.logger.warning(f"⚠️  Skipping {exchange} - placeholder credentials detected")
                setup_results[exchange] = False
                continue
            
            self.logger.info(f"🔄 Adding {exchange} connector...")
            
            try:
                success = await self.manager.add_connector(
                    exchange=exchange,
                    credentials=creds,
                    sandbox=config['sandbox']
                )
                
                if success:
                    self.logger.info(f"✅ {exchange} connector added successfully")
                    setup_results[exchange] = True
                else:
                    self.logger.error(f"❌ Failed to add {exchange} connector")
                    setup_results[exchange] = False
                    
            except Exception as e:
                self.logger.error(f"❌ Error adding {exchange} connector: {e}")
                setup_results[exchange] = False
        
        # Wait for connections to establish
        await asyncio.sleep(3)
        
        return setup_results
    
    async def test_exchange_info(self):
        """Test exchange information retrieval"""
        self.logger.info("\n📊 Testing Exchange Information")
        self.logger.info("=" * 50)
        
        exchange_info = self.manager.get_exchange_info()
        
        for exchange, info in exchange_info.items():
            self.logger.info(f"\n{exchange.upper()}:")
            self.logger.info(f"  Name: {info['name']}")
            self.logger.info(f"  Type: {info['type']}")
            self.logger.info(f"  Funding Interval: {info['funding_interval']} hours")
            self.logger.info(f"  Supported Pairs: {', '.join(info['supported_pairs'][:3])}...")
            self.logger.info(f"  Required Credentials: {', '.join(info['credentials'])}")
            if 'note' in info:
                self.logger.info(f"  Note: {info['note']}")
    
    async def test_funding_rates(self):
        """Test funding rate retrieval"""
        self.logger.info("\n💰 Testing Funding Rate Retrieval")
        self.logger.info("=" * 50)
        
        connected_exchanges = self.manager.get_connected_exchanges()
        
        if not connected_exchanges:
            self.logger.warning("No exchanges connected - skipping funding rate test")
            return
        
        for symbol in self.test_symbols:
            rates = self.manager.get_funding_rates(symbol)
            
            if rates:
                self.logger.info(f"\n{symbol} Funding Rates:")
                for exchange, rate in rates.items():
                    annual_rate = rate.daily_rate * Decimal("365")
                    self.logger.info(f"  {exchange:12}: {rate.rate:>8.6f} ({rate.rate * 100:>6.4f}%) | "
                                   f"Daily: {rate.daily_rate * 100:>6.4f}% | "
                                   f"Annual: {annual_rate * 100:>6.2f}%")
                    self.logger.info(f"               Next funding: {rate.next_funding_time}")
                
                # Calculate spreads
                if len(rates) > 1:
                    rate_values = list(rates.values())
                    max_rate = max(r.rate for r in rate_values)
                    min_rate = min(r.rate for r in rate_values)
                    spread = max_rate - min_rate
                    self.logger.info(f"  📈 Rate Spread: {spread:.6f} ({spread * 100:.4f}%)")
            else:
                self.logger.warning(f"No funding rates found for {symbol}")
    
    async def test_arbitrage_opportunities(self):
        """Test arbitrage opportunity detection"""
        self.logger.info("\n🎯 Testing Arbitrage Opportunities")
        self.logger.info("=" * 50)
        
        min_threshold = Decimal("0.0001")  # 0.01% minimum spread
        
        for symbol in self.test_symbols:
            opportunities = await self.manager.get_arbitrage_opportunities(symbol, min_threshold)
            
            if opportunities:
                self.logger.info(f"\n{symbol} Arbitrage Opportunities (min {min_threshold * 100:.2f}% spread):")
                
                for i, opp in enumerate(opportunities[:5], 1):  # Show top 5
                    profit_pct = opp['profit_potential'] * 100
                    annual_profit = opp['annual_profit_estimate'] * 100
                    
                    self.logger.info(f"  {i}. 📈 Long {opp['long_exchange']:12} ({opp['long_rate']:>8.6f}) | "
                                   f"📉 Short {opp['short_exchange']:12} ({opp['short_rate']:>8.6f})")
                    self.logger.info(f"     💵 Profit/cycle: {profit_pct:>6.4f}% | "
                                   f"Annual estimate: {annual_profit:>6.2f}%")
            else:
                self.logger.info(f"No arbitrage opportunities found for {symbol}")
    
    async def test_balances(self):
        """Test balance retrieval"""
        self.logger.info("\n💳 Testing Balance Retrieval")
        self.logger.info("=" * 50)
        
        connected_exchanges = self.manager.get_connected_exchanges()
        
        if not connected_exchanges:
            self.logger.info("No exchanges connected - skipping balance test")
            return
        
        test_assets = ['USDT', 'BTC', 'ETH']
        
        for asset in test_assets:
            balances = self.manager.get_balances(asset)
            
            if balances:
                self.logger.info(f"\n{asset} Balances:")
                total_balance = Decimal("0")
                
                for exchange, balance in balances.items():
                    self.logger.info(f"  {exchange:12}: Available: {balance.available:>12.6f} | "
                                   f"Total: {balance.total:>12.6f}")
                    total_balance += balance.total
                
                if len(balances) > 1:
                    self.logger.info(f"  {'TOTAL':12}: {total_balance:>12.6f}")
            else:
                self.logger.info(f"No {asset} balances found")
    
    async def test_health_check(self):
        """Test connector health"""
        self.logger.info("\n🏥 Testing Connector Health")
        self.logger.info("=" * 50)
        
        health = await self.manager.health_check()
        
        for exchange, is_healthy in health.items():
            status = "✅ Healthy" if is_healthy else "❌ Unhealthy"
            self.logger.info(f"  {exchange:12}: {status}")
    
    async def monitor_live_updates(self, duration_seconds: int = 30):
        """Monitor live funding rate updates"""
        self.logger.info(f"\n📡 Monitoring Live Updates ({duration_seconds} seconds)")
        self.logger.info("=" * 50)
        
        connected_exchanges = self.manager.get_connected_exchanges()
        
        if not connected_exchanges:
            self.logger.info("No exchanges connected - skipping live monitoring")
            return
        
        start_time = get_utc_datetime()
        update_count = 0
        
        while (get_utc_datetime() - start_time).seconds < duration_seconds:
            await asyncio.sleep(5)
            
            # Show latest rates for BTC-USDT
            rates = self.manager.get_funding_rates('BTC-USDT')
            if rates:
                rate_strings = []
                for exchange, rate in rates.items():
                    rate_strings.append(f"{exchange}: {rate.rate:.6f}")
                
                self.logger.info(f"BTC-USDT: {' | '.join(rate_strings)}")
                update_count += 1
        
        self.logger.info(f"📊 Received {update_count} updates during monitoring period")
    
    async def get_status_summary(self):
        """Get and display status summary"""
        self.logger.info("\n📈 System Status Summary")
        self.logger.info("=" * 50)
        
        summary = self.manager.get_status_summary()
        
        self.logger.info(f"Total Connectors: {summary['total_connectors']}")
        self.logger.info(f"Connected Exchanges: {', '.join(summary['connected_exchanges'])}")
        self.logger.info(f"Total Symbols Tracked: {summary['total_symbols_tracked']}")
        
        self.logger.info("\nExchange Details:")
        for exchange, info in summary['exchanges'].items():
            last_update = info['last_update'].strftime('%H:%M:%S') if info['last_update'] else 'Never'
            self.logger.info(f"  {exchange:12}: {info['status']:12} | "
                           f"Symbols: {info['symbols_tracked']:2} | "
                           f"Last Update: {last_update}")
    
    async def run_full_test(self):
        """Run the complete test suite"""
        try:
            self.logger.info("🚀 Starting Comprehensive Connector Test Suite")
            self.logger.info("=" * 60)
            
            # Setup connectors
            setup_results = await self.setup_connectors()
            
            # Show which exchanges are connected
            connected = [ex for ex, success in setup_results.items() if success]
            if connected:
                self.logger.info(f"\n✅ Connected to: {', '.join(connected)}")
            else:
                self.logger.warning("\n⚠️  No exchanges connected! Update credentials to test.")
                self.logger.info("   Set environment variables or update exchange_configs in the script.")
                return
            
            # Wait for initial data
            self.logger.info("\n⏳ Waiting for initial data...")
            await asyncio.sleep(5)
            
            # Run all tests
            await self.test_exchange_info()
            await self.test_funding_rates()
            await self.test_arbitrage_opportunities()
            await self.test_balances()
            await self.test_health_check()
            await self.get_status_summary()
            
            # Monitor live updates
            await self.monitor_live_updates(30)
            
            self.logger.info("\n🎉 Test Suite Complete!")
            
        except Exception as e:
            self.logger.error(f"Error in test suite: {e}")
            raise
        
        finally:
            # Cleanup
            self.logger.info("\n🧹 Cleaning up...")
            await self.manager.stop_all()


async def quick_test():
    """Quick test without full monitoring"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    tester = ConnectorTester()
    
    try:
        self.logger.info("🔧 Quick Connector Test")
        self.logger.info("=" * 30)
        
        await tester.setup_connectors()
        await tester.test_exchange_info()
        await tester.get_status_summary()
        
    finally:
        await tester.manager.stop_all()


async def test_single_exchange():
    """Test a single exchange in detail"""
    
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("SingleExchangeTest")
    
    print("\nAvailable exchanges:")
    print("1. Binance")
    print("2. Bybit") 
    print("3. Hyperliquid")
    print("4. KuCoin")
    
    choice = input("\nChoose exchange to test (1-4): ")
    
    exchange_map = {
        '1': 'binance',
        '2': 'bybit', 
        '3': 'hyperliquid',
        '4': 'kucoin'
    }
    
    exchange = exchange_map.get(choice)
    if not exchange:
        print("Invalid choice")
        return
    
    manager = ConnectorManager()
    
    try:
        logger.info(f"Testing {exchange} connector...")
        
        # Use test credentials (will fail but tests the flow)
        test_creds = {
            'api_key': 'test_key',
            'api_secret': 'test_secret'
        }
        
        if exchange == 'kucoin':
            test_creds['passphrase'] = 'test_passphrase'
        
        success = await manager.add_connector(exchange, test_creds, sandbox=True)
        
        if success:
            logger.info("✅ Connector started successfully")
        else:
            logger.info("❌ Connector failed to start (expected with test credentials)")
        
        # Show exchange info
        info = manager.get_exchange_info()[exchange]
        logger.info(f"Exchange info: {info}")
        
    except Exception as e:
        logger.error(f"Expected error with test credentials: {e}")
    
    finally:
        await manager.stop_all()


if __name__ == "__main__":
    print("🚀 Funding Arbitrage Bot - Multi-Exchange Connector Test")
    print("=" * 60)
    
    print("\nTest Options:")
    print("1. Full test suite (requires real API keys)")
    print("2. Quick test (exchange info only)")
    print("3. Single exchange test")
    
    choice = input("\nChoose test type (1-3): ")
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if choice == "2":
        asyncio.run(quick_test())
    elif choice == "3":
        asyncio.run(test_single_exchange())
    else:
        tester = ConnectorTester()
        asyncio.run(tester.run_full_test())
    
    print("\n✅ Test completed!")
    print("\n💡 To enable exchange testing:")
    print("   1. Get API keys from exchange testnet/sandbox")
    print("   2. Set environment variables or update exchange_configs")
    print("   3. Set 'enabled': True for exchanges you want to test")


# ========== Configuration Guide ==========

"""
🔧 CONFIGURATION GUIDE

To test with real exchanges, you need to:

1. Get API Keys:
   - Binance: https://testnet.binancefuture.com/
   - Bybit: https://testnet.bybit.com/
   - Hyperliquid: https://app.hyperliquid-testnet.xyz/
   - KuCoin: https://sandbox-futures.kucoin.com/

2. Set Environment Variables:
   export BINANCE_API_KEY="your_key"
   export BINANCE_API_SECRET="your_secret"
   export BYBIT_API_KEY="your_key"
   export BYBIT_API_SECRET="your_secret"
   export HYPERLIQUID_API_KEY="your_wallet_address"
   export HYPERLIQUID_API_SECRET="your_private_key"
   export KUCOIN_API_KEY="your_key"
   export KUCOIN_API_SECRET="your_secret"
   export KUCOIN_PASSPHRASE="your_passphrase"

3. Update Script:
   In ConnectorTester.__init__(), set 'enabled': True for exchanges you want to test

4. Run:
   python test_all_connectors.py
"""
