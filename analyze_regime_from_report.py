import os
import sys
import io

if os.environ.get('PYTEST_CURRENT_TEST') is not None or __name__ != '__main__':
    raise ImportError('analyze_regime_from_report is a script-only module')

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
except Exception:
    pass

import json
from collections import defaultdict

print('=' * 120)


print('ANALYSE DES PERFORMANCES PAR RÉGIME - BASÉE SUR LES 43 TRADES PRÉCÉDENTS')
print('=' * 120)
print()

# Données des 43 trades analysés précédemment (du rapport)
# Win rate: 20.9%, SL rate: 58%, PnL: -0.73 USDT

# Charger les configurations de régime
regime_configs = {}
for regime_name in ['calme', 'normal', 'volatile', 'choppy']:
    try:
        with open(f'config/regimes/{regime_name}.json', 'r') as f:
            config = json.load(f)
            regime_configs[regime_name.upper()] = config
            print(f'✅ Config chargée: {regime_name.upper()}')
    except Exception as e:
        print(f'❌ Erreur lecture config {regime_name}: {e}')

print()
print('=' * 120)
print('CONFIGURATION ACTUELLE DES 4 RÉGIMES')
print('=' * 120)
print()

# Afficher les configs actuelles
for regime_name in ['CALME', 'NORMAL', 'VOLATILE', 'CHOPPY']:
    if regime_name not in regime_configs:
        continue
    
    config = regime_configs[regime_name]
    print(f'🎯 RÉGIME: {regime_name}')
    print(f'   ATR Range: {config.get("optimal_atr_min", "N/A")}% - {config.get("optimal_atr_max", "N/A")}%')
    print(f'   atr_mult_sl: {config.get("atr_mult_sl", "N/A")}')
    print(f'   atr_mult_tp: {config.get("atr_mult_tp", "N/A")}')
    print(f'   min_score_required: {config.get("min_score_required", "N/A")}')
    print(f'   max_position_time: {config.get("max_position_time", "N/A")}s ({config.get("max_position_time", 0)/60:.1f}min)')
    print(f'   stagnation_timeout: {config.get("stagnation_timeout", "N/A")}s ({config.get("stagnation_timeout", 0)/60:.1f}min)')
    print(f'   volume_multiplier: {config.get("volume_multiplier", "N/A")}')
    print()

print('=' * 120)
print('ANALYSE DES PROBLÈMES IDENTIFIÉS (43 trades)')
print('=' * 120)
print()

print('📊 Statistiques globales:')
print('   Win Rate: 20.9% ❌ (cible: >40%)')
print('   SL Hit Rate: 58% ❌ (cible: <45%)')
print('   PnL Total: -0.73 USDT ❌')
print()

print('🔍 Problèmes identifiés:')
print('   1. SL hit rate BEAUCOUP TROP ÉLEVÉ (58%)')
print('      → Les SL sont trop serrés par rapport à la volatilité du marché')
print('   2. Win rate CATASTROPHIQUE (20.9%)')
print('      → Les TP sont peut-être trop ambitieux OU les setups sont de mauvaise qualité')
print()

print('=' * 120)
print('ANALYSE PAR RÉGIME ET RECOMMANDATIONS')
print('=' * 120)
print()

print('⚠️  IMPORTANT: Sans données de régime par trade, je vais analyser les paramètres')
print('   de chaque régime et proposer des ajustements CONSERVATEURS basés sur:')
print('   - Les problèmes globaux identifiés (SL 58%, WR 20.9%)')
print('   - Les meilleures pratiques de trading')
print('   - L\'équilibre risque/récompense')
print()
print('-' * 120)
print()

# Analyse et recommandations par régime
recommendations = {}

# RÉGIME CALME
print('🎯 RÉGIME: CALME (ATR 0.08% - 0.20%)')
print()
config = regime_configs['CALME']
print('   📊 Configuration actuelle:')
print(f'      atr_mult_sl: {config["atr_mult_sl"]} (SL à {config["atr_mult_sl"]*0.15:.3f}% pour ATR moyen 0.15%)')
print(f'      atr_mult_tp: {config["atr_mult_tp"]} (TP à {config["atr_mult_tp"]*0.15:.3f}% pour ATR moyen 0.15%)')
print(f'      Risk/Reward ratio: 1:{config["atr_mult_tp"]/config["atr_mult_sl"]:.2f}')
print()
print('   💡 ANALYSE:')
print('      ✅ Risk/Reward ratio correct (1:2.25)')
print('      ⚠️  Mais avec SL global à 58%, les SL sont trop serrés')
print()
print('   🔧 RECOMMANDATIONS:')
print(f'      atr_mult_sl: {config["atr_mult_sl"]} → 1.2 (+50%)')
print(f'      atr_mult_tp: {config["atr_mult_tp"]} → 2.0 (+11%)')
print(f'      Nouveau R/R: 1:1.67 (moins ambitieux mais plus réaliste)')
print()
recommendations['CALME'] = {
    'atr_mult_sl': 1.2,
    'atr_mult_tp': 2.0,
    'reason': 'Augmenter SL pour réduire le taux de 58% et ajuster TP proportionnellement'
}
print('-' * 120)
print()

