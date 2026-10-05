"""
🔥 SPRINT 1.5: StatsHelper

Pattern 13 - Stats Calculation (4+ occurrences)

Helper pour calcul de statistiques trading depuis liste de trades.

Avant (main.py, lignes 1468-1479):
```python
trades = analytics_db.get_trades(limit=10000)
if trades:
    total = len(trades)
    wins = sum(1 for t in trades if t.get('pnl_usdt', 0) > 0)
    losses = total - wins
    winrate = (wins / total * 100) if total > 0 else 0.0
    stats_dict = {
        'total_trades': total,
        'wins': wins,
        'losses': losses,
        'winrate': winrate
    }
```

Après:
```python
trades = analytics_db.get_trades(limit=10000)
stats_dict = StatsHelper.calculate_stats_from_trades(trades)
```

Impact: -40 à -60 lignes de code dupliqué
"""

from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class StatsHelper:
    """Helper pour calcul de statistiques trading"""

    @staticmethod
    def calculate_stats_from_trades(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculer statistiques depuis liste de trades

        Args:
            trades: Liste de trades (dicts)

        Returns:
            Dict avec statistiques:
            - total_trades
            - wins
            - losses
            - winrate
            - total_pnl_usdt
            - avg_pnl_pct
            - best_trade
            - worst_trade

        Exemple:
        ```python
        stats = StatsHelper.calculate_stats_from_trades(trades)
        print(f"Winrate: {stats['winrate']:.1f}%")
        ```
        """
        if not trades:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'winrate': 0.0,
                'total_pnl_usdt': 0.0,
                'avg_pnl_pct': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0,
            }

        total = len(trades)

        # Compter wins/losses
        # Supporter 2 formats: pnl_usdt et netPnlUSDT
        wins = sum(
            1 for t in trades
            if t.get('pnl_usdt', 0) > 0 or t.get('netPnlUSDT', 0) > 0 or t.get('net_pnl_usdt', 0) > 0
        )
        losses = total - wins

        # Winrate
        winrate = (wins / total * 100) if total > 0 else 0.0

        # PnL total en USDT
        total_pnl_usdt = sum(
            t.get('pnl_usdt', 0) or t.get('netPnlUSDT', 0) or t.get('net_pnl_usdt', 0)
            for t in trades
        )

        # PnL moyen en %
        pnl_pcts = [
            t.get('pnl_pct', 0) or t.get('netPnlPct', 0) or t.get('net_pnl_pct', 0)
            for t in trades
        ]
        avg_pnl_pct = sum(pnl_pcts) / total if total > 0 else 0.0

        # Meilleur et pire trade
        best_trade = max(pnl_pcts) if pnl_pcts else 0.0
        worst_trade = min(pnl_pcts) if pnl_pcts else 0.0

        return {
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'winrate': winrate,
            'total_pnl_usdt': total_pnl_usdt,
            'avg_pnl_pct': avg_pnl_pct,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
        }

    @staticmethod
    def calculate_sharpe_ratio(
        trades: List[Dict[str, Any]],
        risk_free_rate: float = 0.0
    ) -> float:
        """
        Calculer Sharpe Ratio depuis liste de trades

        Args:
            trades: Liste de trades
            risk_free_rate: Taux sans risque (annualisé)

        Returns:
            Sharpe Ratio

        Formule:
        Sharpe = (Rendement Moyen - Taux Sans Risque) / Écart-Type
        """
        if not trades:
            return 0.0

        # Rendements en %
        returns = [
            t.get('pnl_pct', 0) or t.get('netPnlPct', 0) or t.get('net_pnl_pct', 0)
            for t in trades
        ]

        if not returns:
            return 0.0

        # Rendement moyen
        avg_return = sum(returns) / len(returns)

        # Écart-type
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        # Sharpe ratio
        sharpe = (avg_return - risk_free_rate) / std_dev

        return sharpe

    @staticmethod
    def calculate_max_drawdown(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculer Maximum Drawdown depuis liste de trades

        Args:
            trades: Liste de trades (chronologique)

        Returns:
            Dict avec:
            - max_drawdown_pct: DD maximum en %
            - max_drawdown_usdt: DD maximum en USDT
            - recovery_time: Nombre de trades pour récupérer
        """
        if not trades:
            return {
                'max_drawdown_pct': 0.0,
                'max_drawdown_usdt': 0.0,
                'recovery_time': 0,
            }

        # Capital cumulé
        cumulative_pnl = 0.0
        peak = 0.0
        max_dd = 0.0
        max_dd_usdt = 0.0
        recovery_time = 0
        current_dd_time = 0

        for trade in trades:
            pnl = trade.get('pnl_usdt', 0) or trade.get('netPnlUSDT', 0) or trade.get('net_pnl_usdt', 0)
            cumulative_pnl += pnl

            # Nouveau peak
            if cumulative_pnl > peak:
                peak = cumulative_pnl
                current_dd_time = 0
            else:
                # En drawdown
                current_dd = peak - cumulative_pnl
                current_dd_pct = (current_dd / peak * 100) if peak > 0 else 0

                if current_dd_pct > max_dd:
                    max_dd = current_dd_pct
                    max_dd_usdt = current_dd
                    recovery_time = current_dd_time

                current_dd_time += 1

        return {
            'max_drawdown_pct': max_dd,
            'max_drawdown_usdt': max_dd_usdt,
            'recovery_time': recovery_time,
        }

    @staticmethod
    def calculate_profit_factor(trades: List[Dict[str, Any]]) -> float:
        """
        Calculer Profit Factor

        Args:
            trades: Liste de trades

        Returns:
            Profit Factor (Gains Totaux / Pertes Totales)
        """
        if not trades:
            return 0.0

        gross_profit = 0.0
        gross_loss = 0.0

        for trade in trades:
            pnl = trade.get('pnl_usdt', 0) or trade.get('netPnlUSDT', 0) or trade.get('net_pnl_usdt', 0)

            if pnl > 0:
                gross_profit += pnl
            else:
                gross_loss += abs(pnl)

        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0

        return gross_profit / gross_loss

    @staticmethod
    def format_stats_for_display(stats: Dict[str, Any]) -> str:
        """
        Formater statistiques pour affichage

        Args:
            stats: Dict stats (depuis calculate_stats_from_trades)

        Returns:
            String formaté

        Exemple:
        ```python
        stats = StatsHelper.calculate_stats_from_trades(trades)
        print(StatsHelper.format_stats_for_display(stats))
        ```
        """
        return (
            f"📊 Stats Trading:\n"
            f"  Total Trades: {stats['total_trades']}\n"
            f"  Wins: {stats['wins']} | Losses: {stats['losses']}\n"
            f"  Winrate: {stats['winrate']:.1f}%\n"
            f"  PnL Total: {stats['total_pnl_usdt']:.2f} USDT\n"
            f"  PnL Moyen: {stats['avg_pnl_pct']:.2f}%\n"
            f"  Meilleur Trade: {stats['best_trade']:.2f}%\n"
            f"  Pire Trade: {stats['worst_trade']:.2f}%"
        )

    @staticmethod
    def get_trade_pnl(trade: Dict[str, Any], field: str = 'usdt') -> float:
        """
        Extraire PnL d'un trade (supporte plusieurs formats)

        Args:
            trade: Dict trade
            field: 'usdt' ou 'pct'

        Returns:
            PnL value
        """
        if field == 'usdt':
            return (
                trade.get('pnl_usdt', 0) or
                trade.get('netPnlUSDT', 0) or
                trade.get('net_pnl_usdt', 0) or
                0.0
            )
        else:  # pct
            return (
                trade.get('pnl_pct', 0) or
                trade.get('netPnlPct', 0) or
                trade.get('net_pnl_pct', 0) or
                0.0
            )
