import os
import sys
import io

if os.environ.get('PYTEST_CURRENT_TEST') is not None or __name__ != '__main__':
    raise ImportError('analyze_regime_performance is a script-only module')

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
except Exception:
    pass

import sqlite3
import json
from collections import defaultdict
from datetime import datetime

# Connexion à la base de données
db_path = 'data/analytics.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('=' * 120)
print('ANALYSE DES PERFORMANCES PAR RÉGIME DE MARCHÉ')
print('=' * 120)
print()

# Vérifier si on a des données de régime
cursor.execute("SELECT COUNT(*) FROM trades")
total_trades = cursor.fetchone()[0]

print(f'📊 Total trades dans la base: {total_trades}')
print()

# Récupérer tous les trades avec ATR pour déduire le régime
query = """
SELECT 
    id,
    symbol,
    direction,
    entry,
    exit,
    gross_pnl_pct,
    gross_pnl_usdt,
    reason,
    atr_at_entry,
    created_at,
    duration
FROM trades
WHERE atr_at_entry IS NOT NULL
ORDER BY created_at DESC
LIMIT 200
"""

cursor.execute(query)
trades = cursor.fetchall()

print(f'📈 Trades avec ATR disponible: {len(trades)}')
print()

if len(trades) == 0:
    print('❌ Aucun trade avec données ATR disponibles.')
    print('   Impossible d\'analyser par régime sans ces données.')
    print()
    print('💡 Solution: Attendre que le bot génère de nouveaux trades avec logging ATR.')
    conn.close()
    sys.exit(0)

# Charger les configurations de régime
regime_configs = {}
for regime_name in ['calme', 'normal', 'volatile', 'choppy']:
    try:
        with open(f'config/regimes/{regime_name}.json', 'r') as f:
            config = json.load(f)
            regime_configs[regime_name.upper()] = config
    except Exception as e:
        print(f'⚠️  Erreur lecture config {regime_name}: {e}')

# Fonction pour déduire le régime à partir de l'ATR
def deduce_regime(atr_pct):
    """
    Déduit le régime de marché à partir de l'ATR%
    Basé sur les seuils des configs de régime
    """
    if atr_pct is None:
        return 'UNKNOWN'
    
    # Convertir en pourcentage si nécessaire
    atr = atr_pct * 100 if atr_pct < 1 else atr_pct
    
    # Seuils basés sur les configs
    if atr <= 0.20:
        return 'CALME'
    elif atr <= 0.40:
        return 'NORMAL'
    elif atr <= 0.80:
        return 'VOLATILE'
    else:
        return 'VOLATILE'  # Au-delà de 0.8% = très volatile

# Analyser par régime déduit
regime_stats = defaultdict(lambda: {
    'trades': [],
    'count': 0,
    'wins': 0,
    'losses': 0,
    'sl_hits': 0,
    'tp_hits': 0,
    'manual_exits': 0,
    'total_pnl': 0.0,
    'total_duration': 0,
    'atr_values': []
})

for trade in trades:
    (trade_id, symbol, direction, entry, exit_price, pnl_pct, pnl_usdt, 
     reason, atr_entry, created_at, duration) = trade
    
    # Déduire le régime
    regime = deduce_regime(atr_entry)
    
    regime_stats[regime]['trades'].append(trade)
    regime_stats[regime]['count'] += 1
    regime_stats[regime]['total_pnl'] += pnl_usdt if pnl_usdt else 0.0
    regime_stats[regime]['atr_values'].append(atr_entry if atr_entry else 0)
    
    if duration:
        regime_stats[regime]['total_duration'] += duration
    
    if pnl_pct and pnl_pct > 0:
        regime_stats[regime]['wins'] += 1
    elif pnl_pct and pnl_pct < 0:
        regime_stats[regime]['losses'] += 1
    
    if reason:
        reason_upper = reason.upper()
        if 'SL' in reason_upper:
            regime_stats[regime]['sl_hits'] += 1
        elif 'TP' in reason_upper:
            regime_stats[regime]['tp_hits'] += 1
        elif 'MANUAL' in reason_upper or 'STAGNATION' in reason_upper:
            regime_stats[regime]['manual_exits'] += 1

# Calculer les statistiques
for regime, stats in regime_stats.items():
    if stats['count'] > 0:
        stats['win_rate'] = (stats['wins'] / stats['count']) * 100
        stats['sl_rate'] = (stats['sl_hits'] / stats['count']) * 100
        stats['tp_rate'] = (stats['tp_hits'] / stats['count']) * 100
        stats['avg_pnl'] = stats['total_pnl'] / stats['count']
        stats['avg_duration'] = stats['total_duration'] / stats['count'] if stats['total_duration'] > 0 else 0
        stats['avg_atr'] = sum(stats['atr_values']) / len(stats['atr_values']) if stats['atr_values'] else 0

# Afficher les résultats
print('=' * 120)
print('RÉSULTATS PAR RÉGIME (déduit de l\'ATR)')
print('=' * 120)
print()

