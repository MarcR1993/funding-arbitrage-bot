"""
CLI Interface - Interface en ligne de commande interactive
========================================================

Interface inspirée de Hummingbot pour configurer et contrôler
le bot d'arbitrage de funding rates de manière intuitive.
"""

import asyncio
import os
import sys
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

# Rich imports for beautiful CLI
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.prompt import Prompt, Confirm, FloatPrompt, IntPrompt
from rich.text import Text
from rich.align import Align
from rich.progress import Progress, SpinnerColumn, TextColumn

# Questionary for interactive prompts
import questionary
from questionary import Style

from ..bot.arbitrage_engine import ArbitrageEngine, EngineState
from ..models.config import FundingBotConfig, create_config
from ..models.position import Position
from ..models.opportunity import ArbitrageOpportunity


class FundingBotCLI:
    """
    Interface CLI interactive pour le bot d'arbitrage
    
    Fournit une interface utilisateur complète pour :
    - Configuration du bot
    - Contrôle du trading (start/stop)
    - Monitoring des positions
    - Visualisation des opportunités
    - Statistiques de performance
    """
    
    def __init__(self):
        """Initialise l'interface CLI"""
        self.console = Console()
        
        # Configuration et état
        self.config: Optional[FundingBotConfig] = None
        self.engine: Optional[ArbitrageEngine] = None
        self.config_file = "config/config.yaml"
        
        # Style questionary personnalisé
        self.custom_style = Style([
            ('qmark', 'fg:#ff0066 bold'),
            ('question', 'bold'),
            ('answer', 'fg:#44ff00 bold'),
            ('pointer', 'fg:#ff0066 bold'),
            ('highlighted', 'fg:#ff0066 bold'),
            ('selected', 'fg:#44ff00'),
            ('separator', 'fg:#cc5454'),
            ('instruction', ''),
            ('text', ''),
            ('disabled', 'fg:#858585 italic')
        ])
        
        # État de l'interface
        self.running = True
        self.auto_refresh = False
        self.refresh_interval = 5  # secondes
    
    # =============================================================================
    # MAIN INTERFACE
    # =============================================================================
    
    def clear_screen(self) -> None:
        """Efface l'écran"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def show_header(self) -> None:
        """Affiche l'en-tête du bot"""
        header_text = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                   🤖 FUNDING RATE ARBITRAGE BOT 🤖                          ║
