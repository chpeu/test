#!/usr/bin/env python3
"""
Debug PriceProvider Initialization - Diagnostique pourquoi PriceProvider n'est pas initialisé
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

def main():
    print("🔍 DEBUG PRICE PROVIDER INITIALIZATION")
    print("=" * 60)
    
    try:
        # 1. Test import direct PriceProvider
        print("\n📦 TEST IMPORTS")
        print("-" * 40)
        
        try:
            from api.price_provider import HybridPriceProvider, get_price_provider
            print("✅ HybridPriceProvider importé")
        except Exception as e:
            print(f"❌ Erreur import HybridPriceProvider: {e}")
            import traceback
            traceback.print_exc()
            return
        
        try:
            from api.mexc import get_mexc_client
            print("✅ get_mexc_client importé")
        except Exception as e:
            print(f"❌ Erreur import get_mexc_client: {e}")
            return
        
        try:
            from core.state_manager import get_state_manager
            print("✅ StateManager importé")
        except Exception as e:
            print(f"❌ Erreur import StateManager: {e}")
            return
        
        # 2. Test création MEXC client
        print("\n🔌 TEST MEXC CLIENT")
        print("-" * 40)
        
        try:
            mexc_client = get_mexc_client()
            print(f"MEXC Client: {mexc_client}")
            print(f"MEXC Client type: {type(mexc_client).__name__ if mexc_client else 'None'}")
            
            if mexc_client is None:
                print("❌ MEXC Client est None - cela empêchera HybridPriceProvider de s'initialiser")
                
                # Diagnostiquer pourquoi MEXC client est None
                print("🔍 Diagnostic MEXC Client...")
                
                # Vérifier les variables d'environnement
                api_key = os.getenv('MEXC_API_KEY')
                api_secret = os.getenv('MEXC_API_SECRET')
                print(f"   MEXC_API_KEY définie: {bool(api_key)}")
                print(f"   MEXC_API_SECRET définie: {bool(api_secret)}")
                
                if not api_key or not api_secret:
                    print("❌ Clés MEXC manquantes - normal en mode développement")
                    print("   Solution: HybridPriceProvider doit gérer le cas mexc_client=None")
            else:
                print("✅ MEXC Client OK")
        except Exception as e:
            print(f"❌ Erreur get_mexc_client: {e}")
            import traceback
            traceback.print_exc()
        
        # 3. Test création HybridPriceProvider direct
        print("\n🏗️ TEST CRÉATION HYBRIDPRICEPROVIDER")
        print("-" * 40)
        
        try:
            # Test création directe
            provider = HybridPriceProvider()
            print("✅ HybridPriceProvider créé directement")
            print(f"   Type: {type(provider).__name__}")
            print(f"   use_websocket: {provider.use_websocket}")
            print(f"   rest_client: {provider.rest_client is not None}")
        except Exception as e:
            print(f"❌ Erreur création HybridPriceProvider: {e}")
            import traceback
            traceback.print_exc()
        
        # 4. Test fonction get_price_provider() singleton
        print("\n🔧 TEST GET_PRICE_PROVIDER SINGLETON")
        print("-" * 40)
        
        try:
            provider_singleton = get_price_provider()
            print(f"get_price_provider() résultat: {provider_singleton}")
            print(f"Type: {type(provider_singleton).__name__ if provider_singleton else 'None'}")
            
            if provider_singleton is None:
                print("❌ get_price_provider() retourne None")
                print("   Cela explique pourquoi StateManager.get_price_provider() est None")
            else:
                print("✅ get_price_provider() fonctionne")
        except Exception as e:
            print(f"❌ Erreur get_price_provider: {e}")
            import traceback
            traceback.print_exc()
        
        # 5. Test StateManager
        print("\n🏛️ TEST STATEMANAGER")
        print("-" * 40)
        
        try:
            state = get_state_manager()
            current_provider = state.get_price_provider()
            print(f"StateManager.get_price_provider(): {current_provider}")
            
            if current_provider is None:
                print("❌ StateManager n'a pas de PriceProvider")
                print("   Test injection manuelle...")
                
                # Test injection manuelle
                test_provider = get_price_provider()
                if test_provider:
                    state.set_price_provider(test_provider)
                    print("✅ PriceProvider injecté manuellement dans StateManager")
                    
                    # Vérifier
                    check_provider = state.get_price_provider()
                    print(f"   Vérification: {check_provider is not None}")
                else:
                    print("❌ Impossible d'injecter - get_price_provider() retourne None")
            else:
                print("✅ StateManager a un PriceProvider")
        except Exception as e:
            print(f"❌ Erreur StateManager: {e}")
            import traceback
            traceback.print_exc()
        
        # 6. Test simulation bootstrap
        print("\n🚀 TEST SIMULATION BOOTSTRAP")
        print("-" * 40)
        
        try:
            # Simuler le code bootstrap.py ligne 145-148
            print("Simulation bootstrap.py lignes 145-148...")
            
            state = get_state_manager()
            if not state.get_price_provider():
                print("   PriceProvider manquant, tentative création...")
                price_provider = get_price_provider()
                if price_provider:
                    state.set_price_provider(price_provider)
                    print("   ✅ PriceProvider injecté dans StateManager")
                else:
                    print("   ❌ Échec injection - get_price_provider() retourne None")
            else:
                print("   ✅ PriceProvider déjà présent")
            
            # Vérifier résultat final
            final_provider = state.get_price_provider()
            print(f"   Résultat final: {final_provider is not None}")
            
        except Exception as e:
            print(f"❌ Erreur simulation bootstrap: {e}")
            import traceback
            traceback.print_exc()
        
        # 7. Proposer solution
        print("\n" + "=" * 60)
        print("💡 SOLUTION PROPOSÉE")
        print("=" * 60)
        
        state = get_state_manager()
        if state.get_price_provider() is None:
            print("🔴 PROBLÈME CONFIRMÉ: StateManager n'a pas de PriceProvider")
            print("🔧 SOLUTIONS:")
            print("1. Modifier HybridPriceProvider pour accepter mexc_client=None")
            print("2. Ou utiliser un MockPriceProvider en développement")
            print("3. Ou corriger la configuration MEXC")
            
            # Test solution 1: Mode dégradé
            print("\n🧪 Test solution mode dégradé...")
            try:
                # Modifier temporairement le constructeur HybridPriceProvider
                from api.price_provider import HybridPriceProvider
                
                # Patch temporaire pour test
                original_init = HybridPriceProvider.__init__
                
                def patched_init(self):
                    self.ws_manager = None
                    self.rest_client = None  # Accepter None temporairement
                    self.use_websocket = False  # Désactiver WebSocket si pas de client
                    self.price_cache = {}
                    self._cache_lock = None
                    self._ws_lifecycle_lock = None
                    self.message_buffer = []
                    self.socketio_emit_callback = None
                    self.active_position_symbol = None
                    self.monitored_symbols = []
                    self._sl_check_callback = None
                    self._sl_check_params = None
                    print("   ✅ HybridPriceProvider créé en mode dégradé (sans MEXC)")
                
                HybridPriceProvider.__init__ = patched_init
                
                # Test création
                degraded_provider = HybridPriceProvider()
                state.set_price_provider(degraded_provider)
                
                # Restaurer
                HybridPriceProvider.__init__ = original_init
                
                print("   ✅ PriceProvider mode dégradé injecté avec succès!")
                print("   ⚠️  PostExitLoop pourra démarrer mais sans prix réels")
                
            except Exception as e:
                print(f"   ❌ Échec solution mode dégradé: {e}")
        else:
            print("✅ PriceProvider OK dans StateManager")
        
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
