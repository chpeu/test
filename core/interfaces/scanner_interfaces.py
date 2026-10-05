"""
Scanner Interfaces - Trade Cursor v7.0 Phase 3
Interfaces pour le Scanner refactorisé et découplé
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class ScanStatus(Enum):
    """Statut d'un scan"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class PairFilterResult(Enum):
    """Résultat du filtrage d'une paire"""
    ACCEPTED = "accepted"
    REJECTED_SPREAD = "rejected_spread"
    REJECTED_VOLUME = "rejected_volume"
    REJECTED_FUNDING = "rejected_funding"
    REJECTED_BALANCE = "rejected_balance"
    REJECTED_BLACKLIST = "rejected_blacklist"
    REJECTED_FEE = "rejected_fee"
    REJECTED_CUSTOM = "rejected_custom"


class DataSource(Enum):
    """Source des données de marché"""
    MEXC = "mexc"
    BINANCE = "binance"
    CACHE = "cache"
    MOCK = "mock"


class ScanPipelineStepType(Enum):
    """Types d'étapes du pipeline de scan"""
    DATA_COLLECTION = "data_collection"
    SCORING = "scoring"
    FILTERING = "filtering"
    ANALYSIS = "analysis"
    ML_PREDICTION = "ml_prediction"
    LOGGING = "logging"
    CUSTOM = "custom"


# =============================================================================
# DATACLASSES
# =============================================================================

@dataclass
class OrderbookData:
    """Données orderbook d'une paire"""
    symbol: str
    timestamp: datetime
    bids: List[Tuple[float, float]]  # [(price, quantity), ...]
    asks: List[Tuple[float, float]]  # [(price, quantity), ...]
    spread: float = 0.0
    spread_pct: float = 0.0
    book_depth: float = 0.0
    balance_score: float = 0.0
    bid_vol: float = 0.0
    ask_vol: float = 0.0
    direction_bias: str = "NEUTRAL"
    bid_ask_ratio: float = 0.5
    
    def __post_init__(self):
        if self.bids and self.asks:
            self._calculate_metrics()
    
    def _calculate_metrics(self):
        """Calcule les métriques dérivées"""
        if not self.bids or not self.asks:
            return
        
        best_bid = self.bids[0][0]
        best_ask = self.asks[0][0]
        
        # Spread
        mid_price = (best_bid + best_ask) / 2
        self.spread = best_ask - best_bid
        self.spread_pct = (self.spread / mid_price) * 100 if mid_price > 0 else 0
        
        # Volumes
        self.bid_vol = sum(qty for _, qty in self.bids[:5])
        self.ask_vol = sum(qty for _, qty in self.asks[:5])
        
        # Métriques
        self.book_depth = self.bid_vol + self.ask_vol
        total_vol = self.bid_vol + self.ask_vol
        
        if total_vol > 0:
            self.bid_ask_ratio = self.bid_vol / total_vol
            self.balance_score = 1 - (abs(self.bid_ask_ratio - 0.5) * 2)
            
            if self.bid_ask_ratio > 0.6:
                self.direction_bias = "LONG"
            elif self.bid_ask_ratio < 0.4:
                self.direction_bias = "SHORT"


@dataclass
class TickerData:
    """Données ticker d'une paire"""
    symbol: str
    timestamp: datetime
    price: float
    volume_24h: float
    price_change_24h: float = 0.0
    price_change_24h_pct: float = 0.0
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    funding_rate: Optional[float] = None
    next_funding_time: Optional[datetime] = None


@dataclass
class OHLCVData:
    """Données OHLCV pour une paire"""
    symbol: str
    timeframe: str
    timestamp: datetime
    klines: List[List[float]]  # [timestamp, open, high, low, close, volume]
    
    def get_closes(self) -> List[float]:
        """Retourne la liste des prix de clôture"""
        return [k[4] for k in self.klines] if self.klines else []
    
    def get_highs(self) -> List[float]:
        """Retourne la liste des prix hauts"""
        return [k[2] for k in self.klines] if self.klines else []
    
    def get_lows(self) -> List[float]:
        """Retourne la liste des prix bas"""
        return [k[3] for k in self.klines] if self.klines else []
    
    def get_volumes(self) -> List[float]:
        """Retourne la liste des volumes"""
        return [k[5] for k in self.klines] if self.klines else []


