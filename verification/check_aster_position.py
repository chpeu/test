"""
Script pour vérifier la position ASTER active et l'état du trailing stop
"""
import psycopg2
from datetime import datetime, timezone
import os

def main():
    try:
        # Connexion PostgreSQL
        db_config = {
            'dbname': os.getenv('POSTGRES_DB', 'trading_db'),
            'user': os.getenv('POSTGRES_USER', 'trading_user'),
            'password': os.getenv('POSTGRES_PASSWORD', 'trading_password'),
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432')
        }
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        print("=" * 60)
        print("🔍 VÉRIFICATION POSITION ASTER ACTIVE")
        print("=" * 60)
        
        # Récupérer la position ASTER active (exit_price IS NULL)
        query = """
            SELECT 
                t.id,
                t.symbol,
                t.direction,
                t.entry_price,
                t.sl,
                t.tp,
                t.size,
                t.pnl_pct,
                t.timestamp_entry,
                t.tp_sl_mode,
                m.max_pnl_reached,
                m.trailing_activated,
                m.trailing_trigger_pnl_pct,
                m.trailing_final_distance_pct,
                m.be_triggered,
                m.be_triggered_pnl_pct,
                m.stagnation_detected
            FROM trades t
            LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
            WHERE t.symbol LIKE '%ASTER%'
              AND t.exit_price IS NULL
            ORDER BY t.timestamp_entry DESC
            LIMIT 1
        """
        
        cursor.execute(query)
        row = cursor.fetchone()
        
        if not row:
            print("❌ Aucune position ASTER active trouvée")
            return
        
        # Extraire les données
        (trade_id, symbol, direction, entry_price, sl, tp, size, pnl_pct, 
         timestamp_entry, tp_sl_mode, max_pnl_reached, trailing_activated,
         trailing_trigger_pnl_pct, trailing_final_distance_pct, be_triggered,
         be_triggered_pnl_pct, stagnation_detected) = row
        
        # Calculer durée
        now = datetime.now(timezone.utc)
        if timestamp_entry:
            if timestamp_entry.tzinfo is None:
                timestamp_entry = timestamp_entry.replace(tzinfo=timezone.utc)
            duration_seconds = (now - timestamp_entry).total_seconds()
            duration_minutes = duration_seconds / 60
        else:
            duration_minutes = 0
        
        print(f"\n✅ Position trouvée: {symbol}")
        print(f"   Trade ID: {trade_id}")
        print(f"   Direction: {direction}")
        print(f"   Entry: {entry_price:.6f}")
        print(f"   SL actuel: {sl:.6f}")
        print(f"   TP: {tp:.6f}")
        print(f"   Size: {size:.2f} USDT")
        print(f"   Mode: {tp_sl_mode}")
        print(f"   Durée: {duration_minutes:.1f} min")
        
        print(f"\n📊 État actuel:")
        print(f"   PnL: {pnl_pct:.3f}%")
        print(f"   Max PnL (MFE): {max_pnl_reached:.3f}%" if max_pnl_reached else "   Max PnL (MFE): N/A")
        
        print(f"\n🔧 Trailing Stop:")
        print(f"   Trailing activé: {'✅ OUI' if trailing_activated else '❌ NON'}")
        if trailing_trigger_pnl_pct:
            print(f"   Trigger PnL: {trailing_trigger_pnl_pct:.3f}%")
        if trailing_final_distance_pct:
            print(f"   Distance finale: {trailing_final_distance_pct:.3f}%")
        
        print(f"\n🎯 Break-Even:")
        print(f"   BE déclenché: {'✅ OUI' if be_triggered else '❌ NON'}")
        if be_triggered_pnl_pct:
            print(f"   BE PnL: {be_triggered_pnl_pct:.3f}%")
        
        print(f"\n⏱️ Stagnation:")
        print(f"   Détectée: {'⚠️ OUI' if stagnation_detected else '✅ NON'}")
        
        # Analyse du trailing
        print(f"\n" + "=" * 60)
        print("🔍 DIAGNOSTIC TRAILING")
        print("=" * 60)
        
        if not trailing_activated:
            print(f"\n⚠️ TRAILING NON ACTIVÉ")
            print(f"   Raisons possibles:")
            
            # Vérifier config depuis les logs (approximatif)
            if tp_sl_mode == 'FIXE':
                print(f"   • Mode FIXE: trailing_trigger_pnl par défaut = ~0.20%")
            elif tp_sl_mode == 'ATR':
                print(f"   • Mode ATR: trailing_trigger_pnl basé sur ATR")
            
            if pnl_pct is not None:
                if pnl_pct >= 0:
                    print(f"   • PnL actuel ({pnl_pct:.3f}%) n'a peut-être pas atteint le seuil trigger")
                else:
                    print(f"   • Position en perte ({pnl_pct:.3f}%), trailing ne peut pas s'activer")
        else:
            print(f"\n✅ TRAILING ACTIVÉ")
            if trailing_final_distance_pct:
                distance_pct = abs((sl - entry_price) / entry_price * 100)
                print(f"   Distance SL/Entry: {distance_pct:.3f}%")
                print(f"   Distance trailing config: {trailing_final_distance_pct:.3f}%")
                
                if direction == 'LONG':
                    if sl < entry_price:
                        print(f"   ⚠️ SL ({sl:.6f}) est en dessous de l'entry ({entry_price:.6f})")
                        print(f"   ℹ️ Trailing devrait remonter le SL à mesure que le prix monte")
                    else:
                        print(f"   ✅ SL ({sl:.6f}) est au-dessus de l'entry (BE atteint)")
                else:  # SHORT
                    if sl > entry_price:
                        print(f"   ⚠️ SL ({sl:.6f}) est au-dessus de l'entry ({entry_price:.6f})")
                        print(f"   ℹ️ Trailing devrait descendre le SL à mesure que le prix baisse")
                    else:
                        print(f"   ✅ SL ({sl:.6f}) est en dessous de l'entry (BE atteint)")
        
        # Vérifier inversion
        print(f"\n" + "=" * 60)
        print("🔄 VÉRIFICATION INVERSION")
        print("=" * 60)
        print(f"   Direction position: {direction}")
        print(f"   ℹ️ Vérifiez dans les logs si vous voyez:")
        print(f"   '🔄 INVERSION DE SIGNAL ACTIVÉE: {symbol}'")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
