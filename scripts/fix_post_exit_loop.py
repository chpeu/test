#!/usr/bin/env python3
"""
Fix PostExit Loop - Démarre manuellement PostExitLoop et diagnostique les problèmes
"""
import sys
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

async def main():
    print("🔧 FIX POST-EXIT LOOP")
    print("=" * 60)
    
    try:
        # 1. Test import et vérification des dépendances
        print("\n📦 VÉRIFICATION DÉPENDANCES")
        print("-" * 40)
        
        from core.callbacks.post_exit_loop import (
            start_post_exit_loop, stop_post_exit_loop, 
            is_running, set_price_provider
        )
        from core.post_exit import get_post_exit_manager
        from core.state_manager import get_state_manager
        
        print("✅ Tous les modules importés avec succès")
        
        # 2. Vérifier l'état initial
        print("\n🔍 ÉTAT INITIAL")
        print("-" * 40)
        
        loop_running = is_running()
        print(f"PostExitLoop running: {loop_running}")
        
        state = get_state_manager()
        price_provider = state.get_price_provider()
        print(f"PriceProvider disponible: {price_provider is not None}")
        if price_provider:
            print(f"PriceProvider type: {type(price_provider).__name__}")
        
        post_exit_mgr = get_post_exit_manager()
        manager_status = post_exit_mgr.get_tracker_status()
        print(f"PostExitManager enabled: {manager_status['enabled']}")
        print(f"Active trackers: {manager_status['active_count']}")
        
        # 3. Test démarrage de PostExitLoop
        print("\n🚀 DÉMARRAGE POST-EXIT LOOP")
        print("-" * 40)
        
        if loop_running:
            print("⚠️ Loop déjà en cours, arrêt d'abord...")
            await stop_post_exit_loop()
            await asyncio.sleep(1)
        
        # Injecter price_provider
        if price_provider:
            set_price_provider(price_provider)
            print("✅ PriceProvider injecté dans PostExitLoop")
        else:
            print("❌ PriceProvider manquant - PostExitLoop ne fonctionnera pas")
            return
        
        # Démarrer la loop
        print("🔄 Démarrage PostExitLoop...")
        await start_post_exit_loop()
        
        # Vérifier qu'elle a démarré
        await asyncio.sleep(2)  # Laisser le temps de démarrer
        loop_running = is_running()
        print(f"✅ PostExitLoop running: {loop_running}")
        
        if not loop_running:
            print("❌ Échec démarrage PostExitLoop")
            return
        
        # 4. Test avec tracker de test
        print("\n🧪 TEST AVEC TRACKER")
        print("-" * 40)
        
        import uuid
        from datetime import datetime, timezone
        
        test_trade_id = str(uuid.uuid4())
        test_symbol = "BTCUSDT"
        
        print(f"Création tracker test: {test_symbol}")
        post_exit_mgr.start_tracking_sync(
            trade_id=test_trade_id,
            symbol=test_symbol,
            direction="LONG",
            exit_price=50000.0,
            exit_reason="TEST",
            realized_pnl_pct=1.5,
            realized_pnl_usdt=150.0,
            original_sl=49000.0,
            original_tp=52000.0,
            entry_price=49500.0,
            trade_duration_sec=300
        )
        
        # Vérifier qu'il est actif
        active_symbols = post_exit_mgr.get_active_symbols()
        if test_symbol in active_symbols:
            print(f"✅ Tracker créé: {active_symbols}")
            
            # Laisser PostExitLoop collecter quelques prix
            print("⏱️ Collection prix pendant 10 secondes...")
            for i in range(5):
                await asyncio.sleep(2)
                tracker = post_exit_mgr.active_trackers.get(test_symbol)
                if tracker:
                    sample_count = len(tracker.samples)
                    print(f"   Samples collectés: {sample_count}")
                    if sample_count > 0:
                        last_price = tracker.samples[-1].price
                        print(f"   Dernier prix: {last_price}")
                else:
                    print(f"   Tracker {test_symbol} non trouvé")
                    break
            
            # Forcer complétion du tracker de test
            if test_symbol in post_exit_mgr.active_trackers:
                tracker = post_exit_mgr.active_trackers[test_symbol]
                sample_count = len(tracker.samples)
                
                if sample_count > 0:
                    print(f"🎯 Test sauvegarde avec {sample_count} samples...")
                    metrics = await post_exit_mgr._complete_tracker(test_symbol, "TEST_COMPLETE")
                    
                    if metrics:
                        print("✅ Sauvegarde test réussie!")
                        print(f"   Exit efficiency: {metrics.get('exit_efficiency_pct')}%")
                        print(f"   Sample count: {metrics.get('sample_count')}")
                        
                        # Vérifier en base
                        import psycopg2
                        try:
                            conn = psycopg2.connect(
                                host=os.getenv('POSTGRES_HOST', 'localhost'),
                                port=os.getenv('POSTGRES_PORT', '5432'),
                                database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
                                user=os.getenv('POSTGRES_USER', 'postgres'),
                                password=os.getenv('POSTGRES_PASSWORD', '')
                            )
                            with conn.cursor() as cur:
                                cur.execute("""
                                    SELECT exit_efficiency_pct, sample_count 
                                    FROM trade_post_exit_analysis 
                                    WHERE trade_id = %s
                                """, (test_trade_id,))
                                result = cur.fetchone()
                                if result:
                                    print(f"✅ Vérifié en DB: efficiency={result[0]}%, samples={result[1]}")
                                else:
                                    print("⚠️ Pas trouvé en DB")
                            conn.close()
                        except Exception as e:
                            print(f"❌ Erreur vérification DB: {e}")
                    else:
                        print("❌ Sauvegarde test échouée")
                else:
                    print("⚠️ Aucun sample collecté - prix provider défaillant?")
                    
                # Nettoyer
                if test_symbol in post_exit_mgr.active_trackers:
                    del post_exit_mgr.active_trackers[test_symbol]
        else:
            print("❌ Tracker test non créé")
        
        # 5. Laisser la loop continuer
        print("\n✅ POST-EXIT LOOP OPÉRATIONNELLE")
        print("-" * 40)
        print("PostExitLoop fonctionne maintenant!")
        print("Elle continuera à collecter les prix pour les futurs trades.")
        print("\nPour vérifier son état:")
        print("1. Fermez un trade → PostExit tracking démarre")
        print("2. Vérifiez les logs pour '📊 PostExit samples'")
        print("3. Vérifiez la table trade_post_exit_analysis")
        
        # Garder la loop active quelques secondes de plus
        print("\nLoop restera active pendant 30s pour démonstration...")
        await asyncio.sleep(30)
        
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par utilisateur")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Nettoyer
        try:
            print("\n🧹 NETTOYAGE")
            print("-" * 20)
            await stop_post_exit_loop()
            print("✅ PostExitLoop arrêtée")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())
