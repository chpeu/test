# 📈 Backtesting Visualizer - Trade Cursor v7.0

Tester et visualiser les stratégies de trading sur données historiques.

---

## 📋 Vue d'ensemble

Le **Backtesting Visualizer** permet de:
- Tester des stratégies sur données historiques
- Visualiser les résultats avec charts interactifs
- Comparer plusieurs stratégies
- Optimiser les paramètres
- Générer des rapports détaillés

---

## 🏗️ Architecture

### Backend

```
backend/
├── backtester/
│   ├── engine.py              # Moteur de backtesting
│   ├── data_loader.py         # Chargement données historiques
│   ├── strategy.py            # Classe stratégie de base
│   ├── metrics.py             # Calcul des métriques
│   └── optimizer.py           # Optimisation paramètres
├── data/
│   └── historical/
│       ├── BTC_USDT_1h.csv
│       ├── ETH_USDT_1h.csv
│       └── ...
```

### Frontend

```
frontend/src/lib/
├── stores/
│   ├── backtest.js           # Store résultats backtests
│   └── strategies.js         # Store stratégies
├── components/
│   ├── BacktestPanel.svelte      # Interface de configuration
│   ├── BacktestResults.svelte    # Résultats détaillés
│   ├── EquityCurve.svelte        # Courbe d'équité
│   ├── DrawdownChart.svelte      # Chart drawdowns
│   └── TradesTimeline.svelte     # Timeline des trades
```

---

## 🔧 Implémentation Backend

### 1. Moteur de Backtesting (`engine.py`)

```python
# backend/backtester/engine.py

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np

@dataclass
class Trade:
    """Représente un trade backtest"""
    symbol: str
    direction: str  # 'LONG' ou 'SHORT'
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    size: float = 100.0
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    exit_reason: Optional[str] = None

@dataclass
class BacktestResult:
    """Résultats d'un backtest"""
    strategy_name: str
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_pnl_percent: float
    max_drawdown: float
    max_drawdown_percent: float
    sharpe_ratio: float
    profit_factor: float
    trades: List[Trade]
    equity_curve: pd.DataFrame

class BacktestEngine:
    """Moteur de backtesting"""

    def __init__(
        self,
        data: pd.DataFrame,
        initial_capital: float = 10000.0,
        commission: float = 0.001  # 0.1%
    ):
        self.data = data
        self.initial_capital = initial_capital
        self.commission = commission
        self.capital = initial_capital
        self.trades: List[Trade] = []
        self.equity = [initial_capital]
        self.current_position: Optional[Trade] = None

    def run_strategy(self, strategy) -> BacktestResult:
        """Exécuter une stratégie sur les données"""

        for i in range(len(self.data)):
            row = self.data.iloc[i]

            # Générer signal de la stratégie
            signal = strategy.generate_signal(self.data[:i+1])

            # Gérer position existante
            if self.current_position:
                self._check_exit(row, strategy)

            # Ouvrir nouvelle position si signal
            elif signal in ['LONG', 'SHORT']:
                self._open_position(row, signal, strategy)

            # Update equity
            self._update_equity(row)

        # Fermer position ouverte à la fin
        if self.current_position:
            last_row = self.data.iloc[-1]
            self._close_position(last_row, 'END_OF_DATA')

        # Calculer métriques
        return self._calculate_metrics(strategy.name)

    def _open_position(self, row: pd.Series, direction: str, strategy):
        """Ouvrir une position"""

        entry_price = row['close']

        # Appliquer commission
        commission_cost = self.capital * self.commission
        self.capital -= commission_cost

        # Calculer taille position (100% du capital pour simplifier)
        position_size = self.capital

        self.current_position = Trade(
            symbol=row.get('symbol', 'UNKNOWN'),
            direction=direction,
            entry_time=row['timestamp'],
            entry_price=entry_price,
            size=position_size
        )

    def _check_exit(self, row: pd.Series, strategy):
        """Vérifier si sortie de position"""

        pos = self.current_position
        current_price = row['close']

        # Calculer PnL actuel
        if pos.direction == 'LONG':
            pnl_percent = ((current_price - pos.entry_price) / pos.entry_price) * 100
        else:  # SHORT
            pnl_percent = ((pos.entry_price - current_price) / pos.entry_price) * 100

        # Vérifier stop loss
        if pnl_percent <= -strategy.stop_loss_percent:
            self._close_position(row, 'STOP_LOSS')

        # Vérifier take profit
        elif pnl_percent >= strategy.take_profit_percent:
            self._close_position(row, 'TAKE_PROFIT')

        # Vérifier signal inverse
        elif strategy.generate_signal(self.data[:len(self.data)]) == ('SHORT' if pos.direction == 'LONG' else 'LONG'):
            self._close_position(row, 'SIGNAL_REVERSE')

    def _close_position(self, row: pd.Series, reason: str):
        """Fermer la position courante"""

        pos = self.current_position
        exit_price = row['close']

        # Calculer PnL
        if pos.direction == 'LONG':
            pnl = ((exit_price - pos.entry_price) / pos.entry_price) * pos.size
        else:  # SHORT
            pnl = ((pos.entry_price - exit_price) / pos.entry_price) * pos.size

        # Appliquer commission
        commission_cost = pos.size * self.commission
        pnl -= commission_cost

        # Update capital
        self.capital += pos.size + pnl

        # Compléter le trade
        pos.exit_time = row['timestamp']
        pos.exit_price = exit_price
        pos.pnl = pnl
        pos.pnl_percent = (pnl / pos.size) * 100
        pos.exit_reason = reason

        # Ajouter aux trades
        self.trades.append(pos)
        self.current_position = None

    def _update_equity(self, row: pd.Series):
        """Mettre à jour la courbe d'équité"""

        current_equity = self.capital

        # Ajouter PnL non réalisé si position ouverte
        if self.current_position:
            pos = self.current_position
            current_price = row['close']

            if pos.direction == 'LONG':
                unrealized_pnl = ((current_price - pos.entry_price) / pos.entry_price) * pos.size
            else:
                unrealized_pnl = ((pos.entry_price - current_price) / pos.entry_price) * pos.size

            current_equity += unrealized_pnl

        self.equity.append(current_equity)

    def _calculate_metrics(self, strategy_name: str) -> BacktestResult:
        """Calculer les métriques de performance"""

        if not self.trades:
            return BacktestResult(
                strategy_name=strategy_name,
                symbol=self.data.iloc[0].get('symbol', 'UNKNOWN'),
                start_date=self.data.iloc[0]['timestamp'],
                end_date=self.data.iloc[-1]['timestamp'],
                initial_capital=self.initial_capital,
                final_capital=self.capital,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                total_pnl=0,
                total_pnl_percent=0,
                max_drawdown=0,
                max_drawdown_percent=0,
                sharpe_ratio=0,
                profit_factor=0,
                trades=[],
                equity_curve=pd.DataFrame()
            )

        # Winning/Losing trades
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        # PnL total
        total_pnl = sum(t.pnl for t in self.trades)
        total_pnl_percent = (total_pnl / self.initial_capital) * 100

        # Win rate
        win_rate = (len(winning_trades) / len(self.trades)) * 100

        # Max drawdown
        equity_series = pd.Series(self.equity)
        rolling_max = equity_series.cummax()
        drawdown = equity_series - rolling_max
        max_drawdown = abs(drawdown.min())
        max_drawdown_percent = (max_drawdown / rolling_max.max()) * 100

        # Sharpe ratio
        returns = equity_series.pct_change().dropna()
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0

        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Equity curve DataFrame
        equity_df = pd.DataFrame({
            'timestamp': self.data['timestamp'],
            'equity': self.equity[:-1]  # Remove last (incomplete)
        })

        return BacktestResult(
            strategy_name=strategy_name,
            symbol=self.data.iloc[0].get('symbol', 'UNKNOWN'),
            start_date=self.data.iloc[0]['timestamp'],
            end_date=self.data.iloc[-1]['timestamp'],
            initial_capital=self.initial_capital,
            final_capital=self.capital,
            total_trades=len(self.trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            max_drawdown=max_drawdown,
            max_drawdown_percent=max_drawdown_percent,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            trades=self.trades,
            equity_curve=equity_df
        )
```

