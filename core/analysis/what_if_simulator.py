"""
WhatIfSimulator - Calcul des scénarios alternatifs pour optimisation ATR

Ce module calcule ce qu'aurait été le PnL avec des paramètres différents:
- pnl_if_no_be: PnL si Break-Even n'avait pas été activé
- pnl_if_no_trailing: PnL si Trailing Stop n'avait pas été activé
- pnl_if_wider_sl: PnL avec SL × 1.5
- pnl_if_tighter_sl: PnL avec SL × 0.75
- pnl_if_wider_trailing: PnL avec trailing distance × 1.5
- pnl_if_tighter_trailing: PnL avec trailing distance × 0.75

Auteur: Cascade AI
Date: 09/12/2025
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TradeData:
    """Données d'un trade pour simulation"""
    trade_id: str
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    exit_price: float
    sl_price: float
    tp_price: float
    size_usdt: float
    
    # Prix extremes atteints pendant le trade
    max_price: float
    min_price: float
    
    # Événements
    be_triggered: bool = False
    be_price_at_trigger: Optional[float] = None
    trailing_activated: bool = False
    trailing_final_sl: Optional[float] = None
    
    # Paramètres utilisés
    atr_mult_sl: float = 1.2
    atr_mult_tp: float = 2.2
    trailing_trigger_mult: float = 1.5
    trailing_distance_mult: float = 0.8
    be_atr_mult: float = 1.0
    entry_atr_pct: float = 0.2  # ATR en % du prix


@dataclass
class WhatIfResult:
    """Résultats de simulation What-If"""
    pnl_if_no_be: Optional[float] = None
    pnl_if_no_trailing: Optional[float] = None
    pnl_if_fixed_tp: Optional[float] = None
    pnl_if_wider_sl: Optional[float] = None
    pnl_if_tighter_sl: Optional[float] = None
    pnl_if_wider_trailing: Optional[float] = None
    pnl_if_tighter_trailing: Optional[float] = None
    
    # Efficacité
    sl_efficiency: Optional[float] = None  # % du SL utilisé
    tp_efficiency: Optional[float] = None  # % du TP atteint
    be_efficiency: Optional[float] = None  # Trade aurait-il été perdant sans BE?
    trailing_capture_pct: Optional[float] = None  # % du mouvement capturé


