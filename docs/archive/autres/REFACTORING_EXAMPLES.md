# 🛠️ Exemples Concrets de Refactorisation

## Exemple 1: Extraire VolumeAnalyzer de analyzer.py

### Avant (dans core/analyzer.py)
```python
class TechnicalAnalyzer:
    def check_volume_quality(self, vol_spike: float, atr: float,
                            price: float, volume24h: float) -> Dict:
        warnings = []
        quality = 100

        # Cohérence Volume/ATR
        atr_percent = (atr / price) * 100 if price > 0 else 0
        volume_atr_ratio = vol_spike / max(atr_percent * 0.1, 0.1)

        if volume_atr_ratio > 3.0:
            warnings.append('Volume élevé sans mouvement')
            quality -= 20

        # Liquidité
        if volume24h < 1000000 and volume24h > 0:
            warnings.append('Liquidité faible')
            quality -= 15

        return {
            'quality': quality,
            'warnings': warnings,
            'shouldTrade': quality >= 70
        }
```

### Après (nouveau fichier core/analyzer/volume_analyzer.py)
```python
"""
Analyseur de qualité du volume
Vérifie cohérence volume/ATR et liquidité
"""
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class VolumeQualityConfig:
    """Configuration analyse volume"""
    volume_atr_threshold: float = 3.0
    min_liquidity: float = 1000000
    quality_threshold: int = 70


class VolumeAnalyzer:
    """Analyse la qualité du volume pour détecter anomalies"""

    def __init__(self, config: VolumeQualityConfig = None):
        self.config = config or VolumeQualityConfig()

    def check_quality(self, vol_spike: float, atr: float,
                     price: float, volume24h: float) -> Dict:
        """
        Vérifie la qualité du volume

        Args:
            vol_spike: Ratio volume spike
            atr: ATR
            price: Prix actuel
            volume24h: Volume 24h

        Returns:
            Dict avec quality, warnings, shouldTrade
        """
        warnings = []
        quality = 100

        # Cohérence Volume/ATR
        atr_percent = self._calculate_atr_percent(price, atr)
        volume_atr_ratio = self._calculate_volume_atr_ratio(vol_spike, atr_percent)

        if self._is_volume_suspicious(volume_atr_ratio):
            warnings.append('Volume élevé sans mouvement')
            quality -= 20

        # Liquidité
        if self._is_liquidity_low(volume24h):
            warnings.append('Liquidité faible')
            quality -= 15

        return {
            'quality': quality,
            'warnings': warnings,
            'shouldTrade': quality >= self.config.quality_threshold
        }

    def _calculate_atr_percent(self, price: float, atr: float) -> float:
        """Calcule ATR en pourcentage du prix"""
        return (atr / price) * 100 if price > 0 else 0

    def _calculate_volume_atr_ratio(self, vol_spike: float,
                                    atr_percent: float) -> float:
        """Calcule ratio volume/ATR"""
        return vol_spike / max(atr_percent * 0.1, 0.1)

    def _is_volume_suspicious(self, volume_atr_ratio: float) -> bool:
        """Détecte volume suspect (élevé sans mouvement)"""
        return volume_atr_ratio > self.config.volume_atr_threshold

    def _is_liquidity_low(self, volume24h: float) -> bool:
        """Détecte liquidité insuffisante"""
        return 0 < volume24h < self.config.min_liquidity
```