@dataclass
class MarketData:
    """Données complètes de marché pour une paire"""
    symbol: str
    timestamp: datetime
    orderbook: Optional[OrderbookData] = None
    ticker: Optional[TickerData] = None
    ohlcv_1m: Optional[OHLCVData] = None
    ohlcv_5m: Optional[OHLCVData] = None
    ohlcv_15m: Optional[OHLCVData] = None
    data_quality: float = 0.0
    source: DataSource = DataSource.MEXC
    
    def is_complete(self) -> bool:
        """Vérifie si les données sont complètes"""
        return (
            self.orderbook is not None and
            self.ticker is not None and
            self.ohlcv_1m is not None and
            len(self.ohlcv_1m.klines) >= 20
        )


@dataclass
class ScoringMetrics:
    """Métriques pour le scoring de scalabilité"""
    volatility_5: float = 0.0
    volatility_15: float = 0.0
    volume_recent: float = 0.0
    volume_24h: float = 0.0
    atr: float = 0.0
    atr_pct: float = 0.0
    adx: float = 0.0
    
    # Order flow metrics
    delta_volume: float = 0.0
    imbalance_normalized: float = 0.0
    spread_volatility_5: float = 0.0
    book_depth_ratio: float = 1.0
    volume_acceleration: float = 0.0
    price_momentum_5: float = 0.0


@dataclass
class ScoringResult:
    """Résultat du scoring d'une paire"""
    symbol: str
    score: float
    metrics: ScoringMetrics
    rejection_reason: Optional[str] = None
    scoring_details: Dict[str, float] = field(default_factory=dict)
    calculation_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_valid(self) -> bool:
        """Vérifie si le scoring est valide"""
        return self.score > 0 and self.rejection_reason is None


@dataclass
class FilterConfig:
    """Configuration des filtres pour les paires"""
    # Filtres de base
    min_spread: float = 0.001
    max_spread: float = 0.05
    min_volume: float = 100000
    max_funding_rate: float = 0.05
    min_balance_score: float = 0.7
    
    # Listes include/exclude
    symbol_whitelist: List[str] = field(default_factory=list)
    symbol_blacklist: List[str] = field(default_factory=list)
    
    # Filtres avancés
    require_zero_fees: bool = True
    min_book_depth: float = 1000
    max_atr_pct: float = 5.0
    min_volume_24h: float = 10000000
    
    # Filtres temporels
    avoid_weekends: bool = False
    trading_hours_only: bool = False
    
    # Filtres custom
    custom_filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PairFilterResult:
    """Résultat du filtrage d'une paire"""
    symbol: str
    accepted: bool
    filter_results: Dict[str, bool] = field(default_factory=dict)
    rejection_reasons: List[str] = field(default_factory=list)
    filter_details: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ScanResult:
    """Résultat complet du scan d'une paire"""
    symbol: str
    status: ScanStatus
    market_data: Optional[MarketData] = None
    scoring_result: Optional[ScoringResult] = None
    filter_result: Optional[PairFilterResult] = None
    analysis_result: Optional[Any] = None  # AnalysisResult from Phase 2
    ml_prediction: Optional[Dict[str, Any]] = None
    
    # Métriques
    scan_duration_ms: float = 0.0
    data_collection_time_ms: float = 0.0
    scoring_time_ms: float = 0.0
    analysis_time_ms: float = 0.0
    
    # Metadata
    scan_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Erreurs
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def is_success(self) -> bool:
        """Vérifie si le scan est un succès"""
        return self.status == ScanStatus.SUCCESS and not self.errors
    
    @property
    def is_opportunity(self) -> bool:
        """Vérifie si c'est une opportunité de trading"""
        return (
            self.is_success and
            self.analysis_result is not None and
            hasattr(self.analysis_result, 'is_valid') and
            self.analysis_result.is_valid
        )


