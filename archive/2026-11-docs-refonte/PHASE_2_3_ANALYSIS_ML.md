# 🏗️ PHASES 2 & 3: ANALYSE & ML
## Corrélations, Dashboard, Optimizer, ML Regime

> **Prérequis Phase 2:** 50+ trades loggés avec contexte
> **Prérequis Phase 3:** 200+ trades loggés

---

# PHASE 2A: ANALYSE CORRÉLATIONS (4h)

## Objectif
Répondre aux questions:
- "US_OPEN est-il vraiment plus rentable?"
- "Quel régime performe le mieux?"
- "Le régime détecté était-il optimal?"

## 2A.1 Script d'Analyse Principal

### Fichier: `verification/analyze_regime_performance.py`

```python
"""
Analyse complète de la performance par Régime × Session.
Génère un rapport avec recommandations.

Usage:
    python verification/analyze_regime_performance.py
"""
import psycopg2
import os
import sys
from pathlib import Path
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )


def analyze_by_session(conn) -> dict:
    """Analyse performance par session"""
    query = """
    SELECT 
        tam.session_market,
        COUNT(*) as trades,
        SUM(CASE WHEN t.pnl_percent > 0 THEN 1 ELSE 0 END) as wins,
        ROUND(100.0 * SUM(CASE WHEN t.pnl_percent > 0 THEN 1 ELSE 0 END) 
              / NULLIF(COUNT(*), 0), 2) as win_rate,
        ROUND(AVG(t.pnl_percent)::numeric, 4) as avg_pnl,
        ROUND(SUM(t.pnl_percent)::numeric, 4) as total_pnl,
        ROUND(AVG(CASE WHEN t.pnl_percent > 0 THEN t.pnl_percent END)::numeric, 4) as avg_win,
        ROUND(AVG(CASE WHEN t.pnl_percent <= 0 THEN ABS(t.pnl_percent) END)::numeric, 4) as avg_loss
    FROM trade_atr_metrics tam
    JOIN trades t ON t.id = tam.trade_id
    WHERE tam.session_market IS NOT NULL
    GROUP BY tam.session_market
    HAVING COUNT(*) >= 3
    ORDER BY win_rate DESC
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    
    return {
        "columns": columns,
        "data": [dict(zip(columns, row)) for row in rows]
    }


def analyze_by_regime(conn) -> dict:
    """Analyse performance par régime"""
    query = """
    SELECT 
        tam.market_volatility_state as regime,
        COUNT(*) as trades,
        ROUND(100.0 * SUM(CASE WHEN t.pnl_percent > 0 THEN 1 ELSE 0 END) 
              / NULLIF(COUNT(*), 0), 2) as win_rate,
        ROUND(AVG(t.pnl_percent)::numeric, 4) as avg_pnl,
        ROUND(SUM(t.pnl_percent)::numeric, 4) as total_pnl
    FROM trade_atr_metrics tam
    JOIN trades t ON t.id = tam.trade_id
    WHERE tam.market_volatility_state IS NOT NULL
    GROUP BY tam.market_volatility_state
    HAVING COUNT(*) >= 3
    ORDER BY win_rate DESC
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    
    return {
        "columns": columns,
        "data": [dict(zip(columns, row)) for row in rows]
    }


def analyze_regime_accuracy(conn) -> dict:
    """Compare régime utilisé vs régime optimal rétrospectif"""
    query = """
    SELECT 
        market_volatility_state as regime_used,
        optimal_regime_retrospective as optimal,
        COUNT(*) as occurrences,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY market_volatility_state), 2) as pct
    FROM trade_atr_metrics
    WHERE optimal_regime_retrospective IS NOT NULL
      AND market_volatility_state IS NOT NULL
    GROUP BY market_volatility_state, optimal_regime_retrospective
    ORDER BY regime_used, occurrences DESC
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    
    # Calculer taux de précision global
    accuracy_query = """
    SELECT 
        ROUND(100.0 * SUM(CASE WHEN market_volatility_state = optimal_regime_retrospective THEN 1 ELSE 0 END)
              / NULLIF(COUNT(*), 0), 2) as accuracy_pct
    FROM trade_atr_metrics
    WHERE optimal_regime_retrospective IS NOT NULL
    """
    
    with conn.cursor() as cur:
        cur.execute(accuracy_query)
        accuracy = cur.fetchone()[0]
    
    return {
        "columns": columns,
        "data": [dict(zip(columns, row)) for row in rows],
        "global_accuracy": accuracy
    }


def analyze_by_hour(conn) -> dict:
    """Analyse performance par heure UTC"""
    query = """
    SELECT 
        tam.hour_utc,
        COUNT(*) as trades,
        ROUND(100.0 * SUM(CASE WHEN t.pnl_percent > 0 THEN 1 ELSE 0 END) 
              / NULLIF(COUNT(*), 0), 2) as win_rate,
        ROUND(AVG(t.pnl_percent)::numeric, 4) as avg_pnl
    FROM trade_atr_metrics tam
    JOIN trades t ON t.id = tam.trade_id
    WHERE tam.hour_utc IS NOT NULL
    GROUP BY tam.hour_utc
    HAVING COUNT(*) >= 2
    ORDER BY tam.hour_utc
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    
    return {
        "columns": columns,
        "data": [dict(zip(columns, row)) for row in rows]
    }


def generate_recommendations(session_data, regime_data, accuracy_data) -> list:
    """Génère des recommandations basées sur l'analyse"""
    recommendations = []
    
    # Best session
    if session_data['data']:
        best = session_data['data'][0]
        if best['win_rate'] >= 55:
            recommendations.append({
                "type": "session",
                "priority": "HIGH",
                "message": f"Session {best['session_market']} surperforme ({best['win_rate']}% WR)",
                "action": "Considérer augmenter l'exposition pendant cette session"
            })
        
        worst = session_data['data'][-1]
        if worst['win_rate'] < 45:
            recommendations.append({
                "type": "session",
                "priority": "HIGH",
                "message": f"Session {worst['session_market']} sous-performe ({worst['win_rate']}% WR)",
                "action": "Considérer réduire ou éviter cette session"
            })
    
    # Regime accuracy
    if accuracy_data['global_accuracy']:
        acc = float(accuracy_data['global_accuracy'])
        if acc < 60:
            recommendations.append({
                "type": "regime",
                "priority": "MEDIUM",
                "message": f"Précision régime: {acc}% (optimal: >70%)",
                "action": "Les seuils de régime pourraient être ajustés"
            })
    
    return recommendations


def main():
    print("=" * 70)
    print("📊 ANALYSE PERFORMANCE: Régime × Session")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    
    conn = get_connection()
    
    # 1. Performance par Session
    print("\n" + "─" * 70)
    print("🕐 PERFORMANCE PAR SESSION")
    print("─" * 70)
    
    session_data = analyze_by_session(conn)
    if session_data['data']:
        print(f"{'Session':<15} {'Trades':>8} {'WR%':>8} {'Avg PnL':>10} {'Total PnL':>12}")
        print("-" * 60)
        for row in session_data['data']:
            print(f"{row['session_market']:<15} {row['trades']:>8} {row['win_rate']:>7}% {row['avg_pnl']:>10} {row['total_pnl']:>12}")
    else:
        print("⏳ Pas assez de données")
    
    # 2. Performance par Régime
    print("\n" + "─" * 70)
    print("🌡️ PERFORMANCE PAR RÉGIME")
    print("─" * 70)
    
    regime_data = analyze_by_regime(conn)
    if regime_data['data']:
        print(f"{'Régime':<15} {'Trades':>8} {'WR%':>8} {'Avg PnL':>10} {'Total PnL':>12}")
        print("-" * 60)
        for row in regime_data['data']:
            print(f"{row['regime']:<15} {row['trades']:>8} {row['win_rate']:>7}% {row['avg_pnl']:>10} {row['total_pnl']:>12}")
    else:
        print("⏳ Pas assez de données")
    
    # 3. Précision Régime
    print("\n" + "─" * 70)
    print("🎯 PRÉCISION DÉTECTION RÉGIME")
    print("─" * 70)
    
    accuracy_data = analyze_regime_accuracy(conn)
    if accuracy_data['global_accuracy']:
        print(f"Précision globale: {accuracy_data['global_accuracy']}%")
        print("\nDétail (régime utilisé → optimal):")
        for row in accuracy_data['data']:
            marker = "✅" if row['regime_used'] == row['optimal'] else "❌"
            print(f"  {marker} {row['regime_used']} → {row['optimal']}: {row['occurrences']} ({row['pct']}%)")
    else:
        print("⏳ Pas assez de données What-If")
    
    # 4. Performance par Heure
    print("\n" + "─" * 70)
    print("⏰ PERFORMANCE PAR HEURE (UTC)")
    print("─" * 70)
    
    hour_data = analyze_by_hour(conn)
    if hour_data['data']:
        best_hours = [h for h in hour_data['data'] if h['win_rate'] and h['win_rate'] >= 55]
        worst_hours = [h for h in hour_data['data'] if h['win_rate'] and h['win_rate'] < 45]
        
        if best_hours:
            print("🟢 Meilleures heures:", ", ".join([f"{h['hour_utc']}h ({h['win_rate']}%)" for h in best_hours[:3]]))
        if worst_hours:
            print("🔴 Pires heures:", ", ".join([f"{h['hour_utc']}h ({h['win_rate']}%)" for h in worst_hours[:3]]))
    
    # 5. Recommandations
    print("\n" + "─" * 70)
    print("💡 RECOMMANDATIONS")
    print("─" * 70)
    
    recommendations = generate_recommendations(session_data, regime_data, accuracy_data)
    if recommendations:
        for rec in recommendations:
            priority_icon = "🔴" if rec['priority'] == "HIGH" else "🟡"
            print(f"\n{priority_icon} [{rec['type'].upper()}] {rec['message']}")
            print(f"   → {rec['action']}")
    else:
        print("✅ Aucune recommandation critique pour le moment")
    
    # Export JSON
    report = {
        "generated_at": datetime.now().isoformat(),
        "session_performance": session_data,
        "regime_performance": regime_data,
        "regime_accuracy": accuracy_data,
        "hourly_performance": hour_data,
        "recommendations": recommendations
    }
    
    report_path = Path(__file__).parent / "regime_analysis_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n📄 Rapport exporté: {report_path}")
    
    conn.close()
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
```