### 2. Stratégie de Base (`strategy.py`)

```python
# backend/backtester/strategy.py

from abc import ABC, abstractmethod
import pandas as pd

class Strategy(ABC):
    """Classe de base pour les stratégies"""

    def __init__(
        self,
        name: str,
        stop_loss_percent: float = 2.0,
        take_profit_percent: float = 4.0
    ):
        self.name = name
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> str:
        """Générer signal: 'LONG', 'SHORT', ou 'HOLD'"""
        pass

# Exemple: Stratégie MA Crossover
class MACrossoverStrategy(Strategy):
    """Stratégie de croisement de moyennes mobiles"""

    def __init__(
        self,
        fast_period: int = 9,
        slow_period: int = 21,
        **kwargs
    ):
        super().__init__(name='MA Crossover', **kwargs)
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signal(self, data: pd.DataFrame) -> str:
        if len(data) < self.slow_period:
            return 'HOLD'

        # Calculer MAs
        fast_ma = data['close'].rolling(window=self.fast_period).mean()
        slow_ma = data['close'].rolling(window=self.slow_period).mean()

        # Signal de croisement
        if fast_ma.iloc[-1] > slow_ma.iloc[-1] and fast_ma.iloc[-2] <= slow_ma.iloc[-2]:
            return 'LONG'
        elif fast_ma.iloc[-1] < slow_ma.iloc[-1] and fast_ma.iloc[-2] >= slow_ma.iloc[-2]:
            return 'SHORT'

        return 'HOLD'
```

### 3. API Endpoints (`main.py`)