### Tests (tests/test_volume_analyzer.py)
```python
"""Tests pour VolumeAnalyzer"""
import pytest
from core.analyzer.volume_analyzer import (
    VolumeAnalyzer,
    VolumeQualityConfig
)


class TestVolumeAnalyzer:
    """Tests pour VolumeAnalyzer"""

    def test_high_quality_volume(self):
        """Test volume de haute qualité"""
        analyzer = VolumeAnalyzer()
        result = analyzer.check_quality(
            vol_spike=2.0,
            atr=100,
            price=50000,
            volume24h=5000000
        )

        assert result['quality'] == 100
        assert result['warnings'] == []
        assert result['shouldTrade'] is True

    def test_suspicious_volume(self):
        """Test volume suspect (élevé sans mouvement)"""
        analyzer = VolumeAnalyzer()
        result = analyzer.check_quality(
            vol_spike=5.0,  # Très élevé
            atr=10,         # ATR faible → suspect
            price=50000,
            volume24h=5000000
        )

        assert result['quality'] == 80  # -20 pour volume suspect
        assert 'Volume élevé sans mouvement' in result['warnings']

    def test_low_liquidity(self):
        """Test liquidité faible"""
        analyzer = VolumeAnalyzer()
        result = analyzer.check_quality(
            vol_spike=2.0,
            atr=100,
            price=50000,
            volume24h=500000  # < 1M
        )

        assert result['quality'] == 85  # -15 pour liquidité faible
        assert 'Liquidité faible' in result['warnings']

    def test_both_issues(self):
        """Test volume suspect ET liquidité faible"""
        analyzer = VolumeAnalyzer()
        result = analyzer.check_quality(
            vol_spike=5.0,
            atr=10,
            price=50000,
            volume24h=500000
        )

        assert result['quality'] == 65  # -20 -15
        assert len(result['warnings']) == 2
        assert result['shouldTrade'] is False  # < 70

    def test_custom_config(self):
        """Test configuration personnalisée"""
        config = VolumeQualityConfig(
            volume_atr_threshold=5.0,
            min_liquidity=2000000,
            quality_threshold=80
        )
        analyzer = VolumeAnalyzer(config)

        result = analyzer.check_quality(
            vol_spike=4.0,
            atr=10,
            price=50000,
            volume24h=1500000
        )

        # Avec threshold 5.0, volume_atr_ratio=4.0 n'est pas suspect
        assert 'Volume élevé sans mouvement' not in result['warnings']
        # Mais liquidité < 2M est faible
        assert 'Liquidité faible' in result['warnings']


class TestPrivateMethods:
    """Tests pour méthodes privées (boîte blanche)"""

    def test_calculate_atr_percent(self):
        """Test calcul ATR percent"""
        analyzer = VolumeAnalyzer()

        # Cas normal
        assert analyzer._calculate_atr_percent(50000, 100) == 0.2

        # Cas prix = 0
        assert analyzer._calculate_atr_percent(0, 100) == 0

    def test_calculate_volume_atr_ratio(self):
        """Test calcul ratio volume/ATR"""
        analyzer = VolumeAnalyzer()

        # Cas normal
        ratio = analyzer._calculate_volume_atr_ratio(2.0, 0.5)
        assert ratio == pytest.approx(40.0)  # 2.0 / (0.5 * 0.1)

        # Cas ATR très faible (protection division par 0)
        ratio = analyzer._calculate_volume_atr_ratio(2.0, 0.0)
        assert ratio == pytest.approx(20.0)  # 2.0 / 0.1
```

**Gain:**
- VolumeAnalyzer: 50 lignes → +0.1% coverage
- Tests: 80+ lignes testées → +0.2% coverage
- **Total: +0.3%**

---

## Exemple 2: Dependency Injection pour Routes FastAPI

### Avant (api/routes.py)
```python
from fastapi import APIRouter
from core.analyzer import TechnicalAnalyzer

router = APIRouter()

@router.post("/analyze")
async def analyze_symbol(request: dict):
    # ❌ Impossible à mocker pour tests
    analyzer = TechnicalAnalyzer()

    symbol = request['symbol']
    result = await analyzer.analyze_timeframe(symbol, '1m')

    return result
```

### Après (api/routes.py avec DI)
```python
from fastapi import APIRouter, Depends
from core.analyzer import TechnicalAnalyzer
from api.dependencies import get_analyzer

router = APIRouter()

@router.post("/analyze")
async def analyze_symbol(
    request: dict,
    analyzer: TechnicalAnalyzer = Depends(get_analyzer)
):
    # ✅ analyzer peut être mocké via dependency_overrides
    symbol = request['symbol']
    result = await analyzer.analyze_timeframe(symbol, '1m')

    return result
```

