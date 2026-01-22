"""
Analyse détaillée des 3 derniers trades pour vérifier le fonctionnement du trailing stop
"""
import psycopg2
from datetime import datetime, timezone
import os

def main():
    try:
        # Charger les variables d'environnement depuis .env
        from pathlib import Path
        try:
            from dotenv import load_dotenv
            env_path = Path(__file__).parent.parent / '.env'
            load_dotenv(dotenv_path=env_path)
        except:
            pass
        
        # Connexion PostgreSQL avec encoding explicite
        password = os.getenv('POSTGRES_PASSWORD', 'trading_password')
        # Encoder le password correctement
        if isinstance(password, str):
            password = password.encode('latin-1').decode('utf-8', errors='ignore')
        
        db_config = {
            'dbname': os.getenv('POSTGRES_DB', 'trading_db'),
            'user': os.getenv('POSTGRES_USER', 'trading_user'),
            'password': password,
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432')
        }
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("🔍 ANALYSE DES 3 DERNIERS TRADES - TRAILING STOP")
        print("=" * 80)
        
        # Récupérer les 3 derniers trades fermés avec métriques trailing
        query = """
            SELECT 
                t.id,
                t.symbol,
                t.direction,
                t.entry_price,
                t.exit_price,
                t.sl,
                t.tp,
                t.pnl_pct,
                t.exit_reason,
                t.timestamp_entry,
                t.timestamp_exit,
                t.duration_seconds,
                t.tp_sl_mode,
                t.slippage_pct,
                m.max_pnl_reached,
                m.min_pnl_reached,
                m.trailing_activated,
                m.trailing_trigger_pnl_pct,
                m.trailing_final_distance_pct,
                m.be_triggered,
                m.be_triggered_pnl_pct,
                m.stagnation_detected,
                m.entry_atr_1m,
                m.param_trailing_trigger_atr_mult,
                m.param_trailing_distance_mult
            FROM trades t
            LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
            WHERE t.exit_price IS NOT NULL
            ORDER BY t.timestamp_exit DESC
            LIMIT 3
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("❌ Aucun trade fermé trouvé")
            return
        
        print(f"\n✅ {len(rows)} trades analysés\n")
        
        for idx, row in enumerate(rows, 1):
            (trade_id, symbol, direction, entry_price, exit_price, sl, tp, pnl_pct,
             exit_reason, timestamp_entry, timestamp_exit, duration_seconds, tp_sl_mode,
             slippage_pct, max_pnl_reached, min_pnl_reached, trailing_activated,
             trailing_trigger_pnl_pct, trailing_final_distance_pct, be_triggered,
             be_triggered_pnl_pct, stagnation_detected, entry_atr_1m,
             param_trailing_trigger_atr_mult, param_trailing_distance_mult) = row
            
            # Calculer durée
            duration_min = duration_seconds / 60 if duration_seconds else 0
            
            print("=" * 80)
            print(f"📊 TRADE #{idx} - {symbol}")
            print("=" * 80)
            print(f"ID: {trade_id}")
            print(f"Direction: {direction}")
            print(f"Mode: {tp_sl_mode}")
            print(f"Entry: {entry_price:.8f}")
            print(f"Exit: {exit_price:.8f}")
            print(f"SL final: {sl:.8f}")
            print(f"TP: {tp:.8f}")
            print(f"Durée: {duration_min:.1f} min")
            print(f"Exit reason: {exit_reason}")
            
            print(f"\n💰 Performance:")
            print(f"   PnL final: {pnl_pct:.3f}%")
            print(f"   Max PnL (MFE): {max_pnl_reached:.3f}%" if max_pnl_reached else "   Max PnL (MFE): N/A")
            print(f"   Min PnL: {min_pnl_reached:.3f}%" if min_pnl_reached else "   Min PnL: N/A")
            
            # Analyse du trailing
            print(f"\n🎢 Trailing Stop:")
            print(f"   Activé: {'✅ OUI' if trailing_activated else '❌ NON'}")
            
            if trailing_activated:
                print(f"   Trigger PnL: {trailing_trigger_pnl_pct:.3f}%" if trailing_trigger_pnl_pct else "   Trigger PnL: N/A")
                print(f"   Distance finale: {trailing_final_distance_pct:.3f}%" if trailing_final_distance_pct else "   Distance finale: N/A")
                
                # Calculer si le trailing a bien protégé les gains
                if max_pnl_reached and pnl_pct and max_pnl_reached > 0:
                    pullback = max_pnl_reached - pnl_pct
                    print(f"   Pullback depuis MFE: {pullback:.3f}%")
                    
                    if trailing_final_distance_pct:
                        if pullback > trailing_final_distance_pct * 1.5:
                            print(f"   ⚠️ PULLBACK EXCESSIF: {pullback:.3f}% > {trailing_final_distance_pct*1.5:.3f}% (1.5× distance)")
                        else:
                            print(f"   ✅ Pullback acceptable: {pullback:.3f}% ≤ {trailing_final_distance_pct*1.5:.3f}% (1.5× distance)")
            else:
                # Analyser pourquoi le trailing n'a pas été activé
                print(f"\n   ❓ Pourquoi trailing NON activé:")
                
                if entry_atr_1m and param_trailing_trigger_atr_mult:
                    expected_trigger = entry_atr_1m * param_trailing_trigger_atr_mult
                    print(f"   • ATR entry: {entry_atr_1m:.3f}%")
                    print(f"   • Trigger mult: {param_trailing_trigger_atr_mult}×")
                    print(f"   • Seuil trigger attendu: {expected_trigger:.3f}%")
                    
                    if max_pnl_reached:
                        if max_pnl_reached < expected_trigger:
                            print(f"   • Max PnL ({max_pnl_reached:.3f}%) < Trigger ({expected_trigger:.3f}%)")
                            print(f"   ✅ Normal: Le PnL n'a jamais atteint le seuil trigger")
                        else:
                            print(f"   • Max PnL ({max_pnl_reached:.3f}%) >= Trigger ({expected_trigger:.3f}%)")
                            print(f"   ⚠️ PROBLÈME: Trailing aurait dû s'activer!")
                else:
                    print(f"   • Config trailing non disponible dans métriques")
                    if max_pnl_reached:
                        print(f"   • Max PnL: {max_pnl_reached:.3f}%")
                        if max_pnl_reached < 0.15:
                            print(f"   ✅ Normal: PnL trop faible pour activer trailing")
            
            # Break-even
            print(f"\n🎯 Break-Even:")
            print(f"   Déclenché: {'✅ OUI' if be_triggered else '❌ NON'}")
            if be_triggered and be_triggered_pnl_pct:
                print(f"   PnL trigger: {be_triggered_pnl_pct:.3f}%")
            
            # Stagnation
            print(f"\n⏱️ Stagnation:")
            print(f"   Détectée: {'⚠️ OUI' if stagnation_detected else '✅ NON'}")
            
            # Analyse de la sortie
            print(f"\n🚪 Analyse de la sortie:")
            
            if exit_reason == 'SL':
                if pnl_pct < 0:
                    print(f"   ❌ SL touché en perte ({pnl_pct:.3f}%)")
                    if max_pnl_reached and max_pnl_reached > 0:
                        print(f"   ⚠️ Trade était en profit (MFE: {max_pnl_reached:.3f}%) mais a retourné en perte")
                        if not trailing_activated:
                            print(f"   💡 Trailing aurait pu sauver ce trade")
                else:
                    print(f"   ⚠️ SL touché en profit ({pnl_pct:.3f}%) - comportement inhabituel")
                    
            elif exit_reason == 'TS':
                print(f"   ✅ Trailing Stop (profits protégés: {pnl_pct:.3f}%)")
                if max_pnl_reached:
                    capture_rate = (pnl_pct / max_pnl_reached * 100) if max_pnl_reached > 0 else 0
                    print(f"   Taux de capture: {capture_rate:.1f}% du MFE")
                    
            elif exit_reason == 'TP':
                print(f"   ✅ Take Profit atteint ({pnl_pct:.3f}%)")
                
            elif exit_reason == 'STAGNATION':
                print(f"   ⏱️ Sortie par stagnation ({pnl_pct:.3f}%)")
                
            else:
                print(f"   ℹ️ Autre raison: {exit_reason} ({pnl_pct:.3f}%)")
            
            # Recommandations spécifiques
            print(f"\n💡 Recommandation pour ce trade:")
            
            if not trailing_activated and max_pnl_reached and max_pnl_reached > 0.10:
                print(f"   → Réduire le seuil de trigger trailing (actuellement ~0.18%)")
                
            if trailing_activated and max_pnl_reached and pnl_pct:
                pullback = max_pnl_reached - pnl_pct
                if pullback > 0.15:
                    print(f"   → Distance trailing trop large ({trailing_final_distance_pct:.3f}%), réduire à ~0.10%")
            
            if exit_reason == 'SL' and pnl_pct < 0 and max_pnl_reached and max_pnl_reached > 0:
                print(f"   → Trade prometteur gâché, activer trailing plus tôt")
            
            print()
        
        # Statistiques globales
        print("=" * 80)
        print("📈 STATISTIQUES GLOBALES (3 trades)")
        print("=" * 80)
        
        total_trades = len(rows)
        trailing_activated_count = sum(1 for r in rows if r[16])  # trailing_activated
        trailing_rate = (trailing_activated_count / total_trades * 100) if total_trades > 0 else 0
        
        avg_pnl = sum(r[7] for r in rows if r[7]) / total_trades  # pnl_pct
        avg_duration = sum(r[11] for r in rows if r[11]) / total_trades / 60  # duration en minutes
        
        exit_reasons = {}
        for r in rows:
            reason = r[8]  # exit_reason
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        print(f"\nTrailing activé: {trailing_activated_count}/{total_trades} trades ({trailing_rate:.0f}%)")
        print(f"PnL moyen: {avg_pnl:.3f}%")
        print(f"Durée moyenne: {avg_duration:.1f} min")
        
        print(f"\nRaisons de sortie:")
        for reason, count in exit_reasons.items():
            print(f"   • {reason}: {count} trades")
        
        # Conclusion générale
        print(f"\n" + "=" * 80)
        print("🎯 CONCLUSION GLOBALE")
        print("=" * 80)
        
        if trailing_rate < 30:
            print(f"\n⚠️ TAUX D'ACTIVATION TRAILING FAIBLE ({trailing_rate:.0f}%)")
            print(f"   → Les trades n'atteignent pas le seuil trigger")
            print(f"   → Recommandation: Réduire trailing_trigger_atr_mult de 1.5 à 1.0")
        elif trailing_rate > 70:
            print(f"\n✅ TAUX D'ACTIVATION TRAILING BON ({trailing_rate:.0f}%)")
            print(f"   → La majorité des trades activent le trailing")
        else:
            print(f"\n📊 TAUX D'ACTIVATION TRAILING MOYEN ({trailing_rate:.0f}%)")
        
        if avg_pnl < 0:
            print(f"\n❌ PNL MOYEN NÉGATIF ({avg_pnl:.3f}%)")
            print(f"   → Problème principal: SL trop serré ou mauvais timing d'entrée")
        else:
            print(f"\n✅ PNL MOYEN POSITIF ({avg_pnl:.3f}%)")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