# RÉGIME NORMAL
print('🎯 RÉGIME: NORMAL (ATR 0.10% - 0.30%)')
print()
config = regime_configs['NORMAL']
print('   📊 Configuration actuelle:')
print(f'      atr_mult_sl: {config["atr_mult_sl"]} (SL à {config["atr_mult_sl"]*0.20:.3f}% pour ATR moyen 0.20%)')
print(f'      atr_mult_tp: {config["atr_mult_tp"]} (TP à {config["atr_mult_tp"]*0.20:.3f}% pour ATR moyen 0.20%)')
print(f'      Risk/Reward ratio: 1:{config["atr_mult_tp"]/config["atr_mult_sl"]:.2f}')
print()
print('   💡 ANALYSE:')
print('      ✅ Risk/Reward ratio correct (1:1.83)')
print('      ⚠️  Mais avec SL global à 58%, les SL sont trop serrés')
print()
print('   🔧 RECOMMANDATIONS:')
print(f'      atr_mult_sl: {config["atr_mult_sl"]} → 1.6 (+33%)')
print(f'      atr_mult_tp: {config["atr_mult_tp"]} → 2.4 (+9%)')
print(f'      Nouveau R/R: 1:1.50 (plus conservateur)')
print()
recommendations['NORMAL'] = {
    'atr_mult_sl': 1.6,
    'atr_mult_tp': 2.4,
    'reason': 'Augmenter SL significativement pour réduire le taux de 58%'
}
print('-' * 120)
print()

# RÉGIME VOLATILE
print('🎯 RÉGIME: VOLATILE (ATR 0.20% - 0.80%)')
print()
config = regime_configs['VOLATILE']
print('   📊 Configuration actuelle:')
print(f'      atr_mult_sl: {config["atr_mult_sl"]} (SL à {config["atr_mult_sl"]*0.50:.3f}% pour ATR moyen 0.50%)')
print(f'      atr_mult_tp: {config["atr_mult_tp"]} (TP à {config["atr_mult_tp"]*0.50:.3f}% pour ATR moyen 0.50%)')
print(f'      Risk/Reward ratio: 1:{config["atr_mult_tp"]/config["atr_mult_sl"]:.2f}')
print()
print('   💡 ANALYSE:')
print('      ✅ Risk/Reward ratio correct (1:1.67)')
print('      ✅ Paramètres déjà plus larges (adapté à la volatilité)')
print('      ⚠️  Mais peut nécessiter un ajustement si beaucoup de SL')
print()
print('   🔧 RECOMMANDATIONS:')
print(f'      atr_mult_sl: {config["atr_mult_sl"]} → 1.8 (+20%)')
print(f'      atr_mult_tp: {config["atr_mult_tp"]} → 2.7 (+8%)')
print(f'      Nouveau R/R: 1:1.50 (conservateur pour marché volatile)')
print()
recommendations['VOLATILE'] = {
    'atr_mult_sl': 1.8,
    'atr_mult_tp': 2.7,
    'reason': 'Ajustement modéré car paramètres déjà adaptés à la volatilité'
}
print('-' * 120)
print()

# RÉGIME CHOPPY
print('🎯 RÉGIME: CHOPPY (ATR 0.10% - 0.25%, ADX faible)')
print()
config = regime_configs['CHOPPY']
print('   📊 Configuration actuelle:')
print(f'      atr_mult_sl: {config["atr_mult_sl"]} (SL à {config["atr_mult_sl"]*0.175:.3f}% pour ATR moyen 0.175%)')
print(f'      atr_mult_tp: {config["atr_mult_tp"]} (TP à {config["atr_mult_tp"]*0.175:.3f}% pour ATR moyen 0.175%)')
print(f'      Risk/Reward ratio: 1:{config["atr_mult_tp"]/config["atr_mult_sl"]:.2f}')
print(f'      min_score_required: {config["min_score_required"]} (TRÈS STRICT)')
print()
print('   💡 ANALYSE:')
print('      ✅ Risk/Reward ratio correct (1:2.14)')
print('      ✅ Score minimum élevé (10.0) pour filtrer les mauvais setups')
print('      ⚠️  SL très serré (0.7) peut causer beaucoup de faux signaux en choppy')
print()
print('   🔧 RECOMMANDATIONS:')
print(f'      atr_mult_sl: {config["atr_mult_sl"]} → 1.0 (+43%)')
print(f'      atr_mult_tp: {config["atr_mult_tp"]} → 1.8 (+20%)')
print(f'      min_score_required: {config["min_score_required"]} → 10.5 (encore plus strict)')
print(f'      Nouveau R/R: 1:1.80 (plus de marge pour le bruit du marché)')
print()
recommendations['CHOPPY'] = {
    'atr_mult_sl': 1.0,
    'atr_mult_tp': 1.8,
    'min_score_required': 10.5,
    'reason': 'Augmenter SL pour gérer le bruit, TP plus conservateur, score plus strict'
}
print('-' * 120)
print()