### Dépendances (api/dependencies.py - nouveau fichier)
```python
"""Dépendances FastAPI pour injection"""
from core.analyzer import TechnicalAnalyzer
from core.position_manager import PositionManager
from api.mexc import get_mexc_client


def get_analyzer() -> TechnicalAnalyzer:
    """Fournit instance TechnicalAnalyzer"""
    return TechnicalAnalyzer()


def get_position_manager() -> PositionManager:
    """Fournit instance PositionManager"""
    return PositionManager()


def get_client():
    """Fournit client MEXC"""
    return get_mexc_client()
```

### Tests (tests/test_routes_analyze.py)
```python
"""Tests pour routes d'analyse"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from main import app  # Importer l'app FastAPI
from api.dependencies import get_analyzer
from core.analyzer import TechnicalAnalyzer


class TestAnalyzeRoutes:
    """Tests pour /analyze endpoints"""

    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)

    @pytest.fixture
    def mock_analyzer(self):
        """Mock analyzer pour tests"""
        analyzer = AsyncMock(spec=TechnicalAnalyzer)

        # Configurer comportement par défaut
        analyzer.analyze_timeframe = AsyncMock(return_value={
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'score': 8.5,
            'signals': ['EMA_CROSS', 'RSI_OVERSOLD']
        })

        return analyzer

    def test_analyze_success(self, client, mock_analyzer):
        """Test analyse réussie"""
        # Override dependency
        app.dependency_overrides[get_analyzer] = lambda: mock_analyzer

        response = client.post("/analyze", json={
            'symbol': 'BTC/USDT:USDT',
            'timeframe': '1m'
        })

        assert response.status_code == 200
        data = response.json()

        assert data['symbol'] == 'BTC/USDT:USDT'
        assert data['direction'] == 'LONG'
        assert data['score'] == 8.5

        # Vérifier que l'analyzer a été appelé
        mock_analyzer.analyze_timeframe.assert_called_once_with(
            'BTC/USDT:USDT',
            '1m'
        )

        # Cleanup
        app.dependency_overrides.clear()

    def test_analyze_no_setup_found(self, client, mock_analyzer):
        """Test quand aucun setup trouvé"""
        mock_analyzer.analyze_timeframe = AsyncMock(return_value=None)
        app.dependency_overrides[get_analyzer] = lambda: mock_analyzer

        response = client.post("/analyze", json={
            'symbol': 'ETH/USDT:USDT'
        })

        assert response.status_code == 404
        assert 'No setup found' in response.json()['detail']

        app.dependency_overrides.clear()

    def test_analyze_invalid_symbol(self, client, mock_analyzer):
        """Test avec symbole invalide"""
        mock_analyzer.analyze_timeframe = AsyncMock(
            side_effect=ValueError("Invalid symbol")
        )
        app.dependency_overrides[get_analyzer] = lambda: mock_analyzer

        response = client.post("/analyze", json={
            'symbol': 'INVALID'
        })

        assert response.status_code == 400

        app.dependency_overrides.clear()
```

**Gain:**
- Routes testables → +8% coverage (330+ lignes)

---

## Exemple 3: Refactoriser analyze_timeframe() en méthodes plus petites

### Avant (core/analyzer.py - méthode de 200+ lignes)
```python
async def analyze_timeframe(self, symbol: str, timeframe: str) -> Optional[Dict]:
    # 200+ lignes de logique mélangée:
    # - Fetch prix
    # - Calcul indicateurs
    # - Application filtres
    # - Génération signaux
    # - Calcul score
    # - Construction résultat
    ...
```

