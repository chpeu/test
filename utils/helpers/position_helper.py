"""
🔥 SPRINT 1.5: PositionHelper

Patterns 8 & 15 - Position Type Checking + to_dict()

Helper pour normalisation et conversion de positions.

Avant (main.py, lignes 983-1019):
```python
if isinstance(position, str):
    position_dict = json.loads(position)
    # Create proxy
    class PositionProxy:
        def __init__(self, d):
            self.symbol = d.get('symbol', '')
            # ... 20+ lignes
    position = PositionProxy(position_dict)
elif isinstance(position, dict):
    position = PositionProxy(position)
```

Après:
```python
position = PositionHelper.normalize_position(position)
position_dict = PositionHelper.to_dict(position)
```

Impact: -60 à -130 lignes de code dupliqué
"""

import json
import logging
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


class PositionProxy:
    """
    Proxy object pour représenter une position depuis dict

    Permet d'utiliser position.symbol au lieu de position['symbol']
    """

    def __init__(self, data: Dict[str, Any]):
        self.symbol = data.get('symbol', '')
        self.side = data.get('side', '')
        self.direction = data.get('direction', self.side)  # Fallback
        self.entry = data.get('entry', 0.0)
        self.quantity = data.get('quantity', 0.0)
        self.leverage = data.get('leverage', 1)

        # TP/SL
        self.take_profit = data.get('take_profit') or data.get('takeProfit')
        self.stop_loss = data.get('stop_loss') or data.get('stopLoss')

        # Timestamps
        self.opened_at = data.get('opened_at') or data.get('openedAt')
        self.closed_at = data.get('closed_at') or data.get('closedAt')

        # PnL
        self.pnl = data.get('pnl', 0.0)
        self.pnl_percent = data.get('pnl_percent') or data.get('pnlPercent', 0.0)

        # Status
        self.status = data.get('status', 'OPEN')

        # Raison
        self.reason = data.get('reason', '')
        self.close_reason = data.get('close_reason') or data.get('closeReason', '')

        # Extra data
        self._raw_data = data

    def to_dict(self) -> Dict[str, Any]:
        """Convertir en dict"""
        return self._raw_data


