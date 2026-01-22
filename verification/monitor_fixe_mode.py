"""
Script de monitoring en continu du mode FIXE
Surveille les nouveaux trades et vérifie qu'aucun problème n'apparaît en mode FIXE
"""

import sqlite3
from pathlib import Path
import time
from datetime import datetime

ROOT_DIR = Path(__file__).parent.parent
db_path = ROOT_DIR / 'data' / 'analytics.db'

def get_last_trade_id():
    """Récupérer l'ID du dernier trade"""
    if not db_path.exists():
        return None
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    row = cursor.execute("SELECT MAX(id) FROM trades").fetchone()
    conn.close()
    
    return row[0] if row and row[0] else 0


def check_trade(trade_id):
    """Vérifier un trade spécifique"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
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
        WHERE id = ? AND exit IS NOT NULL
    """
    
    row = cursor.execute(query, (trade_id,)).fetchone()
    conn.close()
    
    if not row:
        return None
    
    return dict(row)


def verify_trade(trade):
    """Vérifier qu'un trade respecte les règles du mode FIXE"""
    trade_id = trade['id']
    symbol = trade['symbol']
    direction = trade['direction']
    tp_sl_mode = trade['tp_sl_mode'] or 'NULL'
    exit_reason = trade['exit_reason'] or 'UNKNOWN'
    pnl_pct = trade['net_pnl_pct'] or 0
    timestamp = trade['timestamp']
    
    print(f"\n{'═' * 80}")
    print(f"NOUVEAU TRADE FERMÉ - ID {trade_id}")
    print(f"{'═' * 80}")
    print(f"  Symbole:      {symbol} {direction}")
    print(f"  Mode TP/SL:   {tp_sl_mode}")
    print(f"  Sortie:       {exit_reason}")
    print(f"  PnL:          {pnl_pct:.2f}%")
    print(f"  Timestamp:    {timestamp}")
    
    # Vérifier si c'est un trade FIXE
    if tp_sl_mode == 'FIXE':
        print(f"\n  🔍 VÉRIFICATION MODE FIXE...")
        
        # Vérifier les sorties interdites
        forbidden_exits = ['STAGNATION_MFE_PROTECT', 'STAGNATION_POSITIVE']
        has_error = False
        
        for forbidden in forbidden_exits:
            if forbidden in exit_reason:
                print(f"\n  ❌ ALERTE CRITIQUE: Sortie interdite détectée!")
                print(f"     Exit reason: {exit_reason}")
                print(f"     Ce mécanisme ({forbidden}) ne devrait s'appliquer QU'EN MODE ATR")
                print(f"\n  ⚠️ ACTION REQUISE:")
                print(f"     1. Vérifier que le backend a bien été redémarré")
                print(f"     2. Analyser les logs backend pour ce trade")
                print(f"     3. Vérifier la configuration tp_sl_mode")
                has_error = True
                break
        
        if not has_error:
            print(f"\n  ✅ Trade FIXE CONFORME")
            print(f"     Aucun problème détecté")
    
    elif tp_sl_mode == 'NULL':
        print(f"\n  ⚠️ WARNING: tp_sl_mode non renseigné")
        print(f"     Le champ tp_sl_mode devrait être 'FIXE' ou 'ATR'")
    
    print(f"{'═' * 80}\n")


def main():
    """Fonction principale de monitoring"""
    print("=" * 80)
    print("MONITORING MODE FIXE - SURVEILLANCE EN TEMPS RÉEL")
    print("=" * 80)
    print()
    print("Ce script surveille les nouveaux trades et vérifie:")
    print("  ✓ Pas de sortie par MFE_PROTECT en mode FIXE")
    print("  ✓ Pas de sortie par STAGNATION_POSITIVE en mode FIXE")
    print("  ✓ Le champ tp_sl_mode est bien renseigné")
    print()
    print("Appuyez sur Ctrl+C pour arrêter le monitoring...")
    print("=" * 80)
    
    if not db_path.exists():
        print(f"\n❌ Base de données introuvable: {db_path}")
        return
    
    last_checked_id = get_last_trade_id()
    print(f"\n📊 Dernier trade ID: {last_checked_id}")
    print(f"⏳ En attente de nouveaux trades fermés...\n")
    
    try:
        while True:
            current_max_id = get_last_trade_id()
            
            if current_max_id and current_max_id > last_checked_id:
                # Nouveaux trades détectés
                for trade_id in range(last_checked_id + 1, current_max_id + 1):
                    trade = check_trade(trade_id)
                    if trade:
                        verify_trade(trade)
                
                last_checked_id = current_max_id
            
            # Attendre 5 secondes avant la prochaine vérification
            time.sleep(5)
    
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("MONITORING ARRÊTÉ PAR L'UTILISATEUR")
        print("=" * 80)
        print()


if __name__ == "__main__":
    main()
