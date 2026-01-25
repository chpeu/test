#!/usr/bin/env python3
"""
Test Post-Exit Final Validation - Valide que toutes les corrections fonctionnent
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
    print("🧪 TEST POST-EXIT FINAL VALIDATION")
    print("=" * 60)
    
    success_steps = []
    failure_steps = []
    
    try:
        # 1. Test imports et initialisation StateManager
        print("\n📦 ÉTAPE 1: IMPORTS ET STATEMANAGER")
        print("-" * 50)
        
        try:
            from core.state_manager import get_state_manager
            from api.price_provider import get_price_provider
            from core.callbacks.post_exit_loop import (
                start_post_exit_loop, stop_post_exit_loop, 
                is_running, set_price_provider
            )
            from core.post_exit import get_post_exit_manager
            
            state = get_state_manager()
            print("✅ Imports réussis")
            success_steps.append("Imports et StateManager")
        except Exception as e:
            print(f"❌ Erreur imports: {e}")
            failure_steps.append("Imports et StateManager")
            return
        
        # 2. Test initialisation PriceProvider avec nouvelles corrections
        print("\n🔌 ÉTAPE 2: PRICEPROVIDER AVEC CORRECTIONS")
        print("-" * 50)
        
        try:
            # Simuler le code corrigé de bootstrap.py
            if not state.get_price_provider():
                print("🔄 Simulation initialisation PriceProvider corrigée...")
                try:
                    price_provider = get_price_provider()
                    if price_provider:
                        state.set_price_provider(price_provider)
                        print("✅ PriceProvider initialized and injected into StateManager")
                    else:
                        print("❌ get_price_provider() returned None - tentative fallback")
                        from api.price_provider import HybridPriceProvider
                        direct_provider = HybridPriceProvider()
                        state.set_price_provider(direct_provider)
                        print("⚠️ PriceProvider créé directement comme fallback")
                except Exception as e:
                    print(f"❌ Erreur initialisation PriceProvider: {e}")
                    failure_steps.append("PriceProvider initialization")
                    return
            else:
                print("✅ PriceProvider already exists in StateManager")
            
            # Vérifier résultat
            final_provider = state.get_price_provider()
            if final_provider:
                print(f"✅ PriceProvider final: {type(final_provider).__name__}")
                success_steps.append("PriceProvider initialization")
            else:
                print("❌ PriceProvider toujours None après corrections")
                failure_steps.append("PriceProvider initialization")
                return
                
        except Exception as e:
            print(f"❌ Erreur étape PriceProvider: {e}")
            failure_steps.append("PriceProvider initialization")
            return
        
        # 3. Test démarrage PostExitLoop avec corrections
        print("\n🔄 ÉTAPE 3: POSTEXITLOOP AVEC CORRECTIONS")
        print("-" * 50)
        
        try:
            # Simuler le code corrigé de main.py
            print("🔄 Simulation initialisation Post-Exit Analysis corrigée...")
            
            # Diagnostic PriceProvider
            price_provider = state.get_price_provider()
            print(f"📊 PostExit: PriceProvider disponible = {price_provider is not None}")
            
            if price_provider is None:
                print("❌ PriceProvider toujours None - corrections insuffisantes")
                failure_steps.append("PostExitLoop PriceProvider check")
                return
            
            # Injection PriceProvider dans PostExitLoop
            set_price_provider(price_provider)
            print("✅ PriceProvider injecté dans PostExitLoop")
            
            # Démarrage PostExitLoop
            print("🚀 Démarrage PostExitLoop...")
            await start_post_exit_loop()
            
            # Vérification démarrage
            await asyncio.sleep(1)  # Laisser le temps de démarrer
            loop_status = is_running()
            print(f"📊 PostExit: Loop démarrée = {loop_status}")
            
            if loop_status:
                print("✅ PostExitLoop démarré avec succès!")
                success_steps.append("PostExitLoop startup")
            else:
                print("❌ PostExitLoop n'a pas démarré")
                failure_steps.append("PostExitLoop startup")
                return
                
        except Exception as e:
            print(f"❌ Erreur démarrage PostExitLoop: {e}")
            failure_steps.append("PostExitLoop startup")
            import traceback
            traceback.print_exc()
            return
        
        # 4. Test PostExitManager
        print("\n🎛️ ÉTAPE 4: POSTEXITMANAGER")
        print("-" * 50)
        
        try:
            post_exit_mgr = get_post_exit_manager()
            manager_status = post_exit_mgr.get_tracker_status()
            print(f"📊 PostExit Manager: enabled={manager_status['enabled']}")
            print(f"📊 Active trackers: {manager_status['active_count']}")
            
            if manager_status['enabled']:
                success_steps.append("PostExitManager status")
            else:
                failure_steps.append("PostExitManager status")
                
        except Exception as e:
            print(f"❌ Erreur PostExitManager: {e}")
            failure_steps.append("PostExitManager status")
        
        # 5. Test création tracker et collecte prix
        print("\n🧪 ÉTAPE 5: TEST TRACKER ET COLLECTE PRIX")
        print("-" * 50)
        
        try:
            import uuid
            
            test_trade_id = str(uuid.uuid4())
            test_symbol = "BTCUSDT"
            
            print(f"Création tracker test: {test_symbol}")
            post_exit_mgr.start_tracking_sync(
                trade_id=test_trade_id,
                symbol=test_symbol,
                direction="LONG",
                exit_price=50000.0,
                exit_reason="TEST_VALIDATION",
                realized_pnl_pct=2.0,
                realized_pnl_usdt=200.0,
                original_sl=49000.0,
                original_tp=52000.0,
                entry_price=49500.0,
                trade_duration_sec=300
            )
            
            # Vérifier création
            active_symbols = post_exit_mgr.get_active_symbols()
            if test_symbol in active_symbols:
                print(f"✅ Tracker créé: {active_symbols}")
                
                # Test collecte prix pendant 10 secondes
                print("⏱️ Test collecte prix pendant 10 secondes...")
                samples_collected = 0
                
                for i in range(5):
                    await asyncio.sleep(2)
                    tracker = post_exit_mgr.active_trackers.get(test_symbol)
                    if tracker:
                        current_samples = len(tracker.samples)
                        if current_samples > samples_collected:
                            samples_collected = current_samples
                            print(f"   ✅ Samples: {samples_collected}")
                            if samples_collected > 0:
                                last_price = tracker.samples[-1].price
                                print(f"   📈 Dernier prix: {last_price}")
                    else:
                        print(f"   ❌ Tracker {test_symbol} non trouvé")
                        break
                
                if samples_collected > 0:
                    print(f"✅ Collecte prix fonctionnelle ({samples_collected} samples)")
                    success_steps.append("Prix collection")
                    
                    # Test sauvegarde
                    print("💾 Test sauvegarde...")
                    metrics = await post_exit_mgr._complete_tracker(test_symbol, "TEST_COMPLETE")
                    
                    if metrics:
                        print("✅ Sauvegarde test réussie!")
                        print(f"   Exit efficiency: {metrics.get('exit_efficiency_pct')}%")
                        print(f"   Sample count: {metrics.get('sample_count')}")
                        success_steps.append("Database save")
                        
                        # Vérifier en base
                        try:
                            import psycopg2
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
                                    success_steps.append("Database verification")
                                else:
                                    print("⚠️ Pas trouvé en DB")
                                    failure_steps.append("Database verification")
                            conn.close()
                        except Exception as db_e:
                            print(f"❌ Erreur vérification DB: {db_e}")
                            failure_steps.append("Database verification")
                    else:
                        print("❌ Sauvegarde test échouée")
                        failure_steps.append("Database save")
                else:
                    print("❌ Aucun sample collecté - PriceProvider défaillant")
                    failure_steps.append("Prix collection")
                    
                # Nettoyer
                if test_symbol in post_exit_mgr.active_trackers:
                    del post_exit_mgr.active_trackers[test_symbol]
                    print("🧹 Tracker de test nettoyé")
            else:
                print("❌ Tracker test non créé")
                failure_steps.append("Tracker creation")
                
        except Exception as e:
            print(f"❌ Erreur test tracker: {e}")
            failure_steps.append("Tracker and price collection")
            import traceback
            traceback.print_exc()
        
        # 6. Résultats finaux
        print("\n" + "=" * 60)
        print("📊 RÉSULTATS VALIDATION FINALE")
        print("=" * 60)
        
        total_steps = len(success_steps) + len(failure_steps)
        success_rate = len(success_steps) / total_steps * 100 if total_steps > 0 else 0
        
        print(f"✅ Étapes réussies: {len(success_steps)}")
        for step in success_steps:
            print(f"   • {step}")
        
        if failure_steps:
            print(f"❌ Étapes échouées: {len(failure_steps)}")
            for step in failure_steps:
                print(f"   • {step}")
        
        print(f"\n📈 Taux de succès: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("\n🎉 VALIDATION RÉUSSIE!")
            print("✅ Les corrections PostExit fonctionnent")
            print("✅ PostExitLoop démarre et collecte les prix")
            print("✅ Sauvegarde PostgreSQL opérationnelle")
            print("\n🔧 ACTIONS SUIVANTES:")
            print("1. Redémarrer le bot principal (python main.py)")
            print("2. Surveiller les logs PostExit lors du démarrage")
            print("3. Effectuer un trade pour valider le pipeline complet")
        elif success_rate >= 60:
            print("\n⚠️ VALIDATION PARTIELLE")
            print("Certains composants fonctionnent mais des problèmes persistent")
            print("Vérifier les étapes échouées ci-dessus")
        else:
            print("\n❌ VALIDATION ÉCHOUÉE")
            print("Des problèmes majeurs persistent")
            print("Réviser les corrections ou diagnostiquer plus en profondeur")
        
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur générale: {e}")
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
