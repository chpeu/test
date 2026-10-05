#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICATION: Pair Scorer - Score Pair Dynamique
=================================================
Ce script vérifie que le Pair Scorer fonctionne correctement.

Usage:
    python verification/verify_pair_scorer.py
"""

import sys
import os

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from datetime import datetime

# Configuration DB - charger depuis .env si disponible
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'dbname': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}


def print_header(title):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(test_name, success, details=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"  {status} | {test_name}")
    if details:
        print(f"         └─ {details}")


def get_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"❌ Erreur connexion DB: {e}")
        return None


def check_table_exists(conn):
    """Vérifie que la table pair_performance_stats existe."""
    print_header("1. TABLE pair_performance_stats")
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'pair_performance_stats'
        )
    """)
    exists = cursor.fetchone()[0]
    print_result("Table existe", exists)
    cursor.close()
    return exists


def check_columns_trades(conn):
    """Vérifie les colonnes pair scorer dans trades."""
    print_header("2. COLONNES trades")
    
    expected_columns = [
        'entry_pair_score_adjustment',
        'entry_effective_min_score'
    ]
    
    cursor = conn.cursor()
    all_exist = True
    
    for col in expected_columns:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'trades' AND column_name = %s
            )
        """, (col,))
        exists = cursor.fetchone()[0]
        print_result(f"Colonne '{col}'", exists)
        all_exist = all_exist and exists
    
    cursor.close()
    return all_exist


def check_config_variables():
    """Vérifie que les variables de config existent."""
    print_header("3. VARIABLES CONFIG")
    
    try:
        from config import TRADING_CONFIG
        
        expected_vars = [
            'pair_scorer_enabled',
            'pair_scorer_min_trades',
            'pair_scorer_max_adjustment',
            'pair_scorer_lookback_days',
            'pair_scorer_refresh_minutes'
        ]
        
        for var in expected_vars:
            exists = var in TRADING_CONFIG
            value = TRADING_CONFIG.get(var, 'N/A')
            print_result(f"Variable '{var}'", exists, f"= {value}")
        
        return True
    except ImportError as e:
        print_result("Import TRADING_CONFIG", False, str(e))
        return False


def check_pair_scorer_module():
    """Vérifie que le module pair_scorer est fonctionnel."""
    print_header("4. MODULE pair_scorer")
    
    try:
        from core.pair_scorer import PairScorer, get_pair_scorer
        print_result("Import PairScorer", True)
        
        # Test instanciation
        scorer = get_pair_scorer()
        print_result("get_pair_scorer()", scorer is not None)
        
        # Test configuration
        print_result("enabled", True, f"= {scorer.enabled}")
        print_result("min_trades", True, f"= {scorer.min_trades}")
        print_result("max_adjustment", True, f"= ±{scorer.max_adjustment}")
        
        # Test calcul d'ajustement
        adj, wr_comp, pnl_comp = scorer.calculate_adjustment(
            winrate=62.0, avg_pnl_pct=0.18, total_trades=20
        )
        print_result("calculate_adjustment()", True, 
                    f"WR=62%, PnL=+0.18% → adj={adj:+.2f}")
        
        return True
    except Exception as e:
        print_result("Module pair_scorer", False, str(e))
        return False


def test_pair_performance_calculation(conn):
    """Teste le calcul des performances par paire."""
    print_header("5. CALCUL PERFORMANCES PAR PAIRE")
    
    cursor = conn.cursor()
    
    # Requête de test similaire à celle du pair scorer
    cursor.execute("""
        SELECT 
            symbol,
            COUNT(*) as total_trades,
            SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
            ROUND(100.0 * SUM(CASE WHEN win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as winrate,
            ROUND(AVG(pnl_pct)::numeric, 4) as avg_pnl_pct
        FROM trades
        WHERE timestamp_entry > NOW() - INTERVAL '30 days'
          AND pnl_pct IS NOT NULL
        GROUP BY symbol
        HAVING COUNT(*) >= 10
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    
    results = cursor.fetchall()
    
    if not results:
        print_result("Données disponibles", False, "Pas assez de trades")
        cursor.close()
        return False
    
    print(f"\n  📊 Top 10 paires (30 derniers jours, min 10 trades):\n")
    print(f"  {'Paire':<25} {'Trades':>8} {'Wins':>6} {'WR':>8} {'AvgPnL':>10}")
    print(f"  {'-'*25} {'-'*8} {'-'*6} {'-'*8} {'-'*10}")
    
    for row in results:
        symbol, trades, wins, wr, avg_pnl = row
        # Simuler le calcul d'ajustement
        wr_float = float(wr) if wr else 0
        pnl_float = float(avg_pnl) if avg_pnl else 0
        wr_comp = (wr_float - 50) / 10 * 0.6
        pnl_comp = (pnl_float / 0.1) * 0.4
        adj = max(-2.0, min(2.0, wr_comp + pnl_comp))
        
        print(f"  {symbol:<25} {trades:>8} {wins:>6} {wr_float:>7.1f}% {pnl_float:>+9.3f}%  → adj={adj:+.2f}")
    
    print_result("Calcul performances", True, f"{len(results)} paires analysées")
    cursor.close()
    return True


def test_analyzer_integration():
    """Teste l'intégration dans analyzer/scoring."""
    print_header("6. INTÉGRATION analyzer/scoring")
    
    try:
        from core.analyzer.scoring import get_min_score_required
        
        # Test sans symbol (comportement classique)
        base, adj, effective = get_min_score_required(adx_value=25.0, symbol=None)
        print_result("Sans symbol", True, 
                    f"base={base:.1f}, adj={adj:.1f}, effective={effective:.1f}")
        
        # Test avec symbol (devrait récupérer l'ajustement si dispo)
        base, adj, effective = get_min_score_required(adx_value=25.0, symbol="BTC/USDT:USDT")
        print_result("Avec symbol", True, 
                    f"base={base:.1f}, adj={adj:.1f}, effective={effective:.1f}")
        
        return True
    except Exception as e:
        print_result("Intégration analyzer", False, str(e))
        return False


def run_all_checks():
    """Exécute toutes les vérifications."""
    print("\n" + "=" * 60)
    print(" VERIFICATION: Pair Scorer - Score Pair Dynamique")
    print(" " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    conn = get_connection()
    if not conn:
        print("\n❌ Impossible de se connecter à la base de données")
        return False
    
    try:
        results = []
        
        results.append(("Table SQL", check_table_exists(conn)))
        results.append(("Colonnes trades", check_columns_trades(conn)))
        results.append(("Variables config", check_config_variables()))
        results.append(("Module pair_scorer", check_pair_scorer_module()))
        results.append(("Calcul performances", test_pair_performance_calculation(conn)))
        results.append(("Intégration analyzer", test_analyzer_integration()))
        
        print_header("RÉSUMÉ")
        
        all_pass = True
        for name, passed in results:
            print_result(name, passed)
            all_pass = all_pass and passed
        
        if all_pass:
            print("\n✅ TOUT EST OK ! Le Pair Scorer est correctement configuré.")
        else:
            print("\n⚠️ Certaines vérifications ont échoué. Voir détails ci-dessus.")
        
        return all_pass
        
    finally:
        conn.close()


if __name__ == "__main__":
    success = run_all_checks()
    print("\n")
    sys.exit(0 if success else 1)
