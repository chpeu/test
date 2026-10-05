"""
Script d'analyse de la dégradation de performance des derniers trades
"""

import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
env_path = ROOT_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path)

import psycopg2
from datetime import datetime, timedelta
from collections import defaultdict

def main():
    print("=" * 100)
    print("ANALYSE DE DÉGRADATION DE PERFORMANCE - 17 DERNIERS TRADES")
    print("=" * 100)
    print()
    
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', ''),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml')
        )
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ Erreur connexion PostgreSQL: {e}")
        return 1
    
    try:
        # Récupérer les 17 derniers trades avec les métriques disponibles
        query = """
            SELECT 
                t.id,
                t.symbol,
                t.direction,
                t.entry_price,
                t.exit_price,
                t.pnl_pct,
                t.exit_reason,
                t.tp_sl_mode,
                t.timestamp_exit,
                t.duration_seconds,
                t.slippage_pct,
                m.max_pnl_reached,
                m.min_pnl_reached,
                m.be_triggered,
                m.trailing_activated,
                m.stagnation_detected,
                m.be_triggered_pnl_pct as break_even_pnl_pct,
                m.trailing_final_distance_pct,
                0 as total_costs_pct
            FROM trades t
            LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
            WHERE t.exit_price IS NOT NULL
            ORDER BY t.timestamp_exit DESC
            LIMIT 17
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        if not rows:
            print("❌ Aucun trade trouvé")
            conn.close()
            return 1
        
        print(f"✅ {len(rows)} trades récupérés\n")
        
        # Convertir en liste de dicts
        trades = []
        for row in rows:
            trade = dict(zip(columns, row))
            trades.append(trade)
        
        # Inverser pour ordre chronologique
        trades.reverse()
        
        # ========================================
        # ANALYSE GLOBALE
        # ========================================
        total_pnl = sum(t['pnl_pct'] or 0 for t in trades)
        winning_trades = [t for t in trades if (t['pnl_pct'] or 0) > 0]
        losing_trades = [t for t in trades if (t['pnl_pct'] or 0) <= 0]
        
        print("=" * 100)
        print("📊 STATISTIQUES GLOBALES")
        print("=" * 100)
        print(f"Total trades:           {len(trades)}")
        print(f"Gagnants:               {len(winning_trades)} ({len(winning_trades)/len(trades)*100:.1f}%)")
        print(f"Perdants:               {len(losing_trades)} ({len(losing_trades)/len(trades)*100:.1f}%)")
        print(f"PnL total:              {total_pnl:+.2f}%")
        print(f"PnL moyen:              {total_pnl/len(trades):+.3f}%")
        
        if winning_trades:
            avg_win = sum(t['pnl_pct'] for t in winning_trades) / len(winning_trades)
            print(f"Gain moyen:             +{avg_win:.3f}%")
        
        if losing_trades:
            avg_loss = sum(t['pnl_pct'] for t in losing_trades) / len(losing_trades)
            print(f"Perte moyenne:          {avg_loss:.3f}%")
        
        print()
        
        # ========================================
        # ANALYSE PAR RAISON DE SORTIE
        # ========================================
        exit_reasons = defaultdict(lambda: {'count': 0, 'pnl': 0, 'trades': []})
        for trade in trades:
            reason = trade['exit_reason'] or 'UNKNOWN'
            exit_reasons[reason]['count'] += 1
            exit_reasons[reason]['pnl'] += trade['pnl_pct'] or 0
            exit_reasons[reason]['trades'].append(trade)
        
        print("=" * 100)
        print("📋 ANALYSE PAR RAISON DE SORTIE")
        print("=" * 100)
        for reason, data in sorted(exit_reasons.items(), key=lambda x: x[1]['count'], reverse=True):
            avg_pnl = data['pnl'] / data['count']
            print(f"\n{reason}:")
            print(f"  • Nombre:       {data['count']} trades ({data['count']/len(trades)*100:.1f}%)")
            print(f"  • PnL total:    {data['pnl']:+.2f}%")
            print(f"  • PnL moyen:    {avg_pnl:+.3f}%")
            
            # Montrer les trades individuels
            for t in data['trades']:
                duration_min = t['duration_seconds'] / 60 if t['duration_seconds'] else 0
                status = "✅" if (t['pnl_pct'] or 0) > 0 else "❌"
                mfe = t.get('max_pnl_reached', 0) or 0
                print(f"    {status} {t['symbol']:15} {t['direction']:5} | PnL: {t['pnl_pct']:+6.2f}% | MFE: {mfe:+5.2f}% | Durée: {duration_min:5.1f}min")
        
        print()
        
        # ========================================
        # ANALYSE DES PROBLÈMES POTENTIELS
        # ========================================
        print("=" * 100)
        print("🔍 ANALYSE DES PROBLÈMES POTENTIELS")
        print("=" * 100)
        
        # 1. Sorties prématurées (STAGNATION sur trades positifs)
        premature_exits = [t for t in trades if t['exit_reason'] == 'STAGNATION' and (t['max_pnl_reached'] or 0) > 0.20]
        if premature_exits:
            print(f"\n⚠️ SORTIES PRÉMATURÉES ({len(premature_exits)} trades):")
            print("   Trades fermés par STAGNATION alors qu'ils avaient atteint un bon MFE")
            for t in premature_exits:
                lost_profit = (t['max_pnl_reached'] or 0) - (t['pnl_pct'] or 0)
                print(f"   • {t['symbol']:15} | MFE: {t['max_pnl_reached']:+.2f}% → Final: {t['pnl_pct']:+.2f}% | Perte: {lost_profit:.2f}%")
        
        # 2. SL touchés trop tôt (SL sans avoir atteint un bon PnL)
        early_sl = [t for t in trades if t['exit_reason'] in ['SL', 'SL_EXCHANGE'] and (t['max_pnl_reached'] or 0) < 0.10]
        if early_sl:
            print(f"\n⚠️ SL TOUCHÉS RAPIDEMENT ({len(early_sl)} trades):")
            print("   SL touchés sans avoir eu de chance de progresser (MFE < 0.10%)")
            for t in early_sl:
                duration_min = t['duration_seconds'] / 60 if t['duration_seconds'] else 0
                print(f"   • {t['symbol']:15} | PnL: {t['pnl_pct']:+.2f}% | MFE: {t['max_pnl_reached'] or 0:+.2f}% | Durée: {duration_min:.1f}min")
        
        # 3. TP non atteints (TS au lieu de TP)
        missed_tp = [t for t in trades if t['exit_reason'] == 'TS' and (t['max_pnl_reached'] or 0) > (t['pnl_pct'] or 0) + 0.10]
        if missed_tp:
            print(f"\n⚠️ TP NON ATTEINTS ({len(missed_tp)} trades):")
            print("   Trades fermés par trailing avant d'atteindre le TP alors que le MFE était proche")
            for t in missed_tp:
                potential_gain = (t['max_pnl_reached'] or 0) - (t['pnl_pct'] or 0)
                print(f"   • {t['symbol']:15} | Final: {t['pnl_pct']:+.2f}% | MFE: {t['max_pnl_reached']:+.2f}% | Gain potentiel perdu: {potential_gain:.2f}%")
        
        # 4. Coûts élevés
        high_cost_trades = [t for t in trades if (t.get('total_costs_pct') or 0) > 0.10]
        if high_cost_trades:
            print(f"\n⚠️ COÛTS ÉLEVÉS ({len(high_cost_trades)} trades):")
            print("   Trades avec coûts > 0.10% (slippage + autres frais)")
            for t in high_cost_trades:
                print(f"   • {t['symbol']:15} | Coûts: {t.get('total_costs_pct', 0):+.3f}% | Slippage: {t.get('slippage_pct', 0) or 0:+.3f}%")
        
        # 5. Break-Even trop agressif
        be_premature = [t for t in trades if t['be_triggered'] and (t['max_pnl_reached'] or 0) > 0.30 and (t['pnl_pct'] or 0) < 0.10]
        if be_premature:
            print(f"\n⚠️ BREAK-EVEN PRÉMATURÉ ({len(be_premature)} trades):")
            print("   BE activé trop tôt, empêchant le trade de respirer")
            for t in be_premature:
                print(f"   • {t['symbol']:15} | BE à: {t['break_even_pnl_pct']:+.2f}% | MFE: {t['max_pnl_reached']:+.2f}% | Final: {t['pnl_pct']:+.2f}%")
        
        # 6. Trailing trop serré
        tight_trailing = [t for t in trades if t['trailing_activated'] and (t['trailing_final_distance_pct'] or 0) < 0.10]
        if tight_trailing:
            print(f"\n⚠️ TRAILING TROP SERRÉ ({len(tight_trailing)} trades):")
            print("   Distance trailing < 0.10%, risque de sortie prématurée")
            for t in tight_trailing:
                print(f"   • {t['symbol']:15} | Distance: {t['trailing_final_distance_pct']:.3f}% | PnL: {t['pnl_pct']:+.2f}%")
        
        print()
        
        # ========================================
        # IMPACT FINANCIER DES PROBLÈMES
        # ========================================
        print("=" * 100)
        print("💰 IMPACT FINANCIER DES PROBLÈMES")
        print("=" * 100)
        
        total_lost_potential = 0
        
        # Sorties prématurées
        if premature_exits:
            lost = sum((t['max_pnl_reached'] or 0) - (t['pnl_pct'] or 0) for t in premature_exits)
            total_lost_potential += lost
            print(f"Sorties prématurées:     {lost:+.2f}% perdu")
        
        # TP non atteints
        if missed_tp:
            lost = sum((t['max_pnl_reached'] or 0) - (t['pnl_pct'] or 0) for t in missed_tp)
            total_lost_potential += lost
            print(f"TP non atteints:         {lost:+.2f}% perdu")
        
        if total_lost_potential > 0:
            print(f"\n🔥 POTENTIEL PERDU TOTAL:  {total_lost_potential:+.2f}%")
            print(f"   PnL actuel:              {total_pnl:+.2f}%")
            print(f"   PnL potentiel:           {total_pnl + total_lost_potential:+.2f}%")
            print(f"   Amélioration possible:   +{total_lost_potential:+.2f}%")
        
        print()
        
        # ========================================
        # RECOMMANDATIONS
        # ========================================
        print("=" * 100)
        print("💡 RECOMMANDATIONS")
        print("=" * 100)
        
        stagnation_count = exit_reasons.get('STAGNATION', {}).get('count', 0)
        sl_count = exit_reasons.get('SL', {}).get('count', 0) + exit_reasons.get('SL_EXCHANGE', {}).get('count', 0)
        
        if stagnation_count >= 3:
            print("\n1. 🕐 TIMEOUT STAGNATION TROP COURT")
            print("   → Augmenter 'stagnation_exit_timeout_seconds' de 120s à 180s ou 240s")
            print("   → Ou baisser 'stagnation_exit_min_pnl_to_stay' de 0.10% à 0.05%")
        
        if len(premature_exits) >= 2:
            print("\n2. 🎯 PROTECTION MFE INSUFFISANTE")
            print("   → Activer 'trailing_mfe_enabled = True'")
            print("   → Régler 'trailing_mfe_trigger_pct' à 0.15% ou 0.20%")
        
        if len(early_sl) >= 3:
            print("\n3. 🛑 SL TROP SERRÉ")
            print("   → Augmenter 'sl_percent' de 0.20% à 0.25% ou 0.30%")
            print("   → Ou activer mode ATR pour SL adaptatif")
        
        if len(missed_tp) >= 2:
            print("\n4. 📉 TRAILING TROP AGRESSIF")
            print("   → Augmenter 'trailing_distance' de 0.15% à 0.20%")
            print("   → Ou désactiver trailing temporairement")
        
        if len(be_premature) >= 2:
            print("\n5. 🎚️ BREAK-EVEN TROP TÔT")
            print("   → Augmenter 'break_even_trigger' de 0.20% à 0.30%")
            print("   → Ou désactiver BE temporairement")
        
        print()
        print("=" * 100)
        
        conn.close()
        return 0
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        print(traceback.format_exc())
        conn.close()
        return 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
