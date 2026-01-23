"""
Interfaces pour l'Analyzer refactorisé - Trade Cursor v7.0
Définit les contrats pour l'analyse technique découplée et testable
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from datetime import datetime


class SignalType(Enum):
    """Types de signaux d'analyse"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"


class SignalStrength(Enum):
    """Force du signal"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class AnalysisStatus(Enum):
    """Statut d'analyse"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    INSUFFICIENT_DATA = "insufficient_data"
    TIMEOUT = "timeout"


@dataclass
class TechnicalIndicators:
    """Indicateurs techniques calculés"""
    # RSI
    rsi_1m: Optional[float] = None
    rsi_5m: Optional[float] = None
    rsi_15m: Optional[float] = None
    
    # MACD
    macd_1m: Optional[float] = None
    macd_signal_1m: Optional[float] = None
    macd_histogram_1m: Optional[float] = None
    macd_5m: Optional[float] = None
    macd_signal_5m: Optional[float] = None
    
    # EMA
    ema_20_1m: Optional[float] = None
    ema_50_1m: Optional[float] = None
    ema_200_1m: Optional[float] = None
    ema_20_5m: Optional[float] = None
    ema_50_5m: Optional[float] = None
    
    # ATR et volatilité
    atr_1m: Optional[float] = None
    atr_5m: Optional[float] = None
    atr_pct_1m: Optional[float] = None
    atr_pct_5m: Optional[float] = None
    
    # Volume
    volume_sma_1m: Optional[float] = None
    volume_ratio_1m: Optional[float] = None
    
    # ADX et trend
    adx_1m: Optional[float] = None
    adx_5m: Optional[float] = None
    
    # Stochastic
    stoch_k_1m: Optional[float] = None
    stoch_d_1m: Optional[float] = None
    
    def is_complete(self) -> bool:
        """Vérifie si les indicateurs essentiels sont présents"""
        essential = [self.rsi_1m, self.rsi_5m, self.macd_1m, self.ema_20_1m, self.atr_1m]
        return all(ind is not None for ind in essential)


@dataclass
class MarketContext:
    """Contexte de marché pour l'analyse"""
    symbol: str
    current_price: float
    price_change_24h_pct: Optional[float] = None
    volume_24h: Optional[float] = None
    market_cap_rank: Optional[int] = None
    
    # Session de trading
    trading_session: Optional[str] = None  # 'asian', 'european', 'american', 'overlap'
    is_weekend: bool = False
    
    # Volatilité du marché
    market_volatility: Optional[str] = None  # 'low', 'medium', 'high'
    
    # Tendance générale
    overall_trend: Optional[str] = None  # 'bullish', 'bearish', 'sideways'


@dataclass
class SignalResult:
    """Résultat d'un signal d'analyse"""
    signal_type: SignalType
    strength: SignalStrength
    confidence: float  # 0.0 - 1.0
    
    # Détails du signal
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    
    # Justification
    reasoning: List[str] = None
    key_indicators: Dict[str, float] = None
    
    # Métadonnées
    generated_at: datetime = None
    valid_until: Optional[datetime] = None
    
    def __post_init__(self):
        if self.reasoning is None:
            self.reasoning = []
        if self.key_indicators is None:
            self.key_indicators = {}
        if self.generated_at is None:
            self.generated_at = datetime.utcnow()


@dataclass
class AnalysisResult:
    """Résultat complet d'une analyse"""
    symbol: str
    status: AnalysisStatus
    
    # Signaux générés
    primary_signal: Optional[SignalResult] = None
    secondary_signals: List[SignalResult] = None
    
    # Scores calculés
    score_1m: Optional[float] = None
    score_5m: Optional[float] = None
    combined_score: Optional[float] = None
    
    # Indicateurs utilisés
    indicators: Optional[TechnicalIndicators] = None
    market_context: Optional[MarketContext] = None
    
    # Métriques de qualité
    data_quality_score: float = 1.0  # 0.0 - 1.0
    processing_time_ms: Optional[float] = None
    
    # Erreurs et warnings
    errors: List[str] = None
    warnings: List[str] = None
    
    # Métadonnées
    timestamp: datetime = None
    analyzer_version: str = "testable_v1"
    
    def __post_init__(self):
        if self.secondary_signals is None:
            self.secondary_signals = []
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    @property
    def is_valid(self) -> bool:
        """Vérifie si l'analyse est valide"""
        return (self.status == AnalysisStatus.SUCCESS and 
                self.primary_signal is not None and
                len(self.errors) == 0)
    
    @property
    def has_warnings(self) -> bool:
        """Vérifie s'il y a des warnings"""
        return len(self.warnings) > 0


class IIndicatorCalculator(ABC):
    """Interface pour le calcul d'indicateurs techniques"""
    
    @abstractmethod
    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Calcule RSI"""
        pass
    
    @abstractmethod
    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calcule MACD, signal et histogramme"""
        pass
    
    @abstractmethod
    def calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calcule EMA"""
        pass
    
    @abstractmethod
    def calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
        """Calcule ATR"""
        pass
    
    @abstractmethod
    def calculate_all_indicators(self, market_data: Dict[str, Any]) -> TechnicalIndicators:
        """Calcule tous les indicateurs pour des données de marché"""
        pass


class ISignalGenerator(ABC):
    """Interface pour la génération de signaux"""
    
    @abstractmethod
    def generate_signal(self, indicators: TechnicalIndicators, market_context: MarketContext) -> SignalResult:
        """Génère un signal principal basé sur les indicateurs"""
        pass
    
    @abstractmethod
    def generate_secondary_signals(self, indicators: TechnicalIndicators, market_context: MarketContext) -> List[SignalResult]:
        """Génère des signaux secondaires"""
        pass
    
    @abstractmethod
    def calculate_confidence(self, signal: SignalResult, indicators: TechnicalIndicators) -> float:
        """Calcule la confiance dans un signal"""
        pass


class ISignalValidator(ABC):
    """Interface pour la validation des signaux"""
    
    @abstractmethod
    def validate_signal(self, signal: SignalResult, market_context: MarketContext) -> bool:
        """Valide un signal généré"""
        pass
    
    @abstractmethod
    def validate_signal_quality(self, signal: SignalResult, indicators: TechnicalIndicators) -> float:
        """Évalue la qualité d'un signal (0.0 - 1.0)"""
        pass
    
    @abstractmethod
    def check_signal_consistency(self, primary: SignalResult, secondary: List[SignalResult]) -> bool:
        """Vérifie la cohérence entre signaux"""
        pass
    
    @abstractmethod
    def validate_market_conditions(self, market_context: MarketContext) -> bool:
        """Valide les conditions de marché pour trading"""
        pass