---

# PHASE 2B: DASHBOARD MONITORING (6h)

## 2B.1 Composant Svelte

### Fichier: `frontend/src/lib/components/RegimeAnalyticsDashboard.svelte`

```svelte
<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { Card, CardContent, CardHeader, CardTitle } from '$lib/components/ui/card';
    
    interface SessionPerformance {
        session_market: string;
        trades: number;
        win_rate: number;
        avg_pnl: number;
        total_pnl: number;
    }
    
    interface RegimePerformance {
        regime: string;
        trades: number;
        win_rate: number;
        avg_pnl: number;
    }
    
    let sessionData: SessionPerformance[] = [];
    let regimeData: RegimePerformance[] = [];
    let regimeAccuracy: number = 0;
    let currentSession: string = '';
    let currentRegime: string = '';
    let loading = true;
    let error: string | null = null;
    
    async function fetchData() {
        try {
            const response = await fetch('/api/regime/analytics');
            if (!response.ok) throw new Error('Failed to fetch');
            
            const data = await response.json();
            sessionData = data.session_performance || [];
            regimeData = data.regime_performance || [];
            regimeAccuracy = data.regime_accuracy || 0;
            currentSession = data.current_session || 'UNKNOWN';
            currentRegime = data.current_regime || 'UNKNOWN';
            loading = false;
        } catch (e) {
            error = e.message;
            loading = false;
        }
    }
    
    onMount(() => {
        fetchData();
        const interval = setInterval(fetchData, 60000); // Refresh every minute
        return () => clearInterval(interval);
    });
    
    function getWinRateColor(wr: number): string {
        if (wr >= 55) return 'text-green-500';
        if (wr >= 50) return 'text-yellow-500';
        return 'text-red-500';
    }
    
    function getRegimeIcon(regime: string): string {
        switch(regime) {
            case 'CALME': return '😴';
            case 'NORMAL': return '📊';
            case 'VOLATILE': return '🔥';
            case 'CHOPPY': return '🌊';
            default: return '❓';
        }
    }
</script>

<div class="regime-analytics-dashboard p-4 space-y-4">
    <h2 class="text-xl font-bold">📈 Regime Analytics</h2>
    
    {#if loading}
        <p class="text-gray-500">Chargement...</p>
    {:else if error}
        <p class="text-red-500">Erreur: {error}</p>
    {:else}
        <!-- Current Status -->
        <div class="grid grid-cols-3 gap-4">
            <Card>
                <CardHeader class="pb-2">
                    <CardTitle class="text-sm">Session Actuelle</CardTitle>
                </CardHeader>
                <CardContent>
                    <p class="text-2xl font-bold">{currentSession}</p>
                </CardContent>
            </Card>
            
            <Card>
                <CardHeader class="pb-2">
                    <CardTitle class="text-sm">Régime Actuel</CardTitle>
                </CardHeader>
                <CardContent>
                    <p class="text-2xl font-bold">
                        {getRegimeIcon(currentRegime)} {currentRegime}
                    </p>
                </CardContent>
            </Card>
            
            <Card>
                <CardHeader class="pb-2">
                    <CardTitle class="text-sm">Précision Régime</CardTitle>
                </CardHeader>
                <CardContent>
                    <p class="text-2xl font-bold {getWinRateColor(regimeAccuracy)}">
                        {regimeAccuracy}%
                    </p>
                </CardContent>
            </Card>
        </div>
        
        <!-- Session Performance -->
        <Card>
            <CardHeader>
                <CardTitle>🕐 Performance par Session</CardTitle>
            </CardHeader>
            <CardContent>
                <table class="w-full text-sm">
                    <thead>
                        <tr class="border-b">
                            <th class="text-left py-2">Session</th>
                            <th class="text-right">Trades</th>
                            <th class="text-right">Win Rate</th>
                            <th class="text-right">Avg PnL</th>
                            <th class="text-right">Total PnL</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each sessionData as session}
                            <tr class="border-b hover:bg-gray-50">
                                <td class="py-2 font-medium">{session.session_market}</td>
                                <td class="text-right">{session.trades}</td>
                                <td class="text-right {getWinRateColor(session.win_rate)}">
                                    {session.win_rate}%
                                </td>
                                <td class="text-right">{session.avg_pnl}%</td>
                                <td class="text-right font-medium 
                                    {session.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}">
                                    {session.total_pnl}%
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </CardContent>
        </Card>
        
        <!-- Regime Performance -->
        <Card>
            <CardHeader>
                <CardTitle>🌡️ Performance par Régime</CardTitle>
            </CardHeader>
            <CardContent>
                <div class="grid grid-cols-4 gap-4">
                    {#each regimeData as regime}
                        <div class="p-3 rounded-lg bg-gray-50 text-center">
                            <p class="text-2xl">{getRegimeIcon(regime.regime)}</p>
                            <p class="font-bold">{regime.regime}</p>
                            <p class="text-sm text-gray-500">{regime.trades} trades</p>
                            <p class="text-lg {getWinRateColor(regime.win_rate)}">
                                {regime.win_rate}%
                            </p>
                        </div>
                    {/each}
                </div>
            </CardContent>
        </Card>
    {/if}
</div>
```

