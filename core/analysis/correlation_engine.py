"""
Correlation Engine - Phase 2A
=============================
Analyse les corrélations entre:
- Session de trading ↔ WinRate/PnL
- Régime local (LOW/MEDIUM/HIGH) ↔ Performance
- Paramètres utilisés ↔ Résultats
- Heures UTC ↔ Performance

Fournit des recommandations basées sur les données historiques.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import psycopg2
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()


@dataclass
class CorrelationResult:
    """Résultat d'une analyse de corrélation"""
    dimension: str  # session, regime, hour, etc.
    value: str  # ASIA, LOW, 14, etc.
    trades: int
    wins: int
    winrate: float
    total_pnl: float
    avg_pnl: float
    recommendation: str  # AVOID, NEUTRAL, FAVOR


@dataclass
class OptimizationSuggestion:
    """Suggestion d'optimisation basée sur les corrélations"""
    parameter: str
    current_value: float
    suggested_value: float
    expected_improvement: str
    confidence: str  # LOW, MEDIUM, HIGH
    based_on_trades: int


class CorrelationEngine:
    """
    Moteur d'analyse des corrélations pour optimisation trading.
    """
    
    def __init__(self, db_connection=None):
        """
        Initialiser le moteur de corrélations.
        
        Args:
            db_connection: Connexion PostgreSQL (optionnel, utilisera pool par défaut)
        """
        self.db_connection = db_connection
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._last_cache_update = None
    
    def _get_db_connection(self):
        """Obtenir une connexion à la base de données"""
        if self.db_connection:
            return self.db_connection
        
        try:
            # Essayer DATABASE_URL d'abord
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                return psycopg2.connect(database_url)
            
            # Sinon utiliser les variables POSTGRES_*
            host = os.getenv('POSTGRES_HOST', 'localhost')
            port = os.getenv('POSTGRES_PORT', '5432')
            db = os.getenv('POSTGRES_DB', 'trade_cursor_ml')
            user = os.getenv('POSTGRES_USER', 'postgres')
            password = os.getenv('POSTGRES_PASSWORD', '')
            
            return psycopg2.connect(
                host=host,
                port=port,
                database=db,
                user=user,
                password=password
            )
        except Exception as e:
            logger.error(f"Erreur connexion DB: {e}")
        return None
    
    def _release_connection(self, conn):
        """Libérer la connexion"""
        if conn and not self.db_connection:
            try:
                conn.close()
            except:
                pass
    
    def analyze_by_session(self, days: int = 7) -> List[CorrelationResult]:
        """
        Analyser la performance par session de trading.
        
        Args:
            days: Nombre de jours à analyser
            
        Returns:
            Liste de CorrelationResult par session
        """
        conn = self._get_db_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            query = """
            SELECT 
                tam.session_market,
                COUNT(*) as trades,
                SUM(CASE WHEN t.pnl_usdt > 0 THEN 1 ELSE 0 END) as wins,
                ROUND(100.0 * SUM(CASE WHEN t.pnl_usdt > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
                ROUND(SUM(t.pnl_usdt)::numeric, 3) as total_pnl,
                ROUND(AVG(t.pnl_usdt)::numeric, 4) as avg_pnl
            FROM trade_atr_metrics tam
            JOIN trades t ON tam.trade_id = t.id
            WHERE tam.created_at >= NOW() - INTERVAL '%s days'
            AND tam.session_market IS NOT NULL
            GROUP BY tam.session_market
            ORDER BY total_pnl DESC;
            """
            
            cursor.execute(query, (days,))
            rows = cursor.fetchall()
            cursor.close()
            
            results = []
            for row in rows:
                session, trades, wins, winrate, total_pnl, avg_pnl = row
                
                # Déterminer la recommandation
                if winrate and winrate >= 55:
                    recommendation = "FAVOR"
                elif winrate and winrate <= 40:
                    recommendation = "AVOID"
                else:
                    recommendation = "NEUTRAL"
                
                results.append(CorrelationResult(
                    dimension="session",
                    value=session or "UNKNOWN",
                    trades=trades or 0,
                    wins=wins or 0,
                    winrate=float(winrate or 0),
                    total_pnl=float(total_pnl or 0),
                    avg_pnl=float(avg_pnl or 0),
                    recommendation=recommendation
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur analyze_by_session: {e}")
            return []
        finally:
            self._release_connection(conn)
    
    def analyze_by_local_regime(self, days: int = 7) -> List[CorrelationResult]:
        """
        Analyser la performance par régime local (LOW/MEDIUM/HIGH basé sur ATR%).
        
        Args:
            days: Nombre de jours à analyser
            
        Returns:
            Liste de CorrelationResult par régime
        """
        conn = self._get_db_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            query = """
            SELECT 
                CASE 
                    WHEN tam.entry_atr_pct_1m < 0.2 THEN 'LOW'
                    WHEN tam.entry_atr_pct_1m < 0.5 THEN 'MEDIUM'
                    ELSE 'HIGH'
                END as local_regime,
                COUNT(*) as trades,
                SUM(CASE WHEN t.pnl_usdt > 0 THEN 1 ELSE 0 END) as wins,
                ROUND(100.0 * SUM(CASE WHEN t.pnl_usdt > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
                ROUND(SUM(t.pnl_usdt)::numeric, 3) as total_pnl,
                ROUND(AVG(t.pnl_usdt)::numeric, 4) as avg_pnl
            FROM trade_atr_metrics tam
            JOIN trades t ON tam.trade_id = t.id
            WHERE tam.created_at >= NOW() - INTERVAL '%s days'
            AND tam.entry_atr_pct_1m IS NOT NULL
            GROUP BY 1
            ORDER BY trades DESC;
            """
            
            cursor.execute(query, (days,))
            rows = cursor.fetchall()
            cursor.close()
            
            results = []
            for row in rows:
                regime, trades, wins, winrate, total_pnl, avg_pnl = row
                
                # Déterminer la recommandation
                if winrate and winrate >= 55:
                    recommendation = "FAVOR"
                elif winrate and winrate <= 40:
                    recommendation = "AVOID"
                else:
                    recommendation = "NEUTRAL"
                
                results.append(CorrelationResult(
                    dimension="local_regime",
                    value=regime,
                    trades=trades or 0,
                    wins=wins or 0,
                    winrate=float(winrate or 0),
                    total_pnl=float(total_pnl or 0),
                    avg_pnl=float(avg_pnl or 0),
                    recommendation=recommendation
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur analyze_by_local_regime: {e}")
            return []
        finally:
            self._release_connection(conn)
    
    def analyze_by_hour(self, days: int = 7) -> List[CorrelationResult]:
        """
        Analyser la performance par heure UTC.
        
        Args:
            days: Nombre de jours à analyser
            
        Returns:
            Liste de CorrelationResult par heure
        """
        conn = self._get_db_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            query = """
            SELECT 
                tam.hour_utc,
                COUNT(*) as trades,
                SUM(CASE WHEN t.pnl_usdt > 0 THEN 1 ELSE 0 END) as wins,
                ROUND(100.0 * SUM(CASE WHEN t.pnl_usdt > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
                ROUND(SUM(t.pnl_usdt)::numeric, 3) as total_pnl,
                ROUND(AVG(t.pnl_usdt)::numeric, 4) as avg_pnl
            FROM trade_atr_metrics tam
            JOIN trades t ON tam.trade_id = t.id
            WHERE tam.created_at >= NOW() - INTERVAL '%s days'
            AND tam.hour_utc IS NOT NULL
            GROUP BY tam.hour_utc
            ORDER BY tam.hour_utc;
            """
            
            cursor.execute(query, (days,))
            rows = cursor.fetchall()
            cursor.close()
            
            results = []
            for row in rows:
                hour, trades, wins, winrate, total_pnl, avg_pnl = row
                
                # Déterminer la recommandation
                if winrate and winrate >= 55:
                    recommendation = "FAVOR"
                elif winrate and winrate <= 40:
                    recommendation = "AVOID"
                else:
                    recommendation = "NEUTRAL"
                
                results.append(CorrelationResult(
                    dimension="hour_utc",
                    value=str(hour),
                    trades=trades or 0,
                    wins=wins or 0,
                    winrate=float(winrate or 0),
                    total_pnl=float(total_pnl or 0),
                    avg_pnl=float(avg_pnl or 0),
                    recommendation=recommendation
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur analyze_by_hour: {e}")
            return []
        finally:
            self._release_connection(conn)
    
    def analyze_by_exit_reason(self, days: int = 7) -> List[CorrelationResult]:
        """
        Analyser la performance par raison de sortie.
        
        Args:
            days: Nombre de jours à analyser
            
        Returns:
            Liste de CorrelationResult par exit_reason
        """
        conn = self._get_db_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            query = """
            SELECT 
                t.exit_reason,
                COUNT(*) as trades,
                SUM(CASE WHEN t.pnl_usdt > 0 THEN 1 ELSE 0 END) as wins,
                ROUND(100.0 * SUM(CASE WHEN t.pnl_usdt > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as winrate,
                ROUND(SUM(t.pnl_usdt)::numeric, 3) as total_pnl,
                ROUND(AVG(t.pnl_usdt)::numeric, 4) as avg_pnl
            FROM trades t
            WHERE t.created_at >= NOW() - INTERVAL '%s days'
            AND t.exit_reason IS NOT NULL
            GROUP BY t.exit_reason
            ORDER BY total_pnl DESC;
            """
            
            cursor.execute(query, (days,))
            rows = cursor.fetchall()
            cursor.close()
            
            results = []
            for row in rows:
                reason, trades, wins, winrate, total_pnl, avg_pnl = row
                
                # Déterminer la recommandation basée sur la raison
                if reason in ['TP', 'TS'] and total_pnl > 0:
                    recommendation = "FAVOR"
                elif reason in ['SL', 'SL_EXCHANGE'] and total_pnl < -0.5:
                    recommendation = "AVOID"
                else:
                    recommendation = "NEUTRAL"
                
                results.append(CorrelationResult(
                    dimension="exit_reason",
                    value=reason or "UNKNOWN",
                    trades=trades or 0,
                    wins=wins or 0,
                    winrate=float(winrate or 0),
                    total_pnl=float(total_pnl or 0),
                    avg_pnl=float(avg_pnl or 0),
                    recommendation=recommendation
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur analyze_by_exit_reason: {e}")
            return []
        finally:
            self._release_connection(conn)
    
    def analyze_optimal_regime_distribution(self, days: int = 7) -> Dict:
        """
        Analyser la distribution des régimes optimaux (What-If).
        
        Returns:
            Dict avec distribution et recommandations
        """
        conn = self._get_db_connection()
        if not conn:
            return {}
        
        try:
            cursor = conn.cursor()
            
            query = """
            SELECT 
                optimal_regime_retrospective,
                COUNT(*) as trades,
                ROUND(AVG(pnl_if_calme_params)::numeric, 4) as avg_pnl_calme,
                ROUND(AVG(pnl_if_normal_params)::numeric, 4) as avg_pnl_normal,
                ROUND(AVG(pnl_if_volatile_params)::numeric, 4) as avg_pnl_volatile
            FROM trade_atr_metrics
            WHERE created_at >= NOW() - INTERVAL '%s days'
            AND optimal_regime_retrospective IS NOT NULL
            GROUP BY optimal_regime_retrospective
            ORDER BY trades DESC;
            """
            
            cursor.execute(query, (days,))
            rows = cursor.fetchall()
            cursor.close()
            
            total_trades = sum(row[1] for row in rows)
            
            distribution = {}
            for row in rows:
                regime, trades, pnl_calme, pnl_normal, pnl_volatile = row
                distribution[regime] = {
                    'trades': trades,
                    'percentage': round(100.0 * trades / total_trades, 1) if total_trades > 0 else 0,
                    'avg_pnl_calme': float(pnl_calme or 0),
                    'avg_pnl_normal': float(pnl_normal or 0),
                    'avg_pnl_volatile': float(pnl_volatile or 0)
                }
            
            # Déterminer le régime dominant
            dominant_regime = max(distribution.keys(), key=lambda k: distribution[k]['trades']) if distribution else None
            
            return {
                'distribution': distribution,
                'dominant_regime': dominant_regime,
                'recommendation': f"Optimiser paramètres pour régime {dominant_regime}" if dominant_regime else "Pas assez de données"
            }
            
        except Exception as e:
            logger.error(f"Erreur analyze_optimal_regime_distribution: {e}")
            return {}
        finally:
            self._release_connection(conn)
    
    def generate_suggestions(self, days: int = 7) -> List[OptimizationSuggestion]:
        """
        Générer des suggestions d'optimisation basées sur les corrélations.
        
        IMPORTANT: On ne suggère JAMAIS d'arrêter de trader (sessions, paires, etc.)
        Le but est d'ADAPTER les paramètres pour améliorer les performances.
        
        Returns:
            Liste de suggestions prioritaires
        """
        suggestions = []
        
        # Analyser par régime local - suggérer d'adapter les paramètres, pas d'arrêter
        regime_results = self.analyze_by_local_regime(days)
        for r in regime_results:
            if r.recommendation == "AVOID" and r.trades >= 10:
                # Au lieu d'éviter, on suggère d'augmenter le score requis pour ce régime
                suggestions.append(OptimizationSuggestion(
                    parameter=f"min_score_{r.value.lower()}_regime",
                    current_value=9.0,
                    suggested_value=10.0,
                    expected_improvement=f"Augmenter score requis en régime {r.value} (WR actuel={r.winrate}%)",
                    confidence="HIGH" if r.trades >= 20 else "MEDIUM",
                    based_on_trades=r.trades
                ))
        
        # Analyser par session - suggérer d'adapter les paramètres, PAS de désactiver
        session_results = self.analyze_by_session(days)
        for r in session_results:
            if r.recommendation == "AVOID" and r.trades >= 5:
                # Au lieu de désactiver la session, suggérer d'augmenter le score requis
                suggestions.append(OptimizationSuggestion(
                    parameter=f"min_score_{r.value.lower()}_session",
                    current_value=9.0,
                    suggested_value=10.5,
                    expected_improvement=f"Augmenter score requis session {r.value} (WR={r.winrate}%)",
                    confidence="MEDIUM",
                    based_on_trades=r.trades
                ))
        
        # Analyser distribution régime optimal
        optimal_dist = self.analyze_optimal_regime_distribution(days)
        if optimal_dist.get('dominant_regime'):
            dominant = optimal_dist['dominant_regime']
            dist = optimal_dist.get('distribution', {}).get(dominant, {})
            if dist.get('percentage', 0) >= 60:
                suggestions.append(OptimizationSuggestion(
                    parameter="default_regime_params",
                    current_value=0,
                    suggested_value=1,
                    expected_improvement=f"Utiliser params {dominant} par défaut ({dist['percentage']}% optimal)",
                    confidence="HIGH",
                    based_on_trades=dist.get('trades', 0)
                ))
        
        # Trier par confiance et nombre de trades
        suggestions.sort(key=lambda x: (
            {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}.get(x.confidence, 0),
            x.based_on_trades
        ), reverse=True)
        
        return suggestions
    
    def get_full_analysis_report(self, days: int = 7) -> Dict:
        """
        Générer un rapport complet d'analyse des corrélations.
        
        Returns:
            Dict avec toutes les analyses et suggestions
        """
        return {
            'period_days': days,
            'generated_at': datetime.now().isoformat(),
            'by_session': [r.__dict__ for r in self.analyze_by_session(days)],
            'by_local_regime': [r.__dict__ for r in self.analyze_by_local_regime(days)],
            'by_hour': [r.__dict__ for r in self.analyze_by_hour(days)],
            'by_exit_reason': [r.__dict__ for r in self.analyze_by_exit_reason(days)],
            'optimal_regime_distribution': self.analyze_optimal_regime_distribution(days),
            'suggestions': [s.__dict__ for s in self.generate_suggestions(days)]
        }


# Singleton pour utilisation globale
_correlation_engine = None

def get_correlation_engine() -> CorrelationEngine:
    """Obtenir l'instance singleton du CorrelationEngine"""
    global _correlation_engine
    if _correlation_engine is None:
        _correlation_engine = CorrelationEngine()
    return _correlation_engine