@dataclass
class ScanBatchResult:
    """Résultat d'un scan batch de plusieurs paires"""
    symbols: List[str]
    results: Dict[str, ScanResult] = field(default_factory=dict)
    
    # Statistiques
    total_scanned: int = 0
    successful_scans: int = 0
    failed_scans: int = 0
    opportunities_found: int = 0
    
    # Performance
    total_duration_ms: float = 0.0
    average_scan_time_ms: float = 0.0
    parallel_workers: int = 1
    
    # Metadata
    batch_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Calcule les statistiques automatiquement"""
        if self.results:
            self.total_scanned = len(self.results)
            self.successful_scans = sum(1 for r in self.results.values() if r.is_success)
            self.failed_scans = self.total_scanned - self.successful_scans
            self.opportunities_found = sum(1 for r in self.results.values() if r.is_opportunity)
            
            scan_times = [r.scan_duration_ms for r in self.results.values() if r.scan_duration_ms > 0]
            if scan_times:
                self.average_scan_time_ms = sum(scan_times) / len(scan_times)


@dataclass
class ScannerConfig:
    """Configuration globale du scanner"""
    # Limites et timeouts
    max_concurrent_scans: int = 10
    single_scan_timeout_ms: int = 5000
    batch_scan_timeout_ms: int = 30000
    
    # Cache configuration
    enable_cache: bool = True
    cache_ttl_seconds: int = 30
    cache_size_limit: int = 1000
    
    # Data collection
    orderbook_limit: int = 5
    klines_limit: int = 30
    default_timeframes: List[str] = field(default_factory=lambda: ['1m', '5m'])
    
    # Performance
    enable_parallel_scanning: bool = True
    max_parallel_workers: int = 4
    enable_performance_monitoring: bool = True
    
    # Integration
    enable_analyzer_integration: bool = True
    enable_ml_predictions: bool = True
    enable_postgresql_logging: bool = True
    
    # Error handling
    max_retries: int = 2
    retry_delay_ms: int = 1000
    enable_circuit_breaker: bool = True


@dataclass
class ScanPipelineStep:
    """Étape du pipeline de scan"""
    name: str
    step_type: ScanPipelineStepType
    enabled: bool = True
    timeout_ms: int = 5000
    retry_attempts: int = 1
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanPipelineResult:
    """Résultat d'exécution du pipeline"""
    symbol: str
    steps_executed: List[str] = field(default_factory=list)
    step_results: Dict[str, Any] = field(default_factory=dict)
    step_timings: Dict[str, float] = field(default_factory=dict)
    final_result: Optional[ScanResult] = None
    pipeline_duration_ms: float = 0.0
    errors_by_step: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# INTERFACES
# =============================================================================

class IMarketDataCollector(ABC):
    """Interface pour la collecte des données de marché"""
    
    @abstractmethod
    async def collect_orderbook(self, symbol: str, limit: int = 5) -> Optional[OrderbookData]:
        """Collecte les données orderbook pour une paire"""
        pass
    
    @abstractmethod
    async def collect_ticker(self, symbol: str) -> Optional[TickerData]:
        """Collecte les données ticker pour une paire"""
        pass
    
    @abstractmethod
    async def collect_ohlcv(self, symbol: str, timeframe: str, limit: int = 30) -> Optional[OHLCVData]:
        """Collecte les données OHLCV pour une paire"""
        pass
    
    @abstractmethod
    async def collect_funding_rate(self, symbol: str) -> Optional[float]:
        """Collecte le taux de funding pour une paire"""
        pass
    
    @abstractmethod
    async def collect_complete_market_data(self, symbol: str, timeframes: List[str]) -> MarketData:
        """Collecte toutes les données nécessaires pour une paire"""
        pass
    
    @abstractmethod
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache"""
        pass
    
    @abstractmethod
    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """Vide le cache complètement ou pour un symbole"""
        pass


class IScalabilityScorer(ABC):
    """Interface pour le scoring de scalabilité des paires"""
    
    @abstractmethod
    def calculate_score(self, market_data: MarketData, config: Optional[Dict[str, Any]] = None) -> ScoringResult:
        """Calcule le score de scalabilité pour une paire"""
        pass
    
    @abstractmethod
    def calculate_metrics(self, market_data: MarketData) -> ScoringMetrics:
        """Calcule les métriques techniques pour une paire"""
        pass
    
    @abstractmethod
    def batch_score(self, market_data_batch: Dict[str, MarketData]) -> Dict[str, ScoringResult]:
        """Score plusieurs paires en batch"""
        pass
    
    @abstractmethod
    def get_scoring_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de scoring"""
        pass
    
    @abstractmethod
    def update_scoring_config(self, config: Dict[str, Any]) -> None:
        """Met à jour la configuration de scoring"""
        pass


