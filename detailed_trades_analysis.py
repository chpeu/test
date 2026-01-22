#!/usr/bin/env python3
"""
Analyse détaillée des 17 derniers trades via PostgreSQL
Performance, causes du PnL négatif, et recommandations
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime
import json
from collections import Counter, defaultdict

# Charger les variables d'environnement
load_dotenv()

DB_NAME = os.getenv('DB_NAME', 'trade_cursor_ml')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

def get_connection():
    try:
        return psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            cursor_factory=RealDictCursor
        )
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return None

def analyze_17_last_trades():
    conn = get_connection()
    if not conn:
        return

    cursor = conn.cursor()

    # Requête pour les 17 derniers trades avec les champs disponibles
    query_trades = """
        SELECT 
            id, symbol, direction, entry_price, exit_price, 
            pnl_usdt, net_pnl_usdt, pnl_pct, net_pnl_pct,
            exit_reason, size_usdt, duration_seconds,
            fees_usdt, slippage_usdt, 
            created_at, session_id
        FROM trades 
        WHERE exit_price IS NOT NULL 
        AND exit_reason IS NOT NULL
        ORDER BY created_at DESC 
        LIMIT 17
    """
    
    cursor.execute(query_trades)
    trades = cursor.fetchall()
    
    print("🎯 ANALYSE DÉTAILLÉE - 17 DERNIERS TRADES")
    print("="*80)
    print(f"📊 {len(trades)} trades trouvés")
    print()
    
    # === MÉTRIQUES GÉNÉRALES ===
    total_trades = len(trades)
    wins = sum(1 for t in trades if (t['net_pnl_usdt'] or 0) > 0)
    losses = total_trades - wins
    winrate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    # PnL et moyennes
    total_pnl = sum(t['net_pnl_usdt'] or 0 for t in trades)
    win_pnls = [t['net_pnl_usdt'] for t in trades if (t['net_pnl_usdt'] or 0) > 0]
    loss_pnls = [t['net_pnl_usdt'] for t in trades if (t['net_pnl_usdt'] or 0) < 0]
    
    avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
    avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0
    
    profit_factor = abs(sum(win_pnls) / sum(loss_pnls)) if loss_pnls and sum(loss_pnls) != 0 else 0
    
    # Coûts
    total_fees = sum(t['fees_usdt'] or 0 for t in trades)
    total_slippage = sum(t['slippage_usdt'] or 0 for t in trades)
    
    print("📈 SYNTHÈSE GÉNÉRALE")
    print(f"   Total trades: {total_trades}")
    print(f"   Wins: {wins} ({winrate:.2f}%) | Losses: {losses} ({100-winrate:.2f}%)")
    print(f"   PnL total: {total_pnl:.4f} USDT")
    print(f"   Gain moyen: +{avg_win:.4f} USDT | Perte moyenne: {avg_loss:.4f} USDT")
    print(f"   Ratio Gain/Perte: {abs(avg_win/avg_loss):.2f}:1" if avg_loss != 0 else "   Ratio: N/A")
    print(f"   Profit Factor: {profit_factor:.3f}")
    print(f"   Frais totaux: {total_fees:.4f} USDT | Slippage: {total_slippage:.4f} USDT")
    print()
    
    # === ANALYSE PAR EXIT REASON ===
    exit_reasons = [t['exit_reason'] for t in trades if t['exit_reason']]
    reason_counts = Counter(exit_reasons)
    reason_analysis = defaultdict(lambda: {'count': 0, 'total_pnl': 0, 'wins': 0, 'losses': 0})
    
    for trade in trades:
        reason = trade['exit_reason']
        if reason:
            pnl = trade['net_pnl_usdt'] or 0
            reason_analysis[reason]['count'] += 1
            reason_analysis[reason]['total_pnl'] += pnl
            if pnl > 0:
                reason_analysis[reason]['wins'] += 1
            else:
                reason_analysis[reason]['losses'] += 1
    
    print("🚪 ANALYSE PAR TYPE DE SORTIE")
    for reason, stats in reason_analysis.items():
        avg_pnl = stats['total_pnl'] / stats['count'] if stats['count'] > 0 else 0
        win_pct = (stats['wins'] / stats['count'] * 100) if stats['count'] > 0 else 0
        print(f"   {reason:<15}: {stats['count']:>2} trades | PnL: {stats['total_pnl']:>+7.4f} | Moy: {avg_pnl:>+6.4f} | Win: {win_pct:>5.1f}%")
    print()
    
    # === ANALYSE DES PERTES MAJEURES ===
    major_losses = sorted([t for t in trades if (t['net_pnl_usdt'] or 0) < 0], 
                         key=lambda x: x['net_pnl_usdt'] or 0)
    
    print("💸 TOP 5 PERTES LES PLUS LOURDES")
    for i, trade in enumerate(major_losses[:5], 1):
        pnl = trade['net_pnl_usdt'] or 0
        pnl_pct = trade['net_pnl_pct'] or 0
        duration_min = (trade['duration_seconds'] or 0) / 60
        print(f"   #{i} {trade['symbol']:<15} {pnl:>+7.4f} USDT ({pnl_pct:>+6.2f}%) | {trade['exit_reason']:<12} | {duration_min:.0f}min")
    print()
    
    # === ANALYSE DES MEILLEURS GAINS ===
    major_wins = sorted([t for t in trades if (t['net_pnl_usdt'] or 0) > 0], 
                       key=lambda x: x['net_pnl_usdt'] or 0, reverse=True)
    
    print("💰 TOP 5 GAINS LES PLUS ÉLEVÉS")
    for i, trade in enumerate(major_wins[:5], 1):
        pnl = trade['net_pnl_usdt'] or 0
        pnl_pct = trade['net_pnl_pct'] or 0
        duration_min = (trade['duration_seconds'] or 0) / 60
        print(f"   #{i} {trade['symbol']:<15} {pnl:>+7.4f} USDT ({pnl_pct:>+6.2f}%) | {trade['exit_reason']:<12} | {duration_min:.0f}min")
    print()
    
    # === ANALYSE TEMPORELLE ===
    durations = [t['duration_seconds'] or 0 for t in trades]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    short_trades = [t for t in trades if (t['duration_seconds'] or 0) < 300]  # < 5min
    medium_trades = [t for t in trades if 300 <= (t['duration_seconds'] or 0) < 1800]  # 5-30min
    long_trades = [t for t in trades if (t['duration_seconds'] or 0) >= 1800]  # > 30min
    
    print("⏱️  ANALYSE TEMPORELLE")
    print(f"   Durée moyenne: {avg_duration/60:.1f} minutes")
    print(f"   Trades courts (<5min): {len(short_trades)} | PnL moyen: {sum(t['net_pnl_usdt'] or 0 for t in short_trades)/len(short_trades) if short_trades else 0:.4f}")
    print(f"   Trades moyens (5-30min): {len(medium_trades)} | PnL moyen: {sum(t['net_pnl_usdt'] or 0 for t in medium_trades)/len(medium_trades) if medium_trades else 0:.4f}")
    print(f"   Trades longs (>30min): {len(long_trades)} | PnL moyen: {sum(t['net_pnl_usdt'] or 0 for t in long_trades)/len(long_trades) if long_trades else 0:.4f}")
    print()
    
    # === ANALYSE DES DURÉES ET PATTERNS ===
    print("🎯 ANALYSE DES PATTERNS")
    ts_trades = [t for t in trades if t['exit_reason'] == 'TS']
    tp_trades = [t for t in trades if t['exit_reason'] == 'TP']
    
    if ts_trades:
        ts_pnl = sum(t['net_pnl_usdt'] or 0 for t in ts_trades)
        print(f"   Trailing Stop (TS): {len(ts_trades)} trades | PnL total: {ts_pnl:.4f} USDT")
    if tp_trades:
        tp_pnl = sum(t['net_pnl_usdt'] or 0 for t in tp_trades)
        print(f"   Take Profit (TP): {len(tp_trades)} trades | PnL total: {tp_pnl:.4f} USDT")
    print()
    
    # === TABLEAU DÉTAILLÉ ===
    print("📋 DÉTAIL DES 17 TRADES (récent → ancien)")
    print("-"*120)
    print(f"{'#':<2} {'Symbol':<15} {'Dir':<4} {'Entry':<8} {'Exit':<8} {'PnL$':<8} {'PnL%':<7} {'Reason':<12} {'Duration':<8} {'Fees':<8}")
    print("-"*120)
    
    for i, trade in enumerate(trades, 1):
        pnl_usdt = trade['net_pnl_usdt'] or 0
        pnl_pct = trade['net_pnl_pct'] or 0
        duration_min = (trade['duration_seconds'] or 0) / 60
        fees = trade['fees_usdt'] or 0
        
        pnl_color = "+" if pnl_usdt >= 0 else ""
        
        print(f"{i:<2} {trade['symbol']:<15} {trade['direction']:<4} {trade['entry_price']:<8.4f} {trade['exit_price']:<8.4f} "
              f"{pnl_color}{pnl_usdt:<7.4f} {pnl_color}{pnl_pct:<6.2f}% {trade['exit_reason']:<12} {duration_min:<7.0f}m {fees:<7.4f}")
    
    print("-"*120)
    print()
    
    # === DIAGNOSTIC FINAL ===
    print("🔍 DIAGNOSTIC & CAUSES DU PnL NÉGATIF")
    print("="*60)
    
    # Calcul du ratio risque/récompense
    risk_reward_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    
    print(f"1️⃣  WINRATE vs RENTABILITÉ:")
    print(f"   ✅ Winrate acceptable: {winrate:.1f}% (> 50%)")
    print(f"   ❌ Ratio R:R défavorable: {risk_reward_ratio:.2f}:1 (gains trop faibles vs pertes)")
    print()
    
    print(f"2️⃣  ANALYSE DES SORTIES:")
    sl_trades = [t for t in trades if t['exit_reason'] in ['SL', 'SL_EXCHANGE']]
    sl_pnl = sum(t['net_pnl_usdt'] or 0 for t in sl_trades)
    print(f"   ❌ Stops Loss coûtent cher: {len(sl_trades)} trades SL = {sl_pnl:.4f} USDT")
    
    stagnation_trades = [t for t in trades if 'STAGNATION' in (t['exit_reason'] or '')]
    if stagnation_trades:
        stag_pnl = sum(t['net_pnl_usdt'] or 0 for t in stagnation_trades)
        print(f"   ⚠️  Sorties stagnation: {len(stagnation_trades)} trades = {stag_pnl:.4f} USDT")
    print()
    
    print(f"3️⃣  RECOMMANDATIONS:")
    if risk_reward_ratio < 1.2:
        print(f"   🎯 PRIORITÉ: Améliorer le ratio R:R (actuellement {risk_reward_ratio:.2f}:1)")
        print(f"      → Réduire les pertes moyennes OU augmenter les gains moyens")
    
    if len(sl_trades) > len(trades) * 0.3:
        print(f"   🛑 Trop de stops loss ({len(sl_trades)}/{len(trades)} = {len(sl_trades)/len(trades)*100:.0f}%)")
        print(f"      → Réviser les niveaux de SL ou améliorer les entrées")
    
    if total_fees > abs(total_pnl) * 0.1:
        print(f"   💸 Frais significatifs: {total_fees:.4f} USDT ({total_fees/abs(total_pnl)*100 if total_pnl != 0 else 0:.0f}% du PnL)")
        print(f"      → Optimiser la fréquence de trading ou négocier les frais")
    
    print(f"   💡 Solutions possibles:")
    print(f"      - Augmenter le TP partiel (actuellement visible dans certains trades)")
    print(f"      - Réduire le SL ou améliorer le break-even")
    print(f"      - Filtrer les setups avec ML (si disponible)")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    analyze_17_last_trades()
