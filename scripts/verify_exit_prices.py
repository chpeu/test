#!/usr/bin/env python3
"""
Script de verification des prix de sortie
==========================================
Verifie que les prix de sortie dans la base correspondent aux prix reels d'execution MEXC.

Analyse:
1. Trades avec exit_reason = SL_EXCHANGE -> prix doit correspondre au SL MEXC execute
2. Trades normaux -> prix doit correspondre au filled_price de l'ordre
3. Detecte les ecarts significatifs entre prix theorique et prix reel
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

def analyze_exit_prices():
    from core.postgresql_datalogger import PostgreSQLDataLogger
    
    pg_logger = PostgreSQLDataLogger()
    if not pg_logger.enabled:
        print("PostgreSQL non disponible")
        return
    
    conn = pg_logger.pool.getconn()
    try:
        with conn.cursor() as cur:
            # 1. Analyser les trades recents (7 derniers jours)
            cur.execute("""
                SELECT 
                    id, symbol, direction, 
                    entry_price, exit_price, sl_price, tp_price,
                    exit_reason, pnl_pct, net_pnl_pct,
                    entry_fill_price, exit_fill_price,
                    created_at
                FROM trades 
                WHERE created_at > NOW() - INTERVAL '7 days'
                ORDER BY created_at DESC
                LIMIT 50
            """)
            trades = cur.fetchall()
            
            if not trades:
                print("Aucun trade trouve dans les 7 derniers jours")
                return
            
            print(f"=== ANALYSE DES PRIX DE SORTIE ({len(trades)} trades) ===\n")
            
            # Statistiques
            stats = {
                'total': len(trades),
                'sl_exchange': 0,
                'normal_close': 0,
                'exit_fill_available': 0,
                'exit_fill_missing': 0,
                'price_mismatch': 0,
                'price_mismatch_details': []
            }
            
            for t in trades:
                trade_id = t[0]
                symbol = t[1]
                direction = t[2]
                entry_price = float(t[3]) if t[3] else 0
                exit_price = float(t[4]) if t[4] else 0
                sl_price = float(t[5]) if t[5] else 0
                tp_price = float(t[6]) if t[6] else 0
                exit_reason = t[7]
                pnl_pct = float(t[8]) if t[8] else 0
                net_pnl_pct = float(t[9]) if t[9] else 0
                entry_fill = float(t[10]) if t[10] else 0
                exit_fill = float(t[11]) if t[11] else 0
                created_at = t[12]
                
                # Categoriser
                if exit_reason == 'SL_EXCHANGE':
                    stats['sl_exchange'] += 1
                else:
                    stats['normal_close'] += 1
                
                # Verifier exit_fill_price
                if exit_fill and exit_fill > 0:
                    stats['exit_fill_available'] += 1
                else:
                    stats['exit_fill_missing'] += 1
                
                # Detecter les ecarts significatifs
                # Pour SL_EXCHANGE: comparer exit_price avec sl_price
                if exit_reason == 'SL_EXCHANGE' and sl_price > 0 and exit_price > 0:
                    # Calculer l'ecart entre le SL theorique et le prix de sortie
                    if direction == 'SHORT':
                        # Pour SHORT, SL est au-dessus de entry
                        expected_exit = sl_price  # Le SL du bot
                        actual_exit = exit_price
                    else:
                        expected_exit = sl_price
                        actual_exit = exit_price
                    
                    ecart_pct = abs(actual_exit - expected_exit) / expected_exit * 100 if expected_exit > 0 else 0
                    
                    if ecart_pct > 0.1:  # Plus de 0.1% d'ecart
                        stats['price_mismatch'] += 1
                        stats['price_mismatch_details'].append({
                            'id': str(trade_id)[:8],
                            'symbol': symbol,
                            'reason': exit_reason,
                            'expected': expected_exit,
                            'actual': actual_exit,
                            'ecart_pct': ecart_pct,
                            'exit_fill': exit_fill,
                            'date': created_at
                        })
            
            # Afficher les resultats
            print(f"Total trades: {stats['total']}")
            print(f"  - SL_EXCHANGE: {stats['sl_exchange']}")
            print(f"  - Autres clotures: {stats['normal_close']}")
            print(f"\nPrix de sortie reel (exit_fill_price):")
            print(f"  - Disponible: {stats['exit_fill_available']}")
            print(f"  - Manquant: {stats['exit_fill_missing']}")
            
            if stats['price_mismatch'] > 0:
                print(f"\n!!! ECARTS DETECTES: {stats['price_mismatch']} trades !!!")
                print("-" * 80)
                for m in stats['price_mismatch_details'][:10]:  # Max 10
                    print(f"  Trade {m['id']} | {m['symbol']} | {m['reason']}")
                    print(f"    Attendu: {m['expected']:.6f} | Reel: {m['actual']:.6f} | Ecart: {m['ecart_pct']:.3f}%")
                    print(f"    exit_fill_price: {m['exit_fill'] if m['exit_fill'] else 'NON RENSEIGNE'}")
                    print(f"    Date: {m['date']}")
                    print()
            else:
                print("\nAucun ecart significatif detecte.")
            
            # 2. Verifier les colonnes disponibles
            print("\n=== VERIFICATION COLONNES PRIX ===")
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'trades' 
                AND column_name LIKE '%price%' OR column_name LIKE '%fill%'
                ORDER BY column_name
            """)
            cols = [r[0] for r in cur.fetchall()]
            print(f"Colonnes prix disponibles: {cols}")
            
            # 3. Recommandations
            print("\n=== RECOMMANDATIONS ===")
            if stats['exit_fill_missing'] > 0:
                print(f"- {stats['exit_fill_missing']} trades n'ont pas de exit_fill_price")
                print("  -> Verifier que le code recupere bien le prix reel d'execution")
            
            if stats['price_mismatch'] > 0:
                print(f"- {stats['price_mismatch']} trades ont un ecart entre prix attendu et reel")
                print("  -> Pour SL_EXCHANGE: le prix de sortie devrait etre le dealAvgPrice MEXC")
            
            if stats['exit_fill_missing'] == 0 and stats['price_mismatch'] == 0:
                print("Tout semble correct!")
                
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pg_logger.pool.putconn(conn)

if __name__ == "__main__":
    analyze_exit_prices()