class IPairFilter(ABC):
    """Interface pour le filtrage des paires"""
    
    @abstractmethod
    def filter_pair(self, symbol: str, market_data: MarketData, scoring_result: ScoringResult) -> PairFilterResult:
        """Filtre une paire selon les critères configurés"""
        pass
    
    @abstractmethod
    def batch_filter(self, data_batch: Dict[str, Tuple[MarketData, ScoringResult]]) -> Dict[str, PairFilterResult]:
        """Filtre plusieurs paires en batch"""
        pass
    
    @abstractmethod
    def update_filter_config(self, config: FilterConfig) -> None:
        """Met à jour la configuration des filtres"""
        pass
    
    @abstractmethod
    def add_custom_filter(self, name: str, filter_func) -> None:
        """Ajoute un filtre personnalisé"""
        pass
    
    @abstractmethod
    def get_filter_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de filtrage"""
        pass


class IScanStep(ABC):
    """Interface pour une étape du pipeline de scan"""
    
    @abstractmethod
    async def execute(self, symbol: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute l'étape du pipeline"""
        pass
    
    @abstractmethod
    def get_step_config(self) -> ScanPipelineStep:
        """Retourne la configuration de l'étape"""
        pass
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """Vérifie si l'étape est activée"""
        pass


class IScanPipeline(ABC):
    """Interface pour le pipeline de scan"""
    
    @abstractmethod
    async def execute_pipeline(self, symbol: str, config: Optional[Dict[str, Any]] = None) -> ScanPipelineResult:
        """Exécute le pipeline complet pour une paire"""
        pass
    
    @abstractmethod
    def add_step(self, step: IScanStep) -> None:
        """Ajoute une étape au pipeline"""
        pass
    
    @abstractmethod
    def remove_step(self, step_name: str) -> None:
        """Supprime une étape du pipeline"""
        pass
    
    @abstractmethod
    def configure_step(self, step_name: str, config: Dict[str, Any]) -> None:
        """Configure une étape spécifique"""
        pass
    
    @abstractmethod
    def get_pipeline_config(self) -> List[ScanPipelineStep]:
        """Retourne la configuration du pipeline"""
        pass
    
    @abstractmethod
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du pipeline"""
        pass


class IScannerOrchestrator(ABC):
    """Interface principale pour l'orchestrateur de scan"""
    
    @abstractmethod
    async def scan_single_pair(self, symbol: str, config: Optional[ScannerConfig] = None) -> ScanResult:
        """Scanne une seule paire"""
        pass
    
    @abstractmethod
    async def scan_batch_pairs(self, symbols: List[str], config: Optional[ScannerConfig] = None) -> ScanBatchResult:
        """Scanne plusieurs paires en parallèle"""
        pass
    
    @abstractmethod
    async def scan_top_pairs(self, limit: int = 20, config: Optional[ScannerConfig] = None) -> ScanBatchResult:
        """Scanne les meilleures paires selon les critères"""
        pass
    
    @abstractmethod
    def get_scan_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques globales de scan"""
        pass
    
    @abstractmethod
    def configure_scanner(self, config: ScannerConfig) -> None:
        """Configure le scanner"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Vérifie la santé du scanner"""
        pass


