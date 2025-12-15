#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 ANALYSE TRADES PAR PAIRE POUR MODÈLES ML INDIVIDUALISÉS
============================================================
Compte les trades utilisables pour le ML par symbole.
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
from datetime import datetime
from pathlib import Path

print("=" * 70)
print("  ANALYSE TRADES PAR PAIRE (ML UTILISABLES)")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# =============================================================================
# 1. CHARGEMENT DES DONNÉES VIA FEATURE_LOADER
# =============================================================================
print("\n[1/3] Chargement des données ML...")

try:
    from optimization.data.feature_loader import load_features_from_postgres
    
    df = load_features_from_postgres(timeframe_days=180, min_trades=1)
    print(f"   ✅ {len(df)} trades chargés")
except Exception as e:
    print(f"   ❌ Erreur chargement: {e}")
    sys.exit(1)

# =============================================================================
# 2. ANALYSE TRADES PAR SYMBOLE
# =============================================================================
print("\n[2/3] Analyse des trades par symbole...")

# Vérifier si colonne symbol existe
if 'symbol' not in df.columns:
    print("   ⚠️ Colonne 'symbol' non trouvée, utilisation de données agrégées")
    # Créer stats globales
    total_trades = len(df)
    wins = df['target_win'].sum() if 'target_win' in df.columns else 0
    losses = total_trades - wins
    wr = (wins / total_trades * 100) if total_trades > 0 else 0
    print(f"\n   DONNÉES GLOBALES:")
    print(f"   Total trades ML: {total_trades}")
    print(f"   Wins: {wins} | Losses: {losses}")
    print(f"   Win Rate: {wr:.1f}%")
    symbols_ml_ready = []
else:
    # Grouper par symbole
    symbol_stats = df.groupby('symbol').agg({
        'target_win': ['count', 'sum']
    }).reset_index()
    symbol_stats.columns = ['symbol', 'total_trades', 'wins']
    symbol_stats['losses'] = symbol_stats['total_trades'] - symbol_stats['wins']
    symbol_stats['win_rate'] = (symbol_stats['wins'] / symbol_stats['total_trades'] * 100).round(1)
    symbol_stats = symbol_stats.sort_values('total_trades', ascending=False)
    
    print(f"\n   {'='*65}")
    print(f"   {'Symbole':<15} {'Trades':>8} {'Wins':>6} {'Losses':>6} {'WR %':>7} {'ML Ready':>10}")
    print(f"   {'='*65}")
    
    MIN_TRADES_INDIVIDUAL = 80  # Minimum pour modèle individuel
    total_trades = 0
    symbols_ml_ready = []
    
    for _, row in symbol_stats.iterrows():
        symbol = row['symbol']
        trades = int(row['total_trades'])
        wins = int(row['wins'])
        losses = int(row['losses'])
        wr = row['win_rate']
        ml_ready = "✅" if trades >= MIN_TRADES_INDIVIDUAL else "❌"
        
        print(f"   {symbol:<15} {trades:>8} {wins:>6} {losses:>6} {wr:>6.1f}% {ml_ready:>10}")
        
        total_trades += trades
        if trades >= MIN_TRADES_INDIVIDUAL:
            symbols_ml_ready.append({
                'symbol': symbol,
                'trades': trades,
                'wins': wins,
                'losses': losses,
                'win_rate': wr
            })
    
    print(f"   {'='*65}")
    print(f"   {'TOTAL':<15} {total_trades:>8}")

# =============================================================================
# 3. RECOMMANDATIONS
# =============================================================================
print("\n[3/3] Recommandations pour modèles individualisés...")

MIN_TRADES_INDIVIDUAL = 80 if 'MIN_TRADES_INDIVIDUAL' not in dir() else MIN_TRADES_INDIVIDUAL
print(f"\n   Seuil minimum: {MIN_TRADES_INDIVIDUAL} trades")
print(f"   Symboles éligibles: {len(symbols_ml_ready)}")

if symbols_ml_ready:
    print(f"\n   📊 SYMBOLES POUR MODÈLES INDIVIDUELS:")
    for i, s in enumerate(symbols_ml_ready[:10], 1):
        print(f"      {i}. {s['symbol']}: {s['trades']} trades ({s['win_rate']:.1f}% WR)")
else:
    print(f"\n   ⚠️ Aucun symbole n'a assez de trades ({MIN_TRADES_INDIVIDUAL}+)")
    print(f"   → Continuer à collecter des données avant d'individualiser")

# Stats supplémentaires
print(f"\n   📊 RÉPARTITION:")
ml_total = len(df)
symbols_count = df['symbol'].nunique() if 'symbol' in df.columns else 1

print(f"      Total trades ML: {ml_total}")
print(f"      Symboles uniques: {symbols_count}")
print(f"      Moyenne trades/symbole: {ml_total / symbols_count if symbols_count > 0 else 0:.1f}")

# Colonnes disponibles
print(f"\n   📊 COLONNES DISPONIBLES ({len(df.columns)}):")
print(f"      {', '.join(df.columns[:10])}...")

print("\n" + "=" * 70)
print("  FIN ANALYSE")
print("=" * 70)