║                          Professional Trading Interface                       ║
║                     Binance • KuCoin • Hyperliquid                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """
        self.console.print(header_text, style="bold cyan")
    
    def show_main_menu(self) -> None:
        """Affiche le menu principal"""
        
        # Statut du bot
        if self.engine:
            if self.engine.state == EngineState.RUNNING:
                status = "[green]🟢 RUNNING[/green]"
            elif self.engine.state == EngineState.STOPPED:
                status = "[red]🔴 STOPPED[/red]"
            elif self.engine.state == EngineState.ERROR:
                status = "[red]❌ ERROR[/red]"
            elif self.engine.state == EngineState.EMERGENCY_STOP:
                status = "[red]🚨 EMERGENCY[/red]"
            else:
                status = "[yellow]🟡 " + self.engine.state.value.upper() + "[/yellow]"
        else:
            status = "[gray]⚫ NOT INITIALIZED[/gray]"
        
        # Positions actives
        active_positions = 0
        if self.engine and self.engine.position_manager:
            active_positions = len(self.engine.position_manager.active_positions)
        
        # Opportunités actuelles
        current_opportunities = 0
        if self.engine and self.engine.funding_oracle:
            current_opportunities = len(self.engine.funding_oracle.get_current_opportunities())
        
        # Exchanges connectés
        connected_exchanges = 0
        total_exchanges = 0
        if self.engine:
            total_exchanges = len(self.engine.connectors)
            connected_exchanges = len([c for c in self.engine.connectors.values() if c.is_connected])
        
        table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
        table.add_column("Option", style="cyan", width=4)
        table.add_column("Description", style="white", width=45)
        table.add_column("Status", style="green", width=20)
        
        table.add_row("1", "🎛️  Configure Bot Settings", "⚙️ Ready")
        table.add_row("2", "🔗 Setup Exchange Connections", f"📡 {connected_exchanges}/{total_exchanges} Connected")
        table.add_row("3", "▶️  Start/Stop Trading Bot", status)
        table.add_row("4", "📊 View Active Positions", f"📈 {active_positions} Active")
        table.add_row("5", "💰 View Current Opportunities", f"🎯 {current_opportunities} Available")
        table.add_row("6", "📈 Performance & Statistics", "📊 Analytics")
        table.add_row("7", "🔍 Monitor Live (Auto-refresh)", "👀 Watch Mode")
        table.add_row("8", "🚨 Emergency Stop (Close All)", "⛔ Safety")
        table.add_row("9", "⚙️  Advanced Configuration", "🔧 Expert")
        table.add_row("0", "❌ Exit", "👋 Quit")
        
        panel = Panel(table, title="🎛️ Main Control Panel", border_style="cyan")
        self.console.print(panel)
    
    async def run(self) -> None:
        """Lance l'interface principale"""
        
        try:
            # Charger la configuration
            await self.load_configuration()
            
            while self.running:
                self.clear_screen()
                self.show_header()
                self.show_main_menu()
                
                choice = questionary.text(
                    "\n🔸 Enter your choice:",
                    style=self.custom_style
                ).ask()
                
                if not choice:
                    continue
                
                await self.handle_menu_choice(choice.strip())
                
        except KeyboardInterrupt:
            self.console.print("\n\n🛑 [yellow]Interface interrupted by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n\n❌ [red]Error: {e}[/red]")
        finally:
            await self.cleanup()
    
    async def handle_menu_choice(self, choice: str) -> None:
        """Gère les choix du menu principal"""
        
        if choice == "1":
            await self.configure_bot_settings()
        elif choice == "2":
            await self.setup_exchanges()
        elif choice == "3":
            await self.start_stop_bot()
        elif choice == "4":
            await self.view_active_positions()
        elif choice == "5":
            await self.view_opportunities()
        elif choice == "6":
            await self.view_performance()
        elif choice == "7":
            await self.monitor_live()
        elif choice == "8":
            await self.emergency_stop()
        elif choice == "9":
            await self.advanced_configuration()
        elif choice == "0":
            self.running = False
        else:
            self.console.print("❌ [red]Invalid choice![/red]")
            questionary.press_any_key_to_continue().ask()
    
    # =============================================================================
    # CONFIGURATION
    # =============================================================================
    
    async def load_configuration(self) -> None:
        """Charge la configuration du bot"""
        
        try:
            self.config = create_config(self.config_file, env_override=True)
            self.console.print("✅ [green]Configuration loaded successfully[/green]")
            
        except Exception as e:
            self.console.print(f"⚠️ [yellow]Could not load configuration: {e}[/yellow]")
            
            # Créer une configuration par défaut
            self.config = FundingBotConfig()
            self.console.print("📝 [blue]Using default configuration[/blue]")
    
    async def configure_bot_settings(self) -> None:
        """Configuration des paramètres du bot"""
        
        self.clear_screen()
        self.console.print("🎯 [bold cyan]Bot Configuration[/bold cyan]\n")
        
        if not self.config:
            self.config = FundingBotConfig()
        
        # Trading parameters
        self.console.print("💰 [bold yellow]Trading Parameters[/bold yellow]")
        
        tokens = questionary.checkbox(
            "Select trading tokens:",
            choices=["BTC", "ETH", "SOL", "AVAX", "ATOM", "DOT", "LINK", "UNI", "AAVE", "MATIC"],
            default=self.config.trading.tokens,
            style=self.custom_style
        ).ask()
        
        if tokens:
            self.config.trading.tokens = tokens
        
        position_size = questionary.text(
            "Position size per trade (USD):",
            default=str(self.config.trading.position_size_usd),
            style=self.custom_style
        ).ask()
        
        if position_size:
            self.config.trading.position_size_usd = float(position_size)
        
        max_positions = questionary.text(
            "Maximum concurrent positions:",
            default=str(self.config.trading.max_concurrent_positions),
            style=self.custom_style
        ).ask()
        
        if max_positions:
            self.config.trading.max_concurrent_positions = int(max_positions)
        
        # Risk management
        self.console.print("\n🛡️ [bold yellow]Risk Management[/bold yellow]")
        
        stop_loss = questionary.text(
            "Stop loss threshold (%):",
            default=str(abs(self.config.risk_management.stop_loss_threshold) * 100),
            style=self.custom_style
        ).ask()
        
        if stop_loss:
            self.config.risk_management.stop_loss_threshold = -float(stop_loss) / 100
        
        # Sauvegarder
        save_config = questionary.confirm(
            "Save configuration?",
            default=True,
            style=self.custom_style
        ).ask()
        
        if save_config:
            await self.save_configuration()
        
        self.show_configuration_summary()
        questionary.press_any_key_to_continue().ask()
    
    def show_configuration_summary(self) -> None:
        """Affiche un résumé de la configuration"""
        
        if not self.config:
            return
        
        summary = f"""
[bold cyan]Current Configuration:[/bold cyan]

💰 [yellow]Trading:[/yellow]
  • Tokens: {', '.join(self.config.trading.tokens)}
  • Position Size: ${self.config.trading.position_size_usd:,.0f}
  • Max Positions: {self.config.trading.max_concurrent_positions}
  • Min Spread: {self.config.trading.min_spread_threshold*100:.3f}%

🛡️ [yellow]Risk Management:[/yellow]
  • Stop Loss: {abs(self.config.risk_management.stop_loss_threshold)*100:.1f}%
  • Max Daily Loss: {abs(self.config.risk_management.max_daily_loss)*100:.1f}%
  • Max Position Age: {self.config.risk_management.max_position_age_hours}h

🏛️ [yellow]Exchanges:[/yellow]
  • Binance: {'✅' if self.config.exchanges.binance.enabled else '❌'}
  • KuCoin: {'✅' if self.config.exchanges.kucoin.enabled else '❌'}
  • Hyperliquid: {'✅' if self.config.exchanges.hyperliquid.enabled else '❌'}
        """
        
        panel = Panel(summary, title="⚙️ Configuration Summary", border_style="green")
        self.console.print(panel)
    
    async def save_configuration(self) -> None:
        """Sauvegarde la configuration"""
        
        try:
            # Créer le dossier config s'il n'existe pas
            Path("config").mkdir(exist_ok=True)
            
            # Sauvegarder en YAML
            config_dict = self.config.dict()
            
            import yaml
            with open(self.config_file, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            
            self.console.print("💾 [green]Configuration saved successfully![/green]")
            
        except Exception as e:
            self.console.print(f"❌ [red]Error saving configuration: {e}[/red]")
    
    # =============================================================================
    # BOT CONTROL
    # =============================================================================
    
    async def start_stop_bot(self) -> None:
        """Démarre ou arrête le bot"""
        
        if not self.config:
            self.console.print("❌ [red]No configuration loaded![/red]")
            questionary.press_any_key_to_continue().ask()
            return
        
        if not self.engine:
            # Initialiser le moteur
            self.console.print("🔧 [blue]Initializing trading engine...[/blue]")
            
            try:
                self.engine = ArbitrageEngine(self.config)
                
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console
                ) as progress:
                    
                    task = progress.add_task("Connecting to exchanges...", total=100)
                    
                    success = await self.engine.initialize()
                    progress.update(task, completed=100)
                
                if not success:
                    self.console.print("❌ [red]Failed to initialize engine![/red]")
                    self.engine = None
                    questionary.press_any_key_to_continue().ask()
                    return
                
                self.console.print("✅ [green]Engine initialized successfully![/green]")
                
            except Exception as e:
                self.console.print(f"❌ [red]Initialization error: {e}[/red]")
                self.engine = None
                questionary.press_any_key_to_continue().ask()
                return
        
        # Contrôle start/stop
        if self.engine.state == EngineState.RUNNING:
            # Arrêter le bot
            confirmed = questionary.confirm(
                "🛑 Stop the trading bot?",
                default=False,
                style=self.custom_style
            ).ask()
            
            if confirmed:
                self.console.print("🛑 [yellow]Stopping trading bot...[/yellow]")
                await self.engine.stop()
                self.console.print("✅ [green]Bot stopped successfully![/green]")
        
        else:
            # Démarrer le bot
            confirmed = questionary.confirm(
                "🚀 Start the trading bot?",
                default=True,
                style=self.custom_style
            ).ask()
            
            if confirmed:
                self.console.print("🚀 [green]Starting trading bot...[/green]")
                
                success = await self.engine.start()
                
                if success:
                    self.console.print("✅ [green]Bot started successfully![/green]")
                    await self.show_startup_summary()
                else:
                    self.console.print("❌ [red]Failed to start bot![/red]")
        
        questionary.press_any_key_to_continue().ask()
    
    async def show_startup_summary(self) -> None:
        """Affiche un résumé au démarrage"""
        
        if not self.engine:
            return
        
        status = self.engine.get_engine_status()
        
        summary = f"""
[bold green]🚀 Trading Bot Started Successfully![/bold green]

📊 [yellow]Engine Status:[/yellow]
  • State: {status['engine']['state'].upper()}
  • Connected Exchanges: {len([e for e in status['exchanges'].values() if e['connected']])}
  • Active Positions: {status['positions'].get('active_positions', 0)}
  • Current Opportunities: {status['oracle'].get('current_opportunities', 0)}

⚡ [yellow]Next Actions:[/yellow]
  • Bot will evaluate opportunities every {self.config.bot.evaluation_interval_seconds}s
  • Monitor positions continuously
  • Auto-close positions based on profit/risk criteria
  • Use option 7 to watch live monitoring
        """
        
        panel = Panel(summary, title="🎉 Startup Summary", border_style="green")
        self.console.print(panel)
    
    async def emergency_stop(self) -> None:
        """Arrêt d'urgence du bot"""
        
        if not self.engine or self.engine.state != EngineState.RUNNING:
            self.console.print("⚠️ [yellow]Bot is not running[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
        
        confirmed = questionary.confirm(
            "🚨 EMERGENCY STOP - This will close ALL positions immediately. Are you sure?",
            default=False,
            style=self.custom_style
        ).ask()
        
        if confirmed:
            self.console.print("🚨 [red]EMERGENCY STOP TRIGGERED![/red]")
            self.console.print("🔄 [yellow]Closing all positions...[/yellow]")
            
            await self.engine.stop(emergency=True)
            
            self.console.print("✅ [green]Emergency stop completed![/green]")
        
        questionary.press_any_key_to_continue().ask()
    
    # =============================================================================
    # MONITORING & DISPLAY
    # =============================================================================
    
    async def view_active_positions(self) -> None:
        """Affiche les positions actives"""
        
        self.clear_screen()
        self.console.print("📊 [bold cyan]Active Positions[/bold cyan]\n")
        
        if not self.engine or not self.engine.position_manager:
            self.console.print("⚠️ [yellow]Engine not initialized[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
        
        positions = self.engine.position_manager.get_active_positions()
        
        if not positions:
            self.console.print("💤 [yellow]No active positions[/yellow]")
        else:
            self.display_positions_table(positions)
        
        questionary.press_any_key_to_continue().ask()
    
    def display_positions_table(self, positions: List[Position]) -> None:
        """Affiche un tableau des positions"""
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=8)
        table.add_column("Token", style="yellow", width=6)
        table.add_column("Pair", style="white", width=18)
        table.add_column("Size", style="green", width=10)
        table.add_column("P&L", style="green", width=10)
        table.add_column("ROI%", style="green", width=8)
        table.add_column("Age", style="cyan", width=8)
        table.add_column("Health", style="blue", width=8)
        table.add_column("Status", style="green", width=10)
        
        for pos in positions:
            # Couleur du P&L
            pnl_color = "green" if pos.net_pnl >= 0 else "red"
            roi_color = "green" if pos.roi_percentage >= 0 else "red"
            
            # Status avec couleur
            if pos.is_profitable:
                status = "[green]🟢 Profitable[/green]"
            else:
                status = "[red]🔴 Loss[/red]"
            
            table.add_row(
                pos.id[:8],
                pos.token,
                pos.pair_name.replace('_', ' ↔ '),
                f"${pos.size_usd:,.0f}",
                f"[{pnl_color}]${pos.net_pnl:+.2f}[/{pnl_color}]",
                f"[{roi_color}]{pos.roi_percentage:+.2f}%[/{roi_color}]",
                f"{pos.age_hours:.1f}h",
                f"{pos.health_score:.0f}/100",
                status
            )
        
        self.console.print(table)
    
    async def view_opportunities(self) -> None:
        """Affiche les opportunités actuelles"""
        
        self.clear_screen()
        self.console.print("💰 [bold cyan]Current Opportunities[/bold cyan]\n")
        
        if not self.engine or not self.engine.funding_oracle:
            self.console.print("⚠️ [yellow]Engine not initialized[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
        
        opportunities = self.engine.funding_oracle.get_best_opportunities(10)
        
        if not opportunities:
            self.console.print("📭 [yellow]No opportunities found[/yellow]")
        else:
            self.display_opportunities_table(opportunities)
        
        questionary.press_any_key_to_continue().ask()
    
    def display_opportunities_table(self, opportunities: List[ArbitrageOpportunity]) -> None:
        """Affiche un tableau des opportunités"""
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Token", style="yellow", width=6)
        table.add_column("Pair", style="white", width=18)
        table.add_column("Spread", style="green", width=8)
        table.add_column("Daily Profit", style="green", width=12)
        table.add_column("Score", style="blue", width=8)
        table.add_column("Priority", style="cyan", width=10)
        table.add_column("Age", style="gray", width=8)
        table.add_column("Executable", style="green", width=12)
        
        for opp in opportunities:
            # Couleur selon la priorité
            priority_colors = {
                "low": "gray",
                "medium": "yellow", 
                "high": "orange",
                "critical": "red"
            }
            priority_color = priority_colors.get(opp.priority.value, "white")
            
            executable = "[green]✅ Yes[/green]" if opp.should_execute() else "[red]❌ No[/red]"
            
            table.add_row(
                opp.token,
                opp.pair_name.replace('_', ' ↔ '),
                f"{opp.spread*100:.3f}%",
                f"${opp.expected_daily_profit:.2f}",
                f"{opp.score:.1f}",
                f"[{priority_color}]{opp.priority.value.upper()}[/{priority_color}]",
                f"{opp.age_minutes:.1f}m",
                executable
            )
        
        self.console.print(table)
    
    async def view_performance(self) -> None:
        """Affiche les statistiques de performance"""
        
        self.clear_screen()
        self.console.print("📈 [bold cyan]Performance & Statistics[/bold cyan]\n")
        
        if not self.engine:
            self.console.print("⚠️ [yellow]Engine not initialized[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
        
        # Statistiques du moteur
        status = self.engine.get_engine_status()
        perf = self.engine.get_performance_summary()
        
        # Affichage des métriques
        self.display_performance_summary(status, perf)
        
        questionary.press_any_key_to_continue().ask()
    
    def display_performance_summary(self, status: Dict, perf: Dict) -> None:
        """Affiche le résumé de performance"""
        
        # Métriques principales
        uptime_hours = status['engine']['uptime_seconds'] / 3600
        success_rate = (status['engine']['successful_cycles'] / max(1, status['engine']['total_cycles'])) * 100
        
        summary = f"""
[bold yellow]🤖 Engine Metrics:[/bold yellow]
  • Uptime: {uptime_hours:.1f} hours
  • Total Cycles: {status['engine']['total_cycles']}
  • Success Rate: {success_rate:.1f}%
  • Errors: {status['engine']['error_count']}

[bold yellow]💰 Trading Performance:[/bold yellow]
  • Total P&L: ${perf.get('total_pnl', 0):.2f}
  • Net P&L: ${perf.get('net_pnl', 0):.2f}
  • ROI: {perf.get('roi_percentage', 0):.2f}%
  • Win Rate: {perf.get('win_rate', 0)*100:.1f}%

[bold yellow]📊 Position Stats:[/bold yellow]
  • Active Positions: {status['positions'].get('active_positions', 0)}
  • Total Opened: {status['positions'].get('total_positions_opened', 0)}
  • Total Closed: {status['positions'].get('total_positions_closed', 0)}
  • Avg Age: {perf.get('avg_position_age_hours', 0):.1f}h

[bold yellow]🌐 Exchange Status:[/bold yellow]
        """
        
        # Ajouter le statut des exchanges
        for exchange, exchange_status in status['exchanges'].items():
            status_icon = "🟢" if exchange_status['connected'] else "🔴"
            summary += f"  • {exchange.title()}: {status_icon} {'Connected' if exchange_status['connected'] else 'Disconnected'}\n"
        
        panel = Panel(summary, title="📈 Performance Dashboard", border_style="blue")
        self.console.print(panel)
    
    # =============================================================================
    # LIVE MONITORING
    # =============================================================================
    
    async def monitor_live(self) -> None:
        """Mode monitoring en temps réel"""
        
        if not self.engine:
            self.console.print("⚠️ [yellow]Engine not initialized[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
        
        self.console.print("👀 [green]Entering live monitoring mode...[/green]")
        self.console.print("💡 [blue]Press Ctrl+C to exit[/blue]\n")
        
        try:
            while True:
                self.clear_screen()
                self.show_header()
                
                # Afficher le dashboard en temps réel
                await self.display_live_dashboard()
                
                # Attendre avant la prochaine mise à jour
                await asyncio.sleep(self.refresh_interval)
                
        except KeyboardInterrupt:
            self.console.print("\n👋 [yellow]Exiting live monitoring mode[/yellow]")
            questionary.press_any_key_to_continue().ask()
    
    async def display_live_dashboard(self) -> None:
        """Affiche le dashboard en temps réel"""
        
        if not self.engine:
            return
        
        # Status global
        status = self.engine.get_engine_status()
        
        # Créer le layout
        layout = Layout()
        layout.split_column(
            Layout(name="status", size=8),
            Layout(name="positions", size=10),
            Layout(name="opportunities", size=10)
        )
        
        # Status panel
        engine_status = status['engine']['state'].upper()
        status_color = "green" if engine_status == "RUNNING" else "red"
        
        status_text = f"""
[bold {status_color}]Engine: {engine_status}[/bold {status_color}] | Active Positions: {status['positions'].get('active_positions', 0)} | Opportunities: {status['oracle'].get('current_opportunities', 0)}
Last Cycle: {status['engine'].get('last_cycle', 'Never')} | Total Cycles: {status['engine']['total_cycles']}
Daily P&L: {status['trading']['daily_pnl_percentage']:.2f}% | Positions Today: {status['trading']['positions_opened_today']}
        """
        
        layout["status"].update(Panel(status_text, title="🤖 Live Status", border_style="blue"))
        
        # Positions
        if self.engine.position_manager:
            positions = self.engine.position_manager.get_active_positions()
            if positions:
                pos_table = self.create_compact_positions_table(positions[:5])  # Top 5
                layout["positions"].update(Panel(pos_table, title="📊 Active Positions", border_style="green"))
            else:
                layout["opportunities"].update(Panel("No opportunities found", title="💰 Top Opportunities", border_style="gray"))
        
        # Afficher le layout
        self.console.print(layout)
        
        # Footer avec timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.console.print(f"\n🕒 Last Update: {timestamp} | Auto-refresh every {self.refresh_interval}s", style="dim")
    
    def create_compact_positions_table(self, positions: List[Position]) -> Table:
        """Crée un tableau compact des positions"""
        
        table = Table(show_header=True, header_style="bold white", show_lines=False)
        table.add_column("Token", width=6)
        table.add_column("Pair", width=15)
        table.add_column("P&L", width=10)
        table.add_column("ROI%", width=8)
        table.add_column("Age", width=8)
        
        for pos in positions:
            pnl_color = "green" if pos.net_pnl >= 0 else "red"
            roi_color = "green" if pos.roi_percentage >= 0 else "red"
            
            table.add_row(
                pos.token,
                pos.pair_name.replace('_', '-'),
                f"[{pnl_color}]${pos.net_pnl:+.2f}[/{pnl_color}]",
                f"[{roi_color}]{pos.roi_percentage:+.1f}%[/{roi_color}]",
                f"{pos.age_hours:.1f}h"
            )
        
        return table
    
    def create_compact_opportunities_table(self, opportunities: List[ArbitrageOpportunity]) -> Table:
        """Crée un tableau compact des opportunités"""
        
        table = Table(show_header=True, header_style="bold white", show_lines=False)
        table.add_column("Token", width=6)
        table.add_column("Pair", width=15)
        table.add_column("Spread", width=8)
        table.add_column("Score", width=8)
        table.add_column("Priority", width=10)
        
        for opp in opportunities:
            priority_colors = {
                "low": "gray",
                "medium": "yellow", 
                "high": "orange",
                "critical": "red"
            }
            priority_color = priority_colors.get(opp.priority.value, "white")
            
            table.add_row(
                opp.token,
                opp.pair_name.replace('_', '-'),
                f"{opp.spread*100:.3f}%",
                f"{opp.score:.1f}",
                f"[{priority_color}]{opp.priority.value.upper()}[/{priority_color}]"
            )
        
        return table
    
    # =============================================================================
    # ADVANCED CONFIGURATION
    # =============================================================================
    
    async def setup_exchanges(self) -> None:
        """Configuration des exchanges"""
        
        self.clear_screen()
        self.console.print("🏛️ [bold cyan]Exchange Configuration[/bold cyan]\n")
        
        self.console.print("⚠️ [yellow]Note: API keys should be set via environment variables:[/yellow]")
        self.console.print("• BINANCE_API_KEY, BINANCE_SECRET")
        self.console.print("• KUCOIN_API_KEY, KUCOIN_SECRET, KUCOIN_PASSPHRASE") 
        self.console.print("• HYPERLIQUID_PRIVATE_KEY, HYPERLIQUID_VAULT_ADDRESS\n")
        
        if not self.config:
            self.config = FundingBotConfig()
        
        # Configuration Binance
        binance_enabled = questionary.confirm(
            "Enable Binance Futures?",
            default=self.config.exchanges.binance.enabled,
            style=self.custom_style
        ).ask()
        
        self.config.exchanges.binance.enabled = binance_enabled
        
        if binance_enabled:
            testnet = questionary.confirm(
                "Use Binance Testnet?",
                default=self.config.exchanges.binance.testnet,
                style=self.custom_style
            ).ask()
            self.config.exchanges.binance.testnet = testnet
        
        # Configuration KuCoin
        kucoin_enabled = questionary.confirm(
            "Enable KuCoin Futures?",
            default=self.config.exchanges.kucoin.enabled,
            style=self.custom_style
        ).ask()
        
        self.config.exchanges.kucoin.enabled = kucoin_enabled
        
        if kucoin_enabled:
            sandbox = questionary.confirm(
                "Use KuCoin Sandbox?",
                default=self.config.exchanges.kucoin.sandbox,
                style=self.custom_style
            ).ask()
            self.config.exchanges.kucoin.sandbox = sandbox
        
        # Configuration Hyperliquid
        hyperliquid_enabled = questionary.confirm(
            "Enable Hyperliquid?",
            default=self.config.exchanges.hyperliquid.enabled,
            style=self.custom_style
        ).ask()
        
        self.config.exchanges.hyperliquid.enabled = hyperliquid_enabled
        
        if hyperliquid_enabled:
            testnet = questionary.confirm(
                "Use Hyperliquid Testnet?",
                default=self.config.exchanges.hyperliquid.testnet,
                style=self.custom_style
            ).ask()
            self.config.exchanges.hyperliquid.testnet = testnet
        
        # Test des connexions si demandé
        test_connections = questionary.confirm(
            "Test exchange connections now?",
            default=True,
            style=self.custom_style
        ).ask()
        
        if test_connections:
            await self.test_exchange_connections()
        
        # Sauvegarder
        save_config = questionary.confirm(
            "Save exchange configuration?",
            default=True,
            style=self.custom_style
        ).ask()
        
        if save_config:
            await self.save_configuration()
        
        questionary.press_any_key_to_continue().ask()
    
    async def test_exchange_connections(self) -> None:
        """Test les connexions aux exchanges"""
        
        self.console.print("\n🔗 [blue]Testing exchange connections...[/blue]\n")
        
        if not self.config:
            return
        
        # Créer temporairement un moteur pour tester
        try:
            test_engine = ArbitrageEngine(self.config)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                
                task = progress.add_task("Initializing...", total=100)
                success = await test_engine.initialize()
                progress.update(task, completed=100)
            
            if success:
                connected = await test_engine._test_all_connections()
                
                for exchange in ['binance', 'kucoin', 'hyperliquid']:
                    if getattr(self.config.exchanges, exchange).enabled:
                        if exchange in connected:
                            self.console.print(f"✅ [green]{exchange.title()}: Connected[/green]")
                        else:
                            self.console.print(f"❌ [red]{exchange.title()}: Failed[/red]")
                
                # Nettoyer
                await test_engine.stop()
            
        except Exception as e:
            self.console.print(f"❌ [red]Connection test failed: {e}[/red]")
    
    async def advanced_configuration(self) -> None:
        """Configuration avancée"""
        
        self.clear_screen()
        self.console.print("🔧 [bold cyan]Advanced Configuration[/bold cyan]\n")
        
        if not self.config:
            self.config = FundingBotConfig()
        
        # Options avancées
        options = [
            "🕐 Evaluation Interval",
            "📊 Logging Configuration", 
            "🔔 Telegram Notifications",
            "🛡️ Advanced Risk Settings",
            "💾 Export Configuration",
            "📁 Import Configuration",
            "🔄 Reset to Defaults"
        ]
        
        choice = questionary.select(
            "Select advanced option:",
            choices=options,
            style=self.custom_style
        ).ask()
        
        if choice and "Evaluation Interval" in choice:
            interval = questionary.text(
                "Evaluation interval (seconds):",
                default=str(self.config.bot.evaluation_interval_seconds),
                style=self.custom_style
            ).ask()
            
            if interval:
                self.config.bot.evaluation_interval_seconds = int(interval)
        
        elif choice and "Telegram" in choice:
            enabled = questionary.confirm(
                "Enable Telegram notifications?",
                default=self.config.monitoring.telegram.enabled,
                style=self.custom_style
            ).ask()
            
            self.config.monitoring.telegram.enabled = enabled
            
            if enabled:
                self.console.print("⚠️ [yellow]Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables[/yellow]")
        
        elif choice and "Reset" in choice:
            confirmed = questionary.confirm(
                "Reset all settings to defaults? This cannot be undone.",
                default=False,
                style=self.custom_style
            ).ask()
            
            if confirmed:
                self.config = FundingBotConfig()
                self.console.print("🔄 [green]Configuration reset to defaults[/green]")
        
        questionary.press_any_key_to_continue().ask()
    
    # =============================================================================
    # CLEANUP
    # =============================================================================
    
    async def cleanup(self) -> None:
        """Nettoyage avant fermeture"""
        
        if self.engine and self.engine.state == EngineState.RUNNING:
            self.console.print("\n🛑 [yellow]Stopping bot before exit...[/yellow]")
            await self.engine.stop()
        
        self.console.print("\n👋 [cyan]Thank you for using Funding Arbitrage Bot![/cyan]")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def main():
    """Point d'entrée principal de l'interface CLI"""
    
    try:
        cli = FundingBotCLI()
        await cli.run()
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())["positions"].update(Panel("No active positions", title="📊 Active Positions", border_style="gray"))
        
        # Opportunities
        if self.engine.funding_oracle:
            opportunities = self.engine.funding_oracle.get_best_opportunities(5)
            if opportunities:
                opp_table = self.create_compact_opportunities_table(opportunities)
                layout["opportunities"].update(Panel(opp_table, title="💰 Top Opportunities", border_style="yellow"))
            else:
                layout