class IScanLogger(ABC):
    """Interface pour le logging des scans"""
    
    @abstractmethod
    async def log_scan(self, scan_result: ScanResult) -> Optional[str]:
        """Enregistre un résultat de scan"""
        pass
    
    @abstractmethod
    async def log_opportunity(self, scan_result: ScanResult) -> Optional[str]:
        """Enregistre une opportunité détectée"""
        pass
    
    @abstractmethod
    async def log_batch_scan(self, batch_result: ScanBatchResult) -> None:
        """Enregistre un résultat de scan batch"""
        pass
    
    @abstractmethod
    def get_logging_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de logging"""
        pass


# =============================================================================
# UTILITY CLASSES
# =============================================================================

class ScannerValidationUtils:
    """Utilitaires de validation pour le scanner"""
    
    @staticmethod
    def is_valid_symbol(symbol: str) -> bool:
        """Valide un symbole de trading"""
        return (
            isinstance(symbol, str) and
            len(symbol) >= 6 and
            '/' in symbol and
            symbol.replace('/', '').replace(':', '').isalnum()
        )
    
    @staticmethod
    def is_valid_price(price: float) -> bool:
        """Valide un prix"""
        return isinstance(price, (int, float)) and price > 0 and not (price != price)  # not NaN
    
    @staticmethod
    def is_valid_volume(volume: float) -> bool:
        """Valide un volume"""
        return isinstance(volume, (int, float)) and volume >= 0 and not (volume != volume)  # not NaN
    
    @staticmethod
    def is_valid_percentage(percentage: float) -> bool:
        """Valide un pourcentage"""
        return isinstance(percentage, (int, float)) and not (percentage != percentage)  # not NaN
    
    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """Normalise un symbole au format standard"""
        # Convertir BTC/USDT:USDT vers BTCUSDT pour MEXC
        if ':' in symbol:
            symbol = symbol.split(':')[0]
        return symbol.replace('/', '')
    
    @staticmethod
    def validate_market_data(market_data: MarketData) -> List[str]:
        """Valide les données de marché et retourne les erreurs"""
        errors = []
        
        if not ScannerValidationUtils.is_valid_symbol(market_data.symbol):
            errors.append("Invalid symbol")
        
        if market_data.ticker:
            if not ScannerValidationUtils.is_valid_price(market_data.ticker.price):
                errors.append("Invalid ticker price")
            if not ScannerValidationUtils.is_valid_volume(market_data.ticker.volume_24h):
                errors.append("Invalid ticker volume")
        
        if market_data.orderbook:
            if not market_data.orderbook.bids or not market_data.orderbook.asks:
                errors.append("Empty orderbook")
        
        return errors


class ScannerMetricsCollector:
    """Collecteur de métriques pour le scanner"""
    
    def __init__(self):
        self.reset_metrics()
    
    def reset_metrics(self):
        """Remet à zéro toutes les métriques"""
        self.metrics = {
            'total_scans': 0,
            'successful_scans': 0,
            'failed_scans': 0,
            'total_scan_time_ms': 0.0,
            'average_scan_time_ms': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'opportunities_found': 0,
            'pairs_filtered': 0,
            'errors_by_type': {},
            'last_reset': datetime.utcnow()
        }
    
    def record_scan(self, result: ScanResult):
        """Enregistre les métriques d'un scan"""
        self.metrics['total_scans'] += 1
        
        if result.is_success:
            self.metrics['successful_scans'] += 1
        else:
            self.metrics['failed_scans'] += 1
        
        if result.scan_duration_ms > 0:
            self.metrics['total_scan_time_ms'] += result.scan_duration_ms
            self.metrics['average_scan_time_ms'] = (
                self.metrics['total_scan_time_ms'] / self.metrics['total_scans']
            )
        
        if result.is_opportunity:
            self.metrics['opportunities_found'] += 1
        
        # Enregistrer erreurs par type
        for error in result.errors:
            error_type = error.split(':')[0] if ':' in error else 'general'
            self.metrics['errors_by_type'][error_type] = (
                self.metrics['errors_by_type'].get(error_type, 0) + 1
            )
    
    def record_cache_hit(self):
        """Enregistre un cache hit"""
        self.metrics['cache_hits'] += 1
    
    def record_cache_miss(self):
        """Enregistre un cache miss"""
        self.metrics['cache_misses'] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retourne toutes les métriques"""
        cache_total = self.metrics['cache_hits'] + self.metrics['cache_misses']
        cache_hit_rate = (
            self.metrics['cache_hits'] / cache_total if cache_total > 0 else 0
        )
        
        return {
            **self.metrics,
            'cache_hit_rate': cache_hit_rate,
            'success_rate': (
                self.metrics['successful_scans'] / self.metrics['total_scans']
                if self.metrics['total_scans'] > 0 else 0
            ),
            'opportunity_rate': (
                self.metrics['opportunities_found'] / self.metrics['total_scans']
                if self.metrics['total_scans'] > 0 else 0
            )
        }