class PositionHelper:
    """Helper pour manipulation de positions"""

    @staticmethod
    def normalize_position(position: Union[str, dict, object]) -> object:
        """
        Normaliser position vers format object standard

        Args:
            position: Position (str JSON, dict, ou object Position/PositionProxy)

        Returns:
            Position object (Position ou PositionProxy)

        Exemple:
        ```python
        # Supporte tous formats
        position = PositionHelper.normalize_position('{"symbol": "BTC/USDT", ...}')
        position = PositionHelper.normalize_position({"symbol": "BTC/USDT", ...})
        position = PositionHelper.normalize_position(position_object)

        # Utilisation uniforme
        print(position.symbol)  # Fonctionne pour tous
        ```
        """
        # Déjà un object avec attribut 'entry' → retour direct
        if hasattr(position, 'entry'):
            return position

        # String JSON → parse
        if isinstance(position, str):
            try:
                position = json.loads(position)
            except json.JSONDecodeError as e:
                logger.error(f"❌ Erreur parse JSON position: {e}")
                raise ValueError(f"Invalid position JSON: {e}")

        # Dict → convert to PositionProxy
        if isinstance(position, dict):
            return PositionProxy(position)

        # Type inconnu
        raise ValueError(f"Invalid position type: {type(position)}")

    @staticmethod
    def to_dict(position: Union[str, dict, object]) -> Dict[str, Any]:
        """
        Convertir position vers dict

        Args:
            position: Position (tous formats)

        Returns:
            Position dict

        Exemple:
        ```python
        position_dict = PositionHelper.to_dict(position)
        ```
        """
        # Déjà dict → retour direct
        if isinstance(position, dict):
            return position

        # String JSON → parse
        if isinstance(position, str):
            try:
                return json.loads(position)
            except json.JSONDecodeError as e:
                logger.error(f"❌ Erreur parse JSON position: {e}")
                return {}

        # Object avec méthode to_dict()
        if hasattr(position, 'to_dict'):
            return position.to_dict()

        # Object avec __dict__
        if hasattr(position, '__dict__'):
            return {
                k: v for k, v in position.__dict__.items()
                if not k.startswith('_')
            }

        logger.warning(f"⚠️ Impossible de convertir position en dict: {type(position)}")
        return {}

    @staticmethod
    def extract_key_fields(position: Union[str, dict, object]) -> Dict[str, Any]:
        """
        Extraire champs clés d'une position

        Args:
            position: Position (tous formats)

        Returns:
            Dict avec champs essentiels (symbol, side, entry, etc.)
        """
        position_dict = PositionHelper.to_dict(position)

        return {
            'symbol': position_dict.get('symbol', ''),
            'side': position_dict.get('side') or position_dict.get('direction', ''),
            'entry': float(position_dict.get('entry', 0)),
            'quantity': float(position_dict.get('quantity', 0)),
            'leverage': int(position_dict.get('leverage', 1)),
            'take_profit': position_dict.get('take_profit') or position_dict.get('takeProfit'),
            'stop_loss': position_dict.get('stop_loss') or position_dict.get('stopLoss'),
        }

    @staticmethod
    def calculate_pnl(
        position: Union[str, dict, object],
        current_price: float,
        include_fees: bool = True,
        fee_rate: float = 0.0006
    ) -> Dict[str, float]:
        """
        Calculer PnL d'une position

        Args:
            position: Position (tous formats)
            current_price: Prix actuel
            include_fees: Inclure fees dans calcul
            fee_rate: Taux de fees (0.06% par défaut)

        Returns:
            Dict avec:
            - pnl_pct: PnL en %
            - pnl_usdt: PnL en USDT
            - gross_pnl_pct: PnL brut %
            - net_pnl_pct: PnL net % (après fees)
        """
        position_dict = PositionHelper.to_dict(position)

        entry = float(position_dict.get('entry', 0))
        quantity = float(position_dict.get('quantity', 0))
        side = position_dict.get('side') or position_dict.get('direction', 'LONG')
        leverage = int(position_dict.get('leverage', 1))

        if entry == 0 or current_price == 0:
            return {
                'pnl_pct': 0.0,
                'pnl_usdt': 0.0,
                'gross_pnl_pct': 0.0,
                'net_pnl_pct': 0.0,
            }

        # Calcul PnL brut
        if side.upper() == 'LONG':
            gross_pnl_pct = ((current_price - entry) / entry) * 100 * leverage
        else:  # SHORT
            gross_pnl_pct = ((entry - current_price) / entry) * 100 * leverage

        # PnL en USDT
        position_size_usdt = entry * quantity
        gross_pnl_usdt = position_size_usdt * (gross_pnl_pct / 100)

        # Fees (entrée + sortie)
        if include_fees:
            total_fees_pct = fee_rate * 2 * 100 * leverage  # Fees en %
            net_pnl_pct = gross_pnl_pct - total_fees_pct
            fees_usdt = position_size_usdt * fee_rate * 2
            net_pnl_usdt = gross_pnl_usdt - fees_usdt
        else:
            net_pnl_pct = gross_pnl_pct
            net_pnl_usdt = gross_pnl_usdt

        return {
            'pnl_pct': net_pnl_pct,  # Alias pour net
            'pnl_usdt': net_pnl_usdt,
            'gross_pnl_pct': gross_pnl_pct,
            'net_pnl_pct': net_pnl_pct,
        }

    @staticmethod
    def is_long(position: Union[str, dict, object]) -> bool:
        """
        Vérifier si position est LONG

        Args:
            position: Position (tous formats)

        Returns:
            True si LONG
        """
        position_dict = PositionHelper.to_dict(position)
        side = (position_dict.get('side') or position_dict.get('direction', '')).upper()
        return side == 'LONG'

    @staticmethod
    def is_short(position: Union[str, dict, object]) -> bool:
        """
        Vérifier si position est SHORT

        Args:
            position: Position (tous formats)

        Returns:
            True si SHORT
        """
        return not PositionHelper.is_long(position)

    @staticmethod
    def format_position_summary(position: Union[str, dict, object]) -> str:
        """
        Formater résumé position pour affichage

        Args:
            position: Position (tous formats)

        Returns:
            String formaté

        Exemple:
        ```python
        summary = PositionHelper.format_position_summary(position)
        print(summary)
        # Output: "BTC/USDT LONG @50000.0 (x10) | TP: 51000.0 | SL: 49000.0"
        ```
        """
        fields = PositionHelper.extract_key_fields(position)

        symbol = fields['symbol']
        side = fields['side']
        entry = fields['entry']
        leverage = fields['leverage']
        tp = fields['take_profit']
        sl = fields['stop_loss']

        summary = f"{symbol} {side} @{entry:.2f}"

        if leverage > 1:
            summary += f" (x{leverage})"

        if tp:
            summary += f" | TP: {tp:.2f}"

        if sl:
            summary += f" | SL: {sl:.2f}"

        return summary