print('=' * 120)
print('RÉSUMÉ DES RECOMMANDATIONS')
print('=' * 120)
print()

print('📋 Changements proposés par régime:')
print()

for regime_name in ['CALME', 'NORMAL', 'VOLATILE', 'CHOPPY']:
    rec = recommendations[regime_name]
    old_config = regime_configs[regime_name]
    
    print(f'🎯 {regime_name}:')
    print(f'   atr_mult_sl: {old_config["atr_mult_sl"]} → {rec["atr_mult_sl"]} ({(rec["atr_mult_sl"]/old_config["atr_mult_sl"]-1)*100:+.0f}%)')
    print(f'   atr_mult_tp: {old_config["atr_mult_tp"]} → {rec["atr_mult_tp"]} ({(rec["atr_mult_tp"]/old_config["atr_mult_tp"]-1)*100:+.0f}%)')
    if 'min_score_required' in rec:
        print(f'   min_score_required: {old_config["min_score_required"]} → {rec["min_score_required"]}')
    print(f'   Raison: {rec["reason"]}')
    print()

print('=' * 120)
print('IMPACT ATTENDU')
print('=' * 120)
print()

print('📈 Avec ces ajustements:')
print()
print('   SL Hit Rate:')
print('      Actuel: 58% ❌')
print('      Cible: 35-45% ✅')
print('      → Augmentation moyenne de 35% des SL devrait réduire significativement le taux')
print()
print('   Win Rate:')
print('      Actuel: 20.9% ❌')
print('      Cible: 40-50% ✅')
print('      → TP légèrement ajustés + moins de SL prématurés = meilleur win rate')
print()
print('   Risk/Reward:')
print('      Nouveau R/R moyen: 1:1.5 - 1:1.8')
print('      → Plus conservateur mais plus réaliste pour les conditions actuelles')
print()

print('=' * 120)
print('PROCHAINES ÉTAPES')
print('=' * 120)
print()

print('1️⃣  APPLIQUER LES MODIFICATIONS:')
print()
for regime_name in ['calme', 'normal', 'volatile', 'choppy']:
    print(f'   Éditer: config/regimes/{regime_name}.json')
    rec = recommendations[regime_name.upper()]
    print(f'   Modifier:')
    print(f'      "atr_mult_sl": {rec["atr_mult_sl"]},')
    print(f'      "atr_mult_tp": {rec["atr_mult_tp"]},')
    if 'min_score_required' in rec:
        print(f'      "min_score_required": {rec["min_score_required"]},')
    print()

print('2️⃣  REDÉMARRER LE BOT')
print('   → Les nouveaux paramètres seront appliqués au prochain démarrage')
print()

print('3️⃣  SURVEILLER LES RÉSULTATS')
print('   → Analyser les 20-30 prochains trades')
print('   → Vérifier que le SL rate diminue vers 35-45%')
print('   → Vérifier que le win rate augmente vers 40-50%')
print()

print('4️⃣  AJUSTER SI NÉCESSAIRE')
print('   → Si SL rate encore trop élevé: augmenter encore atr_mult_sl de 10-15%')
print('   → Si win rate encore faible: réduire atr_mult_tp de 10%')
print()

print('=' * 120)
print('NOTES IMPORTANTES')
print('=' * 120)
print()

print('⚠️  Ces recommandations sont basées sur:')
print('   • Les statistiques globales des 43 trades (SL 58%, WR 20.9%)')
print('   • Les meilleures pratiques de trading')
print('   • Un équilibre risque/récompense conservateur')
print()
print('💡 Pour une analyse plus précise:')
print('   • Attendre que le bot génère des trades avec logging du régime actif')
print('   • Analyser les performances RÉELLES par régime')
print('   • Ajuster finement les paramètres de chaque régime')
print()
print('🎯 Objectif:')
print('   • Réduire le SL rate de 58% à 35-45%')
print('   • Augmenter le win rate de 20.9% à 40-50%')
print('   • Atteindre un PnL positif sur 30-50 trades')
print()

print('=' * 120)
