#!/usr/bin/env python3
"""
Vérification post-redémarrage: colonnes anti-giveback + invert_signals sur les 2 derniers trades
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from dotenv import load_dotenv

def verify_post_restart():
    load_dotenv()
    
    pg_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD'),
    }
    
    print("🔍 Vérification post-redémarrage: Anti-Giveback + Invert Signals")
    print("=" * 70)
    
    try:
        conn = psycopg2.connect(**pg_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Récupérer les 2 derniers trades (les plus récents)
        print("\n📊 Analyse des 2 derniers trades...")
        cursor.execute("""
            SELECT 
                id, symbol, direction, entry_price, exit_price, exit_reason,
                pnl_pct, pnl_usdt, created_at, timestamp_exit,
                -- Colonnes anti-giveback config
                config_trailing_mfe_enabled,
                config_trailing_mfe_trigger_pct,
                config_trailing_mfe_lock_in_pct, 
                config_partial_tp_be_lock_in_pct,
                -- Colonnes anti-giveback tracking
                trailing_mfe_triggered,
                trailing_mfe_triggered_at,
                trailing_mfe_trigger_pnl_pct,
                trailing_mfe_trigger_price,
                trailing_mfe_new_sl,
                -- Colonnes protection existantes
                break_even_set,
                break_even_triggered_at,
                max_favorable_excursion,
                max_adverse_excursion
            FROM trades 
            ORDER BY created_at DESC 
            LIMIT 2
        """)
        
        recent_trades = cursor.fetchall()
        
        if not recent_trades:
            print("❌ Aucun trade trouvé dans la base")
            return False
            
        print(f"✅ {len(recent_trades)} trades récents analysés\n")
        
        # Analyser chaque trade
        for i, trade in enumerate(recent_trades, 1):
            print(f"🔹 TRADE #{i} - {trade['symbol']} {trade['direction']}")
            print(f"   ├─ ID: {trade['id']}")
            print(f"   ├─ Entry: {trade['entry_price']} → Exit: {trade['exit_price']}")
            print(f"   ├─ PnL: {trade['pnl_pct']:.2f}% ({trade['pnl_usdt']:.4f} USDT)")
            print(f"   ├─ Raison: {trade['exit_reason']}")
            print(f"   ├─ Créé: {trade['created_at']}")
            if trade['timestamp_exit']:
                duration = (trade['timestamp_exit'] - trade['created_at']).total_seconds()
                print(f"   ├─ Durée: {duration:.0f}s")
            
            # Vérifier colonnes anti-giveback CONFIG
            print(f"   │")
            print(f"   ├─ 🛡️ CONFIG ANTI-GIVEBACK:")
            ag_config_filled = 0
            ag_config_total = 4
            
            if trade['config_trailing_mfe_enabled'] is not None:
                print(f"   │   ├─ trailing_mfe_enabled: {trade['config_trailing_mfe_enabled']}")
                ag_config_filled += 1
            else:
                print(f"   │   ├─ trailing_mfe_enabled: ❌ NULL")
                
            if trade['config_trailing_mfe_trigger_pct'] is not None:
                print(f"   │   ├─ trailing_mfe_trigger_pct: {trade['config_trailing_mfe_trigger_pct']:.2f}%")
                ag_config_filled += 1
            else:
                print(f"   │   ├─ trailing_mfe_trigger_pct: ❌ NULL")
                
            if trade['config_trailing_mfe_lock_in_pct'] is not None:
                print(f"   │   ├─ trailing_mfe_lock_in_pct: {trade['config_trailing_mfe_lock_in_pct']:.2f}%")
                ag_config_filled += 1
            else:
                print(f"   │   ├─ trailing_mfe_lock_in_pct: ❌ NULL")
                
            if trade['config_partial_tp_be_lock_in_pct'] is not None:
                print(f"   │   └─ partial_tp_be_lock_in_pct: {trade['config_partial_tp_be_lock_in_pct']:.2f}%")
                ag_config_filled += 1
            else:
                print(f"   │   └─ partial_tp_be_lock_in_pct: ❌ NULL")
            
            config_coverage = ag_config_filled / ag_config_total * 100
            print(f"   │   📋 Couverture config: {ag_config_filled}/{ag_config_total} ({config_coverage:.0f}%)")
            
            # Vérifier colonnes anti-giveback TRACKING
            print(f"   │")
            print(f"   ├─ 🎯 TRACKING ANTI-GIVEBACK:")
            ag_tracking_info = 0
            
            print(f"   │   ├─ trailing_mfe_triggered: {trade['trailing_mfe_triggered']}")
            if trade['trailing_mfe_triggered']:
                ag_tracking_info += 1
                if trade['trailing_mfe_triggered_at']:
                    print(f"   │   ├─ trailing_mfe_triggered_at: {trade['trailing_mfe_triggered_at']}")
                if trade['trailing_mfe_trigger_pnl_pct']:
                    print(f"   │   ├─ trigger_pnl_pct: {trade['trailing_mfe_trigger_pnl_pct']:.2f}%")
                if trade['trailing_mfe_trigger_price']:
                    print(f"   │   ├─ trigger_price: {trade['trailing_mfe_trigger_price']}")
                if trade['trailing_mfe_new_sl']:
                    print(f"   │   └─ new_sl: {trade['trailing_mfe_new_sl']}")
            else:
                print(f"   │   └─ (Trailing MFE non déclenché)")
            
            # Vérifier protections existantes
            print(f"   │")
            print(f"   ├─ 🔒 PROTECTIONS CLASSIQUES:")
            print(f"   │   ├─ break_even_set: {trade['break_even_set']}")
            if trade['break_even_triggered_at']:
                print(f"   │   ├─ break_even_triggered_at: {trade['break_even_triggered_at']}")
            if trade['max_favorable_excursion']:
                print(f"   │   ├─ MFE: {trade['max_favorable_excursion']:.2f}%")
            if trade['max_adverse_excursion']:
                print(f"   │   └─ MAE: {trade['max_adverse_excursion']:.2f}%")
            
            # Analyse giveback potentiel
            pnl = trade['pnl_pct'] or 0
            mfe = trade['max_favorable_excursion'] or 0
            be_set = trade['break_even_set'] or False
            mfe_triggered = trade['trailing_mfe_triggered'] or False
            
            print(f"   │")
            if (be_set or mfe_triggered) and pnl < 0 and mfe > 0.05:
                gap = mfe - pnl
                print(f"   └─ ⚠️ GIVEBACK DÉTECTÉ: MFE {mfe:.2f}% → PnL {pnl:.2f}% (gap: {gap:.2f}%)")
            elif (be_set or mfe_triggered) and pnl >= 0:
                print(f"   └─ ✅ Protection réussie: MFE {mfe:.2f}% → PnL {pnl:.2f}%")
            elif mfe > 0.15 and pnl < -0.1:
                print(f"   └─ 🔴 Gestion problématique: MFE {mfe:.2f}% → PnL {pnl:.2f}% (pas de protection)")
            else:
                print(f"   └─ 📊 Trade standard")
            
            print("")
        
        # Statistiques globales sur plus de trades récents
        print("\n" + "=" * 70)
        print("📈 STATISTIQUES ANTI-GIVEBACK (10 derniers trades)")
        print("=" * 70)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                COUNT(config_trailing_mfe_enabled) as has_config,
                SUM(CASE WHEN trailing_mfe_triggered = true THEN 1 ELSE 0 END) as mfe_triggered_count,
                SUM(CASE WHEN break_even_set = true THEN 1 ELSE 0 END) as be_set_count,
                AVG(CASE WHEN config_trailing_mfe_trigger_pct IS NOT NULL THEN config_trailing_mfe_trigger_pct END) as avg_mfe_trigger_threshold,
                AVG(CASE WHEN config_trailing_mfe_lock_in_pct IS NOT NULL THEN config_trailing_mfe_lock_in_pct END) as avg_mfe_lock_in_pct
            FROM (
                SELECT * FROM trades ORDER BY created_at DESC LIMIT 10
            ) recent_trades
        """)
        
        stats = cursor.fetchone()
        if stats:
            print(f"Total trades récents: {stats['total_trades']}")
            print(f"Config anti-giveback remplie: {stats['has_config']}/{stats['total_trades']} ({stats['has_config']/stats['total_trades']*100:.0f}%)")
            print(f"Trailing MFE déclenché: {stats['mfe_triggered_count']} fois")
            print(f"Break-Even activé: {stats['be_set_count']} fois")
            if stats['avg_mfe_trigger_threshold']:
                print(f"Seuil MFE moyen configuré: {stats['avg_mfe_trigger_threshold']:.2f}%")
            if stats['avg_mfe_lock_in_pct']:
                print(f"Lock-in moyen configuré: {stats['avg_mfe_lock_in_pct']:.2f}%")
        
        # Vérifier invert_signals sur les récents trades
        print(f"\n🔄 VÉRIFICATION INVERT_SIGNALS:")
        cursor.execute("""
            SELECT symbol, direction, COUNT(*) as count
            FROM trades 
            WHERE created_at > NOW() - INTERVAL '1 hour'
            GROUP BY symbol, direction
            ORDER BY count DESC
        """)
        
        direction_stats = cursor.fetchall()
        if direction_stats:
            print("Directions récentes (dernière heure):")
            long_count = sum(row['count'] for row in direction_stats if row['direction'] == 'LONG')
            short_count = sum(row['count'] for row in direction_stats if row['direction'] == 'SHORT')
            total_recent = long_count + short_count
            
            if total_recent > 0:
                print(f"  LONG: {long_count}/{total_recent} ({long_count/total_recent*100:.0f}%)")
                print(f"  SHORT: {short_count}/{total_recent} ({short_count/total_recent*100:.0f}%)")
                print("  (Si invert_signals=true actif, vérifier si distribution diffère de l'historique)")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        return False

if __name__ == "__main__":
    success = verify_post_restart()
    if success:
        print("\n✅ Vérification post-redémarrage terminée")
    else:
        print("\n❌ Problèmes détectés lors de la vérification")
