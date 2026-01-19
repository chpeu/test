#!/usr/bin/env python3
"""
Script d'analyse Post-Exit - Phase 2
====================================

Calcule les targets ML optimaux à partir des données post-exit collectées.

Usage:
    python scripts/analyze_post_exit.py --min-trades 10

Output:
    - Statistiques globales
    - Distribution exit_efficiency
    - Targets ML calculés et sauvegardés dans DB
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any
from datetime import datetime

def calculate_ml_targets(trade_data: Dict[str, Any], post_exit_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcule les targets ML optimaux basés sur les données post-exit.
    
    Args:
        trade_data: Données du trade (entry_price, direction, etc.)
        post_exit_data: Données post-exit (mfe, mae, efficiency, etc.)
    
    Returns:
        dict avec ml_optimal_sl_pct, ml_optimal_trailing_trigger, etc.
    """
    targets = {}
    
    # Extraire les données nécessaires
    realized_pnl = float(post_exit_data.get('realized_pnl_pct') or 0)
    post_exit_mae = float(post_exit_data.get('post_exit_mae_pct') or 0)
    post_exit_mfe = float(post_exit_data.get('post_exit_mfe_pct') or 0)
    used_sl = float(post_exit_data.get('used_sl_pct') or 0.15)
    time_to_mfe = int(post_exit_data.get('time_to_mfe_sec') or 60)
    would_have_hit_tp = post_exit_data.get('would_have_hit_original_tp', False)
    
    # 1. SL optimal: basé sur MAE post-exit
    #    Si le prix a rebondi après notre exit, notre SL était peut-être trop serré
    if realized_pnl > 0:  # Trade gagnant
        # SL optimal = max(SL utilisé, |MAE post-exit| + marge de sécurité)
        targets['ml_optimal_sl_pct'] = max(used_sl, abs(post_exit_mae) * 1.1 + 0.02)
    else:  # Trade perdant
        # SL était peut-être trop large - réduire légèrement
        targets['ml_optimal_sl_pct'] = used_sl * 0.9
    
    # Bornes de sécurité: entre 0.08% et 0.50%
    targets['ml_optimal_sl_pct'] = max(0.08, min(0.50, targets['ml_optimal_sl_pct']))
    
    # 2. Trailing trigger optimal: basé sur timing MFE
    if post_exit_mfe > 0.5:  # Mouvement significatif après exit
        # On aurait dû rester plus longtemps → trigger plus haut
        targets['ml_optimal_trailing_trigger'] = abs(realized_pnl) * 0.8 if realized_pnl != 0 else 0.20
    else:
        # Exit était bon - trigger conservateur
        targets['ml_optimal_trailing_trigger'] = abs(realized_pnl) * 0.5 if realized_pnl != 0 else 0.15
    
    # Bornes: entre 0.10% et 0.50%
    targets['ml_optimal_trailing_trigger'] = max(0.10, min(0.50, targets['ml_optimal_trailing_trigger']))
    
    # 3. BE trigger optimal
    if realized_pnl > 0:
        # Basé sur le PnL réalisé
        targets['ml_optimal_be_trigger'] = realized_pnl * 0.4
    else:
        # Fallback conservateur
        targets['ml_optimal_be_trigger'] = 0.15
    
    # Bornes: entre 0.10% et 0.40%
    targets['ml_optimal_be_trigger'] = max(0.10, min(0.40, targets['ml_optimal_be_trigger']))
    
    # 4. Should use partial TP
    # Si le TP original aurait été touché, partial TP était une bonne idée
    targets['ml_should_use_partial'] = would_have_hit_tp
    
    return targets


