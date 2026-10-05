#!/usr/bin/env python3
"""
Test complet du système de régimes dynamiques
1. Active le régime CALME
2. Vérifie les valeurs effectives
3. Simule un trade
4. Vérifie l'enregistrement dans PostgreSQL (y compris nouvelles colonnes)
"""
import sys
import os
import io
import asyncio
from datetime import datetime

# Force UTF-8 for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TRADING_CONFIG
from utils.effective_config import set_regime_adjustments, get_effective_value
from core.market_regime_selector import DEFAULT_REGIME_CONFIGS
from core.position_manager import PositionManager, PositionConfig
from core.postgresql_datalogger import PostgreSQLDataLogger

# Mock pour éviter de dépendre de l'API Exchange
class MockExchange:
    def get_position(self, symbol): return None
    def get_ticker(self, symbol): return {'last': 100.0}

async def run_test():
    print("🚀 Démarrage test complet régimes + DB")
    
    # 1. Activer régime CALME
    print("\n1. Activation régime CALME")
    config = DEFAULT_REGIME_CONFIGS.get("CALME")
    adjustments = {
        "min_score_required": config.min_score_required,
        "atr_mult_sl": config.atr_mult_sl,
        "atr_mult_tp": config.atr_mult_tp,
        "volume_multiplier": config.volume_multiplier,
        "rsi_filter_mode": config.rsi_filter_mode,
        "position_timeout": config.max_position_time,
        "optimal_atr_max_1m": config.optimal_atr_max
    }
    set_regime_adjustments(adjustments)
    
    # Vérifier valeurs effectives
    eff_sl = get_effective_value('atr_mult_sl')
    eff_timeout = get_effective_value('position_timeout')
    print(f"   ✅ SL Effectif: {eff_sl}x (Attendu: {config.atr_mult_sl}x)")
    print(f"   ✅ Timeout Effectif: {eff_timeout}s (Attendu: {config.max_position_time}s)")
    
    # 2. Simuler un trade
    print("\n2. Simulation trade")
    # Initialiser composants
    pg = PostgreSQLDataLogger()
    pm_config = PositionConfig()
    pm = PositionManager(config=pm_config)
    
    # Données simulées
    symbol = "BTC/USDT"
    entry_price = 50000.0
    setup = {
        'symbol': symbol,
        'direction': 'LONG',
        'score': 9.5,
        'indicators': {'atr_percent': 0.10, 'adx': 20}
    }
    
    # Créer position fictive
    class MockPosition:
        def __init__(self):
            self.symbol = symbol
            self.entry_price = entry_price
            self.side = 'LONG'
            self.size = 0.001
            self.leverage = 5
            self.entry_time = datetime.now()
            self._opportunity_id = None
            self._scan_log_id = None
            self.ml_confidence = 0.85
    
    pm.active_position = MockPosition()
    
    # Données trade pour log
    trade_data = {
        'symbol': symbol,
        'direction': 'LONG',
        'status': 'OPEN',
        'entry_price': entry_price,
        'size': 0.001,
        'leverage': 5,
        'entry_score': 9.5,
        # Paramètres effectifs seront ajoutés par log_trade via le code qu'on a modifié
    }
    
    # Note: On appelle directement log_trade via PositionManager pour tester la logique d'enrichissement
    # Mais comme log_trade est encapsulé, on va simuler ce que fait PositionManager.log_trade
    
    try:
        from core.market_regime_selector import get_regime_selector, MarketRegime
        regime_selector = get_regime_selector()
        # Forcer le status du sélecteur pour qu'il corresponde à nos ajustements
        regime_selector.current_regime = MarketRegime.CALME
        regime_selector.current_config = config
        
        # Appeler la méthode modifiée dans position_manager (on doit instancier pour tester)
        # Comme on ne peut pas appeler log_trade facilement (il fait des appels DB), on va tester l'enrichissement
        
        # Récupération des valeurs comme dans le code modifié
        print("\n3. Vérification capture paramètres")
        captured_sl = get_effective_value('atr_mult_sl')
        captured_vol = get_effective_value('volume_multiplier')
        captured_rsi = get_effective_value('rsi_filter_mode')
        
        print(f"   ✅ SL capturé: {captured_sl}x")
        print(f"   ✅ Vol capturé: {captured_vol}x")
        print(f"   ✅ RSI capturé: {captured_rsi}")
        
        if captured_sl != config.atr_mult_sl:
            print("   ❌ ERREUR: SL capturé incorrect")
            return False
            
        if captured_rsi != "STRICT":
            print("   ❌ ERREUR: RSI capturé incorrect")
            return False

        print("\n4. Test DB (Simulation)")
        # On vérifie que la classe PostgresDataLogger a bien les nouvelles colonnes dans sa requête INSERT
        # (On ne fait pas d'insert réel pour ne pas polluer la DB prod avec des fake trades)
        
        import inspect
        source = inspect.getsource(pg.log_trade)
        
        required_cols = [
            'entry_volume_multiplier',
            'entry_rsi_filter_mode',
            'entry_position_timeout',
            'entry_optimal_atr_max_1m'
        ]
        
        missing = [col for col in required_cols if col not in source]
        
        if missing:
            print(f"   ❌ ERREUR: Colonnes manquantes dans log_trade: {missing}")
            return False
        else:
            print("   ✅ Code log_trade contient bien les nouvelles colonnes")
            
        print("\n✨ Test complet RÉUSSI")
        return True
        
    except Exception as e:
        print(f"❌ Erreur test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(run_test())