class WhatIfSimulator:
    """
    Simulateur de scénarios alternatifs pour optimisation des paramètres ATR.
    
    Usage:
        simulator = WhatIfSimulator()
        result = simulator.simulate(trade_data)
        simulator.update_database(trade_id, result)
    """
    
    def __init__(self, db_connection=None):
        """
        Initialiser le simulateur.
        
        Args:
            db_connection: Connexion PostgreSQL (optionnel, créée si non fournie)
        """
        self.db_connection = db_connection
    
    def simulate(self, trade: TradeData) -> WhatIfResult:
        """
        Simuler tous les scénarios What-If pour un trade.
        
        Args:
            trade: Données du trade
            
        Returns:
            WhatIfResult avec tous les scénarios calculés
        """
        result = WhatIfResult()
        
        try:
            # 1. PnL si pas de Break-Even
            result.pnl_if_no_be = self._simulate_no_be(trade)
            
            # 2. PnL si pas de Trailing Stop
            result.pnl_if_no_trailing = self._simulate_no_trailing(trade)
            
            # 3. PnL avec TP fixe (sans trailing)
            result.pnl_if_fixed_tp = self._simulate_fixed_tp(trade)
            
            # 4. PnL avec SL plus large (× 1.5)
            result.pnl_if_wider_sl = self._simulate_wider_sl(trade, multiplier=1.5)
            
            # 5. PnL avec SL plus serré (× 0.75)
            result.pnl_if_tighter_sl = self._simulate_tighter_sl(trade, multiplier=0.75)
            
            # 6. PnL avec trailing plus large (× 1.5)
            result.pnl_if_wider_trailing = self._simulate_wider_trailing(trade, multiplier=1.5)
            
            # 7. PnL avec trailing plus serré (× 0.75)
            result.pnl_if_tighter_trailing = self._simulate_tighter_trailing(trade, multiplier=0.75)
            
            # 8. Calculer les métriques d'efficacité
            result.sl_efficiency = self._calculate_sl_efficiency(trade)
            result.tp_efficiency = self._calculate_tp_efficiency(trade)
            result.be_efficiency = self._calculate_be_efficiency(trade, result.pnl_if_no_be)
            result.trailing_capture_pct = self._calculate_trailing_capture(trade)
            
            logger.debug(
                f"📊 What-If simulé pour {trade.symbol}: "
                f"no_be={result.pnl_if_no_be:.3f}%, no_trail={result.pnl_if_no_trailing:.3f}%"
            )
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur simulation What-If pour {trade.symbol}: {e}")
        
        return result
    
    def _calculate_pnl(self, trade: TradeData, exit_price: float) -> float:
        """Calculer le PnL% pour un prix de sortie donné."""
        if trade.direction == 'LONG':
            return ((exit_price - trade.entry_price) / trade.entry_price) * 100
        else:  # SHORT
            return ((trade.entry_price - exit_price) / trade.entry_price) * 100
    
    def _simulate_no_be(self, trade: TradeData) -> Optional[float]:
        """
        Simuler le PnL si Break-Even n'avait pas été activé.
        
        Si BE était activé, le SL original aurait pu être touché.
        """
        if not trade.be_triggered:
            # BE pas activé, même résultat que le trade réel
            return self._calculate_pnl(trade, trade.exit_price)
        
        # BE était activé - simuler avec SL original
        if trade.direction == 'LONG':
            # Si le prix minimum est allé sous le SL original, on aurait été stoppé
            if trade.min_price <= trade.sl_price:
                return self._calculate_pnl(trade, trade.sl_price)
            else:
                # SL original n'aurait pas été touché
                return self._calculate_pnl(trade, trade.exit_price)
        else:  # SHORT
            if trade.max_price >= trade.sl_price:
                return self._calculate_pnl(trade, trade.sl_price)
            else:
                return self._calculate_pnl(trade, trade.exit_price)
    
    def _simulate_no_trailing(self, trade: TradeData) -> Optional[float]:
        """
        Simuler le PnL si Trailing Stop n'avait pas été activé.
        
        Le trade aurait continué jusqu'au TP fixe ou SL.
        """
        if not trade.trailing_activated:
            return self._calculate_pnl(trade, trade.exit_price)
        
        # Trailing était activé - simuler avec TP fixe
        if trade.direction == 'LONG':
            # TP atteint?
            if trade.max_price >= trade.tp_price:
                return self._calculate_pnl(trade, trade.tp_price)
            # SL touché?
            elif trade.min_price <= trade.sl_price:
                return self._calculate_pnl(trade, trade.sl_price)
            else:
                # Ni TP ni SL - sortie au même prix
                return self._calculate_pnl(trade, trade.exit_price)
        else:  # SHORT
            if trade.min_price <= trade.tp_price:
                return self._calculate_pnl(trade, trade.tp_price)
            elif trade.max_price >= trade.sl_price:
                return self._calculate_pnl(trade, trade.sl_price)
            else:
                return self._calculate_pnl(trade, trade.exit_price)
    
    def _simulate_fixed_tp(self, trade: TradeData) -> Optional[float]:
        """Simuler avec un TP fixe (sans trailing)."""
        if trade.direction == 'LONG':
            if trade.max_price >= trade.tp_price:
                return self._calculate_pnl(trade, trade.tp_price)
            elif trade.min_price <= trade.sl_price:
                return self._calculate_pnl(trade, trade.sl_price)
            else:
                return self._calculate_pnl(trade, trade.exit_price)
        else:
            if trade.min_price <= trade.tp_price:
                return self._calculate_pnl(trade, trade.tp_price)
            elif trade.max_price >= trade.sl_price:
                return self._calculate_pnl(trade, trade.sl_price)
            else:
                return self._calculate_pnl(trade, trade.exit_price)
    
    def _simulate_wider_sl(self, trade: TradeData, multiplier: float = 1.5) -> Optional[float]:
        """Simuler avec un SL plus large."""
        atr_distance = trade.entry_price * (trade.entry_atr_pct / 100) * trade.atr_mult_sl
        wider_distance = atr_distance * multiplier
        
        if trade.direction == 'LONG':
            wider_sl = trade.entry_price - wider_distance
            # SL plus large aurait-il été touché?
            if trade.min_price <= wider_sl:
                return self._calculate_pnl(trade, wider_sl)
            else:
                # SL pas touché, même sortie
                return self._calculate_pnl(trade, trade.exit_price)
        else:
            wider_sl = trade.entry_price + wider_distance
            if trade.max_price >= wider_sl:
                return self._calculate_pnl(trade, wider_sl)
            else:
                return self._calculate_pnl(trade, trade.exit_price)
    
    def _simulate_tighter_sl(self, trade: TradeData, multiplier: float = 0.75) -> Optional[float]:
        """Simuler avec un SL plus serré."""
        atr_distance = trade.entry_price * (trade.entry_atr_pct / 100) * trade.atr_mult_sl
        tighter_distance = atr_distance * multiplier
        
        if trade.direction == 'LONG':
            tighter_sl = trade.entry_price - tighter_distance
            if trade.min_price <= tighter_sl:
                return self._calculate_pnl(trade, tighter_sl)
            else:
                return self._calculate_pnl(trade, trade.exit_price)
        else:
            tighter_sl = trade.entry_price + tighter_distance
            if trade.max_price >= tighter_sl:
                return self._calculate_pnl(trade, tighter_sl)
            else:
                return self._calculate_pnl(trade, trade.exit_price)
    
    def _simulate_wider_trailing(self, trade: TradeData, multiplier: float = 1.5) -> Optional[float]:
        """Simuler avec un trailing stop plus large."""
        if not trade.trailing_activated or not trade.trailing_final_sl:
            return self._calculate_pnl(trade, trade.exit_price)
        
        # Calculer la distance du trailing original
        if trade.direction == 'LONG':
            original_distance = trade.max_price - trade.trailing_final_sl
            wider_distance = original_distance * multiplier
            wider_trailing_sl = trade.max_price - wider_distance
            
            # Le trailing plus large aurait-il été touché?
            if trade.min_price <= wider_trailing_sl:
                return self._calculate_pnl(trade, wider_trailing_sl)
            else:
                return self._calculate_pnl(trade, trade.exit_price)
        else:
            original_distance = trade.trailing_final_sl - trade.min_price
            wider_distance = original_distance * multiplier
            wider_trailing_sl = trade.min_price + wider_distance
            
            if trade.max_price >= wider_trailing_sl:
                return self._calculate_pnl(trade, wider_trailing_sl)
            else:
                return self._calculate_pnl(trade, trade.exit_price)
    
    def _simulate_tighter_trailing(self, trade: TradeData, multiplier: float = 0.75) -> Optional[float]:
        """Simuler avec un trailing stop plus serré."""
        if not trade.trailing_activated or not trade.trailing_final_sl:
            return self._calculate_pnl(trade, trade.exit_price)
        
        if trade.direction == 'LONG':
            original_distance = trade.max_price - trade.trailing_final_sl
            tighter_distance = original_distance * multiplier
            tighter_trailing_sl = trade.max_price - tighter_distance
            
            if trade.min_price <= tighter_trailing_sl:
                return self._calculate_pnl(trade, tighter_trailing_sl)
            else:
                return self._calculate_pnl(trade, trade.exit_price)
        else:
            original_distance = trade.trailing_final_sl - trade.min_price
            tighter_distance = original_distance * multiplier
            tighter_trailing_sl = trade.min_price + tighter_distance
            
            if trade.max_price >= tighter_trailing_sl:
                return self._calculate_pnl(trade, tighter_trailing_sl)
            else:
                return self._calculate_pnl(trade, trade.exit_price)
    
    def _calculate_sl_efficiency(self, trade: TradeData) -> Optional[float]:
        """
        Calculer l'efficacité du SL (% du SL utilisé).
        
        100% = SL touché exactement
        0% = Jamais approché du SL
        """
        if trade.direction == 'LONG':
            sl_distance = trade.entry_price - trade.sl_price
            if sl_distance <= 0:
                return None
            min_distance = trade.entry_price - trade.min_price
            return min(100, (min_distance / sl_distance) * 100)
        else:
            sl_distance = trade.sl_price - trade.entry_price
            if sl_distance <= 0:
                return None
            max_distance = trade.max_price - trade.entry_price
            return min(100, (max_distance / sl_distance) * 100)
    
    def _calculate_tp_efficiency(self, trade: TradeData) -> Optional[float]:
        """
        Calculer l'efficacité du TP (% du TP atteint).
        
        100% = TP touché
        0% = N'a pas bougé vers le TP
        """
        if trade.direction == 'LONG':
            tp_distance = trade.tp_price - trade.entry_price
            if tp_distance <= 0:
                return None
            max_distance = trade.max_price - trade.entry_price
            return min(100, (max_distance / tp_distance) * 100)
        else:
            tp_distance = trade.entry_price - trade.tp_price
            if tp_distance <= 0:
                return None
            min_distance = trade.entry_price - trade.min_price
            return min(100, (min_distance / tp_distance) * 100)
    
    def _calculate_be_efficiency(self, trade: TradeData, pnl_if_no_be: Optional[float]) -> Optional[float]:
        """
        Calculer l'efficacité du Break-Even.
        
        Retourne la différence de PnL grâce au BE.
        Positif = BE a amélioré le résultat
        Négatif = BE a dégradé le résultat
        """
        if not trade.be_triggered or pnl_if_no_be is None:
            return None
        
        actual_pnl = self._calculate_pnl(trade, trade.exit_price)
        return actual_pnl - pnl_if_no_be
    
    def _calculate_trailing_capture(self, trade: TradeData) -> Optional[float]:
        """
        Calculer le pourcentage du mouvement max capturé par le trailing.
        
        100% = Sorti au plus haut (LONG) ou plus bas (SHORT)
        0% = Sorti à l'entrée
        """
        if trade.direction == 'LONG':
            max_move = trade.max_price - trade.entry_price
            if max_move <= 0:
                return 0
            actual_move = trade.exit_price - trade.entry_price
            return max(0, (actual_move / max_move) * 100)
        else:
            max_move = trade.entry_price - trade.min_price
            if max_move <= 0:
                return 0
            actual_move = trade.entry_price - trade.exit_price
            return max(0, (actual_move / max_move) * 100)
    
    # ═══════════════════════════════════════════════════════════════════════
    # 🔥 PHASE 1C: Simulation par régime
    # ═══════════════════════════════════════════════════════════════════════
    
    def simulate_regime_scenarios(self, trade: TradeData, atr_pct: float = None) -> Dict[str, Any]:
        """
        Simule le PnL avec les paramètres de chaque régime.
        
        Permet de déterminer rétrospectivement quel régime aurait été optimal.
        
        Args:
            trade: TradeData du trade
            atr_pct: ATR% au moment de l'entrée (optionnel, sinon estimé)
            
        Returns:
            Dict avec pnl_if_calme/normal/volatile_params et optimal_regime_retrospective
        """
        from core.market_regime_selector import DEFAULT_REGIME_CONFIGS
        
        # ATR par défaut si non fourni
        if atr_pct is None:
            atr_pct = 0.5  # Valeur médiane typique
        
        if not trade.entry_price or not trade.exit_price:
            return {}
        
        results = {}
        
        for regime_name, config in DEFAULT_REGIME_CONFIGS.items():
            if regime_name == "CHOPPY":
                continue  # Skip CHOPPY pour simplifier
            
            # Calculer SL/TP avec les params de ce régime
            sl_distance_pct = (atr_pct * config.atr_mult_sl) / 100
            tp_distance_pct = (atr_pct * config.atr_mult_tp) / 100
            
            if trade.direction == 'LONG':
                sim_sl = trade.entry_price * (1 - sl_distance_pct)
                sim_tp = trade.entry_price * (1 + tp_distance_pct)
            else:  # SHORT
                sim_sl = trade.entry_price * (1 + sl_distance_pct)
                sim_tp = trade.entry_price * (1 - tp_distance_pct)
            
            # Simuler où le trade aurait fermé avec ces params
            # On utilise min_price/max_price pour vérifier si SL/TP auraient été touchés
            
            if trade.direction == 'LONG':
                # Vérifier si SL aurait été touché
                if trade.min_price <= sim_sl:
                    sim_pnl = -sl_distance_pct * 100
                # Vérifier si TP aurait été touché
                elif trade.max_price >= sim_tp:
                    sim_pnl = tp_distance_pct * 100
                else:
                    # Ni SL ni TP touchés, utiliser exit_price réel
                    sim_pnl = ((trade.exit_price - trade.entry_price) / trade.entry_price) * 100
            else:  # SHORT
                if trade.max_price >= sim_sl:
                    sim_pnl = -sl_distance_pct * 100
                elif trade.min_price <= sim_tp:
                    sim_pnl = tp_distance_pct * 100
                else:
                    sim_pnl = ((trade.entry_price - trade.exit_price) / trade.entry_price) * 100
            
            results[f"pnl_if_{regime_name.lower()}_params"] = round(sim_pnl, 4)
        
        # Déterminer le régime optimal (celui avec le meilleur PnL simulé)
        if results:
            best_key = max(results, key=results.get)
            results["optimal_regime_retrospective"] = best_key.replace("pnl_if_", "").replace("_params", "").upper()
        
        logger.debug(
            f"📊 Régime What-If pour {trade.symbol}: "
            f"CALME={results.get('pnl_if_calme_params', 'N/A'):.3f}%, "
            f"NORMAL={results.get('pnl_if_normal_params', 'N/A'):.3f}%, "
            f"VOLATILE={results.get('pnl_if_volatile_params', 'N/A'):.3f}% | "
            f"Optimal: {results.get('optimal_regime_retrospective', 'N/A')}"
        )
        
        return results
    
    def update_database(self, trade_id: str, result: WhatIfResult) -> bool:
        """
        Mettre à jour la table trade_atr_metrics avec les résultats What-If.
        
        Args:
            trade_id: UUID du trade
            result: Résultats de simulation
            
        Returns:
            True si mise à jour réussie
        """
        try:
            import psycopg2
            import os
            from dotenv import load_dotenv
            load_dotenv()
            
            conn = self.db_connection
            if not conn:
                conn = psycopg2.connect(
                    host=os.getenv('POSTGRES_HOST', 'localhost'),
                    port=int(os.getenv('POSTGRES_PORT', '5432')),
                    database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
                    user=os.getenv('POSTGRES_USER', 'postgres'),
                    password=os.getenv('POSTGRES_PASSWORD', '')
                )
            
            cur = conn.cursor()
            
            query = """
                UPDATE trade_atr_metrics SET
                    pnl_if_no_be = %s,
                    pnl_if_no_trailing = %s,
                    pnl_if_fixed_tp = %s,
                    pnl_if_wider_sl = %s,
                    pnl_if_tighter_sl = %s,
                    pnl_if_wider_trailing = %s,
                    pnl_if_tighter_trailing = %s,
                    sl_efficiency = %s,
                    tp_efficiency = %s,
                    be_efficiency = %s,
                    trailing_capture_pct = %s,
                    updated_at = NOW()
                WHERE trade_id = %s
            """
            
            params = (
                result.pnl_if_no_be,
                result.pnl_if_no_trailing,
                result.pnl_if_fixed_tp,
                result.pnl_if_wider_sl,
                result.pnl_if_tighter_sl,
                result.pnl_if_wider_trailing,
                result.pnl_if_tighter_trailing,
                result.sl_efficiency,
                result.tp_efficiency,
                result.be_efficiency,
                result.trailing_capture_pct,
                trade_id
            )
            
            cur.execute(query, params)
            
            if not self.db_connection:
                conn.commit()
                conn.close()
            
            logger.info(f"✅ What-If mis à jour pour trade {trade_id[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur update What-If pour {trade_id[:8]}: {e}")
            return False
    
    def update_regime_whatif(self, trade_id: str, regime_results: Dict[str, Any]) -> bool:
        """
        🔥 PHASE 1C: Mettre à jour les colonnes What-If régime.
        
        Args:
            trade_id: UUID du trade
            regime_results: Dict avec pnl_if_calme_params, etc.
            
        Returns:
            True si mise à jour réussie
        """
        try:
            import psycopg2
            import os
            from dotenv import load_dotenv
            load_dotenv()
            
            conn = self.db_connection
            if not conn:
                conn = psycopg2.connect(
                    host=os.getenv('POSTGRES_HOST', 'localhost'),
                    port=int(os.getenv('POSTGRES_PORT', '5432')),
                    database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
                    user=os.getenv('POSTGRES_USER', 'postgres'),
                    password=os.getenv('POSTGRES_PASSWORD', '')
                )
            
            cur = conn.cursor()
            
            query = """
                UPDATE trade_atr_metrics SET
                    pnl_if_calme_params = %s,
                    pnl_if_normal_params = %s,
                    pnl_if_volatile_params = %s,
                    optimal_regime_retrospective = %s,
                    updated_at = NOW()
                WHERE trade_id = %s
            """
            
            params = (
                regime_results.get('pnl_if_calme_params'),
                regime_results.get('pnl_if_normal_params'),
                regime_results.get('pnl_if_volatile_params'),
                regime_results.get('optimal_regime_retrospective'),
                trade_id
            )
            
            cur.execute(query, params)
            
            if not self.db_connection:
                conn.commit()
                conn.close()
            
            logger.debug(
                f"✅ Régime What-If mis à jour pour trade {trade_id[:8]}: "
                f"optimal={regime_results.get('optimal_regime_retrospective', 'N/A')}"
            )
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur update Régime What-If pour {trade_id[:8]}: {e}")
            return False


