"""
Analyse détaillée du trade ASTER
"""
import sqlite3
import os
import json

def main():
    try:
        db_path = 'data/analytics.db'
        
        if not os.path.exists(db_path):
            print(f"❌ Base de données introuvable: {db_path}")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("🔍 ANALYSE DU TRADE ASTER")
        print("=" * 80)
        
        # D'abord lister tous les symboles récents
        cursor.execute("SELECT DISTINCT symbol FROM trades ORDER BY timestamp DESC LIMIT 20")
        recent_symbols = cursor.fetchall()
        print("Symboles récents dans la DB:")
        for s in recent_symbols:
            print(f"  - {s[0]}")
        print()
        
        # Chercher tous les trades ASTER avec plusieurs variantes
        query = """
            SELECT 
                id, symbol, direction, entry, exit, 
                net_pnl_pct, reason, duration,
                max_pnl_reached, min_pnl_reached,
                trailing_stop_triggered, break_even_triggered,
                trailing_stop_updates,
                timestamp, tp_sl_mode
            FROM trades
            WHERE symbol LIKE '%ASTER%' OR symbol LIKE '%ASTR%'
            ORDER BY timestamp DESC
            LIMIT 5
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("❌ Aucun trade ASTER trouvé")
            return
        
        print(f"\n✅ {len(rows)} trade(s) ASTER trouvé(s)\n")
        
        for idx, row in enumerate(rows, 1):
            (trade_id, symbol, direction, entry, exit_price, 
             pnl_pct, exit_reason, duration,
             max_pnl, min_pnl,
             trailing_triggered, be_triggered,
             trailing_updates,
             timestamp, tp_sl_mode) = row
            
            duration_min = (duration / 60) if duration else 0
            
            print("="*80)
            print(f"TRADE #{idx} - {symbol}")
            print("="*80)
            print(f"ID: {trade_id}")
            print(f"Timestamp: {timestamp}")
            print(f"Direction: {direction}")
            print(f"Mode: {tp_sl_mode}")
            print(f"Entry: {entry:.8f}")
            print(f"Exit: {exit_price:.8f}")
            print(f"Durée: {duration_min:.1f} min")
            
            print(f"\n💰 Performance:")
            print(f"   PnL final: {pnl_pct:.3f}%")
            print(f"   Max PnL (MFE): {max_pnl:.3f}%" if max_pnl else "   Max PnL (MFE): N/A")
            print(f"   Min PnL: {min_pnl:.3f}%" if min_pnl else "   Min PnL: N/A")
            
            if max_pnl and pnl_pct:
                pullback = max_pnl - pnl_pct
                print(f"   📉 Pullback depuis MFE: {pullback:.3f}%")
                if max_pnl > 0:
                    capture_rate = (pnl_pct / max_pnl * 100)
                    print(f"   📊 Taux de capture MFE: {capture_rate:.1f}%")
            
            print(f"\n🎢 Trailing Stop:")
            print(f"   Activé: {'✅ OUI' if trailing_triggered else '❌ NON'}")
            print(f"   Break-Even: {'✅ OUI' if be_triggered else '❌ NON'}")
            
            # Analyser les updates de trailing si disponibles
            if trailing_updates:
                try:
                    updates = json.loads(trailing_updates)
                    if updates:
                        print(f"\n   📝 Historique trailing ({len(updates)} updates):")
                        for i, update in enumerate(updates[-5:], 1):  # 5 derniers
                            print(f"      {i}. {update}")
                except:
                    print(f"\n   📝 Trailing updates: {trailing_updates}")
            
            print(f"\n🚪 Analyse de sortie:")
            print(f"   Raison: {exit_reason}")
            
            if exit_reason == 'TS':
                print(f"   ✅ Trailing Stop a fermé le trade")
                if max_pnl and pnl_pct:
                    if pullback > 0.15:
                        print(f"   ⚠️ PULLBACK IMPORTANT: {pullback:.3f}%")
                        print(f"   💡 Le trailing était peut-être trop loin")
                    else:
                        print(f"   ✅ Pullback acceptable: {pullback:.3f}%")
            elif exit_reason == 'SL' and pnl_pct < 0:
                print(f"   ❌ SL touché en perte")
                if max_pnl and max_pnl > 0.15:
                    print(f"   ⚠️ PROBLÈME MAJEUR: Trade avait {max_pnl:.3f}% de gains")
                    print(f"   ⚠️ Trailing aurait dû protéger ces gains!")
                    print(f"   ⚠️ Perte totale depuis MFE: {pullback:.3f}%")
            
            # Diagnostic spécifique
            print(f"\n🔧 Diagnostic:")
            
            if not trailing_triggered and max_pnl and max_pnl > 0.15:
                print(f"   ❌ PROBLÈME: Trailing NON activé malgré MFE de {max_pnl:.3f}%")
                print(f"   → Avec trigger 0.15%, trailing aurait dû s'activer")
                print(f"   → Vérifier si la config était chargée au moment du trade")
            
            if trailing_triggered and exit_reason == 'SL' and pnl_pct < 0:
                print(f"   ❌ PROBLÈME: Trailing activé MAIS SL touché en perte")
                print(f"   → Le trailing n'a pas suivi le prix correctement")
                print(f"   → Distance trailing (0.1%) peut-être trop large")
            
            if max_pnl and max_pnl > 0.3 and pnl_pct < 0.1:
                print(f"\n   🚨 PERTE MAJEURE DE PROFITS:")
                print(f"      • Potentiel max: +{max_pnl:.3f}%")
                print(f"      • Réalisé: +{pnl_pct:.3f}%")
                print(f"      • Manqué: {max_pnl - pnl_pct:.3f}%")
                print(f"   💡 Trailing distance 0.1% est TROP LARGE pour cette volatilité")
            
            # Calcul du SL idéal qui aurait dû être en place
            if direction == 'LONG' and max_pnl and max_pnl > 0.15:
                # À MFE max, le SL trailing aurait dû être à:
                ideal_price_at_mfe = entry * (1 + max_pnl / 100)
                ideal_sl_at_mfe = ideal_price_at_mfe * (1 - 0.1 / 100)  # -0.1% distance
                ideal_sl_pct_from_entry = ((ideal_sl_at_mfe - entry) / entry * 100)
                
                print(f"\n   📐 Calcul SL idéal:")
                print(f"      • Au MFE ({max_pnl:.3f}%), prix était: {ideal_price_at_mfe:.8f}")
                print(f"      • SL trailing aurait dû être à: {ideal_sl_at_mfe:.8f}")
                print(f"      • = {ideal_sl_pct_from_entry:.3f}% depuis entry")
                print(f"      • PnL si SL touché: ~{ideal_sl_pct_from_entry - 0.1:.3f}%")
            
            print()
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
