"""
Script de vérification des 47 derniers trades en mode FIXE
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any

ROOT_DIR = Path(__file__).parent.parent
db_path = ROOT_DIR / 'data' / 'analytics.db'

def main():
    """Fonction principale"""
    print("=" * 80)
    print("VÉRIFICATION MODE FIXE - 47 DERNIERS TRADES")
    print("=" * 80)
    print()
    
    if not db_path.exists():
        print(f"❌ Base de données introuvable: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Récupérer les 47 derniers trades fermés
    print("📊 Récupération des 47 derniers trades fermés...")
    query = """
        SELECT 
            id,
            symbol,
            direction,
            entry,
            exit,
            net_pnl_pct,
            reason as exit_reason,
            tp_sl_mode,
            timestamp
        FROM trades
        WHERE exit IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 47
    """
    
    rows = cursor.execute(query).fetchall()
    
    if not rows:
        print("❌ Aucun trade trouvé")
        conn.close()
        return
    
    print(f"✅ {len(rows)} trades récupérés\n")
    
    # Statistiques globales
    total_trades = len(rows)
    fixe_trades = []
    atr_trades = []
    unknown_trades = []
    
    # Erreurs détectées
    all_errors = []
    trades_with_errors = []
    
    # Analyser chaque trade
    for i, row in enumerate(rows, 1):
        trade_id = row['id']
        symbol = row['symbol']
        direction = row['direction']
        tp_sl_mode = row['tp_sl_mode'] or 'NULL'
        exit_reason = row['exit_reason'] or 'UNKNOWN'
        pnl_pct = row['net_pnl_pct'] or 0
        timestamp = row['timestamp']
        
        trade_info = {
            'id': trade_id,
            'symbol': symbol,
            'direction': direction,
            'tp_sl_mode': tp_sl_mode,
            'exit_reason': exit_reason,
            'pnl_pct': pnl_pct,
            'timestamp': timestamp
        }
        
        # Classifier par mode
        if tp_sl_mode == 'FIXE':
            fixe_trades.append(trade_info)
        elif tp_sl_mode == 'ATR':
            atr_trades.append(trade_info)
        else:
            unknown_trades.append(trade_info)
        
        # Vérifier les trades FIXE
        if tp_sl_mode == 'FIXE':
            forbidden_exits = ['STAGNATION_MFE_PROTECT', 'STAGNATION_POSITIVE']
            for forbidden in forbidden_exits:
                if forbidden in exit_reason:
                    error = {
                        'trade_id': trade_id,
                        'symbol': symbol,
                        'direction': direction,
                        'exit_reason': exit_reason,
                        'pnl_pct': pnl_pct,
                        'timestamp': timestamp,
                        'forbidden_mechanism': forbidden
                    }
                    all_errors.append(error)
                    trades_with_errors.append(trade_info)
                    break
    
    conn.close()
    
    # Afficher les statistiques
    print("=" * 80)
    print("STATISTIQUES GLOBALES")
    print("=" * 80)
    print(f"Total trades analysés:     {total_trades}")
    print(f"  • Mode FIXE:             {len(fixe_trades)} ({len(fixe_trades)/total_trades*100:.1f}%)")
    print(f"  • Mode ATR:              {len(atr_trades)} ({len(atr_trades)/total_trades*100:.1f}%)")
    print(f"  • Mode UNKNOWN/NULL:     {len(unknown_trades)} ({len(unknown_trades)/total_trades*100:.1f}%)")
    print()
    
    # Afficher les erreurs détectées
    if all_errors:
        print("=" * 80)
        print(f"❌ ERREURS CRITIQUES DÉTECTÉES : {len(all_errors)} TRADE(S)")
        print("=" * 80)
        print()
        
        for i, error in enumerate(all_errors, 1):
            print(f"{'─' * 80}")
            print(f"ERREUR #{i} - Trade ID {error['trade_id']}")
            print(f"{'─' * 80}")
            print(f"  Symbole:        {error['symbol']} {error['direction']}")
            print(f"  Sortie:         {error['exit_reason']}")
            print(f"  PnL:            {error['pnl_pct']:.2f}%")
            print(f"  Timestamp:      {error['timestamp']}")
            print(f"  Mécanisme:      {error['forbidden_mechanism']}")
            print()
            print(f"  ⚠️ PROBLÈME: Ce mécanisme ({error['forbidden_mechanism']}) ne devrait")
            print(f"             s'appliquer QU'EN MODE ATR, pas en mode FIXE!")
            print()
    else:
        print("=" * 80)
        print("✅ AUCUNE ERREUR DÉTECTÉE")
        print("=" * 80)
        print()
        if len(fixe_trades) > 0:
            print(f"Tous les {len(fixe_trades)} trades en mode FIXE sont CONFORMES:")
            print("  ✓ Pas de sortie par MFE_PROTECT")
            print("  ✓ Pas de sortie par STAGNATION_POSITIVE")
        else:
            print("⚠️ Aucun trade en mode FIXE trouvé dans les 47 derniers trades")
    
    print()
    
    # Afficher un aperçu des trades FIXE
    if len(fixe_trades) > 0:
        print("=" * 80)
        print(f"APERÇU DES TRADES MODE FIXE ({len(fixe_trades)} trades)")
        print("=" * 80)
        print()
        
        # Statistiques des sorties
        exit_stats = {}
        pnl_positive = 0
        pnl_negative = 0
        total_pnl = 0
        
        for trade in fixe_trades:
            exit_reason = trade['exit_reason']
            if exit_reason not in exit_stats:
                exit_stats[exit_reason] = 0
            exit_stats[exit_reason] += 1
            
            pnl = trade['pnl_pct']
            total_pnl += pnl
            if pnl > 0:
                pnl_positive += 1
            else:
                pnl_negative += 1
        
        print(f"Raisons de sortie:")
        for reason, count in sorted(exit_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {reason:30} {count:3} trades ({count/len(fixe_trades)*100:.1f}%)")
        
        print()
        print(f"Performance:")
        print(f"  • Trades gagnants:  {pnl_positive} ({pnl_positive/len(fixe_trades)*100:.1f}%)")
        print(f"  • Trades perdants:  {pnl_negative} ({pnl_negative/len(fixe_trades)*100:.1f}%)")
        print(f"  • PnL moyen:        {total_pnl/len(fixe_trades):.3f}%")
        print(f"  • PnL total:        {total_pnl:.2f}%")
        print()
        
        # Afficher les 5 premiers et 5 derniers
        print("5 trades les plus récents:")
        for trade in fixe_trades[:5]:
            status = "✅" if trade['pnl_pct'] > 0 else "❌"
            print(f"  {status} ID {trade['id']:3} | {trade['symbol']:15} {trade['direction']:5} | "
                  f"Sortie: {trade['exit_reason']:20} | PnL: {trade['pnl_pct']:6.2f}%")
        
        if len(fixe_trades) > 10:
            print("\n5 trades les plus anciens:")
            for trade in fixe_trades[-5:]:
                status = "✅" if trade['pnl_pct'] > 0 else "❌"
                print(f"  {status} ID {trade['id']:3} | {trade['symbol']:15} {trade['direction']:5} | "
                      f"Sortie: {trade['exit_reason']:20} | PnL: {trade['pnl_pct']:6.2f}%")
    
    print()
    print("=" * 80)
    print("FIN DE LA VÉRIFICATION")
    print("=" * 80)
    
    # Retourner code d'erreur si problèmes
    return 1 if all_errors else 0


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code if exit_code else 0)
