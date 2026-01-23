#!/usr/bin/env python3
"""
Interface IAnalyzer - Trade Cursor v7.0
Interface pour refactorisation sécurisée du TechnicalAnalyzer
ZÉRO RISQUE - Code existant inchangé, interface créée à côté
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class AnalysisSetup:
    """Setup standardisé pour analyse technique"""
    symbol: str
    direction: str  # 'LONG', 'SHORT' ou None
    timeframe: str  # '1m', '5m', etc.
    entry_price: float
    sl_price: float
    tp_price: float
    atr: float
    total_score: float
    long_score: float = 0.0
    short_score: float = 0.0
    signals: List[str] = None
    rsi_1m: Optional[float] = None
    rsi_5m: Optional[float] = None
    macd_1m: Optional[float] = None
    macd_5m: Optional[float] = None
    adx_1m: Optional[float] = None
    adx_5m: Optional[float] = None
    volume_spike: Optional[float] = None
    
    def __post_init__(self):
        if self.signals is None:
            self.signals = []


@dataclass
class AnalysisResult:
    """Résultat standardisé d'analyse"""
    success: bool
    setup: Optional[AnalysisSetup]
    reason: str
    reject_category: Optional[str] = None
    is_opportunity: bool = False
    confluence_score: Optional[float] = None
    final_score: Optional[float] = None
    filters_passed: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.filters_passed is None:
            self.filters_passed = {}