for regime in ['CALME', 'NORMAL', 'VOLATILE', 'UNKNOWN']:
    if regime not in regime_stats or regime_stats[regime]['count'] == 0:
        continue
    
    stats = regime_stats[regime]
    config = regime_configs.get(regime, {})
    
    print(f'🎯 RÉGIME: {regime}')
    print(f'   Trades: {stats["count"]} ({stats["count"]/len(trades)*100:.1f}% du total)')
    print(f'   ATR moyen: {stats["avg_atr"]:.4f}%')
    print()
    
    print(f'   📊 Performances:')
    print(f'      Win Rate: {stats["win_rate"]:.1f}% ({stats["wins"]}W / {stats["losses"]}L)')
    print(f'      SL Hit Rate: {stats["sl_rate"]:.1f}% ({stats["sl_hits"]} trades)')
    print(f'      TP Hit Rate: {stats["tp_rate"]:.1f}% ({stats["tp_hits"]} trades)')
    print(f'      Exits manuels/stagnation: {stats["manual_exits"]} trades')
    print(f'      PnL Total: {stats["total_pnl"]:.2f} USDT')
    print(f'      PnL Moyen: {stats["avg_pnl"]:.3f} USDT')
    print(f'      Durée moyenne: {stats["avg_duration"]:.0f}s ({stats["avg_duration"]/60:.1f}min)')
    print()
    
    if config:
        print(f'   ⚙️  Configuration actuelle:')
        print(f'      atr_mult_sl: {config.get("atr_mult_sl", "N/A")}')
        print(f'      atr_mult_tp: {config.get("atr_mult_tp", "N/A")}')
        print(f'      min_score_required: {config.get("min_score_required", "N/A")}')
        print(f'      max_position_time: {config.get("max_position_time", "N/A")}s')
        print()
        
        # Recommandations basées sur les données
        recommendations = []
        
        # Problème: SL hit rate trop élevé
        if stats["sl_rate"] > 50:
            current_sl = config.get("atr_mult_sl", 1.0)
            recommended_sl = current_sl * 1.3
            recommendations.append(f'⚠️  SL hit rate TROP ÉLEVÉ ({stats["sl_rate"]:.1f}%)')
            recommendations.append(f'    → Augmenter atr_mult_sl de {current_sl} à {recommended_sl:.1f}')
        
        # Problème: Win rate trop faible
        if stats["win_rate"] < 35:
            current_tp = config.get("atr_mult_tp", 2.0)
            recommended_tp = current_tp * 0.85
            recommendations.append(f'⚠️  Win rate TROP FAIBLE ({stats["win_rate"]:.1f}%)')
            recommendations.append(f'    → Réduire atr_mult_tp de {current_tp} à {recommended_tp:.1f} (TP plus proche)')
        
        # Problème: Durée moyenne trop longue
        if stats["avg_duration"] > config.get("max_position_time", 300):
            recommendations.append(f'⚠️  Durée moyenne DÉPASSE max_position_time')
            recommendations.append(f'    → Vérifier les exits de stagnation')
        
        # Bon équilibre
        if 40 <= stats["win_rate"] <= 60 and 30 <= stats["sl_rate"] <= 45:
            recommendations.append(f'✅ Bon équilibre win rate / SL rate')
            recommendations.append(f'    → Paramètres actuels semblent adaptés')
        
        if recommendations:
            print(f'   💡 RECOMMANDATIONS:')
            for rec in recommendations:
                print(f'      {rec}')
            print()
    
    print('-' * 120)
    print()

# Analyse globale
print('=' * 120)
print('ANALYSE GLOBALE')
print('=' * 120)
print()

total_count = sum(stats['count'] for stats in regime_stats.values())
total_wins = sum(stats['wins'] for stats in regime_stats.values())
total_sl = sum(stats['sl_hits'] for stats in regime_stats.values())
total_pnl = sum(stats['total_pnl'] for stats in regime_stats.values())

global_win_rate = (total_wins / total_count * 100) if total_count > 0 else 0
global_sl_rate = (total_sl / total_count * 100) if total_count > 0 else 0

print(f'Total trades analysés: {total_count}')
print(f'Win rate global: {global_win_rate:.1f}%')
print(f'SL hit rate global: {global_sl_rate:.1f}%')
print(f'PnL total: {total_pnl:.2f} USDT')
print()

# Distribution des trades par régime
print('📊 Distribution des trades par régime:')
for regime in ['CALME', 'NORMAL', 'VOLATILE', 'UNKNOWN']:
    if regime in regime_stats and regime_stats[regime]['count'] > 0:
        pct = regime_stats[regime]['count'] / total_count * 100
        print(f'   {regime}: {regime_stats[regime]["count"]} trades ({pct:.1f}%)')
print()

print('=' * 120)
print('CONCLUSION ET ACTIONS')
print('=' * 120)
print()

# Identifier le régime le plus problématique
worst_regime = None
worst_sl_rate = 0
for regime, stats in regime_stats.items():
    if regime != 'UNKNOWN' and stats['count'] >= 5:  # Au moins 5 trades pour être significatif
        if stats['sl_rate'] > worst_sl_rate:
            worst_sl_rate = stats['sl_rate']
            worst_regime = regime

if worst_regime and worst_sl_rate > 50:
    print(f'🔴 RÉGIME LE PLUS PROBLÉMATIQUE: {worst_regime}')
    print(f'   SL hit rate: {worst_sl_rate:.1f}%')
    print(f'   → Priorité: Ajuster config/regimes/{worst_regime.lower()}.json')
    print()

# Identifier le meilleur régime
best_regime = None
best_win_rate = 0
for regime, stats in regime_stats.items():
    if regime != 'UNKNOWN' and stats['count'] >= 5:
        if stats['win_rate'] > best_win_rate:
            best_win_rate = stats['win_rate']
            best_regime = regime

if best_regime:
    print(f'🟢 RÉGIME LE PLUS PERFORMANT: {best_regime}')
    print(f'   Win rate: {best_win_rate:.1f}%')
    print(f'   → Paramètres de ce régime peuvent servir de référence')
    print()

print('📝 PROCHAINES ÉTAPES:')
print('   1. Modifier les fichiers config/regimes/*.json selon les recommandations ci-dessus')
print('   2. Redémarrer le bot pour appliquer les changements')
print('   3. Surveiller les 10-20 prochains trades pour valider les ajustements')
print()
print('=' * 120)

conn.close()