class IScoreCalculator(ABC):
    """Interface pour le calcul des scores d'analyse"""
    
    @abstractmethod
    def calculate_score_1m(self, indicators: TechnicalIndicators, market_context: MarketContext) -> float:
        """Calcule score basé sur indicateurs 1m"""
        pass
    
    @abstractmethod
    def calculate_score_5m(self, indicators: TechnicalIndicators, market_context: MarketContext) -> float:
        """Calcule score basé sur indicateurs 5m"""
        pass
    
    @abstractmethod
    def calculate_combined_score(self, score_1m: float, score_5m: float, market_context: MarketContext) -> float:
        """Calcule score combiné avec pondération"""
        pass
    
    @abstractmethod
    def adjust_score_for_conditions(self, base_score: float, market_context: MarketContext) -> float:
        """Ajuste le score selon les conditions de marché"""
        pass


class IAnalyzer(ABC):
    """Interface principale pour l'analyseur technique"""
    
    @abstractmethod
    def analyze_pair(self, symbol: str, market_data: Dict[str, Any]) -> AnalysisResult:
        """Analyse complète d'une paire"""
        pass
    
    @abstractmethod
    def batch_analyze(self, symbols: List[str], market_data: Dict[str, Dict[str, Any]]) -> Dict[str, AnalysisResult]:
        """Analyse en batch de plusieurs paires"""
        pass
    
    @abstractmethod
    def quick_score(self, symbol: str, market_data: Dict[str, Any]) -> Tuple[float, float]:
        """Calcul rapide des scores 1m et 5m seulement"""
        pass
    
    @abstractmethod
    def validate_data_quality(self, market_data: Dict[str, Any]) -> float:
        """Évalue la qualité des données de marché (0.0 - 1.0)"""
        pass


class IAnalysisOrchestrator(ABC):
    """Interface pour l'orchestrateur d'analyse"""
    
    @abstractmethod
    def coordinate_analysis(self, symbols: List[str], market_data: Dict[str, Dict[str, Any]]) -> Dict[str, AnalysisResult]:
        """Coordonne l'analyse de plusieurs symboles"""
        pass
    
    @abstractmethod
    def filter_opportunities(self, analysis_results: Dict[str, AnalysisResult], filters: Dict[str, Any]) -> Dict[str, AnalysisResult]:
        """Filtre les opportunités selon des critères"""
        pass
    
    @abstractmethod
    def rank_opportunities(self, opportunities: Dict[str, AnalysisResult]) -> List[Tuple[str, AnalysisResult]]:
        """Classe les opportunités par pertinence"""
        pass
    
    @abstractmethod
    def get_analysis_summary(self, analysis_results: Dict[str, AnalysisResult]) -> Dict[str, Any]:
        """Résumé des analyses effectuées"""
        pass


# Configuration pour les analyseurs
@dataclass
class AnalyzerConfig:
    """Configuration pour l'analyzer testable"""
    # Seuils de signaux
    min_signal_confidence: float = 0.6
    min_score_threshold: float = 3.0
    max_score_threshold: float = 8.0
    
    # Paramètres d'indicateurs
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    rsi_period: int = 14
    
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    ema_periods: List[int] = None
    atr_period: int = 14
    
    # Timeframes
    primary_timeframe: str = "1m"
    secondary_timeframe: str = "5m"
    
    # Filtres de qualité
    min_data_quality: float = 0.8
    min_volume_threshold: float = 100000.0
    
    # Timeouts
    analysis_timeout_ms: int = 5000
    batch_timeout_ms: int = 30000
    
    def __post_init__(self):
        if self.ema_periods is None:
            self.ema_periods = [20, 50, 200]


# Utilitaires pour la validation
class ValidationUtils:
    """Utilitaires pour la validation des analyses"""
    
    @staticmethod
    def is_valid_price(price: Optional[float]) -> bool:
        """Valide un prix"""
        return price is not None and price > 0
    
    @staticmethod
    def is_valid_percentage(pct: Optional[float], allow_negative: bool = True) -> bool:
        """Valide un pourcentage"""
        if pct is None:
            return False
        if not allow_negative and pct < 0:
            return False
        return -100 <= pct <= 1000  # Limites raisonnables
    
    @staticmethod
    def is_valid_rsi(rsi: Optional[float]) -> bool:
        """Valide une valeur RSI"""
        return rsi is not None and 0 <= rsi <= 100
    
    @staticmethod
    def is_valid_confidence(confidence: float) -> bool:
        """Valide une valeur de confiance"""
        return 0.0 <= confidence <= 1.0
    
    @staticmethod
    def normalize_score(score: float, min_val: float = 0.0, max_val: float = 10.0) -> float:
        """Normalise un score dans une plage donnée"""
        return max(min_val, min(max_val, score))