class IAnalyzer(ABC):
    """
    Interface pour TechnicalAnalyzer - Permet tests sans dépendances
    
    Cette interface définit les méthodes critiques du TechnicalAnalyzer
    sans toucher au code existant. Permet injection de dépendances
    et testabilité complète.
    """
    
    @abstractmethod
    async def analyze_pair_testable(
        self, 
        symbol: str, 
        mock_data: Optional[Dict[str, Any]] = None,
        use_confluence: bool = True,
        return_reason: bool = False,
        position_manager=None
    ) -> AnalysisResult:
        """
        Analyser paire avec données mockées ou réelles
        
        Args:
            symbol: Symbole à analyser (ex: 'BTC/USDT:USDT')
            mock_data: Données mockées pour tests (optionnel)
            use_confluence: Utiliser confluence ou non
            return_reason: Retourner raison détaillée
            position_manager: Manager positions pour recovery state
            
        Returns:
            AnalysisResult: Résultat analyse avec setup ou raison rejet
        """
        pass
    
    @abstractmethod
    async def analyze_timeframe(
        self, 
        symbol: str, 
        timeframe: str,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Optional[AnalysisSetup]:
        """
        Analyser timeframe spécifique
        
        Args:
            symbol: Symbole à analyser
            timeframe: Timeframe ('1m', '5m', etc.)
            market_data: Données marché optionnelles
            
        Returns:
            AnalysisSetup: Setup si opportunité détectée, None sinon
        """
        pass
    
    @abstractmethod
    async def calculate_confluence_score(
        self,
        setup_1m: Optional[AnalysisSetup],
        setup_5m: Optional[AnalysisSetup],
        symbol: str
    ) -> Dict[str, Any]:
        """
        Calculer score confluence entre timeframes
        
        Args:
            setup_1m: Setup 1 minute
            setup_5m: Setup 5 minutes  
            symbol: Symbole analysé
            
        Returns:
            Dict: Score confluence et détails
        """
        pass
    
    @abstractmethod
    async def apply_filters(
        self,
        symbol: str,
        setup: AnalysisSetup,
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Appliquer filtres (spread, volume, corrélation, etc.)
        
        Args:
            symbol: Symbole analysé
            setup: Setup à valider
            market_data: Données marché
            
        Returns:
            Dict: Résultats filtres avec détails
        """
        pass
    
    @abstractmethod
    def calculate_score_adjustments(
        self,
        base_score: float,
        symbol: str,
        loss_streak: int = 0,
        market_conditions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Calculer ajustements de score (recovery, circuit breaker, etc.)
        
        Args:
            base_score: Score de base
            symbol: Symbole analysé
            loss_streak: Nombre pertes consécutives
            market_conditions: Conditions marché
            
        Returns:
            Dict: Ajustements avec détails
        """
        pass
    
    @abstractmethod
    def get_min_score_required(
        self,
        symbol: str,
        recovery_state: Optional[Dict[str, Any]] = None,
        market_regime: Optional[str] = None
    ) -> float:
        """
        Obtenir score minimum requis
        
        Args:
            symbol: Symbole analysé
            recovery_state: État recovery mode
            market_regime: Régime marché
            
        Returns:
            float: Score minimum requis
        """
        pass
    
    @abstractmethod
    async def validate_market_conditions(
        self,
        symbol: str,
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Valider conditions marché (manipulation, liquidité, etc.)
        
        Args:
            symbol: Symbole analysé
            market_data: Données marché
            
        Returns:
            Dict: Validation avec raisons
        """
        pass


class IAnalyzerDependencies(ABC):
    """Interface pour dépendances du TechnicalAnalyzer"""
    
    @abstractmethod
    def get_mexc_client(self):
        """Retourne client MEXC"""
        pass
        
    @abstractmethod
    def get_price_provider(self):
        """Retourne provider prix"""
        pass
        
    @abstractmethod
    def get_pair_scorer(self):
        """Retourne scorer paires"""
        pass
        
    @abstractmethod
    def get_circuit_breaker(self):
        """Retourne circuit breaker"""
        pass
        
    @abstractmethod
    def get_regime_selector(self):
        """Retourne sélecteur régime"""
        pass
        
    @abstractmethod
    def get_correlation_filter(self):
        """Retourne filtre corrélation"""
        pass


class AnalyzerConfig:
    """Configuration pour Analyzer testable"""
    
    def __init__(self, **kwargs):
        # Configuration analyse
        self.min_score_base = kwargs.get('min_score_base', 75.0)
        self.use_confluence = kwargs.get('use_confluence', True)
        self.confluence_required_score = kwargs.get('confluence_required_score', 85.0)
        
        # Configuration filtres
        self.spread_filter_enabled = kwargs.get('spread_filter_enabled', True)
        self.max_spread_pct = kwargs.get('max_spread_pct', 0.05)
        self.volume_filter_enabled = kwargs.get('volume_filter_enabled', True)
        self.min_volume_ratio = kwargs.get('min_volume_ratio', 1.5)
        
        # Configuration corrélation
        self.correlation_filter_enabled = kwargs.get('correlation_filter_enabled', True)
        self.max_correlation = kwargs.get('max_correlation', 0.8)
        
        # Configuration RSI
        self.rsi_final_filter_enabled = kwargs.get('rsi_final_filter_enabled', False)
        self.rsi_oversold_threshold = kwargs.get('rsi_oversold_threshold', 30)
        self.rsi_overbought_threshold = kwargs.get('rsi_overbought_threshold', 70)
        
        # Configuration tests
        self.test_mode = kwargs.get('test_mode', False)
        self.mock_external_calls = kwargs.get('mock_external_calls', False)
        self.enable_logging = kwargs.get('enable_logging', True)


# Utilitaires pour conversion
def setup_from_legacy_dict(data: Dict[str, Any]) -> AnalysisSetup:
    """Convertir dict legacy en AnalysisSetup"""
    return AnalysisSetup(
        symbol=data.get('symbol', ''),
        direction=data.get('direction', 'LONG'),
        timeframe=data.get('timeframe', '1m'),
        entry_price=float(data.get('entry', data.get('entry_price', 0))),
        sl_price=float(data.get('sl', data.get('sl_price', 0))),
        tp_price=float(data.get('tp', data.get('tp_price', 0))),
        atr=float(data.get('atr', 1.0)),
        total_score=float(data.get('totalScore', data.get('total_score', 0))),
        long_score=float(data.get('long_score', 0)),
        short_score=float(data.get('short_score', 0)),
        signals=data.get('signals', []),
        rsi_1m=data.get('rsi_1m'),
        rsi_5m=data.get('rsi_5m'),
        macd_1m=data.get('macd_1m'),
        macd_5m=data.get('macd_5m'),
        adx_1m=data.get('adx_1m'),
        adx_5m=data.get('adx_5m'),
        volume_spike=data.get('volumeSpike', data.get('volume_spike'))
    )


def setup_to_legacy_dict(setup: AnalysisSetup) -> Dict[str, Any]:
    """Convertir AnalysisSetup en dict legacy"""
    result = {
        'symbol': setup.symbol,
        'direction': setup.direction,
        'timeframe': setup.timeframe,
        'entry': setup.entry_price,
        'entry_price': setup.entry_price,
        'sl': setup.sl_price,
        'sl_price': setup.sl_price,
        'tp': setup.tp_price,
        'tp_price': setup.tp_price,
        'atr': setup.atr,
        'totalScore': setup.total_score,
        'total_score': setup.total_score,
        'long_score': setup.long_score,
        'short_score': setup.short_score,
        'signals': setup.signals
    }
    
    # Ajouter indicateurs optionnels s'ils existent
    if setup.rsi_1m is not None:
        result['rsi_1m'] = setup.rsi_1m
    if setup.rsi_5m is not None:
        result['rsi_5m'] = setup.rsi_5m
    if setup.macd_1m is not None:
        result['macd_1m'] = setup.macd_1m
    if setup.macd_5m is not None:
        result['macd_5m'] = setup.macd_5m
    if setup.adx_1m is not None:
        result['adx_1m'] = setup.adx_1m
    if setup.adx_5m is not None:
        result['adx_5m'] = setup.adx_5m
    if setup.volume_spike is not None:
        result['volumeSpike'] = setup.volume_spike
        result['volume_spike'] = setup.volume_spike
    
    return result


def result_from_legacy_dict(data: Dict[str, Any]) -> AnalysisResult:
    """Convertir résultat legacy en AnalysisResult"""
    setup = None
    if data and 'symbol' in data:
        setup = setup_from_legacy_dict(data)
    
    return AnalysisResult(
        success=data is not None,
        setup=setup,
        reason=data.get('reason', 'No reason provided'),
        reject_category=data.get('reject_category'),
        is_opportunity=setup is not None,
        confluence_score=data.get('confluence_score'),
        final_score=data.get('final_score', data.get('totalScore')),
        filters_passed=data.get('filters_passed', {})
    )


def result_to_legacy_dict(result: AnalysisResult) -> Optional[Dict[str, Any]]:
    """Convertir AnalysisResult en dict legacy"""
    if not result.success or not result.setup:
        return None
    
    data = setup_to_legacy_dict(result.setup)
    
    # Ajouter métadonnées résultat
    if result.confluence_score is not None:
        data['confluence_score'] = result.confluence_score
    if result.final_score is not None:
        data['final_score'] = result.final_score
    if result.filters_passed:
        data['filters_passed'] = result.filters_passed
    
    return data
