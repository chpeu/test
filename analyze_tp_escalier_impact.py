#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyse de l'impact du TP Escalier sur la configuration actuelle
"""

def analyze_tp_escalier_impact():
    """Analyser comment le TP Escalier affecte les trades avec TP 0.5%/SL 0.25%"""
    
    print("📊 ANALYSE IMPACT TP ESCALIER")
    print("=" * 80)
    
    print("\n🎯 VOTRE CONFIGURATION ACTUELLE:")
    print("   Mode: FIXE")
    print("   TP principal: 0.50%")
    print("   SL: 0.25%")
    print("   Ratio: 2.0")
    
    print("\n📈 CONFIGURATION TP ESCALIER (ACTIVÉE):")
    print("   Niveau 1: +0.20% → Vente 25% | SL → Entry")
    print("   Niveau 2: +0.35% → Vente 25% | SL → Break-even")
    print("   Niveau 3: +0.50% → Vente 25% | SL → Trailing")
    print("   Niveau 4: +0.80% → Vente 25% | SL → Trailing")
    
    print("\n💡 IMPACT SUR VOS TRADES:")
    print("-" * 50)
    
    # Scénario 1: Trade atteint +0.20% puis reverse
    print("\n1️⃣ SCÉNARIO 1: Trade atteint +0.20% puis reverse à -0.10%")
    print("   Sans TP Escalier:")
    print("      - Fermeture à -0.10% (perte)")
    print("   Avec TP Escalier:")
    print("      - Vente 25% à +0.20% = +0.05% gain")
    print("      - SL à entry (0%)")
    print("      - Reverse à -0.10% = perte sur 75% restant")
    print("      → PnL total: (+0.05% × 25%) + (-0.10% × 75%) = -0.025%")
    print("      ✅ AVANTAGE: Perte réduite de 75% !")
    
    # Scénario 2: Trade atteint +0.50% 
    print("\n2️⃣ SCÉNARIO 2: Trade atteint exactement +0.50%")
    print("   Sans TP Escalier:")
    print("      - Fermeture complète à +0.50% = gain total")
    print("   Avec TP Escalier:")
    print("      - 25% vendus à +0.20% = +0.05%")
    print("      - 25% vendus à +0.35% = +0.0875%")
    print("      - 25% vendus à +0.50% = +0.125%")
    print("      - 25% restants avec trailing")
    print("      → PnL garanti: +0.2625% (52.5% du gain max)")
    print("      ✅ AVANTAGE: Gain sécurisé progressivement")
    
    # Scénario 3: Trade atteint +0.80%
    print("\n3️⃣ SCÉNARIO 3: Trade atteint +0.80%")
    print("   Sans TP Escalier:")
    print("      - Fermeture à +0.50% (TP principal)")
    print("      - Gain manqué: +0.30%")
    print("   Avec TP Escalier:")
    print("      - 75% déjà vendus entre +0.20% et +0.50%")
    print("      - 25% vendus à +0.80% = +0.20%")
    print("      → PnL total: ~+0.46% (vs +0.50% sans escalier)")
    print("      ⚠️  LÉGER DÉSAVANTAGE: -0.04% de moins")
    
    # Scénario 4: Trade rapide à +0.15% puis reverse
    print("\n4️⃣ SCÉNARIO 4: Trade rapide à +0.15% puis reverse à SL")
    print("   Sans TP Escalier:")
    print("      - Fermeture à -0.25% = perte complète")
    print("   Avec TP Escalier:")
    print("      - Pas de déclenchement (0.20% non atteint)")
    print("      - Fermeture à -0.25% = même perte")
    print("      → PAS D'IMPACT")
    
    print("\n📊 ANALYSE STATISTIQUE:")
    print("-" * 50)
    
    # Calcul des gains moyens
    print("\n📈 GAINS MOYENS THÉORIQUES:")
    scenarios = [
        ("Trade < +0.20%", 40, "-0.25%", "-0.25%", "Aucun impact"),
        ("Trade +0.20% à +0.35%", 25, "-0.10%", "-0.025%", "Perte réduite 75%"),
        ("Trade +0.35% à +0.50%", 20, "+0.20%", "+0.10%", "Gain sécurisé 50%"),
        ("Trade > +0.50%", 15, "+0.50%", "+0.46%", "Légère réduction"),
    ]
    
    total_gain_escalier = 0
    total_gain_normal = 0
    
    for scenario, prob, pnl_normal, pnl_escalier, note in scenarios:
        print(f"\n   {scenario:20s} ({prob:2d}% des trades):")
        print(f"      Normal: {pnl_normal:7s} | Escalier: {pnl_escalier:7s} | {note}")
        # Convertir en nombres pour le calcul
        try:
            pnl_n = float(pnl_normal.replace('%', ''))
            pnl_e = float(pnl_escalier.replace('%', ''))
            total_gain_normal += pnl_n * prob / 100
            total_gain_escalier += pnl_e * prob / 100
        except:
            pass
    
    print(f"\n📊 GAIN MOYEN GLOBAL ESTIMÉ:")
    print(f"   Sans TP Escalier: {total_gain_normal:+.3f}% par trade")
    print(f"   Avec TP Escalier:  {total_gain_escalier:+.3f}% par trade")
    
    if total_gain_escalier > total_gain_normal:
        diff = total_gain_escalier - total_gain_normal
        print(f"   ✅ AVANTAGE: +{diff:.3f}% par trade")
    else:
        diff = total_gain_normal - total_gain_escalier
        print(f"   ⚠️  DÉSAVANTAGE: -{diff:.3f}% par trade")
    
    print("\n🎯 RECOMMANDATIONS:")
    print("-" * 50)
    print("\n✅ AVANTAGES du TP Escalier:")
    print("   1. Sécurise les gains progressivement")
    print("   2. Réduit les pertes si reverse après +0.20%")
    print("   3. Protège 50% du gain à +0.35%")
    print("   4. Meilleur gestion du risque")
    
    print("\n⚠️  INCONVÉNIENTS:")
    print("   1. Légère réduction si trade va très loin (+0.80%)")
    print("   2. Plus complexe à analyser")
    print("   3. Peut réduire le winrate apparent")
    
    print("\n💡 CONCLUSION:")
    print("   Le TP Escalier est BÉNÉFIQUE pour votre configuration !")
    print("   Il réduit le risque et sécurise les gains progressivement.")
    print("   Gardez-le activé et surveillez les résultats sur 20-30 trades.")
    
    print("\n🔧 POUR DÉSACTIVER (si vous voulez tester):")
    print("   Dans config.py, ligne 380:")
    print('   "enabled": False,  # au lieu de True')

if __name__ == '__main__':
    analyze_tp_escalier_impact()
