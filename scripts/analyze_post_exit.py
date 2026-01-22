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

# Paramètres actuels de la config (lus depuis config_overrides.json)
CURRENT_CONFIG = {
    'sl_percent': 0.15,
    'break_even_trigger': 0.20,
    'trailing_trigger_pnl': 0.20,
    'trailing_distance': 0.10
}

def load_current_config():
    """Charge les paramètres actuels depuis config_overrides.json"""
    import json
    import os
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config_overrides.json')
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return {
                'sl_percent': config.get('sl_percent', 0.15),
                'break_even_trigger': config.get('break_even_trigger', 0.20),
                'trailing_trigger_pnl': config.get('trailing_trigger_pnl', 0.20),
                'trailing_distance': config.get('trailing_distance', 0.10)
            }
    except:
        return CURRENT_CONFIG


def simulate_optimal_parameters(cursor) -> Dict[str, Any]:
    """
    Simule les performances si les paramètres ML optimaux avaient été utilisés.
    Compare les résultats actuels avec ceux qu'on aurait obtenus avec les params optimaux.
    
    Returns:
        Dict avec comparaisons actuelles vs optimales
    """
    try:
        # Charger les vrais paramètres actuels
        current_config = load_current_config()
        
        # Récupérer tous les trades avec leurs données post-exit et optimales
        cursor.execute("""
            SELECT 
                pea.*,
                t.entry_price,
                t.direction,
                t.symbol
            FROM trade_post_exit_analysis pea
            JOIN trades t ON t.id::text = pea.trade_id::text
            WHERE 
                pea.ml_optimal_sl_pct IS NOT NULL
                AND pea.post_exit_mfe_pct IS NOT NULL
                AND pea.post_exit_mae_pct IS NOT NULL
                AND pea.realized_pnl_pct IS NOT NULL
        """)
        
        trades = cursor.fetchall()
        if not trades:
            return None
        
        # Statistiques actuelles
        current_stats = {
            'total_trades': len(trades),
            'winning_trades': len([t for t in trades if float(t['realized_pnl_pct'] or 0) > 0]),
            'total_pnl': sum(float(t['realized_pnl_pct'] or 0) for t in trades),
            'total_efficiency': sum(float(t['exit_efficiency_pct'] or 0) for t in trades),
            'total_regret': sum(float(t['regret_pct'] or 0) for t in trades),
            'grade_distribution': {}
        }
        
        # Distribution actuelle des grades
        for trade in trades:
            grade = trade['exit_timing_grade'] or 'N/A'
            current_stats['grade_distribution'][grade] = current_stats['grade_distribution'].get(grade, 0) + 1
        
        # Simulation avec paramètres optimaux
        optimal_stats = {
            'total_trades': len(trades),
            'winning_trades': 0,
            'total_pnl': 0,
            'total_efficiency': 0,
            'total_regret': 0,
            'grade_distribution': {}
        }
        
        # Grouper les trades par configuration utilisée
        config_groups = {}
        
        for trade in trades:
            # Récupérer les paramètres RÉELS utilisés par ce trade
            trade_config = {
                'sl_percent': float(trade['used_sl_pct'] or current_config['sl_percent']),
                'break_even_trigger': float(trade['used_be_trigger'] or current_config['break_even_trigger']),
                'trailing_trigger_pnl': float(trade['used_trailing_trigger'] or current_config['trailing_trigger_pnl']),
            }
            
            # Clé de configuration pour grouper
            config_key = f"SL:{trade_config['sl_percent']:.2f}% BE:{trade_config['break_even_trigger']:.2f}%"
            if config_key not in config_groups:
                config_groups[config_key] = {'trades': 0, 'wins': 0, 'pnl': 0, 'optimal_pnl': 0}
            
            # Simuler avec les paramètres optimaux (en passant les params réels du trade)
            optimal_result = simulate_trade_with_optimal_params(trade, trade_config)
            
            if optimal_result['pnl'] > 0:
                optimal_stats['winning_trades'] += 1
            
            optimal_stats['total_pnl'] += optimal_result['pnl']
            optimal_stats['total_efficiency'] += optimal_result['efficiency']
            optimal_stats['total_regret'] += optimal_result['regret']
            
            grade = optimal_result['grade']
            optimal_stats['grade_distribution'][grade] = optimal_stats['grade_distribution'].get(grade, 0) + 1
            
            # Grouper par config
            realized_pnl = float(trade['realized_pnl_pct'] or 0)
            config_groups[config_key]['trades'] += 1
            if realized_pnl > 0:
                config_groups[config_key]['wins'] += 1
            config_groups[config_key]['pnl'] += realized_pnl
            config_groups[config_key]['optimal_pnl'] += optimal_result['pnl']
        
        # Calculer les comparaisons
        result = {
            'current_winrate': (current_stats['winning_trades'] / current_stats['total_trades']) * 100,
            'optimal_winrate': (optimal_stats['winning_trades'] / optimal_stats['total_trades']) * 100,
            'current_pnl_total': current_stats['total_pnl'],
            'optimal_pnl_total': optimal_stats['total_pnl'],
            'current_pnl_avg': current_stats['total_pnl'] / current_stats['total_trades'],
            'optimal_pnl_avg': optimal_stats['total_pnl'] / optimal_stats['total_trades'],
            'current_efficiency': current_stats['total_efficiency'] / current_stats['total_trades'],
            'optimal_efficiency': optimal_stats['total_efficiency'] / optimal_stats['total_trades'],
            'current_regret': current_stats['total_regret'] / current_stats['total_trades'],
            'optimal_regret': optimal_stats['total_regret'] / optimal_stats['total_trades'],
            'current_grade_distribution': {},
            'optimal_grade_distribution': {}
        }
        
        # Convertir distributions en pourcentages
        for grade, count in current_stats['grade_distribution'].items():
            result['current_grade_distribution'][grade] = {
                'count': count,
                'pct': (count / current_stats['total_trades']) * 100
            }
        
        for grade, count in optimal_stats['grade_distribution'].items():
            result['optimal_grade_distribution'][grade] = {
                'count': count,
                'pct': (count / optimal_stats['total_trades']) * 100
            }
        
        # Calculer les améliorations
        result['winrate_improvement'] = result['optimal_winrate'] - result['current_winrate']
        result['pnl_improvement'] = result['optimal_pnl_total'] - result['current_pnl_total']
        result['pnl_avg_improvement'] = result['optimal_pnl_avg'] - result['current_pnl_avg']
        result['efficiency_improvement'] = result['optimal_efficiency'] - result['current_efficiency']
        result['regret_improvement'] = result['optimal_regret'] - result['current_regret']
        
        # Ajouter les paramètres actuels utilisés pour la comparaison
        result['current_config'] = current_config
        
        # Ajouter les configs groupées
        result['config_groups'] = config_groups
        
        return result
        
    except Exception as e:
        print(f"⚠️ Erreur simulation: {e}")
        return None


