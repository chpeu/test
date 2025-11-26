#!/usr/bin/env python3
"""
Check Progress - Monitoring Parallèle Live Trading + EDA V2
Affiche statut actuel des deux pistes
"""

import os
import sys
import json
import psycopg2
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Couleurs
class C:
    G = '\033[92m'  # Green
    Y = '\033[93m'  # Yellow
    R = '\033[91m'  # Red
    B = '\033[94m'  # Blue
    BOLD = '\033[1m'
    RESET = '\033[0m'

def check_live_trading_status():
    """Vérifier status Live Trading"""
    print(f"\n{C.B}{C.BOLD}🔴 LIVE TRADING STATUS{C.RESET}")
    print("="*60)
    
    # 1. Vérifier API Keys
    api_key = os.getenv('MEXC_API_KEY', '')
    api_secret = os.getenv('MEXC_API_SECRET', '')
    
    if api_key and api_secret:
        print(f"{C.G}✅ API Keys configurées{C.RESET}: {api_key[:10]}...")
    else:
        print(f"{C.R}❌ API Keys manquantes{C.RESET}")
        return
    
    # 2. Vérifier config live
    config_file = Path("config_live_persistent.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        mode = config.get('trading_mode', 'PAPER')
        dry_run = config.get('dry_run', True)
        
        print(f"{C.G}✅ Config Live trouvée{C.RESET}")
        print(f"   Mode: {mode} | Dry-Run: {dry_run}")
    else:
        print(f"{C.Y}⚠️  config_live_persistent.json manquant{C.RESET}")
    
    # 3. Vérifier stats via PostgreSQL (si possible)
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', 5432),
            dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        
        cursor = conn.cursor()
        
        # Nombre de trades dernières 24h
        cursor.execute("""
            SELECT COUNT(*) 
            FROM trades 
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        trades_24h = cursor.fetchone()[0]
        
        # Nombre total trades
        cursor.execute("SELECT COUNT(*) FROM trades")
        total_trades = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        print(f"{C.G}✅ PostgreSQL connecté{C.RESET}")
        print(f"   Trades 24h: {trades_24h}")
        print(f"   Total trades: {total_trades}")
        
    except Exception as e:
        print(f"{C.Y}⚠️  PostgreSQL non disponible{C.RESET}: {str(e)[:50]}")

def check_eda_v2_status():
    """Vérifier status EDA V2"""
    print(f"\n{C.B}{C.BOLD}🔵 EDA V2 STATUS{C.RESET}")
    print("="*60)
    
    # 1. Vérifier modèle V2 existe
    model_path = Path("optimization/saved_models/xgboost_v2_latest.pkl")
    if model_path.exists():
        mod_time = datetime.fromtimestamp(model_path.stat().st_mtime)
        age = datetime.now() - mod_time
        
        print(f"{C.G}✅ Modèle V2 trouvé{C.RESET}")
        print(f"   Dernière MAJ: {mod_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"   Age: {age.days} jours, {age.seconds//3600} heures")
    else:
        print(f"{C.R}❌ Modèle V2 non trouvé{C.RESET}")
        print(f"{C.Y}   Action: Lancer entraînement V2{C.RESET}")
        return
    
    # 2. Vérifier métriques dans PostgreSQL
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', 5432),
            dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        
        cursor = conn.cursor()
        
        # Dernier modèle V2
        cursor.execute("""
            SELECT 
                model_name,
                test_r2,
                test_mae,
                test_f1,
                total_samples,
                trained_at
            FROM ml_models
            WHERE model_name LIKE 'xgboost_v2%'
            ORDER BY trained_at DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        
        if row:
            name, r2, mae, f1, samples, trained = row
            
            print(f"{C.G}✅ Métriques V2 dans PostgreSQL{C.RESET}")
            print(f"   Nom: {name}")
            print(f"   R² Test: {r2:.3f} {'✅' if r2 > 0.28 else '⚠️'}")
            print(f"   MAE Test: {mae:.3f}%")
            print(f"   F1 Test: {f1:.3f}")
            print(f"   Dataset: {samples} trades {'✅' if samples >= 100 else '⚠️'}")
            print(f"   Entraîné: {trained.strftime('%Y-%m-%d %H:%M')}")
            
            # Objectifs
            if r2 >= 0.30:
                print(f"\n{C.G}🎯 OBJECTIF ATTEINT: R² >= 0.30!{C.RESET}")
            elif r2 >= 0.28:
                print(f"\n{C.Y}🎯 Proche objectif: R² = {r2:.3f} (cible 0.30){C.RESET}")
            else:
                print(f"\n{C.R}🎯 Objectif manqué: R² = {r2:.3f} < 0.28{C.RESET}")
                print(f"{C.Y}   Action: Augmenter dataset ou créer features{C.RESET}")
        else:
            print(f"{C.Y}⚠️  Aucun modèle V2 dans PostgreSQL{C.RESET}")
        
        # Dataset disponible
        cursor.execute("""
            SELECT COUNT(*) 
            FROM trades 
            WHERE pnl_pct IS NOT NULL
              AND created_at > NOW() - INTERVAL '540 days'
              AND ABS(pnl_pct) >= 0.15
        """)
        available = cursor.fetchone()[0]
        
        print(f"\n{C.B}📊 Dataset Disponible (540j, |PNL|>=0.15%):{C.RESET}")
        print(f"   Trades: {available} {'✅' if available >= 150 else '⚠️'}")
        
        if available < 100:
            print(f"{C.R}   ⚠️  Dataset trop petit! Réduire threshold à 0.10{C.RESET}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"{C.Y}⚠️  PostgreSQL erreur{C.RESET}: {str(e)[:50]}")

def check_config():
    """Vérifier configuration actuelle"""
    print(f"\n{C.B}{C.BOLD}⚙️  CONFIGURATION{C.RESET}")
    print("="*60)
    
    # Vérifier config_overrides.json
    config_file = Path("config_overrides.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        v2_timeframe = config.get('ml_v2_timeframe_days', 'non défini')
        v2_threshold = config.get('ml_v2_marginal_threshold', 'non défini')
        v2_filter = config.get('ml_v2_filter_enabled', 'non défini')
        
        print(f"{C.G}✅ config_overrides.json{C.RESET}")
        print(f"   ml_v2_timeframe_days: {v2_timeframe} {'✅' if v2_timeframe == 540 else '⚠️'}")
        print(f"   ml_v2_marginal_threshold: {v2_threshold} {'✅' if v2_threshold == 0.15 else '⚠️'}")
        print(f"   ml_v2_filter_enabled: {v2_filter}")
    else:
        print(f"{C.Y}⚠️  config_overrides.json manquant{C.RESET}")

def print_recommendations():
    """Afficher recommandations"""
    print(f"\n{C.B}{C.BOLD}💡 RECOMMANDATIONS{C.RESET}")
    print("="*60)
    
    print("\n🔴 Live Trading:")
    print("  1. Vérifier logs: tail -f logs/backend.log | grep LIVE")
    print("  2. Interface: http://localhost:5173 → Live Trading Panel")
    print("  3. Stats API: curl http://localhost:8000/api/live/stats")
    
    print("\n🔵 EDA V2:")
    print("  1. Entraîner: curl -X POST http://localhost:8000/api/ml/train_v2")
    print("  2. Vérifier: curl http://localhost:8000/api/ml/models")
    print("  3. Analyser SQL: psql -d trade_cursor_ml")
    
    print("\n📊 Monitoring:")
    print("  - Relancer ce script: python check_progress.py")
    print("  - Logs temps réel: tail -f logs/backend.log")

def main():
    """Main"""
    print(f"\n{C.BOLD}{'='*60}{C.RESET}")
    print(f"{C.BOLD}Check Progress - Live Trading + EDA V2{C.RESET}")
    print(f"{C.BOLD}{'='*60}{C.RESET}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Vérifier .env
    if not Path(".env").exists():
        print(f"{C.R}❌ .env introuvable!{C.RESET}")
        return 1
    
    # Status des deux pistes
    check_live_trading_status()
    check_eda_v2_status()
    check_config()
    print_recommendations()
    
    print(f"\n{C.G}✅ Check terminé{C.RESET}\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
