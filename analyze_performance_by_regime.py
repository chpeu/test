import sys
import sqlite3
import json
from datetime import datetime, timedelta

def _setup_stdout_utf8() -> None:
    try:
        if sys.platform == 'win32' and sys.stdout is sys.__stdout__ and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def main() -> None:
    _setup_stdout_utf8()

    # Connexion à la base de données
    db_path = 'data/analytics.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print('=' * 100)
    print('ANALYSE DES PERFORMANCES PAR REGIME DE MARCHÉ')
    print('=' * 100)
    print()

    # Récupérer tous les trades avec leurs régimes
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
    created_at
FROM trades
ORDER BY created_at DESC
LIMIT 100
"""

    cursor.execute(query)
    trades = cursor.fetchall()

    print(f'📊 Total trades avec régime: {len(trades)}')
    print()

    # Analyser les trades
    stats = {
        'total': len(trades),
        'wins': 0,
        'losses': 0,
        'sl_hits': 0,
        'tp_hits': 0,
        'total_pnl': 0.0
    }

    for trade in trades:
        (trade_id, symbol, direction, entry, exit_price, pnl_pct, pnl_usdt, reason, created_at) = trade

        stats['total_pnl'] += pnl_usdt if pnl_usdt else 0.0

        if pnl_pct and pnl_pct > 0:
            stats['wins'] += 1
        elif pnl_pct and pnl_pct < 0:
            stats['losses'] += 1

        if reason and 'SL' in reason.upper():
            stats['sl_hits'] += 1
        elif reason and 'TP' in reason.upper():
            stats['tp_hits'] += 1

    # Calculer les statistiques
    if stats['total'] > 0:
        win_rate = (stats['wins'] / stats['total']) * 100
        sl_rate = (stats['sl_hits'] / stats['total']) * 100
        avg_pnl = stats['total_pnl'] / stats['total']
    else:
        win_rate = 0
        sl_rate = 0
        avg_pnl = 0

    # Afficher les résultats
    print('=' * 100)
    print('RÉSULTATS DES 100 DERNIERS TRADES')
    print('=' * 100)
    print()

    print(f'📊 Total trades: {stats["total"]}')
    print(f'✅ Wins: {stats["wins"]} ({win_rate:.1f}%)')
    print(f'❌ Losses: {stats["losses"]} ({100-win_rate:.1f}%)')
    print(f'🛑 SL Hits: {stats["sl_hits"]} ({sl_rate:.1f}%)')
    print(f'🎯 TP Hits: {stats["tp_hits"]}')
    print(f'💰 PnL Total: {stats["total_pnl"]:.2f} USDT')
    print(f'📈 PnL Moyen: {avg_pnl:.3f} USDT')
    print()

    # Charger les configs de régime
    print('=' * 100)
    print('CONFIGURATION ACTUELLE DES RÉGIMES')
    print('=' * 100)
    print()

    regime_configs = {}
    for regime_name in ['calme', 'normal', 'volatile', 'choppy']:
        try:
            with open(f'config/regimes/{regime_name}.json', 'r') as f:
                config = json.load(f)
                regime_configs[regime_name.upper()] = config

                print(f'🎯 RÉGIME: {config["name"]}')
                print(f'   atr_mult_sl: {config.get("atr_mult_sl", "N/A")}')
                print(f'   atr_mult_tp: {config.get("atr_mult_tp", "N/A")}')
                print(f'   optimal_atr_min: {config.get("optimal_atr_min", "N/A")}%')
                print(f'   optimal_atr_max: {config.get("optimal_atr_max", "N/A")}%')
                print()
        except Exception as e:
            print(f'❌ Erreur lecture config {regime_name}: {e}')

    print('=' * 100)
    print('ANALYSE ET RECOMMANDATIONS')
    print('=' * 100)
    print()

    print('⚠️  IMPORTANT: Les paramètres atr_mult_sl et atr_mult_tp sont SPÉCIFIQUES À CHAQUE RÉGIME')
    print()
    print('Les modifications que tu as faites dans config_overrides.json (atr_mult_sl=2.0, atr_mult_tp=2.0)')
    print('sont des valeurs GLOBALES qui sont ÉCRASÉES par les valeurs spécifiques de chaque régime.')
    print()
    print('📋 VALEURS ACTUELLES PAR RÉGIME:')
    print('   • CALME:    atr_mult_sl=0.8,  atr_mult_tp=1.8')
    print('   • NORMAL:   atr_mult_sl=1.2,  atr_mult_tp=2.2')
    print('   • VOLATILE: atr_mult_sl=1.5,  atr_mult_tp=2.5')
    print('   • CHOPPY:   atr_mult_sl=0.7,  atr_mult_tp=1.5')
    print()

    if sl_rate > 50:
        print('❌ PROBLÈME DÉTECTÉ: Taux de SL trop élevé ({:.1f}%)'.format(sl_rate))
        print()
        print('💡 SOLUTION: Analyser les trades PAR RÉGIME pour ajuster les paramètres')
        print()
        print('   Pour identifier quel régime cause le problème, il faut:')
        print('   1. Ajouter la colonne market_regime à la table trades (migration SQL)')
        print('   2. Logger le régime actif lors de chaque trade')
        print('   3. Analyser les performances par régime')
        print('   4. Ajuster atr_mult_sl dans le fichier config/regimes/XXX.json du régime problématique')
        print()
    else:
        print('✅ Taux de SL acceptable ({:.1f}% < 50%)'.format(sl_rate))
        print()

    if win_rate < 40:
        print('❌ PROBLÈME DÉTECTÉ: Win rate trop faible ({:.1f}%)'.format(win_rate))
        print()
        print('💡 SOLUTION: Même approche - analyser par régime')
        print()
    else:
        print('✅ Win rate acceptable ({:.1f}% > 40%)'.format(win_rate))
        print()

    print('=' * 100)
    print('PROCHAINES ÉTAPES')
    print('=' * 100)
    print()
    print('1. ❌ NE PAS modifier atr_mult_sl/atr_mult_tp dans config_overrides.json')
    print('      (ces valeurs sont écrasées par les régimes)')
    print()
    print('2. ✅ Vérifier quel régime est actuellement actif')
    print('      (regarder les logs du bot ou l\'API /api/regime/status)')
    print()
    print('3. ✅ Modifier les paramètres dans config/regimes/XXX.json')
    print('      où XXX est le régime actif')
    print()
    print('4. ✅ Redémarrer le bot pour appliquer les changements')
    print()
    print('=' * 100)

    conn.close()


if __name__ == '__main__':
    main()
