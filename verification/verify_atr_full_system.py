"""
Verification Complete du Systeme ATR Optimization
=================================================

Ce script verifie que tous les composants fonctionnent correctement:
1. Configuration (parametres ATR)
2. Base de donnees (tables et colonnes)
3. Logger enrichi (trade_atr_metrics)
4. What-If Simulator
5. Handlers backend (main.py)
6. Frontend (VariablesPanel.svelte)

Usage: python verification/verify_atr_full_system.py
"""

import os
import sys
import json
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Colors for terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(title):
    print(f"\n{BLUE}{BOLD}{'=' * 70}{RESET}")
    print(f"{BLUE}{BOLD}{title}{RESET}")
    print(f"{BLUE}{BOLD}{'=' * 70}{RESET}")

def print_ok(msg):
    print(f"  {GREEN}[OK]{RESET} {msg}")

def print_fail(msg):
    print(f"  {RED}[FAIL]{RESET} {msg}")

def print_warn(msg):
    print(f"  {YELLOW}[WARN]{RESET} {msg}")

def print_info(msg):
    print(f"  {BLUE}[INFO]{RESET} {msg}")


class ATRSystemVerifier:
    """Verificateur complet du systeme ATR"""
    
    def __init__(self):
        self.results = {}
        self.errors = []
    
    def verify_all(self):
        """Executer toutes les verifications"""
        print_header("VERIFICATION SYSTEME ATR OPTIMIZATION")
        print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        checks = [
            ("1. Configuration", self.verify_config),
            ("2. Base de donnees", self.verify_database),
            ("3. Logger Enrichi", self.verify_logger),
            ("4. What-If Simulator", self.verify_whatif),
            ("5. Handlers Backend", self.verify_handlers),
            ("6. Frontend", self.verify_frontend),
            ("7. Integration End-to-End", self.verify_integration),
        ]
        
        for name, check_func in checks:
            print_header(name)
            try:
                result = check_func()
                self.results[name] = result
            except Exception as e:
                self.results[name] = False
                self.errors.append(f"{name}: {e}")
                print_fail(f"Exception: {e}")
        
        self.print_summary()
        return all(self.results.values())
    
    def verify_config(self):
        """Verifier les parametres de configuration"""
        from config import TRADING_CONFIG
        
        required_params = [
            ('trailing_distance_atr_mult', 0.3, 2.0),
            ('trailing_trigger_atr_mult', 0.5, 3.0),
            ('break_even_atr_mult', 0.2, 2.5),
            ('atr_mult_sl', 0.5, 3.0),
            ('atr_mult_tp', 1.0, 5.0),
            ('stagnation_exit_timeout_seconds', 60, 1800),
            ('stagnation_exit_min_pnl_to_stay', -1.0, 1.0),
        ]
        
        all_ok = True
        for param, min_val, max_val in required_params:
            value = TRADING_CONFIG.get(param)
            if value is None:
                print_fail(f"{param}: MANQUANT")
                all_ok = False
            elif not (min_val <= value <= max_val):
                print_warn(f"{param}: {value} (hors plage [{min_val}, {max_val}])")
            else:
                print_ok(f"{param}: {value}")
        
        # Verifier config_overrides.json
        try:
            with open('config_overrides.json', 'r') as f:
                overrides = json.load(f)
            
            if 'trailing_distance_atr_mult' in overrides:
                print_ok(f"config_overrides.json: trailing_distance_atr_mult = {overrides['trailing_distance_atr_mult']}")
            else:
                print_warn("config_overrides.json: trailing_distance_atr_mult absent")
        except Exception as e:
            print_fail(f"config_overrides.json: {e}")
            all_ok = False
        
        return all_ok
    
    def verify_database(self):
        """Verifier les tables et colonnes SQL"""
        import psycopg2
        from dotenv import load_dotenv
        load_dotenv()
        
        try:
            conn = psycopg2.connect(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=int(os.getenv('POSTGRES_PORT', '5432')),
                database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
                user=os.getenv('POSTGRES_USER', 'postgres'),
                password=os.getenv('POSTGRES_PASSWORD', '')
            )
            cur = conn.cursor()
            print_ok("Connexion PostgreSQL etablie")
            
            # Verifier table trade_atr_metrics
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = 'trade_atr_metrics'
            """)
            if cur.fetchone()[0] > 0:
                print_ok("Table trade_atr_metrics existe")
                
                # Verifier colonnes cles
                cur.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'trade_atr_metrics'
                """)
                columns = [row[0] for row in cur.fetchall()]
                
                required_cols = [
                    'param_trailing_distance_mult',
                    'market_volatility_state',
                    'market_trend_state',
                    'pnl_if_no_be',
                    'pnl_if_no_trailing',
                    'sl_efficiency',
                    'trailing_capture_pct'
                ]
                
                for col in required_cols:
                    if col in columns:
                        print_ok(f"  Colonne {col}: presente")
                    else:
                        print_fail(f"  Colonne {col}: MANQUANTE")
                        return False
            else:
                print_fail("Table trade_atr_metrics MANQUANTE")
                return False
            
            # Verifier vue v_atr_optimization_summary
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.views 
                WHERE table_name = 'v_atr_optimization_summary'
            """)
            if cur.fetchone()[0] > 0:
                print_ok("Vue v_atr_optimization_summary existe")
            else:
                print_warn("Vue v_atr_optimization_summary absente")
            
            cur.close()
            conn.close()
            return True
            
        except Exception as e:
            print_fail(f"Erreur DB: {e}")
            return False
    
    def verify_logger(self):
        """Verifier le logger enrichi"""
        try:
            from core.postgresql_datalogger import PostgreSQLDataLogger
            print_ok("Import PostgreSQLDataLogger OK")
            
            # Verifier methode log_trade_atr_metrics
            if hasattr(PostgreSQLDataLogger, 'log_trade_atr_metrics'):
                print_ok("Methode log_trade_atr_metrics presente")
            else:
                print_fail("Methode log_trade_atr_metrics MANQUANTE")
                return False
            
            # Verifier que la methode est appelee dans log_trade
            with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'self.log_trade_atr_metrics(trade_id' in content:
                print_ok("Appel log_trade_atr_metrics dans log_trade")
            else:
                print_fail("Appel log_trade_atr_metrics MANQUANT dans log_trade")
                return False
            
            return True
            
        except Exception as e:
            print_fail(f"Erreur logger: {e}")
            return False
    
    def verify_whatif(self):
        """Verifier le What-If Simulator"""
        try:
            from core.analysis.what_if_simulator import WhatIfSimulator, TradeData, process_trade_whatif
            print_ok("Import WhatIfSimulator OK")
            
            # Test simulation simple
            trade = TradeData(
                trade_id="test-123",
                symbol="TEST/USDT",
                direction="LONG",
                entry_price=100.0,
                exit_price=101.0,
                sl_price=99.0,
                tp_price=103.0,
                size_usdt=10.0,
                max_price=102.0,
                min_price=99.5,
                be_triggered=True,
                trailing_activated=False
            )
            
            simulator = WhatIfSimulator()
            result = simulator.simulate(trade)
            
            if result.pnl_if_no_be is not None:
                print_ok(f"Simulation What-If: pnl_if_no_be = {result.pnl_if_no_be:.3f}%")
            else:
                print_warn("Simulation What-If: pnl_if_no_be = None")
            
            if result.trailing_capture_pct is not None:
                print_ok(f"Simulation What-If: trailing_capture = {result.trailing_capture_pct:.1f}%")
            else:
                print_info("Simulation What-If: trailing_capture = N/A (pas de trailing)")
            
            return True
            
        except Exception as e:
            print_fail(f"Erreur What-If: {e}")
            return False
    
    def verify_handlers(self):
        """Verifier les handlers backend"""
        try:
            # Verifier main.py handlers
            with open('main.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            handlers = [
                ("trailing_distance_atr_mult handler", "'trailing_distance_atr_mult' in params"),
                ("Sync trailing_atr_multiplier", "TRADING_CONFIG['trailing_atr_multiplier'] = val"),
            ]
            
            all_ok = True
            for name, pattern in handlers:
                if pattern in content:
                    print_ok(f"Handler: {name}")
                else:
                    print_fail(f"Handler MANQUANT: {name}")
                    all_ok = False
            
            # Verifier effective_config
            from utils.effective_config import get_effective_value
            
            test_value = get_effective_value('atr_mult_sl')
            if test_value is not None:
                print_ok(f"get_effective_value('atr_mult_sl') = {test_value}")
            else:
                print_warn("get_effective_value('atr_mult_sl') = None")
            
            return all_ok
            
        except Exception as e:
            print_fail(f"Erreur handlers: {e}")
            return False
    
    def verify_frontend(self):
        """Verifier le frontend"""
        try:
            with open('frontend/src/lib/components/VariablesPanel.svelte', 'r', encoding='utf-8') as f:
                content = f.read()
            
            checks = [
                ("Slider trailing_distance_atr_mult", "trailing-distance-atr-mult"),
                ("Label Trailing Distance", "Trailing Distance"),
                ("Variables en cours", "trailing_distance_atr_mult:"),
            ]
            
            all_ok = True
            for name, pattern in checks:
                if pattern in content:
                    print_ok(f"Frontend: {name}")
                else:
                    print_fail(f"Frontend MANQUANT: {name}")
                    all_ok = False
            
            return all_ok
            
        except Exception as e:
            print_fail(f"Erreur frontend: {e}")
            return False
    
    def verify_integration(self):
        """Verifier l'integration end-to-end"""
        try:
            import psycopg2
            from dotenv import load_dotenv
            load_dotenv()
            
            conn = psycopg2.connect(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=int(os.getenv('POSTGRES_PORT', '5432')),
                database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
                user=os.getenv('POSTGRES_USER', 'postgres'),
                password=os.getenv('POSTGRES_PASSWORD', '')
            )
            cur = conn.cursor()
            
            # Compter les trades avec ATR metrics
            cur.execute("SELECT COUNT(*) FROM trade_atr_metrics")
            atr_count = cur.fetchone()[0]
            
            # Compter les trades avec What-If
            cur.execute("SELECT COUNT(*) FROM trade_atr_metrics WHERE pnl_if_no_be IS NOT NULL OR pnl_if_no_trailing IS NOT NULL")
            whatif_count = cur.fetchone()[0]
            
            # Compter les trades totaux
            cur.execute("SELECT COUNT(*) FROM trades")
            total_trades = cur.fetchone()[0]
            
            print_info(f"Trades totaux: {total_trades}")
            print_info(f"Trades avec ATR metrics: {atr_count}")
            print_info(f"Trades avec What-If: {whatif_count}")
            
            if atr_count > 0:
                print_ok(f"Integration OK: {atr_count} trades ont des ATR metrics")
            else:
                print_warn("Aucun trade avec ATR metrics (normal si pas de nouveaux trades)")
            
            if whatif_count > 0:
                print_ok(f"What-If OK: {whatif_count} trades ont des calculs What-If")
            else:
                print_warn("Aucun trade avec What-If (lancer backfill si necessaire)")
            
            # Verifier coherence
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN param_trailing_distance_mult IS NOT NULL THEN 1 END) as with_distance,
                    COUNT(CASE WHEN market_volatility_state IS NOT NULL THEN 1 END) as with_volatility
                FROM trade_atr_metrics
            """)
            row = cur.fetchone()
            
            if row[0] > 0:
                print_ok(f"Param trailing_distance_mult: {row[0]} entrees")
            if row[1] > 0:
                print_ok(f"Context volatility_state: {row[1]} entrees")
            
            cur.close()
            conn.close()
            return True
            
        except Exception as e:
            print_fail(f"Erreur integration: {e}")
            return False
    
    def print_summary(self):
        """Afficher le resume"""
        print_header("RESUME FINAL")
        
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        for name, result in self.results.items():
            if result:
                print_ok(name)
            else:
                print_fail(name)
        
        print(f"\n  {BOLD}Score: {passed}/{total} ({100*passed/total:.0f}%){RESET}")
        
        if self.errors:
            print(f"\n  {RED}Erreurs:{RESET}")
            for error in self.errors:
                print(f"    - {error}")
        
        if passed == total:
            print(f"\n  {GREEN}{BOLD}SYSTEME ATR OPTIMIZATION: OPERATIONNEL{RESET}")
        else:
            print(f"\n  {YELLOW}{BOLD}SYSTEME ATR OPTIMIZATION: VERIFICATIONS REQUISES{RESET}")


def main():
    verifier = ATRSystemVerifier()
    success = verifier.verify_all()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
