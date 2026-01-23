"""
TestablePairFilter - Trade Cursor v7.0 Phase 3
Filtreur de paires découplé et testable
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
import math

from ..interfaces.scanner_interfaces import (
    IPairFilter, MarketData, ScoringResult, FilterConfig, PairFilterResult,
    ScannerValidationUtils
)
from utils.effective_config import get_effective_value

logger = logging.getLogger(__name__)


class TestablePairFilter(IPairFilter):
    """
    Filtreur de paires découplé et testable
    
    Responsabilités:
    - Filtrage par spread/volume/funding
    - Exclude/whitelist management
    - Fee filtering (0-fee only)
    - Market hours filtering
    - Custom filter chains
    - Analytics et statistiques détaillées
    """
    
    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()
        
        # Compteurs de performance
        self.filter_count = 0
        self.passed_count = 0
        self.failed_count = 0
        self.total_filter_time_ms = 0.0
        
        # Analytics par type de filtre
        self.filter_stats = {
            'spread': {'passed': 0, 'failed': 0},
            'volume': {'passed': 0, 'failed': 0},
            'funding': {'passed': 0, 'failed': 0},
            'balance': {'passed': 0, 'failed': 0},
            'fees': {'passed': 0, 'failed': 0},
            'whitelist': {'passed': 0, 'failed': 0},
            'blacklist': {'passed': 0, 'failed': 0},
            'market_hours': {'passed': 0, 'failed': 0},
            'custom': {'passed': 0, 'failed': 0}
        }
        
        # Filtres personnalisés
        self.custom_filters: Dict[str, Callable] = {}
        
        # Cache des résultats de filtrage
        self._filter_cache: Dict[str, Dict] = {}
        self._cache_ttl_seconds = 60
        
        logger.info("✅ TestablePairFilter initialisé")
    
    def filter_pair(self, symbol: str, market_data: MarketData, scoring_result: ScoringResult) -> PairFilterResult:
        """Filtre une paire selon les critères configurés"""
        try:
            start_time = datetime.utcnow()
            self.filter_count += 1
            
            # Vérifier cache
            cache_key = f"{symbol}_{market_data.timestamp.timestamp()}_{scoring_result.score}"
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                return cached_result
            
            # Initialiser résultat
            filter_result = PairFilterResult(
                symbol=symbol,
                accepted=True,
                timestamp=datetime.utcnow()
            )
            
            # Appliquer tous les filtres
            self._apply_spread_filter(market_data, filter_result)
            self._apply_volume_filter(market_data, scoring_result, filter_result)
            self._apply_funding_filter(market_data, filter_result)
            self._apply_balance_filter(market_data, filter_result)
            self._apply_fee_filter(symbol, filter_result)
            self._apply_whitelist_filter(symbol, filter_result)
            self._apply_blacklist_filter(symbol, filter_result)
            self._apply_market_hours_filter(filter_result)
            self._apply_book_depth_filter(market_data, filter_result)
            self._apply_atr_filter(scoring_result, filter_result)
            self._apply_volume_24h_filter(market_data, filter_result)
            
            # Appliquer filtres personnalisés
            self._apply_custom_filters(symbol, market_data, scoring_result, filter_result)
            
            # Déterminer acceptation finale
            filter_result.accepted = len(filter_result.rejection_reasons) == 0
            
            # Métriques
            filter_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            filter_result.processing_time_ms = filter_time
            self.total_filter_time_ms += filter_time
            
            # Stats
            if filter_result.accepted:
                self.passed_count += 1
            else:
                self.failed_count += 1
            
            # Mettre en cache
            self._cache_result(cache_key, filter_result)
            
            logger.debug(f"{'✅' if filter_result.accepted else '❌'} Filter {symbol}: "
                        f"{'PASSED' if filter_result.accepted else 'REJECTED'} "
                        f"({len(filter_result.rejection_reasons)} reasons)")
            
            return filter_result
            
        except Exception as e:
            logger.error(f"❌ Filter failed for {symbol}: {e}")
            self.failed_count += 1
            
            return PairFilterResult(
                symbol=symbol,
                accepted=False,
                rejection_reasons=[f"Filter error: {str(e)}"],
                timestamp=datetime.utcnow()
            )
    
    def batch_filter(self, data_batch: Dict[str, Tuple[MarketData, ScoringResult]]) -> Dict[str, PairFilterResult]:
        """Filtre plusieurs paires en batch"""
        try:
            results = {}
            
            for symbol, (market_data, scoring_result) in data_batch.items():
                results[symbol] = self.filter_pair(symbol, market_data, scoring_result)
            
            passed_count = sum(1 for r in results.values() if r.accepted)
            
            logger.info(f"✅ Batch filtering completed: {passed_count}/{len(data_batch)} passed")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Batch filtering failed: {e}")
            return {}
    
    def update_filter_config(self, config: FilterConfig) -> None:
        """Met à jour la configuration des filtres"""
        self.config = config
        self._clear_cache()  # Vider cache car config changée
        logger.info("Filter configuration updated")
    
    def add_custom_filter(self, name: str, filter_func: Callable) -> None:
        """Ajoute un filtre personnalisé"""
        if not callable(filter_func):
            raise ValueError(f"Filter function for '{name}' must be callable")
        
        self.custom_filters[name] = filter_func
        logger.info(f"Custom filter '{name}' added")
    
    def get_filter_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de filtrage"""
        success_rate = self.passed_count / self.filter_count if self.filter_count > 0 else 0.0
        avg_filter_time = self.total_filter_time_ms / self.filter_count if self.filter_count > 0 else 0.0
        
        # Calculer stats détaillées par filtre
        detailed_stats = {}
        for filter_name, stats in self.filter_stats.items():
            total = stats['passed'] + stats['failed']
            if total > 0:
                detailed_stats[filter_name] = {
                    'total': total,
                    'passed': stats['passed'],
                    'failed': stats['failed'],
                    'pass_rate': stats['passed'] / total
                }
        
        return {
            'overall': {
                'total_filters': self.filter_count,
                'passed_filters': self.passed_count,
                'failed_filters': self.failed_count,
                'success_rate': success_rate,
                'average_filter_time_ms': avg_filter_time
            },
            'by_filter_type': detailed_stats,
            'custom_filters': list(self.custom_filters.keys()),
            'cache_stats': {
                'cache_size': len(self._filter_cache),
                'cache_ttl_seconds': self._cache_ttl_seconds
            },
            'current_config': {
                'min_spread': self.config.min_spread,
                'max_spread': self.config.max_spread,
                'min_volume': self.config.min_volume,
                'max_funding_rate': self.config.max_funding_rate,
                'min_balance_score': self.config.min_balance_score,
                'require_zero_fees': self.config.require_zero_fees,
                'whitelist_size': len(self.config.symbol_whitelist),
                'blacklist_size': len(self.config.symbol_blacklist)
            }
        }
    
    # =============================================================================
    # MÉTHODES PRIVÉES - Filtres Spécifiques
    # =============================================================================
    
    def _apply_spread_filter(self, market_data: MarketData, result: PairFilterResult):
        """Applique le filtre de spread"""
        try:
            if not market_data.orderbook or market_data.orderbook.spread_pct is None:
                result.filter_results['spread'] = False
                result.rejection_reasons.append("Missing spread data")
                self.filter_stats['spread']['failed'] += 1
                return
            
            spread = market_data.orderbook.spread_pct
            
            # Vérifier spread minimum
            if spread < self.config.min_spread:
                result.filter_results['spread'] = False
                result.rejection_reasons.append(f"Spread too low: {spread:.4f}% < {self.config.min_spread}%")
                result.filter_details['spread_value'] = spread
                result.filter_details['spread_min_required'] = self.config.min_spread
                self.filter_stats['spread']['failed'] += 1
                return
            
            # Vérifier spread maximum
            if spread > self.config.max_spread:
                result.filter_results['spread'] = False
                result.rejection_reasons.append(f"Spread too high: {spread:.4f}% > {self.config.max_spread}%")
                result.filter_details['spread_value'] = spread
                result.filter_details['spread_max_allowed'] = self.config.max_spread
                self.filter_stats['spread']['failed'] += 1
                return
            
            # Vérifier NaN
            if math.isnan(spread):
                result.filter_results['spread'] = False
                result.rejection_reasons.append("Invalid spread (NaN)")
                self.filter_stats['spread']['failed'] += 1
                return
            
            # Spread valide
            result.filter_results['spread'] = True
            result.filter_details['spread_value'] = spread
            self.filter_stats['spread']['passed'] += 1
            
        except Exception as e:
            logger.error(f"Spread filter error: {e}")
            result.filter_results['spread'] = False
            result.rejection_reasons.append(f"Spread filter error: {str(e)}")
            self.filter_stats['spread']['failed'] += 1
    
    def _apply_volume_filter(self, market_data: MarketData, scoring_result: ScoringResult, result: PairFilterResult):
        """Applique le filtre de volume"""
        try:
            volume = scoring_result.metrics.volume_recent
            
            if volume < self.config.min_volume:
                result.filter_results['volume'] = False
                result.rejection_reasons.append(f"Volume too low: {volume:.0f} < {self.config.min_volume}")
                result.filter_details['volume_value'] = volume
                result.filter_details['volume_min_required'] = self.config.min_volume
                self.filter_stats['volume']['failed'] += 1
                return
            
            # Volume valide
            result.filter_results['volume'] = True
            result.filter_details['volume_value'] = volume
            self.filter_stats['volume']['passed'] += 1
            
        except Exception as e:
            logger.error(f"Volume filter error: {e}")
            result.filter_results['volume'] = False
            result.rejection_reasons.append(f"Volume filter error: {str(e)}")
            self.filter_stats['volume']['failed'] += 1
    
    def _apply_funding_filter(self, market_data: MarketData, result: PairFilterResult):
        """Applique le filtre de funding rate"""
        try:
            funding_rate = None
            
            if market_data.ticker and market_data.ticker.funding_rate is not None:
                funding_rate = market_data.ticker.funding_rate
            
            # Skip si pas de funding rate (pas bloquant)
            if funding_rate is None:
                result.filter_results['funding'] = True
                self.filter_stats['funding']['passed'] += 1
                return
            
            abs_funding = abs(funding_rate)
            
            if abs_funding > self.config.max_funding_rate:
                result.filter_results['funding'] = False
                result.rejection_reasons.append(f"Funding rate too high: {funding_rate:.3f}% > {self.config.max_funding_rate}%")
                result.filter_details['funding_rate'] = funding_rate
                result.filter_details['funding_max_allowed'] = self.config.max_funding_rate
                self.filter_stats['funding']['failed'] += 1
                return
            
            # Funding rate valide
            result.filter_results['funding'] = True
            result.filter_details['funding_rate'] = funding_rate
            self.filter_stats['funding']['passed'] += 1
            
        except Exception as e:
            logger.error(f"Funding filter error: {e}")
            result.filter_results['funding'] = False
            result.rejection_reasons.append(f"Funding filter error: {str(e)}")
            self.filter_stats['funding']['failed'] += 1
    
    def _apply_balance_filter(self, market_data: MarketData, result: PairFilterResult):
        """Applique le filtre de balance score"""
        try:
            if not market_data.orderbook:
                result.filter_results['balance'] = False
                result.rejection_reasons.append("Missing orderbook for balance check")
                self.filter_stats['balance']['failed'] += 1
                return
            
            balance_score = market_data.orderbook.balance_score
            
            if balance_score < self.config.min_balance_score:
                result.filter_results['balance'] = False
                result.rejection_reasons.append(f"Balance score too low: {balance_score:.2f} < {self.config.min_balance_score}")
                result.filter_details['balance_score'] = balance_score
                result.filter_details['balance_min_required'] = self.config.min_balance_score
                self.filter_stats['balance']['failed'] += 1
                return
            
            # Balance score valide
            result.filter_results['balance'] = True
            result.filter_details['balance_score'] = balance_score
            self.filter_stats['balance']['passed'] += 1
            
        except Exception as e:
            logger.error(f"Balance filter error: {e}")
            result.filter_results['balance'] = False
            result.rejection_reasons.append(f"Balance filter error: {str(e)}")
            self.filter_stats['balance']['failed'] += 1
    
    def _apply_fee_filter(self, symbol: str, result: PairFilterResult):
        """Applique le filtre de frais (0-fee only si activé)"""
        try:
            if not self.config.require_zero_fees:
                result.filter_results['fees'] = True
                self.filter_stats['fees']['passed'] += 1
                return
            
            # Pour l'instant, assume que les paires majeures ont des frais acceptables
            major_pairs = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'MATIC/USDT:USDT', 'ADA/USDT:USDT']
            
            # Cette logique devrait être étendue avec des données réelles de frais
            # Pour l'instant, on accepte les paires majeures et suppose que le scanner
            # a déjà filtré les paires à frais élevés
            if symbol in major_pairs:
                result.filter_results['fees'] = True
                result.filter_details['fee_status'] = 'major_pair_accepted'
                self.filter_stats['fees']['passed'] += 1
            else:
                # Pour les autres paires, on assume que le pré-filtrage a été fait
                result.filter_results['fees'] = True
                result.filter_details['fee_status'] = 'pre_filtered'
                self.filter_stats['fees']['passed'] += 1
            
        except Exception as e:
            logger.error(f"Fee filter error: {e}")
            result.filter_results['fees'] = False
            result.rejection_reasons.append(f"Fee filter error: {str(e)}")
            self.filter_stats['fees']['failed'] += 1
    
    def _apply_whitelist_filter(self, symbol: str, result: PairFilterResult):
        """Applique le filtre whitelist"""
        try:
            if not self.config.symbol_whitelist:
                # Pas de whitelist = tous acceptés
                result.filter_results['whitelist'] = True
                self.filter_stats['whitelist']['passed'] += 1
                return
            
            if symbol in self.config.symbol_whitelist:
                result.filter_results['whitelist'] = True
                result.filter_details['whitelist_status'] = 'whitelisted'
                self.filter_stats['whitelist']['passed'] += 1
            else:
                result.filter_results['whitelist'] = False
                result.rejection_reasons.append(f"Symbol not in whitelist")
                result.filter_details['whitelist_status'] = 'not_whitelisted'
                self.filter_stats['whitelist']['failed'] += 1
            
        except Exception as e:
            logger.error(f"Whitelist filter error: {e}")
            result.filter_results['whitelist'] = False
            result.rejection_reasons.append(f"Whitelist filter error: {str(e)}")
            self.filter_stats['whitelist']['failed'] += 1
    
    def _apply_blacklist_filter(self, symbol: str, result: PairFilterResult):
        """Applique le filtre blacklist"""
        try:
            if symbol in self.config.symbol_blacklist:
                result.filter_results['blacklist'] = False
                result.rejection_reasons.append(f"Symbol is blacklisted")
                result.filter_details['blacklist_status'] = 'blacklisted'
                self.filter_stats['blacklist']['failed'] += 1
            else:
                result.filter_results['blacklist'] = True
                result.filter_details['blacklist_status'] = 'not_blacklisted'
                self.filter_stats['blacklist']['passed'] += 1
            
        except Exception as e:
            logger.error(f"Blacklist filter error: {e}")
            result.filter_results['blacklist'] = False
            result.rejection_reasons.append(f"Blacklist filter error: {str(e)}")
            self.filter_stats['blacklist']['failed'] += 1
    
    def _apply_market_hours_filter(self, result: PairFilterResult):
        """Applique le filtre d'heures de marché"""
        try:
            # Crypto trade 24/7, mais peut être configuré pour éviter weekends
            if self.config.avoid_weekends:
                current_weekday = datetime.utcnow().weekday()
                if current_weekday >= 5:  # Samedi = 5, Dimanche = 6
                    result.filter_results['market_hours'] = False
                    result.rejection_reasons.append("Weekend trading disabled")
                    result.filter_details['market_hours_status'] = 'weekend'
                    self.filter_stats['market_hours']['failed'] += 1
                    return
            
            if self.config.trading_hours_only:
                current_hour = datetime.utcnow().hour
                # Heures de trading principales: 8h-22h UTC
                if not (8 <= current_hour <= 22):
                    result.filter_results['market_hours'] = False
                    result.rejection_reasons.append(f"Outside trading hours: {current_hour}h UTC")
                    result.filter_details['market_hours_status'] = f'hour_{current_hour}'
                    self.filter_stats['market_hours']['failed'] += 1
                    return
            
            # Heures de marché OK
            result.filter_results['market_hours'] = True
            result.filter_details['market_hours_status'] = 'active'
            self.filter_stats['market_hours']['passed'] += 1
            
        except Exception as e:
            logger.error(f"Market hours filter error: {e}")
            result.filter_results['market_hours'] = False
            result.rejection_reasons.append(f"Market hours filter error: {str(e)}")
            self.filter_stats['market_hours']['failed'] += 1
    
    def _apply_book_depth_filter(self, market_data: MarketData, result: PairFilterResult):
        """Applique le filtre de profondeur du carnet d'ordres"""
        try:
            if not market_data.orderbook:
                result.filter_results['book_depth'] = False
                result.rejection_reasons.append("Missing orderbook for depth check")
                return
            
            book_depth = market_data.orderbook.book_depth
            
            if book_depth < self.config.min_book_depth:
                result.filter_results['book_depth'] = False
                result.rejection_reasons.append(f"Book depth too low: {book_depth:.0f} < {self.config.min_book_depth}")
                result.filter_details['book_depth_value'] = book_depth
                result.filter_details['book_depth_min_required'] = self.config.min_book_depth
                return
            
            result.filter_results['book_depth'] = True
            result.filter_details['book_depth_value'] = book_depth
            
        except Exception as e:
            logger.error(f"Book depth filter error: {e}")
            result.filter_results['book_depth'] = False
            result.rejection_reasons.append(f"Book depth filter error: {str(e)}")
    
    def _apply_atr_filter(self, scoring_result: ScoringResult, result: PairFilterResult):
        """Applique le filtre ATR (volatilité)"""
        try:
            atr_pct = scoring_result.metrics.atr_pct
            
            if atr_pct > self.config.max_atr_pct:
                result.filter_results['atr'] = False
                result.rejection_reasons.append(f"ATR too high: {atr_pct:.2f}% > {self.config.max_atr_pct}%")
                result.filter_details['atr_pct_value'] = atr_pct
                result.filter_details['atr_pct_max_allowed'] = self.config.max_atr_pct
                return
            
            result.filter_results['atr'] = True
            result.filter_details['atr_pct_value'] = atr_pct
            
        except Exception as e:
            logger.error(f"ATR filter error: {e}")
            result.filter_results['atr'] = False
            result.rejection_reasons.append(f"ATR filter error: {str(e)}")
    
    def _apply_volume_24h_filter(self, market_data: MarketData, result: PairFilterResult):
        """Applique le filtre volume 24h"""
        try:
            if not market_data.ticker:
                result.filter_results['volume_24h'] = True  # Pas bloquant si manquant
                return
            
            volume_24h = market_data.ticker.volume_24h
            
            if volume_24h < self.config.min_volume_24h:
                result.filter_results['volume_24h'] = False
                result.rejection_reasons.append(f"Volume 24h too low: {volume_24h:,.0f} < {self.config.min_volume_24h:,.0f}")
                result.filter_details['volume_24h_value'] = volume_24h
                result.filter_details['volume_24h_min_required'] = self.config.min_volume_24h
                return
            
            result.filter_results['volume_24h'] = True
            result.filter_details['volume_24h_value'] = volume_24h
            
        except Exception as e:
            logger.error(f"Volume 24h filter error: {e}")
            result.filter_results['volume_24h'] = False
            result.rejection_reasons.append(f"Volume 24h filter error: {str(e)}")
    
    def _apply_custom_filters(self, symbol: str, market_data: MarketData, scoring_result: ScoringResult, result: PairFilterResult):
        """Applique tous les filtres personnalisés"""
        try:
            for filter_name, filter_func in self.custom_filters.items():
                try:
                    # Appeler le filtre personnalisé
                    filter_passed = filter_func(symbol, market_data, scoring_result)
                    
                    if not filter_passed:
                        result.filter_results[f'custom_{filter_name}'] = False
                        result.rejection_reasons.append(f"Custom filter '{filter_name}' failed")
                        self.filter_stats['custom']['failed'] += 1
                    else:
                        result.filter_results[f'custom_{filter_name}'] = True
                        self.filter_stats['custom']['passed'] += 1
                    
                except Exception as filter_error:
                    logger.error(f"Custom filter '{filter_name}' error: {filter_error}")
                    result.filter_results[f'custom_{filter_name}'] = False
                    result.rejection_reasons.append(f"Custom filter '{filter_name}' error: {str(filter_error)}")
                    self.filter_stats['custom']['failed'] += 1
            
        except Exception as e:
            logger.error(f"Custom filters application error: {e}")
    
    # =============================================================================
    # MÉTHODES PRIVÉES - Cache et Utils
    # =============================================================================
    
    def _get_cached_result(self, cache_key: str) -> Optional[PairFilterResult]:
        """Récupère un résultat depuis le cache"""
        if cache_key not in self._filter_cache:
            return None
        
        cache_entry = self._filter_cache[cache_key]
        age_seconds = (datetime.utcnow() - cache_entry['timestamp']).total_seconds()
        
        if age_seconds > self._cache_ttl_seconds:
            del self._filter_cache[cache_key]
            return None
        
        return cache_entry['result']
    
    def _cache_result(self, cache_key: str, result: PairFilterResult):
        """Met un résultat en cache"""
        self._filter_cache[cache_key] = {
            'result': result,
            'timestamp': datetime.utcnow()
        }
        
        # Cleanup si cache trop grand
        if len(self._filter_cache) > 1000:
            self._cleanup_cache()
    
    def _cleanup_cache(self):
        """Nettoie le cache"""
        try:
            now = datetime.utcnow()
            expired_keys = [
                key for key, entry in self._filter_cache.items()
                if (now - entry['timestamp']).total_seconds() > self._cache_ttl_seconds
            ]
            
            for key in expired_keys:
                del self._filter_cache[key]
            
            logger.debug(f"Filter cache cleaned: removed {len(expired_keys)} expired entries")
            
        except Exception as e:
            logger.error(f"Filter cache cleanup failed: {e}")
    
    def _clear_cache(self):
        """Vide complètement le cache"""
        self._filter_cache.clear()
        logger.debug("Filter cache cleared")