## 2B.2 API Endpoint

### Fichier: `api/regime_endpoints.py` (Extension)

```python
@router.get("/analytics")
async def get_regime_analytics():
    """
    Retourne les analytics de performance par régime et session.
    """
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        from core.market_regime_selector import get_regime_selector
        from utils.session_detector import get_current_session
        
        pg_logger = get_pg_datalogger()
        rs = get_regime_selector()
        session = get_current_session()
        
        # Performance par session
        session_perf = pg_logger.execute_query("""
            SELECT session_market, COUNT(*) as trades,
                   ROUND(100.0 * SUM(CASE WHEN t.pnl_percent > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate,
                   ROUND(AVG(t.pnl_percent)::numeric, 4) as avg_pnl,
                   ROUND(SUM(t.pnl_percent)::numeric, 4) as total_pnl
            FROM trade_atr_metrics tam
            JOIN trades t ON t.id = tam.trade_id
            WHERE tam.session_market IS NOT NULL
            GROUP BY session_market
            HAVING COUNT(*) >= 3
            ORDER BY win_rate DESC
        """)
        
        # Performance par régime
        regime_perf = pg_logger.execute_query("""
            SELECT market_volatility_state as regime, COUNT(*) as trades,
                   ROUND(100.0 * SUM(CASE WHEN t.pnl_percent > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate,
                   ROUND(AVG(t.pnl_percent)::numeric, 4) as avg_pnl
            FROM trade_atr_metrics tam
            JOIN trades t ON t.id = tam.trade_id
            WHERE tam.market_volatility_state IS NOT NULL
            GROUP BY market_volatility_state
            HAVING COUNT(*) >= 3
        """)
        
        # Précision régime
        accuracy = pg_logger.execute_query("""
            SELECT ROUND(100.0 * SUM(CASE WHEN market_volatility_state = optimal_regime_retrospective THEN 1 ELSE 0 END)
                  / NULLIF(COUNT(*), 0), 2)
            FROM trade_atr_metrics
            WHERE optimal_regime_retrospective IS NOT NULL
        """)
        
        return {
            "session_performance": session_perf,
            "regime_performance": regime_perf,
            "regime_accuracy": accuracy[0][0] if accuracy else 0,
            "current_session": session['name'],
            "current_regime": rs.current_regime.value if rs.current_regime else "UNKNOWN"
        }
        
    except Exception as e:
        logger.error(f"Erreur analytics régime: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

# PHASE 2C: OPTIMIZER SUGGESTIONS (8h)

## 2C.1 Module Optimizer

### Fichier: `core/analysis/regime_optimizer.py`

```python
"""
Génère des suggestions de paramètres optimaux par contexte (Régime × Session).
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OptimizationSuggestion:
    context: str                    # Ex: "VOLATILE_US_OPEN"
    current_params: Dict[str, float]
    suggested_params: Dict[str, float]
    expected_improvement: float     # % amélioration WR estimée
    confidence: float               # 0-1
    sample_size: int
    reasoning: str


class RegimeOptimizer:
    """
    Analyse les trades par contexte et suggère des paramètres optimaux.
    """
    
    MIN_TRADES_PER_CONTEXT = 20
    MIN_CONFIDENCE = 0.60
    
    def __init__(self):
        self.suggestions: List[OptimizationSuggestion] = []
    
    def analyze_and_suggest(self) -> List[OptimizationSuggestion]:
        """
        Analyse tous les contextes et génère des suggestions.
        """
        from core.postgresql_datalogger import get_pg_datalogger
        
        pg_logger = get_pg_datalogger()
        suggestions = []
        
        # Récupérer trades groupés par contexte
        query = """
        SELECT 
            CONCAT(market_volatility_state, '_', session_market) as context,
            COUNT(*) as trades,
            AVG(param_atr_mult_sl) as avg_sl_mult,
            AVG(param_atr_mult_tp) as avg_tp_mult,
            AVG(CASE WHEN t.pnl_percent > 0 THEN 1.0 ELSE 0.0 END) as win_rate,
            AVG(t.pnl_percent) as avg_pnl,
            -- What-If analysis
            AVG(pnl_if_calme_params) as pnl_calme,
            AVG(pnl_if_normal_params) as pnl_normal,
            AVG(pnl_if_volatile_params) as pnl_volatile
        FROM trade_atr_metrics tam
        JOIN trades t ON t.id = tam.trade_id
        WHERE market_volatility_state IS NOT NULL 
          AND session_market IS NOT NULL
        GROUP BY market_volatility_state, session_market
        HAVING COUNT(*) >= %s
        """
        
        results = pg_logger.execute_query(query, (self.MIN_TRADES_PER_CONTEXT,))
        
        for row in results:
            context = row['context']
            
            # Analyser si un autre régime aurait été meilleur
            best_regime_pnl = max(
                row['pnl_calme'] or -999,
                row['pnl_normal'] or -999,
                row['pnl_volatile'] or -999
            )
            
            current_pnl = row['avg_pnl']
            
            if best_regime_pnl > current_pnl * 1.1:  # 10% amélioration potentielle
                # Identifier quel régime était meilleur
                if best_regime_pnl == row['pnl_volatile']:
                    suggested_regime = 'VOLATILE'
                    suggested_sl = 1.5
                    suggested_tp = 2.5
                elif best_regime_pnl == row['pnl_normal']:
                    suggested_regime = 'NORMAL'
                    suggested_sl = 1.2
                    suggested_tp = 2.2
                else:
                    suggested_regime = 'CALME'
                    suggested_sl = 0.8
                    suggested_tp = 1.8
                
                improvement = ((best_regime_pnl - current_pnl) / abs(current_pnl)) * 100 if current_pnl != 0 else 0
                confidence = min(row['trades'] / 50, 1.0)  # Max confidence at 50 trades
                
                suggestion = OptimizationSuggestion(
                    context=context,
                    current_params={
                        'atr_mult_sl': row['avg_sl_mult'],
                        'atr_mult_tp': row['avg_tp_mult']
                    },
                    suggested_params={
                        'atr_mult_sl': suggested_sl,
                        'atr_mult_tp': suggested_tp,
                        'regime_hint': suggested_regime
                    },
                    expected_improvement=round(improvement, 2),
                    confidence=round(confidence, 2),
                    sample_size=row['trades'],
                    reasoning=f"What-If montre +{improvement:.1f}% PnL avec params {suggested_regime}"
                )
                
                suggestions.append(suggestion)
        
        self.suggestions = suggestions
        return suggestions
    
    def get_suggestion_for_context(
        self, 
        regime: str, 
        session: str
    ) -> Optional[OptimizationSuggestion]:
        """Retourne la suggestion pour un contexte spécifique"""
        context = f"{regime}_{session}"
        for s in self.suggestions:
            if s.context == context and s.confidence >= self.MIN_CONFIDENCE:
                return s
        return None


# Singleton
_optimizer: Optional[RegimeOptimizer] = None

def get_regime_optimizer() -> RegimeOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = RegimeOptimizer()
    return _optimizer
```

---

# PHASE 3: ML REGIME (12h total)

## 3A: ML Regime Training

### Fichier: `core/ml/regime_classifier.py`

```python
"""
ML Classifier pour prédire le régime optimal.
Entraîné sur les données What-If rétrospectives.
"""
import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class MLRegimeClassifier:
    """
    Prédit le régime optimal basé sur les conditions de marché.
    
    Features:
    - ATR 1m, 5m, 15m
    - ADX 1m, 5m
    - Volume ratio
    - Hour UTC
    - Day of week
    - BTC correlation
    """
    
    FEATURE_NAMES = [
        'atr_1m', 'atr_5m',
        'adx_1m', 'adx_5m',
        'volume_ratio',
        'hour_utc', 'day_of_week',
        'regime_stability_minutes'
    ]
    
    REGIME_LABELS = ['CALME', 'NORMAL', 'VOLATILE']
    
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path("models/regime_classifier.pkl")
        self.model = None
        self.is_trained = False
        self.last_trained = None
        self.training_metrics = {}
        
        self._load_model()
    
    def _load_model(self):
        """Charge le modèle si existant"""
        if self.model_path.exists():
            try:
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data['model']
                    self.is_trained = True
                    self.last_trained = data.get('trained_at')
                    self.training_metrics = data.get('metrics', {})
                logger.info(f"✅ ML Regime model chargé: {self.model_path}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur chargement modèle: {e}")
    
    def train(self, min_samples: int = 200) -> Dict:
        """
        Entraîne le modèle sur les données What-If.
        
        Target: optimal_regime_retrospective
        """
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import LabelEncoder
        from core.postgresql_datalogger import get_pg_datalogger
        
        logger.info("🔄 Début entraînement ML Regime...")
        
        # Récupérer données
        pg_logger = get_pg_datalogger()
        query = """
        SELECT 
            entry_atr_pct_1m as atr_1m,
            entry_atr_pct_5m as atr_5m,
            entry_adx as adx_1m,
            entry_adx as adx_5m,
            1.0 as volume_ratio,
            hour_utc,
            day_of_week,
            COALESCE(regime_stability_minutes, 60) as regime_stability_minutes,
            optimal_regime_retrospective as target
        FROM trade_atr_metrics
        WHERE optimal_regime_retrospective IS NOT NULL
          AND entry_atr_pct_1m IS NOT NULL
          AND hour_utc IS NOT NULL
        """
        
        results = pg_logger.execute_query(query)
        
        if len(results) < min_samples:
            return {
                "success": False,
                "error": f"Pas assez de données: {len(results)}/{min_samples}"
            }
        
        # Préparer features et target
        X = np.array([[
            r['atr_1m'], r['atr_5m'],
            r['adx_1m'], r['adx_5m'],
            r['volume_ratio'],
            r['hour_utc'], r['day_of_week'],
            r['regime_stability_minutes']
        ] for r in results])
        
        y_raw = [r['target'] for r in results]
        
        # Encoder labels
        le = LabelEncoder()
        y = le.fit_transform(y_raw)
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train
        self.model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42
        )
        
        self.model.fit(X_train, y_train)
        
        # Evaluate
        train_acc = self.model.score(X_train, y_train)
        test_acc = self.model.score(X_test, y_test)
        cv_scores = cross_val_score(self.model, X, y, cv=5)
        
        self.training_metrics = {
            "train_accuracy": round(train_acc, 4),
            "test_accuracy": round(test_acc, 4),
            "cv_mean": round(cv_scores.mean(), 4),
            "cv_std": round(cv_scores.std(), 4),
            "samples": len(results),
            "class_distribution": dict(zip(
                le.classes_,
                [int(sum(y_raw == c)) for c in le.classes_]
            ))
        }
        
        self.is_trained = True
        self.last_trained = datetime.now()
        self._label_encoder = le
        
        # Sauvegarder
        self._save_model()
        
        logger.info(f"✅ ML Regime entraîné: {self.training_metrics}")
        
        return {
            "success": True,
            "metrics": self.training_metrics
        }
    
    def _save_model(self):
        """Sauvegarde le modèle"""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.model_path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'trained_at': self.last_trained,
                'metrics': self.training_metrics,
                'label_encoder': self._label_encoder
            }, f)
        
        logger.info(f"💾 Modèle sauvegardé: {self.model_path}")
    
    def predict(self, features: Dict[str, float]) -> Tuple[str, float]:
        """
        Prédit le régime optimal.
        
        Returns:
            Tuple (regime_predicted, confidence)
        """
        if not self.is_trained:
            return None, 0.0
        
        X = np.array([[
            features.get('atr_1m', 0.3),
            features.get('atr_5m', 0.3),
            features.get('adx_1m', 25),
            features.get('adx_5m', 25),
            features.get('volume_ratio', 1.0),
            features.get('hour_utc', 12),
            features.get('day_of_week', 2),
            features.get('regime_stability_minutes', 60)
        ]])
        
        # Prédiction
        pred_idx = self.model.predict(X)[0]
        proba = self.model.predict_proba(X)[0]
        confidence = float(max(proba))
        
        regime = self._label_encoder.inverse_transform([pred_idx])[0]
        
        return regime, confidence


# Singleton
_ml_regime: Optional[MLRegimeClassifier] = None

def get_ml_regime_classifier() -> MLRegimeClassifier:
    global _ml_regime
    if _ml_regime is None:
        _ml_regime = MLRegimeClassifier()
    return _ml_regime
```

---

## 3B: Intégration GB Features

### Modification `ml/feature_loader.py`

```python
# Ajouter ces features à la liste des features ML

REGIME_FEATURES = [
    'regime_current_encoded',      # 0=CALME, 1=NORMAL, 2=VOLATILE
    'session_market_encoded',      # Encodé
    'regime_stability_minutes',
    'session_atr_multiplier',
    'regime_ml_confidence',        # Si ML actif
]

def add_regime_features(df, trade_data):
    """
    Ajoute les features de régime au DataFrame.
    """
    # Mapping régime
    regime_map = {'CALME': 0, 'NORMAL': 1, 'VOLATILE': 2, 'CHOPPY': 3}
    session_map = {'ASIA': 0, 'EUROPE_OPEN': 1, 'EUROPE': 2, 'US_PREMARKET': 3,
                   'US_OPEN': 4, 'US_SESSION': 5, 'US_CLOSE': 6, 'NIGHT': 7}
    
    df['regime_current_encoded'] = regime_map.get(
        trade_data.get('market_volatility_state'), 1
    )
    df['session_market_encoded'] = session_map.get(
        trade_data.get('session_market'), 2
    )
    df['regime_stability_minutes'] = trade_data.get('regime_stability_minutes', 60)
    df['session_atr_multiplier'] = trade_data.get('session_atr_multiplier', 1.0)
    df['regime_ml_confidence'] = trade_data.get('regime_ml_confidence', 0.5)
    
    return df
```

---

## CHECKLIST PHASES 2 & 3

### Phase 2A (50+ trades requis)
```
[ ] Script analyze_regime_performance.py créé
[ ] Exécution sans erreur
[ ] Rapport JSON généré
[ ] Recommandations identifiées
```

### Phase 2B (Dashboard)
```
[ ] Composant RegimeAnalyticsDashboard.svelte créé
[ ] Endpoint /api/regime/analytics créé
[ ] Intégration dans le layout principal
[ ] Refresh automatique fonctionnel
```

### Phase 2C (Optimizer)
```
[ ] Module regime_optimizer.py créé
[ ] Suggestions générées pour contextes avec 20+ trades
[ ] API endpoint pour récupérer suggestions
```

### Phase 3A (200+ trades requis)
```
[ ] Module regime_classifier.py créé
[ ] Entraînement fonctionnel
[ ] Accuracy > 60%
[ ] Sauvegarde/chargement modèle
```

### Phase 3B (GB Integration)
```
[ ] Features régime ajoutées au feature_loader
[ ] Ré-entraînement GB avec nouvelles features
[ ] Amélioration accuracy mesurable
```

---

## TIMELINE ESTIMÉE

```
Semaine 1: Phase 0 + 1A (infrastructure + logging)
           ⏸️ Accumulation données

Semaine 2: Phase 1B + 1C (Régime V2 + What-If)
           ⏸️ Accumulation 50 trades

Semaine 3: Phase 2A + 2B (Analyse + Dashboard)

Semaine 4: Phase 2C (Optimizer)
           ⏸️ Accumulation 200 trades

Semaine 5-6: Phase 3 (ML Regime + GB Integration)
```
