"""
Analyse du trade ASTER depuis PostgreSQL
"""
import psycopg2
from urllib.parse import quote_plus

def main():
    try:
        # Connexion avec DSN string (évite les problèmes d'encodage)
        password = quote_plus("@Cmtr1di12345")
        dsn = f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml"
        
        conn = psycopg2.connect(dsn)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("🔍 ANALYSE DU TRADE ASTER - PostgreSQL")
        print("=" * 80)
        
        # D'abord voir le schéma
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'trades' 
            ORDER BY ordinal_position
        """)
        cols = [r[0] for r in cursor.fetchall()]
        print(f"Colonnes trades: {', '.join(cols[:20])}...")
        
        # Vérifier colonnes trade_atr_metrics
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'trade_atr_metrics' 
            ORDER BY ordinal_position
        """)
        mcols = [r[0] for r in cursor.fetchall()]
        print(f"Colonnes metrics: {', '.join(mcols[:15])}...")
        
        # Chercher le trade ASTER - requête simplifiée
        query = """
            SELECT 
                t.id, t.symbol, t.direction, 
                t.entry_price, t.exit_price, t.pnl_pct, 
                t.exit_reason, t.duration_seconds,
                t.timestamp_entry, t.timestamp_exit, t.tp_sl_mode,
                t.sl_price, t.tp_price,
                m.max_pnl_reached, m.min_pnl_reached,
                m.trailing_activated, m.be_triggered
            FROM trades t
            LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
            WHERE t.symbol LIKE '%ASTER%'
            ORDER BY t.timestamp_exit DESC NULLS FIRST
            LIMIT 5
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("❌ Aucun trade ASTER trouvé")
            # Lister les trades récents
            cursor.execute("""
                SELECT symbol, direction, pnl_pct, exit_reason, timestamp_exit 
                FROM trades 
                ORDER BY timestamp_exit DESC NULLS FIRST 
                LIMIT 10
            """)
            recent = cursor.fetchall()
            print("\nTrades récents:")
            for r in recent:
                print(f"  {r[0]} | {r[1]} | PnL: {r[2]:.3f}% | {r[3]} | {r[4]}")
            return
        
        print(f"\n✅ {len(rows)} trade(s) ASTER trouvé(s)\n")
        
        for idx, row in enumerate(rows, 1):
            (trade_id, symbol, direction, entry, exit_price,
             pnl_pct, exit_reason, duration,
             ts_entry, ts_exit, tp_sl_mode, sl_price, tp_price,
             max_pnl, min_pnl, trailing_activated, be_triggered) = row
            
            duration_min = (duration / 60) if duration else 0
            
            print("="*80)
            print(f"TRADE #{idx} - {symbol}")
            print("="*80)
            print(f"ID: {trade_id}")
            print(f"Direction: {direction}")
            print(f"Mode: {tp_sl_mode}")
            print(f"Entry: {entry}")
            print(f"Exit: {exit_price}")
            print(f"Durée: {duration_min:.1f} min")
            print(f"Timestamp: {ts_exit}")
            
            print(f"\n💰 Performance:")
            print(f"   PnL final: {pnl_pct:.3f}%" if pnl_pct else "   PnL: N/A")
            print(f"   Max PnL (MFE): {max_pnl:.3f}%" if max_pnl else "   MFE: N/A")
            print(f"   Min PnL: {min_pnl:.3f}%" if min_pnl else "   Min: N/A")
            
            if max_pnl and pnl_pct:
                pullback = max_pnl - pnl_pct
                print(f"   📉 Pullback: {pullback:.3f}%")
                if max_pnl > 0:
                    capture = (pnl_pct / max_pnl * 100)
                    print(f"   📊 Capture MFE: {capture:.1f}%")
            
            print(f"\n🎢 Trailing:")
            print(f"   Activé: {'✅' if trailing_activated else '❌'}")
            print(f"   BE: {'✅' if be_triggered else '❌'}")
            print(f"   SL: {sl_price}")
            print(f"   TP: {tp_price}")
            
            print(f"\n🚪 Sortie: {exit_reason}")
            
            # Diagnostic
            print(f"\n🔧 Diagnostic:")
            if max_pnl and max_pnl > 0.15 and not trailing_activated:
                print(f"   ❌ PROBLÈME: MFE {max_pnl:.3f}% > 0.15% mais trailing NON activé")
            
            if trailing_activated and pnl_pct and max_pnl:
                if (max_pnl - pnl_pct) > 0.2:
                    print(f"   ⚠️ Trailing activé mais pullback important: {max_pnl - pnl_pct:.3f}%")
                    print(f"   💡 Distance trailing trop large ou mise à jour trop lente")
            
            if max_pnl and max_pnl > 0.3 and pnl_pct and pnl_pct < 0.1:
                print(f"   🚨 PERTE MAJEURE: +{max_pnl:.3f}% → +{pnl_pct:.3f}%")
                print(f"   💡 Trailing distance (0.1%) insuffisante pour cette volatilité")
            
            print()
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
