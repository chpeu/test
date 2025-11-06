#!/usr/bin/env python3
"""
🎯 OPTIMISEUR DE SEUILS
Outil pour optimiser les seuils de filtrage :
- Spread dynamique (FIXE vs ATR)
- Orderbook imbalance (LONG/SHORT)
- Invalidation précoce (ATR adaptatif)
- Score minimum requis
"""

import json
import logging
from typing import Dict, List, Tuple
from datetime import datetime
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ThresholdOptimizer:
    """Optimiseur de seuils de filtrage"""
    
    def __init__(self, trade_history_file: str = "trade_history_instance_5000.json"):
        self.trade_history_file = trade_history_file
        self.trades = []
        self.current_thresholds = {}
        self.optimization_results = {}
    
    def load_trade_history(self):
        """Charger l'historique des trades"""
        try:
            with open(self.trade_history_file, 'r', encoding='utf-8') as f:
                self.trades = json.load(f)
            
            logger.info(f"✅ {len(self.trades)} trades chargés")
            return True
        except FileNotFoundError:
            logger.error(f"❌ Fichier non trouvé: {self.trade_history_file}")
            return False
        except Exception as e:
            logger.error(f"❌ Erreur chargement: {e}")
            return False
    
    def load_current_config(self):
        """Charger la configuration actuelle"""
        try:
            from config import TRADING_CONFIG
            
            self.current_thresholds = {
                # Spread
                'spread_fixe': TRADING_CONFIG.get('tp_sl_mode') == 'FIXE',
                'spread_max_fixe': 0.03,  # Hardcodé dans analyzer.py
                'spread_max_atr': 0.06,   # Hardcodé dans analyzer.py
                
                # Orderbook
                'orderbook_long_min': 1.1,   # Hardcodé dans analyzer.py
                'orderbook_short_max': 0.95, # Hardcodé dans analyzer.py
                
                # Invalidation précoce
                'early_inv_15s': TRADING_CONFIG.get('early_invalidation', {}).get('threshold_15s', -0.12),
                'early_inv_30s': TRADING_CONFIG.get('early_invalidation', {}).get('threshold_30s', -0.08),
                
                # Seuils adaptatifs
                'adaptive_low_vol_mult': TRADING_CONFIG.get('adaptive_thresholds', {}).get('early_invalidation', {}).get('low_vol_multiplier', 0.7),
                'adaptive_high_vol_mult': TRADING_CONFIG.get('adaptive_thresholds', {}).get('early_invalidation', {}).get('high_vol_multiplier', 1.3),
                
                # Score
                'min_score_required': TRADING_CONFIG.get('min_score_required', 7.5),
                'min_score_adx_high': TRADING_CONFIG.get('min_score_adx_high', 7.0),
                'min_score_adx_low': TRADING_CONFIG.get('min_score_adx_low', 8.0),
            }
            
            logger.info("✅ Configuration actuelle chargée")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur chargement config: {e}")
            return False
    
    def analyze_spread_impact(self):
        """Analyser l'impact du seuil de spread"""
        logger.info("\n" + "="*60)
        logger.info("📊 ANALYSE IMPACT SPREAD")
        logger.info("="*60)
        
        # Simulation : combien de trades auraient été rejetés avec différents seuils
        spread_thresholds = [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]
        
        results = {}
        for threshold in spread_thresholds:
            # Note: Nous n'avons pas l'info spread dans l'historique
            # On peut seulement estimer basé sur la volatilité
            results[threshold] = {
                'accepted': 0,
                'rejected': 0,
                'avg_pnl': 0.0
            }
        
        logger.info("\n💡 RECOMMANDATIONS SPREAD")
        logger.info(f"  Actuel FIXE: {self.current_thresholds['spread_max_fixe']:.2%}")
        logger.info(f"  Actuel ATR:  {self.current_thresholds['spread_max_atr']:.2%}")
        logger.info("\n  Si trop de rejets:")
        logger.info("    → FIXE: 0.03% → 0.04%")
        logger.info("    → ATR:  0.06% → 0.08%")
        
        return results
    
    def analyze_orderbook_impact(self):
        """Analyser l'impact des seuils orderbook"""
        logger.info("\n" + "="*60)
        logger.info("📊 ANALYSE IMPACT ORDERBOOK")
        logger.info("="*60)
        
        # Simulation : différents seuils
        long_thresholds = [1.05, 1.1, 1.15, 1.2]
        short_thresholds = [0.90, 0.92, 0.95, 0.98]
        
        logger.info("\n💡 RECOMMANDATIONS ORDERBOOK")
        logger.info(f"  Actuel LONG:  ≥ {self.current_thresholds['orderbook_long_min']}")
        logger.info(f"  Actuel SHORT: ≤ {self.current_thresholds['orderbook_short_max']}")
        logger.info("\n  Si trop de rejets LONG:")
        logger.info("    → Réduire seuil: 1.1 → 1.05")
        logger.info("  Si trop de rejets SHORT:")
        logger.info("    → Augmenter seuil: 0.95 → 0.98")
        
        return {'long': long_thresholds, 'short': short_thresholds}
    
    def analyze_early_invalidation(self):
        """Analyser l'impact de l'invalidation précoce"""
        logger.info("\n" + "="*60)
        logger.info("📊 ANALYSE INVALIDATION PRÉCOCE")
        logger.info("="*60)
        
        # Analyser les trades fermés par EARLY_INVALIDATION
        early_inv_trades = [t for t in self.trades if t.get('reason') == 'EARLY_INVALIDATION']
        
        if early_inv_trades:
            avg_pnl = sum(t.get('net_pnl_pct', 0) for t in early_inv_trades) / len(early_inv_trades)
            avg_duration = sum(t.get('duration', 0) for t in early_inv_trades) / len(early_inv_trades)
            
            logger.info(f"\n📈 STATISTIQUES")
            logger.info(f"  Trades invalidés: {len(early_inv_trades)}")
            logger.info(f"  PnL moyen: {avg_pnl:.2f}%")
            logger.info(f"  Durée moyenne: {avg_duration:.0f}s")
            
            # Si PnL moyen trop négatif → seuils trop tolérants
            # Si PnL moyen proche de 0 → seuils optimaux
            # Si PnL moyen positif → seuils trop stricts
            
            logger.info("\n💡 RECOMMANDATIONS")
            logger.info(f"  Actuel 15s: {self.current_thresholds['early_inv_15s']:.2%}")
            logger.info(f"  Actuel 30s: {self.current_thresholds['early_inv_30s']:.2%}")
            
            if avg_pnl < -0.15:
                logger.info("  ⚠️ PnL très négatif → Seuils trop tolérants")
                logger.info("    → Réduire: -0.12% → -0.10% (15s)")
                logger.info("    → Réduire: -0.08% → -0.06% (30s)")
            elif avg_pnl > 0:
                logger.info("  ⚠️ PnL positif → Seuils trop stricts")
                logger.info("    → Augmenter: -0.12% → -0.15% (15s)")
                logger.info("    → Augmenter: -0.08% → -0.10% (30s)")
            else:
                logger.info("  ✅ Seuils optimaux (PnL proche de 0)")
        else:
            logger.info("  ℹ️ Aucun trade invalidé précocement")
        
        return early_inv_trades
    
    def analyze_score_threshold(self):
        """Analyser l'impact du score minimum requis"""
        logger.info("\n" + "="*60)
        logger.info("📊 ANALYSE SCORE MINIMUM")
        logger.info("="*60)
        
        # Note: Nous n'avons pas l'info score dans l'historique
        # On peut seulement donner des recommandations générales
        
        total_trades = len(self.trades)
        wins = sum(1 for t in self.trades if t.get('net_pnl_pct', 0) > 0)
        winrate = wins / total_trades * 100 if total_trades > 0 else 0
        
        logger.info(f"\n📈 STATISTIQUES GLOBALES")
        logger.info(f"  Total trades: {total_trades}")
        logger.info(f"  Winrate: {winrate:.1f}%")
        
        logger.info("\n💡 RECOMMANDATIONS SCORE")
        logger.info(f"  Actuel: {self.current_thresholds['min_score_required']}")
        logger.info(f"  ADX > 30: {self.current_thresholds['min_score_adx_high']}")
        logger.info(f"  ADX < 25: {self.current_thresholds['min_score_adx_low']}")
        
        if winrate < 65:
            logger.info("  ⚠️ Winrate bas → Augmenter score minimum")
            logger.info("    → 7.5 → 8.0")
            logger.info("    → ADX > 30: 7.0 → 7.5")
        elif winrate > 80:
            logger.info("  ⚠️ Winrate très haut → Possibilité de réduire")
            logger.info("    → 7.5 → 7.0 (plus d'opportunités)")
        else:
            logger.info("  ✅ Score optimal (winrate 65-80%)")
        
        return winrate
    
    def generate_optimization_report(self):
        """Générer rapport d'optimisation complet"""
        logger.info("\n" + "="*60)
        logger.info("🎯 RAPPORT D'OPTIMISATION")
        logger.info("="*60)
        
        # Analyser chaque seuil
        spread_results = self.analyze_spread_impact()
        orderbook_results = self.analyze_orderbook_impact()
        early_inv_trades = self.analyze_early_invalidation()
        winrate = self.analyze_score_threshold()
        
        # Résumé des recommandations
        logger.info("\n" + "="*60)
        logger.info("💡 RÉSUMÉ DES RECOMMANDATIONS")
        logger.info("="*60)
        
        recommendations = []
        
        # Basé sur le winrate
        if winrate < 65:
            recommendations.append({
                'type': 'score',
                'priority': 'HAUTE',
                'action': 'Augmenter min_score_required: 7.5 → 8.0',
                'reason': f'Winrate bas ({winrate:.1f}%)'
            })
        
        # Basé sur les invalidations précoces
        if early_inv_trades:
            avg_pnl = sum(t.get('net_pnl_pct', 0) for t in early_inv_trades) / len(early_inv_trades)
            if avg_pnl < -0.15:
                recommendations.append({
                    'type': 'early_invalidation',
                    'priority': 'MOYENNE',
                    'action': 'Réduire seuils invalidation: -0.12% → -0.10%',
                    'reason': f'PnL moyen invalidations trop négatif ({avg_pnl:.2f}%)'
                })
        
        # Afficher recommandations
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                logger.info(f"\n{i}. [{rec['priority']}] {rec['type'].upper()}")
                logger.info(f"   Action: {rec['action']}")
                logger.info(f"   Raison: {rec['reason']}")
        else:
            logger.info("\n✅ Tous les seuils semblent optimaux")
        
        # Sauvegarder rapport
        report = {
            'timestamp': datetime.now().isoformat(),
            'current_thresholds': self.current_thresholds,
            'statistics': {
                'total_trades': len(self.trades),
                'winrate': winrate,
                'early_invalidations': len(early_inv_trades)
            },
            'recommendations': recommendations
        }
        
        return report
    
    def save_report(self, output_file: str = "threshold_optimization_report.json"):
        """Sauvegarder le rapport"""
        report = self.generate_optimization_report()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n✅ Rapport sauvegardé dans: {output_file}")
        
        # Générer fichier de config suggérée
        self.generate_suggested_config(report)
    
    def generate_suggested_config(self, report: Dict):
        """Générer un fichier de configuration suggérée"""
        logger.info("\n" + "="*60)
        logger.info("📝 CONFIGURATION SUGGÉRÉE")
        logger.info("="*60)
        
        suggestions = []
        
        # Appliquer les recommandations
        for rec in report.get('recommendations', []):
            if rec['type'] == 'score':
                suggestions.append("TRADING_CONFIG['min_score_required'] = 8.0  # Augmenté de 7.5")
            elif rec['type'] == 'early_invalidation':
                suggestions.append("TRADING_CONFIG['early_invalidation']['threshold_15s'] = -0.10  # Réduit de -0.12")
                suggestions.append("TRADING_CONFIG['early_invalidation']['threshold_30s'] = -0.06  # Réduit de -0.08")
        
        if suggestions:
            logger.info("\n📋 Modifications suggérées dans config.py:")
            for suggestion in suggestions:
                logger.info(f"  {suggestion}")
            
            # Sauvegarder dans un fichier
            with open("config_suggestions.txt", 'w', encoding='utf-8') as f:
                f.write("# Modifications suggérées pour config.py\n")
                f.write(f"# Généré le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                for suggestion in suggestions:
                    f.write(f"{suggestion}\n")
            
            logger.info(f"\n✅ Suggestions sauvegardées dans: config_suggestions.txt")
        else:
            logger.info("\n✅ Aucune modification nécessaire")


def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Optimiser les seuils de filtrage")
    parser.add_argument('--history', default="trade_history_instance_5000.json",
                       help="Fichier d'historique des trades")
    parser.add_argument('-o', '--output', default="threshold_optimization_report.json",
                       help="Fichier de sortie")
    
    args = parser.parse_args()
    
    optimizer = ThresholdOptimizer(args.history)
    
    if not optimizer.load_trade_history():
        return
    
    if not optimizer.load_current_config():
        return
    
    optimizer.save_report(args.output)


if __name__ == "__main__":
    main()