### Après (refactorisé en pipeline)
```python
async def analyze_timeframe(self, symbol: str, timeframe: str) -> Optional[Dict]:
    """
    Analyse un timeframe - orchestrateur principal

    Pipeline:
    1. Fetch market data
    2. Calculate indicators
    3. Apply filters
    4. Generate signals
    5. Calculate score
    6. Build result
    """
    # Étape 1: Récupérer données
    market_data = await self._fetch_market_data(symbol, timeframe)
    if not market_data:
        return None

    # Étape 2: Calculer indicateurs
    indicators = self._calculate_indicators(market_data)

    # Étape 3: Appliquer filtres
    filter_result = self._apply_filters(market_data, indicators)
    if filter_result:  # Rejeté
        return None

    # Étape 4: Générer signaux
    signals = self._generate_signals(market_data, indicators)
    if not signals:
        return None

    # Étape 5: Calculer score
    score = self._calculate_score(signals, indicators)

    # Étape 6: Construire résultat
    return self._build_result(symbol, timeframe, signals, score, indicators)


async def _fetch_market_data(self, symbol: str, timeframe: str) -> Optional[Dict]:
    """Récupère prix et OHLCV"""
    ticker = await self.price_provider.get_price(symbol)
    if not ticker:
        return None

    ohlcv = await self.client.fetch_ohlcv(symbol, timeframe, limit=100)
    if not ohlcv or len(ohlcv) < 20:
        return None

    return {
        'price': float(ticker['lastPrice']),
        'ohlcv': ohlcv,
        'volume24h': float(ticker.get('quoteVolume', 0))
    }


def _calculate_indicators(self, market_data: Dict) -> Dict:
    """Calcule tous les indicateurs techniques"""
    closes = [k[4] for k in market_data['ohlcv']]
    highs = [k[2] for k in market_data['ohlcv']]
    lows = [k[3] for k in market_data['ohlcv']]
    volumes = [k[5] for k in market_data['ohlcv']]

    return {
        'rsi': self.indicators.calculate_rsi(closes, 14),
        'rsi_prev': self.indicators.calculate_rsi_previous(closes, 14),
        'atr': self.indicators.calculate_atr(highs, lows, closes, 14),
        'ema9': self.indicators.calculate_ema(closes, 9),
        'ema21': self.indicators.calculate_ema(closes, 21),
        'macd': self.indicators.calculate_macd(closes, 3, 10, 16),
        'macd_prev': self.indicators.calculate_macd_previous(closes, 3, 10, 16),
        'bb': self.indicators.calculate_bollinger_bands(closes, 20, 2),
        'adx': self.indicators.calculate_adx(highs, lows, closes, 14),
        'vol_spike': self._calculate_vol_spike(volumes)
    }


def _apply_filters(self, market_data: Dict, indicators: Dict) -> Optional[str]:
    """
    Applique filtres de validation

    Returns:
        None si valide, raison du rejet sinon
    """
    from core.analyzer.filters import (
        check_volume_filter,
        check_atr_filter,
        check_snr_filter
    )

    # Filtre volume
    vol_result = check_volume_filter(
        indicators['vol_spike'],
        min_vol_ratio=1.0,
        symbol=market_data['symbol'],
        timeframe=market_data['timeframe'],
        atr_percent=(indicators['atr'] / market_data['price']) * 100,
        volume_multiplier=1.0
    )
    if vol_result:
        return "Volume insufficient"

    # Filtre ATR
    atr_result = check_atr_filter(
        (indicators['atr'] / market_data['price']) * 100,
        market_data['timeframe'],
        market_data['symbol']
    )
    if atr_result:
        return "ATR out of range"

    return None


def _generate_signals(self, market_data: Dict, indicators: Dict) -> List[str]:
    """Génère signaux LONG/SHORT"""
    from core.analyzer.signal_generator import (
        generate_long_conditions,
        generate_short_conditions
    )

    long_signals = generate_long_conditions(
        price=market_data['price'],
        rsi=indicators['rsi'],
        rsi_prev=indicators['rsi_prev'],
        ema9=indicators['ema9'],
        ema21=indicators['ema21'],
        macd=indicators['macd'],
        macd_prev=indicators['macd_prev'],
        bb=indicators['bb']
    )

    short_signals = generate_short_conditions(
        price=market_data['price'],
        rsi=indicators['rsi'],
        rsi_prev=indicators['rsi_prev'],
        ema9=indicators['ema9'],
        ema21=indicators['ema21'],
        macd=indicators['macd'],
        macd_prev=indicators['macd_prev'],
        bb=indicators['bb']
    )

    # Retourner les signaux les plus forts
    return long_signals if len(long_signals) > len(short_signals) else short_signals


def _calculate_score(self, signals: List[str], indicators: Dict) -> float:
    """Calcule score pondéré du setup"""
    from core.analyzer.scoring import calculate_weighted_score

    return calculate_weighted_score(signals, indicators['adx'])


def _build_result(self, symbol: str, timeframe: str, signals: List[str],
                  score: float, indicators: Dict) -> Dict:
    """Construit le résultat final"""
    return {
        'symbol': symbol,
        'timeframe': timeframe,
        'direction': 'LONG' if 'EMA_CROSS_LONG' in signals else 'SHORT',
        'signals': signals,
        'score': score,
        'rsi': indicators['rsi'],
        'atr': indicators['atr'],
        'adx': indicators['adx']
    }
```

