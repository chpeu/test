"""
Script de vérification simplifié du mode FIXE
Vérifie les 4 derniers trades pour détecter les problèmes de mode FIXE
"""

import sqlite3
from pathlib import Path
import json
from typing import List, Dict, Any

ROOT_DIR = Path(__file__).parent.parent
db_path = ROOT_DIR / 'data' / 'analytics.db'

def main():
    """Fonction principale"""
    print("=" * 80)
    print("VÉRIFICATION MODE FIXE - 4 DERNIERS TRADES")
    print("=" * 80)
    print()
    
    if not db_path.exists():
        print(f"❌ Base de données introuvable: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Récupérer les 4 derniers trades
    print("📊 Récupération des 4 derniers trades...")
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
        LIMIT 4
    """
    
    rows = cursor.execute(query).fetchall()
    
    if not rows:
        print("❌ Aucun trade trouvé")
        conn.close()
        return
    
    print(f"✅ {len(rows)} trades récupérés\n")
    
    # Analyser chaque trade
    all_errors = []
    fixe_count = 0
    
    for i, row in enumerate(rows, 1):
        trade_id = row['id']
        symbol = row['symbol']
        direction = row['direction']
        tp_sl_mode = row['tp_sl_mode'] or 'UNKNOWN'
        exit_reason = row['exit_reason'] or 'UNKNOWN'
        pnl_pct = row['net_pnl_pct'] or 0
        timestamp = row['timestamp']
        
        print(f"{'─' * 80}")
        print(f"Trade #{i} - ID {trade_id}")
        print(f"{'─' * 80}")
        print(f"  Symbole:      {symbol} {direction}")
        print(f"  Mode TP/SL:   {tp_sl_mode}")
        print(f"  Sortie:       {exit_reason}")
        print(f"  PnL:          {pnl_pct:.2f}%")
        print(f"  Timestamp:    {timestamp}")
        
        # Vérifications si c'est un trade FIXE
        if tp_sl_mode == 'FIXE':
            fixe_count += 1
            errors = []
            
            # 1. Vérifier que le trade ne s'est PAS fermé par MFE_PROTECT ou STAGNATION_POSITIVE
            forbidden_exits = ['STAGNATION_MFE_PROTECT', 'STAGNATION_POSITIVE']
            if any(forbidden in exit_reason for forbidden in forbidden_exits):
                errors.append(
                    f"❌ CRITIQUE: Sortie interdite en mode FIXE: {exit_reason}\n"
                    f"   Ce mécanisme ne devrait s'appliquer QU'EN MODE ATR"
                )
            
            # Afficher les résultats
            if errors:
                print("\n  ⚠️ PROBLÈMES DÉTECTÉS:")
                for error in errors:
                    print(f"    {error}")
                all_errors.extend(errors)
            else:
                print("\n  ✅ Trade FIXE conforme - Aucun problème détecté")
        else:
            print(f"\n  ℹ️ Trade en mode {tp_sl_mode} (pas de vérification FIXE)")
        
        print()
    
    conn.close()
    
    # Résumé final
    print("=" * 80)
    print("RÉSUMÉ DE LA VÉRIFICATION")
    print("=" * 80)
    
    if fixe_count == 0:
        print(f"⚠️ Aucun trade en mode FIXE trouvé dans les 4 derniers trades")
        print(f"\nModes trouvés:")
        for row in rows:
            print(f"  - Trade {row['id']}: {row['tp_sl_mode'] or 'NULL'}")
    elif not all_errors:
        print(f"✅ TOUS LES TRADES FIXE SONT CONFORMES ({fixe_count}/{len(rows)} trades)")
        print("\n   Vérifications effectuées:")
        print("   ✓ Pas de sortie par MFE_PROTECT ou STAGNATION_POSITIVE")
        print("\n   Le mode FIXE fonctionne comme attendu !")
    else:
        print(f"❌ {len(all_errors)} ERREUR(S) CRITIQUE(S) DÉTECTÉE(S) sur {fixe_count} trade(s) FIXE")
        print("\n⚠️ Actions recommandées:")
        print("1. Vérifier que le backend a bien été redémarré après les corrections")
        print("2. Vérifier le paramètre tp_sl_mode dans la configuration")
        print("3. Analyser les logs backend pour comprendre pourquoi MFE_PROTECT s'est déclenché")
        print("4. Si le backend n'a pas été redémarré, le faire maintenant")
    
    print()
    
    # Retourner un code d'erreur si des problèmes ont été détectés
    return 1 if all_errors else 0


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code if exit_code else 0)