```python
# backend/main.py (ajouter ces endpoints)

from backtester.engine import BacktestEngine
from backtester.strategy import MACrossoverStrategy
from backtester.data_loader import load_historical_data

@app.post("/api/backtest/run")
async def run_backtest(request: Request):
    """Lancer un backtest"""
    params = await request.json()

    # Charger données
    data = load_historical_data(
        symbol=params['symbol'],
        timeframe=params['timeframe'],
        start=params['start_date'],
        end=params['end_date']
    )

    # Créer stratégie
    strategy = MACrossoverStrategy(
        fast_period=params.get('fast_period', 9),
        slow_period=params.get('slow_period', 21),
        stop_loss_percent=params.get('stop_loss', 2.0),
        take_profit_percent=params.get('take_profit', 4.0)
    )

    # Lancer backtest
    engine = BacktestEngine(
        data=data,
        initial_capital=params.get('initial_capital', 10000.0)
    )

    result = engine.run_strategy(strategy)

    # Retourner résultats
    return {
        "status": "success",
        "result": {
            "strategy_name": result.strategy_name,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "total_pnl": result.total_pnl,
            "total_pnl_percent": result.total_pnl_percent,
            "max_drawdown_percent": result.max_drawdown_percent,
            "sharpe_ratio": result.sharpe_ratio,
            "profit_factor": result.profit_factor,
            "trades": [
                {
                    "symbol": t.symbol,
                    "direction": t.direction,
                    "entry_time": t.entry_time.isoformat(),
                    "entry_price": t.entry_price,
                    "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                    "exit_price": t.exit_price,
                    "pnl": t.pnl,
                    "pnl_percent": t.pnl_percent,
                    "exit_reason": t.exit_reason
                }
                for t in result.trades
            ],
            "equity_curve": result.equity_curve.to_dict('records')
        }
    }
```

---

## 🎨 Implémentation Frontend

### 1. Store Backtest (`backtest.js`)

```javascript
// frontend/src/lib/stores/backtest.js

import { writable } from 'svelte/store';

export const backtestResults = writable(null);
export const backtestRunning = writable(false);

export async function runBacktest(params) {
	backtestRunning.set(true);

	try {
		const res = await fetch('/api/backtest/run', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(params)
		});

		const data = await res.json();
		backtestResults.set(data.result);

		return data.result;
	} catch (error) {
		console.error('Backtest error:', error);
		throw error;
	} finally {
		backtestRunning.set(false);
	}
}
```

### 2. Equity Curve Chart (`EquityCurve.svelte`)

```svelte
<!-- frontend/src/lib/components/EquityCurve.svelte -->

<script>
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';
	import { backtestResults } from '$lib/stores/backtest';

	let canvas;
	let chart;

	onMount(() => {
		const unsubscribe = backtestResults.subscribe((results) => {
			if (!results || !results.equity_curve) return;

			if (chart) chart.destroy();

			chart = new Chart(canvas, {
				type: 'line',
				data: {
					labels: results.equity_curve.map(d => d.timestamp),
					datasets: [{
						label: 'Equity',
						data: results.equity_curve.map(d => d.equity),
						borderColor: '#00ff88',
						backgroundColor: 'rgba(0, 255, 136, 0.1)',
						fill: true,
						tension: 0.4
					}]
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: {
						title: {
							display: true,
							text: 'Equity Curve',
							color: '#00ff88'
						}
					},
					scales: {
						y: {
							beginAtZero: false,
							ticks: { color: '#888' },
							grid: { color: 'rgba(255, 255, 255, 0.1)' }
						},
						x: {
							ticks: { color: '#888' },
							grid: { color: 'rgba(255, 255, 255, 0.1)' }
						}
					}
				}
			});
		});

		return () => {
			if (chart) chart.destroy();
			unsubscribe();
		};
	});
</script>

<div class="chart-container">
	<canvas bind:this={canvas}></canvas>
</div>
```

---

## 🚀 Utilisation

### 1. Lancer un backtest via API

```bash
curl -X POST http://localhost:5000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "start_date": "2024-01-01",
    "end_date": "2024-03-01",
    "initial_capital": 10000,
    "fast_period": 9,
    "slow_period": 21,
    "stop_loss": 2.0,
    "take_profit": 4.0
  }'
```

### 2. Interface Frontend

1. Ouvrir BacktestPanel
2. Sélectionner symbole, timeframe, dates
3. Configurer paramètres stratégie
4. Cliquer "Run Backtest"
5. Visualiser résultats (equity curve, drawdown, trades)

---

## 📊 Métriques Calculées

- **Win Rate**: % de trades gagnants
- **Total PnL**: Profit/Loss total en USDT et %
- **Max Drawdown**: Plus grande perte depuis le pic
- **Sharpe Ratio**: Rendement ajusté au risque
- **Profit Factor**: Ratio profits/pertes

---

## 🎯 Roadmap Implementation

1. **Phase 1**: Backend engine + metrics (3-4 jours)
2. **Phase 2**: Data loader + stratégies (2 jours)
3. **Phase 3**: Frontend charts + UI (2-3 jours)
4. **Phase 4**: Optimisation paramètres (2 jours)

**Total: ~1-2 semaines** pour feature complète
