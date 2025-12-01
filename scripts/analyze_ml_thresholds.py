
import sys
import os
import pandas as pd
from datetime import timedelta

# Force UTF-8 for stdout
sys.stdout.reconfigure(encoding='utf-8')

# Ajouter le dossier racine au path pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.callbacks.scanner_loop import get_pg_datalogger

def analyze_ml_thresholds():
    print("Connexion a la base de donnees...")
    pg = get_pg_datalogger()
    if not pg or not pg.enabled:
        print("[ERREUR] PostgreSQL non active ou non configure.")
        return

    # 1. Récupérer les trades
    print("Recuperation des trades...")
    query_trades = """
        SELECT symbol, timestamp_entry as opened_at, net_pnl_usdt, net_pnl_pct 
        FROM trades 
        WHERE session_id IS NOT NULL 
        ORDER BY timestamp_entry ASC
    """
    trades_data = pg._execute_query(query_trades, fetch=True)
    if not trades_data:
        print("[ERREUR] Aucun trade trouve.")
        return
    
    df_trades = pd.DataFrame(trades_data, columns=['symbol', 'opened_at', 'net_pnl_usdt', 'net_pnl_pct'])
    df_trades['opened_at'] = pd.to_datetime(df_trades['opened_at'])
    
    # 2. Récupérer les logs de scan avec ML
    print("Recuperation des logs ML...")
    query_scans = """
        SELECT symbol, timestamp, ml_confidence 
        FROM scan_logs 
        WHERE ml_confidence IS NOT NULL 
        ORDER BY timestamp ASC
    """
    scans_data = pg._execute_query(query_scans, fetch=True)
    if not scans_data:
        print("[WARN] Aucun log ML trouve. L'analyse sera limitee.")
        df_scans = pd.DataFrame(columns=['symbol', 'timestamp', 'ml_confidence'])
    else:
        df_scans = pd.DataFrame(scans_data, columns=['symbol', 'timestamp', 'ml_confidence'])
        df_scans['timestamp'] = pd.to_datetime(df_scans['timestamp'])

    # 3. Matcher les trades avec leur confiance ML
    print("Association Trades <-> ML Confidence...")
    
    # On va chercher le scan le plus proche AVANT le trade (max 15 min avant)
    trades_with_ml = []
    
    # Pour optimiser, on peut trier
    df_scans = df_scans.sort_values('timestamp')
    
    # Optimisation: ne pas iterer si pas de scans
    if df_scans.empty:
        for idx, trade in df_trades.iterrows():
            trades_with_ml.append({
                'net_pnl_usdt': trade['net_pnl_usdt'],
                'is_win': 1 if trade['net_pnl_usdt'] >= 0 else 0,
                'ml_confidence': 0.0
            })
    else:
        for idx, trade in df_trades.iterrows():
            # Filtrer scans pour ce symbole avant le trade
            # Note: On utilise .values pour performance si possible, mais ici restons simple
            mask = (
                (df_scans['symbol'] == trade['symbol']) & 
                (df_scans['timestamp'] <= trade['opened_at']) & 
                (df_scans['timestamp'] >= trade['opened_at'] - timedelta(minutes=15))
            )
            relevant_scans = df_scans[mask]
            
            ml_conf = 0.0 # Par défaut 0 si pas de ML trouvé
            if not relevant_scans.empty:
                # Prendre le plus récent
                ml_conf = float(relevant_scans.iloc[-1]['ml_confidence'])
                
            trades_with_ml.append({
                'net_pnl_usdt': float(trade['net_pnl_usdt']),
                'is_win': 1 if trade['net_pnl_usdt'] >= 0 else 0,
                'ml_confidence': ml_conf
            })
    
    df_final = pd.DataFrame(trades_with_ml)
    
    # 4. Calculer les stats par seuil
    print("\nRESULTATS DE L'ANALYSE ML")
    print("=" * 85)
    print(f"{'SEUIL ML':<15} | {'NB TRADES':<10} | {'WINRATE':<10} | {'PNL TOTAL':<12} | {'PNL MOYEN':<10}")
    print("-" * 85)
    
    thresholds = [0, 25, 30, 35, 40, 45, 50, 55, 60]
    
    # Base (Tous les trades sans filtre ou filtre 0)
    base_count = len(df_final)
    base_wins = df_final['is_win'].sum()
    base_wr = (base_wins / base_count * 100) if base_count > 0 else 0
    base_pnl = df_final['net_pnl_usdt'].sum()
    base_avg = df_final['net_pnl_usdt'].mean() if base_count > 0 else 0
    
    print(f"{'Desactive':<15} | {base_count:<10} | {base_wr:6.1f}%    | {base_pnl:9.2f}$  | {base_avg:6.2f}$")
    print("-" * 85)
    
    for thresh in thresholds:
        if thresh == 0: continue
        
        # Filtrer
        subset = df_final[df_final['ml_confidence'] >= thresh]
        
        count = len(subset)
        wins = subset['is_win'].sum()
        wr = (wins / count * 100) if count > 0 else 0
        pnl = subset['net_pnl_usdt'].sum()
        avg = subset['net_pnl_usdt'].mean() if count > 0 else 0
        
        print(f"{f'>= {thresh}%':<15} | {count:<10} | {wr:6.1f}%    | {pnl:9.2f}$  | {avg:6.2f}$")

    print("=" * 85)
    print("\nNote: Cette analyse matche chaque trade passe avec le log de scan ML le plus proche")
    print("trouve dans les 15 minutes precedant l'ouverture du trade.")

if __name__ == "__main__":
    analyze_ml_thresholds()