def simulate_trade_with_optimal_params(trade: Dict[str, Any], current_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simule un trade individuel avec les paramètres ML optimaux.
    Utilise les vrais paramètres actuels depuis la config.
    
    La simulation est basée sur les données post-exit réelles pour estimer
    ce qui se serait passé avec des paramètres différents.
    
    Args:
        trade: Données du trade avec post-exit et ML targets
        current_config: Paramètres actuels depuis config_overrides.json
    
    Returns:
        Dict avec PnL, efficiency, regret et grade simulés
    """
    # Extraire les données du trade
    realized_pnl = float(trade['realized_pnl_pct'] or 0)
    post_exit_mfe = float(trade['post_exit_mfe_pct'] or 0)  # Max favorable après sortie
    post_exit_mae = float(trade['post_exit_mae_pct'] or 0)  # Max adverse après sortie
    current_efficiency = float(trade['exit_efficiency_pct'] or 50)
    
    # Paramètres ML optimaux calculés pour ce trade
    optimal_sl = float(trade['ml_optimal_sl_pct'] or 0.15)
    optimal_trailing = float(trade['ml_optimal_trailing_trigger'] or 0.15)
    optimal_be = float(trade['ml_optimal_be_trigger'] or 0.15)
    
    # Paramètres REELS utilisés (depuis config)
    used_sl = current_config['sl_percent']  # 0.15%
    used_be = current_config['break_even_trigger']  # 0.20%
    used_trailing = current_config['trailing_trigger_pnl']  # 0.20%
    
    # === SIMULATION BASÉE SUR LES DONNÉES POST-EXIT ===
    
    if realized_pnl > 0:
        # TRADE GAGNANT
        # Si post_exit_mfe > 0, on a quitté trop tôt → potentiel d'amélioration
        
        potential_gain = 0
        
        # Le MFE post-exit représente ce qu'on aurait pu gagner en plus
        if post_exit_mfe > 0:
            # Avec un BE/trailing optimal plus bas, on aurait capté une partie du MFE
            if optimal_be < used_be or optimal_trailing < used_trailing:
                # Estimation: on aurait capté 50-70% du MFE post-exit
                capture_ratio = 0.6
                potential_gain = post_exit_mfe * capture_ratio
        
        optimal_pnl = realized_pnl + potential_gain
        
    else:
        # TRADE PERDANT
        # Plusieurs scénarios possibles
        
        if post_exit_mfe > abs(realized_pnl):
            # CAS 1: Le prix est remonté PLUS que notre perte après sortie
            # → Avec un SL plus large, on aurait pu être gagnant !
            if optimal_sl > used_sl:
                # Estimation: on aurait capté une partie du rebond
                optimal_pnl = post_exit_mfe * 0.5  # Devient gagnant
            else:
                # SL optimal pas plus large, mais le prix a rebondi
                # → On serait quand même sorti en perte, mais le SL aurait limité
                optimal_pnl = realized_pnl * 0.85  # Amélioration marginale
        
        elif post_exit_mfe > 0:
            # CAS 2: Le prix a un peu remonté mais pas assez
            # → Amélioration possible si SL différent
            if optimal_sl > used_sl:
                # Un SL plus large aurait laissé respirer
                recovery = min(post_exit_mfe * 0.7, abs(realized_pnl) * 0.3)
                optimal_pnl = realized_pnl + recovery
            else:
                optimal_pnl = realized_pnl * 0.95  # Légère amélioration
        
        else:
            # CAS 3: Le prix a continué à baisser (post_exit_mfe ≈ 0)
            # → Le SL était bien placé, pas d'amélioration significative
            if optimal_sl < used_sl:
                # Un SL plus serré aurait limité la perte
                improvement = min(used_sl - optimal_sl, abs(realized_pnl) * 0.2)
                optimal_pnl = realized_pnl + improvement
            else:
                optimal_pnl = realized_pnl  # Pas d'amélioration
    
    # Calculer les métriques optimales
    return _calculate_optimal_metrics(
        optimal_pnl=optimal_pnl,
        post_exit_mfe=post_exit_mfe,
        current_efficiency=current_efficiency,
        realized_pnl=realized_pnl
    )


def _calculate_optimal_metrics(optimal_pnl: float, post_exit_mfe: float, 
                                current_efficiency: float = 50, realized_pnl: float = 0) -> Dict[str, Any]:
    """
    Calcule les métriques (efficiency, regret, grade) pour un PnL optimal donné.
    Compare avec les métriques actuelles pour s'assurer que l'optimal est meilleur.
    """
    # Calculer l'amélioration du PnL
    pnl_improvement = optimal_pnl - realized_pnl
    
    # Calculer efficiency optimal basé sur l'amélioration
    if optimal_pnl > realized_pnl:
        # On a amélioré → efficiency augmente proportionnellement
        improvement_ratio = pnl_improvement / max(abs(realized_pnl), 0.01)
        efficiency_boost = min(improvement_ratio * 20, 30)  # Max +30%
        optimal_efficiency = min(100, current_efficiency + efficiency_boost)
    elif optimal_pnl == realized_pnl:
        # Pas d'amélioration possible
        optimal_efficiency = current_efficiency
    else:
        # Cas théorique où optimal < actuel (ne devrait pas arriver)
        optimal_efficiency = current_efficiency
    
    # Calculer regret optimal (réduit car on capture plus)
    if optimal_pnl > 0:
        # MFE résiduel après avoir capté le gain optimal
        remaining_mfe = max(0, post_exit_mfe - pnl_improvement)
        optimal_regret = remaining_mfe
    else:
        # Toujours en perte, regret = MFE + perte restante
        optimal_regret = max(0, post_exit_mfe - pnl_improvement)
    
    # Calculer le grade optimal basé sur l'efficiency
    if optimal_efficiency >= 85:
        grade = 'A+'
    elif optimal_efficiency >= 70:
        grade = 'A'
    elif optimal_efficiency >= 55:
        grade = 'B+'
    elif optimal_efficiency >= 45:
        grade = 'B'
    elif optimal_efficiency >= 35:
        grade = 'C'
    elif optimal_efficiency >= 25:
        grade = 'D'
    else:
        grade = 'F'
    
    return {
        'pnl': optimal_pnl,
        'efficiency': optimal_efficiency,
        'regret': optimal_regret,
        'grade': grade
    }


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
    
    # 4. Trailing distance optimal: basé sur MAE post-exit
    #    Une distance plus serrée capture plus de gains mais risque plus de stops prématurés
    used_trailing_dist = float(post_exit_data.get('used_trailing_min_distance') or 0.10)
    if realized_pnl > 0 and post_exit_mfe > 0.05:
        # Trade gagnant avec MFE: distance = max(MAE * 1.2, distance utilisée * 0.8)
        targets['ml_optimal_trailing_distance'] = max(abs(post_exit_mae) * 1.2, used_trailing_dist * 0.8)
    else:
        # Garder la distance actuelle ou légèrement plus large
        targets['ml_optimal_trailing_distance'] = used_trailing_dist
    
    # Bornes: entre 0.03% et 0.30%
    targets['ml_optimal_trailing_distance'] = max(0.03, min(0.30, targets['ml_optimal_trailing_distance']))
    
    # 5. Should use partial TP
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
            print(f"   → ML Optimal Trailing Trigger: {targets['ml_optimal_trailing_trigger']:.3f}%")
            print(f"   → ML Optimal Trailing Distance: {targets['ml_optimal_trailing_distance']:.3f}%")
            print(f"   → ML Optimal BE: {targets['ml_optimal_be_trigger']:.3f}%")
            print(f"   → ML Use Partial: {targets['ml_should_use_partial']}")
            
            # Mettre à jour la DB
            cursor.execute("""
                UPDATE trade_post_exit_analysis
                SET 
                    ml_optimal_sl_pct = %s,
                    ml_optimal_trailing_trigger = %s,
                    ml_optimal_trailing_distance = %s,
                    ml_optimal_be_trigger = %s,
                    ml_should_use_partial = %s
                WHERE trade_id = %s
            """, (
                targets['ml_optimal_sl_pct'],
                targets['ml_optimal_trailing_trigger'],
                targets['ml_optimal_trailing_distance'],
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
                AVG(ml_optimal_trailing_distance) as avg_optimal_trailing_distance,
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
        print(f"   - Trailing trigger optimal moyen: {stats['avg_optimal_trailing']:.3f}%")
        print(f"   - Trailing distance optimal moyen: {stats['avg_optimal_trailing_distance']:.3f}%")
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
        
        # 6. 🔥 SIMULATION: Performance avec paramètres optimaux
        print("\n" + "=" * 80)
        print("🚀 SIMULATION: Performance avec paramètres ML optimaux")
        print("=" * 80)
        
        simulation_results = simulate_optimal_parameters(cursor)
        
        if simulation_results:
            # Afficher les configurations utilisées (groupées)
            config_groups = simulation_results.get('config_groups', {})
            if config_groups:
                print(f"\n⚙️ Configurations UTILISÉES ({len(config_groups)} différentes):")
                for config_key, stats in sorted(config_groups.items(), key=lambda x: -x[1]['trades']):
                    winrate = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
                    improvement = stats['optimal_pnl'] - stats['pnl']
                    print(f"   {config_key}: {stats['trades']} trades | WR: {winrate:.0f}% | PnL: {stats['pnl']:.2f}% → {stats['optimal_pnl']:.2f}% ({improvement:+.2f}%)")
            
            print(f"\n📈 Comparaison ACTUEL vs OPTIMAL (tous trades):")
            print(f"   Winrate:        {simulation_results['current_winrate']:.1f}% → {simulation_results['optimal_winrate']:.1f}% ({simulation_results['winrate_improvement']:+.1f}%)")
            print(f"   PnL total:      {simulation_results['current_pnl_total']:.2f}% → {simulation_results['optimal_pnl_total']:.2f}% ({simulation_results['pnl_improvement']:+.2f}%)")
            print(f"   PnL moyen:      {simulation_results['current_pnl_avg']:.2f}% → {simulation_results['optimal_pnl_avg']:.2f}% ({simulation_results['pnl_avg_improvement']:+.2f}%)")
            print(f"   Exit Efficiency:{simulation_results['current_efficiency']:.1f}% → {simulation_results['optimal_efficiency']:.1f}% ({simulation_results['efficiency_improvement']:+.1f}%)")
            print(f"   Regret moyen:   {simulation_results['current_regret']:.3f}% → {simulation_results['optimal_regret']:.3f}% ({simulation_results['regret_improvement']:+.3f}%)")
            
            print(f"\n📊 Distribution des grades avec paramètres optimaux:")
            for grade, data in simulation_results['optimal_grade_distribution'].items():
                current_data = simulation_results['current_grade_distribution'].get(grade, {'count': 0, 'pct': 0})
                current_count = current_data['count']
                optimal_count = data['count']
                diff = optimal_count - current_count
                diff_str = f"({diff:+d})" if diff != 0 else ""
                print(f"   {grade:3s}: {optimal_count:2d} ({data['pct']:4.1f}%) [vs {current_count} actuels] {diff_str}")
            
            print(f"\n💰 Impact financier:")
            if simulation_results['pnl_improvement'] > 0:
                gain_factor = (simulation_results['optimal_pnl_total'] / max(simulation_results['current_pnl_total'], 0.01))
                print(f"   Gains multipliés par {gain_factor:.1f}x avec paramètres optimaux!")
            else:
                print(f"   Pas d'amélioration significative avec les paramètres optimaux")
        
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