def process_trade_whatif(trade_data: Dict[str, Any]) -> Optional[WhatIfResult]:
    """
    Fonction helper pour traiter un trade et calculer les What-If.
    
    Args:
        trade_data: Dictionnaire avec les données du trade
        
    Returns:
        WhatIfResult ou None si erreur
    """
    try:
        # Convertir dict en TradeData
        trade = TradeData(
            trade_id=trade_data.get('id', ''),
            symbol=trade_data.get('symbol', ''),
            direction=trade_data.get('direction', 'LONG'),
            entry_price=float(trade_data.get('entry_price', 0)),
            exit_price=float(trade_data.get('exit_price', 0)),
            sl_price=float(trade_data.get('sl', 0)),
            tp_price=float(trade_data.get('tp', 0)),
            size_usdt=float(trade_data.get('size_usdt', 0)),
            max_price=float(trade_data.get('max_price_reached', trade_data.get('exit_price', 0))),
            min_price=float(trade_data.get('min_price_reached', trade_data.get('exit_price', 0))),
            be_triggered=trade_data.get('break_even_triggered', False),
            be_price_at_trigger=trade_data.get('break_even_price'),
            trailing_activated=trade_data.get('trailing_stop_triggered', False),
            trailing_final_sl=trade_data.get('trailing_final_sl'),
            atr_mult_sl=float(trade_data.get('config_atr_mult_sl', 1.2)),
            atr_mult_tp=float(trade_data.get('config_atr_mult_tp', 2.2)),
            trailing_trigger_mult=float(trade_data.get('config_trailing_trigger_atr_mult', 1.5)),
            trailing_distance_mult=float(trade_data.get('config_trailing_distance_atr_mult', 0.8)),
            be_atr_mult=float(trade_data.get('config_be_atr_mult', 1.0)),
            entry_atr_pct=float(trade_data.get('entry_atr_pct_1m', 0.2))
        )
        
        simulator = WhatIfSimulator()
        result = simulator.simulate(trade)
        simulator.update_database(trade.trade_id, result)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur process_trade_whatif: {e}")
        return None
