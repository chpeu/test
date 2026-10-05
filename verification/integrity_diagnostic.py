
import asyncio
import logging
import os
import sys
from datetime import datetime

# Path setup
sys.path.append(os.getcwd())

from core.state_manager import get_state_manager
from core.market_regime_selector import get_regime_selector
from api.price_provider import get_price_provider
from trading.live_order_manager_futures import LiveOrderManagerFutures
from utils.effective_config import get_effective_config, get_active_adjustments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IntegrityDiag")

async def run_diagnostic():
    print("\n🔍 Démarrage du diagnostic d'intégrité du système...")
    
    # 🔥 INITIALISATION DES INSTANCES
    from core.bootstrap import init_instances, init_background_services, run_initial_top_pairs_scan
    print("🚀 Initialisation des instances via bootstrap...")
    try:
        await init_instances()
        print("⏳ Attente de l'initialisation des services d'arrière-plan...")
        await init_background_services()
        print("✅ bootstrap.init_instances() et init_background_services() terminés")
        
        print("🔍 Lancement du scan de scalabilité initial (Market Regime detection)...")
        await run_initial_top_pairs_scan()
        print("✅ Scan initial terminé")
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation: {e}")
        import traceback
        print(traceback.format_exc())

    state = get_state_manager()
    
    # 1. Vérification des instances Core
    print("\n--- 1. Instances Core ---")
    instances = {
        "Scanner": state.get_scanner(),
        "Analyzer": state.get_analyzer(),
        "PositionManager": state.get_position_manager(),
        "PriceProvider": state.get_price_provider(),
        "Scheduler": state.get_scheduler(),
        "LiveOrderManager": state.get_live_order_manager(),
        "WSManager": state.get_ws_manager()
    }
    
    for name, inst in instances.items():
        status = "✅ OK" if inst else "❌ Manquant"
        print(f"{name}: {status}")

    # 2. Vérification du Market Regime
    print("\n--- 2. Market Regime ---")
    selector = get_regime_selector()
    status = selector.get_status()
    print(f"Régime actuel: {status.get('current_regime')}")
    print(f"ATR Moyen: {status.get('avg_atr')}%")
    print(f"Dernier check: {status.get('last_check')}")
    print(f"Is Scanning (State Manager): {state.is_scanning}")
    
    # 3. Vérification de la Configuration Effective
    print("\n--- 3. Configuration Effective ---")
    eff_cfg = get_effective_config()
    adj = get_active_adjustments()
    
    print(f"Mode TP/SL (Effective): {eff_cfg.get('tp_sl_mode')}")
    print(f"Mode TP/SL (Base): {state.get_legacy_proxy().get('tp_sl_mode')}")
    print(f"Ajustements actifs (sources): {list(adj.keys())}")
    if adj.get('regime'):
        print(f"✅ Ajustements Régime présents: {len(adj['regime'])} clés")
        for k, v in adj['regime'].items():
            print(f"  - {k}: {v}")
    else:
        print("⚠️ Aucun ajustement de régime appliqué à la config effective")

    # 4. Vérification du Scheduler et Callbacks
    print("\n--- 4. État du Scheduler & Callbacks ---")
    sched = state.get_scheduler()
    if sched:
        print(f"Scheduler Running: {sched.is_running}")
        print(f"Scanner Task: {'✅' if sched.scanner_task else '❌'}")
        print(f"Position Check Task: {'✅' if sched.position_check_task else '❌'}")
        print(f"Scalability Refresh Task: {'✅' if sched.scalability_refresh_task else '❌'}")
        
        from core.callbacks.scalability_refresh import _app_state, _scanner, _last_refresh_time, _current_interval
        print(f"Scalability Refresh Context (Globals):")
        print(f"  - _app_state (proxy): {'✅ OK' if _app_state else '❌ MISSING'}")
        if _app_state:
            print(f"  - _app_state['is_scanning']: {_app_state.get('is_scanning')}")
        print(f"  - _scanner: {'✅ OK' if _scanner else '❌ MISSING'}")
        print(f"  - _last_refresh_time: {datetime.fromtimestamp(_last_refresh_time) if _last_refresh_time > 0 else 'Jamais'}")
        print(f"  - _current_interval: {_current_interval}s")
    
    # 5. Test de récupération de données (Bypass MEXC)
    print("\n--- 5. Test LiveOrderManager (Bypass) ---")
    lom = state.get_live_order_manager()
    if lom:
        print(f"Mode Bypass: {getattr(lom, 'use_bypass', 'Unknown')}")
        print(f"Dry Run: {lom.dry_run}")
        if hasattr(lom, 'bypass_client') and lom.bypass_client:
            print("✅ Client Bypass initialisé")
        else:
            print("❌ Client Bypass NON initialisé")
    else:
        print("❌ LiveOrderManager manquant")

    print("\n🏁 Diagnostic terminé.\n")

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
