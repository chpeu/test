"""
🚀 MULTI-CONFIG BACKTEST FRAMEWORK
Framework de test parallèle pour valider plusieurs configurations en simultané.
Permet de trouver les paramètres optimaux (TP/SL, filtres, sizing) par Grid Search.
"""

import logging
import json
import time
import itertools
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from pathlib import Path
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

# Imports internes
import sys
import os
sys.path.append(os.getcwd())

from backtesting.engine import BacktestEngine
from config import TRADING_CONFIG

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MultiConfigTester")

@dataclass
class ConfigVariant:
    """Une variante de configuration à tester"""
    name: str
    
    # Paramètres de risque
    risk_per_trade: float
    leverage: int
    
    # Paramètres TP/SL
    fixed_tp_pct: float
    fixed_sl_pct: float
    trailing_enabled: bool
    trailing_distance_pct: float
    
    # Paramètres Filtres
    min_score_1m: float
    min_snr_1m: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir en dictionnaire compatible avec TRADING_CONFIG"""
        return {
            'risk_per_trade': self.risk_per_trade,
            'default_leverage': self.leverage,
            'fixed_tp_pct': self.fixed_tp_pct,
            'fixed_sl_pct': self.fixed_sl_pct,
            'trailing_stop': {
                'enabled': self.trailing_enabled,
                'distance_pct': self.trailing_distance_pct
            },
            'min_score_1m': self.min_score_1m,
            'min_snr_1m': self.min_snr_1m
        }

class MultiConfigTester:
    """
    Gestionnaire de tests multi-configurations
    Exécute des backtests en parallèle et agrège les résultats
    """
    
    def __init__(self, data_path: str = "historical_data"):
        self.data_path = data_path
        self.results = []
        
    def generate_grid(self, param_grid: Dict[str, List[Any]]) -> List[ConfigVariant]:
        """
        Générer toutes les combinaisons possibles (Produit Cartésien)
        """
        keys = param_grid.keys()
        values = param_grid.values()
        combinations = list(itertools.product(*values))
        
        variants = []
        for i, combo in enumerate(combinations):
            params = dict(zip(keys, combo))
            
            # Créer variant
            variant = ConfigVariant(
                name=f"config_{i+1:03d}",
                risk_per_trade=params.get('risk_per_trade', 0.02),
                leverage=params.get('leverage', 5),
                fixed_tp_pct=params.get('fixed_tp_pct', 0.6),
                fixed_sl_pct=params.get('fixed_sl_pct', 0.25),
                trailing_enabled=params.get('trailing_enabled', True),
                trailing_distance_pct=params.get('trailing_distance_pct', 0.15),
                min_score_1m=params.get('min_score_1m', 6.0),
                min_snr_1m=params.get('min_snr_1m', 5.0)
            )
            variants.append(variant)
            
        logger.info(f"Generated {len(variants)} configurations from grid")
        return variants

    def _run_single_backtest(
        self, 
        variant: ConfigVariant, 
        symbols: List[str], 
        start_date: str, 
        end_date: str
    ) -> Dict:
        """
        Exécuter un seul backtest (fonction worker)
        """
        try:
            # Initialiser moteur avec config spécifique
            engine = BacktestEngine(
                initial_capital=1000.0,
                data_path=self.data_path,
                config=variant.to_dict()
            )
            
            # Lancer backtest (sans stratégie custom pour l'instant, utilise logique par défaut engine)
            # Note: Dans le vrai système, il faut passer la strategy_func
            # Ici on simule ou on adapte selon engine.py
            
            # Hack: Injecter les setups via un mock ou charger depuis scan_logs si dispo
            # Pour l'instant, on assume que engine.run_backtest fait le job
            
            results = engine.run_backtest(symbols, start_date, end_date)
            
            # Ajouter métadonnées config
            results['config_name'] = variant.name
            results.update(variant.to_dict())
            
            # Calculer Score Composite (Performance Index)
            # Score = (Profit Factor * 2) + (Winrate / 10) - (Max DD / 5)
            score = (
                (results.get('profit_factor', 0) * 20) + 
                (results.get('winrate', 0) * 0.5) - 
                (results.get('max_drawdown', 0) * 1.5)
            )
            results['composite_score'] = score
            
            return results
            
        except Exception as e:
            logger.error(f"Error in backtest {variant.name}: {e}")
            return {'config_name': variant.name, 'error': str(e)}

    def run_parallel(
        self, 
        variants: List[ConfigVariant], 
        symbols: List[str],
        start_date: str,
        end_date: str,
        max_workers: int = 4
    ) -> pd.DataFrame:
        """
        Lancer l'exécution parallèle
        """
        logger.info(f"🚀 Starting parallel backtest on {len(variants)} configs with {max_workers} workers")
        start_time = time.time()
        
        results_list = []
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Soumettre toutes les tâches
            future_to_config = {
                executor.submit(self._run_single_backtest, v, symbols, start_date, end_date): v 
                for v in variants
            }
            
            for i, future in enumerate(as_completed(future_to_config)):
                config = future_to_config[future]
                try:
                    res = future.result()
                    results_list.append(res)
                    if i % 5 == 0:
                        logger.info(f"Progress: {i+1}/{len(variants)} completed")
                except Exception as exc:
                    logger.error(f"Config {config.name} generated an exception: {exc}")
        
        duration = time.time() - start_time
        logger.info(f"✅ All backtests completed in {duration:.2f}s")
        
        # Créer DataFrame
        df = pd.DataFrame(results_list)
        
        # Trier par score
        if 'composite_score' in df.columns:
            df = df.sort_values('composite_score', ascending=False)
            
        return df

# Exemple d'utilisation
if __name__ == "__main__":
    # 1. Définir la grille de recherche
    grid = {
        'fixed_tp_pct': [0.4, 0.6, 0.8],
        'fixed_sl_pct': [0.2, 0.3],
        'trailing_enabled': [True, False],
        'leverage': [5, 10],
        'min_score_1m': [5.0, 6.0, 7.0]
    }
    
    # 2. Initialiser tester
    tester = MultiConfigTester(data_path="historical_data")
    
    # 3. Générer variants
    variants = tester.generate_grid(grid)
    
    # 4. Lancer (Mode Démo - besoin données réelles pour fonctionner)
    print(f"Prêt à tester {len(variants)} configurations...")
    # df = tester.run_parallel(variants, ['BTC/USDT:USDT'], '2023-01-01', '2023-01-31')
    # print(df.head())