**Tests pour chaque méthode:**
```python
class TestAnalyzeTimeframePipeline:
    """Tests pour pipeline analyze_timeframe"""

    @pytest.mark.asyncio
    async def test_fetch_market_data_success(self):
        """Test récupération données marché"""
        analyzer = TechnicalAnalyzer()

        # Mock price provider
        analyzer.price_provider.get_price = AsyncMock(return_value={
            'lastPrice': 50000,
            'quoteVolume': 5000000
        })

        # Mock client
        analyzer.client.fetch_ohlcv = AsyncMock(return_value=[
            [0, 50000, 50100, 49900, 50050, 1000] for _ in range(60)
        ])

        result = await analyzer._fetch_market_data('BTC/USDT:USDT', '1m')

        assert result is not None
        assert result['price'] == 50000
        assert len(result['ohlcv']) == 60

    def test_calculate_indicators(self):
        """Test calcul indicateurs"""
        analyzer = TechnicalAnalyzer()

        market_data = {
            'ohlcv': [[i, 50000+i, 50100+i, 49900+i, 50000+i, 1000]
                     for i in range(60)]
        }

        indicators = analyzer._calculate_indicators(market_data)

        assert 'rsi' in indicators
        assert 'atr' in indicators
        assert 'ema9' in indicators
        assert indicators['rsi'] > 0

    def test_apply_filters_pass(self):
        """Test filtres passent"""
        analyzer = TechnicalAnalyzer()

        market_data = {'symbol': 'BTC/USDT:USDT', 'timeframe': '1m', 'price': 50000}
        indicators = {'vol_spike': 2.0, 'atr': 100}

        result = analyzer._apply_filters(market_data, indicators)

        assert result is None  # Aucun rejet

    def test_apply_filters_reject(self):
        """Test filtres rejettent"""
        analyzer = TechnicalAnalyzer()

        market_data = {'symbol': 'BTC/USDT:USDT', 'timeframe': '1m', 'price': 50000}
        indicators = {'vol_spike': 0.5, 'atr': 100}  # Volume trop faible

        result = analyzer._apply_filters(market_data, indicators)

        assert result is not None  # Rejeté
        assert 'Volume' in result
```

**Gain:**
- Chaque méthode testable indépendamment
- Coverage analyzer.py: 25% → 75% (+50%)
- **Total: +5%**

---

## Résumé des Gains Potentiels

| Refactorisation | Lignes | Gain Coverage |
|----------------|--------|---------------|
| VolumeAnalyzer | 50 | +0.3% |
| Routes DI | 330 | +8.0% |
| Analyzer pipeline | 200 | +5.0% |
| **TOTAL** | **580** | **+13.3%** |

**Avec ces 3 refactorisations:** 66.30% + 13.3% = **79.6%** ✅ (objectif atteint!)