def analyze_and_update_targets(min_trades: int = 10, force_recalculate: bool = False):
    """
    Analyse tous les trades post-exit et calcule les targets ML.
    
    Args:
        min_trades: Nombre minimum de trades requis
        force_recalculate: Si True, recalcule même si déjà calculé
    """
    print("=" * 80)
    print("ANALYSE POST-EXIT - PHASE 2: ML TARGETS")
    print("=" * 80)
    
    # Connexion PostgreSQL
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=5432,
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Compter les trades disponibles
        cursor.execute("SELECT COUNT(*) as count FROM trade_post_exit_analysis")
        total_trades = cursor.fetchone()['count']
        
        print(f"\n📊 Trades post-exit disponibles: {total_trades}")
        
        if total_trades < min_trades:
            print(f"⚠️ Pas assez de trades (minimum: {min_trades})")
            print(f"   Continuez à trader pour collecter plus de données.")
            return
        
        # 2. Récupérer les trades à analyser
        where_clause = "" if force_recalculate else "WHERE pea.ml_optimal_sl_pct IS NULL"
        
        query = f"""
            SELECT 
                pea.*,
                t.entry_price, 
                t.direction, 
                t.symbol
            FROM trade_post_exit_analysis pea
            JOIN trades t ON t.id::text = pea.trade_id::text
            {where_clause}
            ORDER BY pea.created_at DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print(f"\n✅ Tous les trades ont déjà leurs targets ML calculés.")
            print(f"   Utilisez --force pour recalculer.")
            return
        
        print(f"\n📊 {len(rows)} trades à analyser")
        print("-" * 80)
        
        # 3. Calculer les targets pour chaque trade
        updated_count = 0
        
        for row in rows:
            trade_data = {
                'entry_price': row['entry_price'],
                'direction': row['direction'],
                'symbol': row['symbol']
            }
            
            post_exit_data = dict(row)
            
            # Calculer les targets
            targets = calculate_ml_targets(trade_data, post_exit_data)
            
            # Afficher le résultat
            print(f"\n🔍 Trade {row['symbol']} (ID: {str(row['trade_id'])[:8]}...)")
            print(f"   Realized PnL: {row['realized_pnl_pct']:.2f}%")
            print(f"   Post-Exit MFE: {row['post_exit_mfe_pct']:.2f}%")
            print(f"   Post-Exit MAE: {row['post_exit_mae_pct']:.2f}%")
            print(f"   Exit Efficiency: {row['exit_efficiency_pct']:.1f}%")
            print(f"   Grade: {row['exit_timing_grade']}")
            print(f"   → ML Optimal SL: {targets['ml_optimal_sl_pct']:.3f}%")
            print(f"   → ML Optimal Trailing: {targets['ml_optimal_trailing_trigger']:.3f}%")
            print(f"   → ML Optimal BE: {targets['ml_optimal_be_trigger']:.3f}%")
            print(f"   → ML Use Partial: {targets['ml_should_use_partial']}")
            
            # Mettre à jour la DB
            cursor.execute("""
                UPDATE trade_post_exit_analysis
                SET 
                    ml_optimal_sl_pct = %s,
                    ml_optimal_trailing_trigger = %s,
                    ml_optimal_be_trigger = %s,
                    ml_should_use_partial = %s
                WHERE trade_id = %s
            """, (
                targets['ml_optimal_sl_pct'],
                targets['ml_optimal_trailing_trigger'],
                targets['ml_optimal_be_trigger'],
                targets['ml_should_use_partial'],
                row['trade_id']
            ))
            
            updated_count += 1
        
        conn.commit()
        
        # 4. Statistiques globales
        print("\n" + "=" * 80)
        print("📈 STATISTIQUES GLOBALES")
        print("=" * 80)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                AVG(exit_efficiency_pct) as avg_efficiency,
                AVG(regret_pct) as avg_regret,
                COUNT(CASE WHEN exit_timing_grade IN ('A+', 'A') THEN 1 END) as excellent_exits,
                AVG(ml_optimal_sl_pct) as avg_optimal_sl,
                AVG(ml_optimal_trailing_trigger) as avg_optimal_trailing,
                AVG(ml_optimal_be_trigger) as avg_optimal_be,
                COUNT(CASE WHEN ml_should_use_partial = true THEN 1 END) as should_use_partial_count
            FROM trade_post_exit_analysis
            WHERE ml_optimal_sl_pct IS NOT NULL
        """)
        
        stats = cursor.fetchone()
        
        print(f"\n📊 Métriques:")
        print(f"   - Total trades analysés: {stats['total_trades']}")
        print(f"   - Exit Efficiency moyenne: {stats['avg_efficiency']:.1f}%")
        print(f"   - Regret moyen: {stats['avg_regret']:.2f}%")
        print(f"   - Taux d'excellents exits (A+/A): {stats['excellent_exits']/stats['total_trades']*100:.1f}%")
        
        print(f"\n🎯 Targets ML moyens:")
        print(f"   - SL optimal moyen: {stats['avg_optimal_sl']:.3f}%")
        print(f"   - Trailing optimal moyen: {stats['avg_optimal_trailing']:.3f}%")
        print(f"   - BE optimal moyen: {stats['avg_optimal_be']:.3f}%")
        print(f"   - Devrait utiliser Partial TP: {stats['should_use_partial_count']}/{stats['total_trades']} trades")
        
        # 5. Distribution des grades
        cursor.execute("""
            SELECT 
                exit_timing_grade,
                COUNT(*) as count
            FROM trade_post_exit_analysis
            GROUP BY exit_timing_grade
            ORDER BY exit_timing_grade
        """)
        
        print(f"\n📊 Distribution des grades:")
        for row in cursor.fetchall():
            grade = row['exit_timing_grade'] or 'N/A'
            count = row['count']
            pct = count / stats['total_trades'] * 100
            bar = '█' * int(pct / 2)
            print(f"   {grade:3s}: {bar} {count} ({pct:.1f}%)")
        
        print("\n" + "=" * 80)
        print(f"✅ {updated_count} trades mis à jour avec succès!")
        print("=" * 80)
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Analyse Post-Exit et calcul des ML Targets (Phase 2)'
    )
    parser.add_argument(
        '--min-trades',
        type=int,
        default=10,
        help='Nombre minimum de trades requis (défaut: 10)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Forcer le recalcul même si déjà calculé'
    )
    
    args = parser.parse_args()
    
    analyze_and_update_targets(
        min_trades=args.min_trades,
        force_recalculate=args.force
    )


if __name__ == "__main__":
    main()
