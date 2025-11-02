"""
Scanner de scalabilité pour les paires MEXC
Identifie les meilleures paires pour le scalping basé sur:
- Volatilité optimale
- Spread faible
- Volume élevé
- Profondeur du carnet d'ordres
- Balance bid/ask
"""
import asyncio
from typing import List, Dict, Optional, Tuple
import math

from api.mexc import get_mexc_client
from config import TRADING_CONFIG, DEBUG_ENABLED
from utils.logger import get_logger


logger = get_logger()


class ScalabilityScanner:
    """Scanner de scalabilité pour identifier les meilleures paires"""
    
    def __init__(self):
        self.client = get_mexc_client()
        self.is_scanning = False
    
    def calculate_volatility(self, closes: List[float], period: int) -> float:
        """
        Calcul volatilité (écart-type normalisé)
        
        Args:
            closes: Liste des prix de clôture
            period: Période de calcul
            
        Returns:
            Volatilité en %
        """
        if len(closes) < period:
            return 0.0
        
        recent_closes = closes[-period:]
        mean = sum(recent_closes) / len(recent_closes)
        variance = sum((v - mean) ** 2 for v in recent_closes) / len(recent_closes)
        std = math.sqrt(variance)
        
        return (std / mean) * 100 if mean > 0 else 0.0
    
    async def fetch_spread_data(self, symbol: str) -> Dict:
        """
        Récupère spread et profondeur du carnet d'ordres
        
        Args:
            symbol: Symbole de la paire
            
        Returns:
            Dict avec spread, bookDepth, balanceScore
        """
        try:
            orderbook = await self.client.fetch_order_book(symbol, limit=5)
            
            if not orderbook or 'bids' not in orderbook or 'asks' not in orderbook:
                return {'spread': float('nan'), 'bookDepth': 0, 'balanceScore': 0, 'bidVol': 0, 'askVol': 0}
            
            asks = orderbook['asks']
            bids = orderbook['bids']
            
            if not asks or not bids:
                return {'spread': float('nan'), 'bookDepth': 0, 'balanceScore': 0, 'bidVol': 0, 'askVol': 0}
            
            best_ask = float(asks[0][0])
            best_bid = float(bids[0][0])
            
            if not best_ask or not best_bid or best_ask <= 0 or best_bid <= 0:
                return {'spread': float('nan'), 'bookDepth': 0, 'balanceScore': 0, 'bidVol': 0, 'askVol': 0}
            
            # Calcul spread
            mid_price = (best_ask + best_bid) / 2
            spread = ((best_ask - best_bid) / mid_price) * 100
            
            # Calcul profondeur
            ask_vol = sum(float(ask[1]) for ask in asks[:5])
            bid_vol = sum(float(bid[1]) for bid in bids[:5])
            total_vol = ask_vol + bid_vol
            
            # Balance score (0-1): 1 = équilibré, 0 = déséquilibré
            bid_ask_ratio = bid_vol / total_vol if total_vol > 0 else 0.5
            balance_score = 1 - (abs(bid_ask_ratio - 0.5) * 2)
            
            return {
                'spread': spread,
                'bookDepth': total_vol,
                'balanceScore': balance_score,
                'bidVol': bid_vol,
                'askVol': ask_vol
            }
            
        except Exception as e:
            if DEBUG_ENABLED:
                logger.error(f"Erreur spread pour {symbol}: {e}")
            return {'spread': float('nan'), 'bookDepth': 0, 'balanceScore': 0, 'bidVol': 0, 'askVol': 0}
    
    def calculate_score(self, pair: Dict, max_volume: float, max_depth: float) -> float:
        """
        Calcule le score de scalabilité d'une paire
        
        Formula: (volSpreadRatio × log10(volume) × normFactor × balanceBonus)
        
        Args:
            pair: Données de la paire
            max_volume: Volume max normalisé
            max_depth: Profondeur max normalisée
            
        Returns:
            Score de scalabilité
        """
        spread = pair.get('spread', float('nan'))
        vol5 = pair.get('vol5', 0.0)
        recent_volume = pair.get('recentVolume', 0)
        book_depth = pair.get('bookDepth', 0)
        balance_score = pair.get('balanceScore', 0)
        
        # Filtres stricts
        if spread > 0.05 or recent_volume < 100000 or balance_score < TRADING_CONFIG['balance_score_min']:
            return 0.0
        
        # Ratio volatilité/spread (plus élevé = mieux)
        vol_spread_ratio = (vol5 / spread) if (spread > 0 and not math.isnan(spread) and vol5 > 0) else 0.0
        
        # Facteur de normalisation (volume + depth)
        norm_factor = 0.5 * (recent_volume / max_volume) + 0.5 * (book_depth / max_depth)
        
        # Bonus balance
        balance_bonus = balance_score
        
        # Score brut
        raw_score = vol_spread_ratio * math.log10(recent_volume + 1) * norm_factor * balance_bonus
        
        # Retourner score limité
        return round(raw_score, 2) if (math.isfinite(raw_score) and raw_score >= 0) else 0.0
    
    async def scan_pair(self, symbol: str) -> Optional[Dict]:
        """
        Scanne une paire pour calculer ses métriques
        
        Args:
            symbol: Symbole de la paire
            
        Returns:
            Dict avec les métriques ou None si erreur
        """
        try:
            # Récupérer klines 1m
            klines = await self.client.fetch_ohlcv(symbol, '1m', limit=60)
            
            if not klines or len(klines) < 20:
                return None
            
            # Parser klines
            closes = [k[4] for k in klines]  # Close
            volumes = [k[5] for k in klines]  # Volume
            
            # Calculer volatilités
            vol5_recent = sum(volumes[-5:])
            vol5_volatility = self.calculate_volatility(closes, 5)
            vol15_recent = sum(volumes[-15:])
            vol15_volatility = self.calculate_volatility(closes, 15)
            
            # Récupérer spread & depth
            spread_data = await self.fetch_spread_data(symbol)
            
            # Construire objet paire
            pair = {
                'symbol': symbol,
                'price': closes[-1] if closes else 0,
                'recentVolume': vol5_recent,
                'vol5': vol5_volatility,
                'vol15': vol15_volatility,
                'spread': spread_data['spread'],
                'bookDepth': spread_data['bookDepth'],
                'balanceScore': spread_data['balanceScore'],
                'bidVol': spread_data['bidVol'],
                'askVol': spread_data['askVol']
            }
            
            return pair
            
        except Exception as e:
            if DEBUG_ENABLED:
                logger.error(f"Erreur scan pair {symbol}: {e}")
            return None
    
    async def scan_top_pairs(self, n: int = 20) -> List[Dict]:
        """
        Scanne toutes les paires 0% fees et retourne le top N
        
        Args:
            n: Nombre de paires à retourner
            
        Returns:
            Liste des paires triée par score décroissant
        """
        if self.is_scanning:
            logger.warning("Scanner déjà en cours")
            return []
        
        self.is_scanning = True
        
        try:
            logger.info("Recuperation details futures...")
            
            # Récupérer toutes les paires futures USDT
            markets = await self.client.exchange.load_markets()
            futures_pairs = []
            
            for symbol, market in markets.items():
                if market['type'] == 'swap' and market['quote'] == 'USDT':
                    # Vérifier 0% fees
                    maker_fee = market.get('maker', 0)
                    taker_fee = market.get('taker', 0)
                    if maker_fee == 0 and taker_fee == 0:
                        futures_pairs.append({
                            'symbol': symbol,
                            'maker': maker_fee,
                            'taker': taker_fee
                        })
            
            logger.info(f"{len(futures_pairs)} paires 0% fees retrouvees")
            
            # Scanner par batch
            BATCH_SIZE = 5
            total_batches = math.ceil(len(futures_pairs) / BATCH_SIZE)
            
            for i in range(0, len(futures_pairs), BATCH_SIZE):
                batch = futures_pairs[i:i + BATCH_SIZE]
                batch_num = (i // BATCH_SIZE) + 1
                progress = f"{i + 1}-{min(i + BATCH_SIZE, len(futures_pairs))}"
                
                logger.info(f"Batch {batch_num}/{total_batches} ({progress}/{len(futures_pairs)})")
                
                # Scanner en parallèle
                results = await asyncio.gather(*[self.scan_pair(p['symbol']) for p in batch], return_exceptions=True)
                
                # Intégrer résultats
                for j, result in enumerate(results):
                    if isinstance(result, dict) and result:
                        futures_pairs[i + j].update(result)
                    else:
                        # Valeurs par défaut
                        futures_pairs[i + j].update({
                            'recentVolume': 0,
                            'vol5': 0,
                            'vol15': 0,
                            'spread': float('nan'),
                            'bookDepth': 0,
                            'balanceScore': 0,
                            'bidVol': 0,
                            'askVol': 0,
                            'price': 0
                        })
                
                # Petite pause entre batches
                if i + BATCH_SIZE < len(futures_pairs):
                    await asyncio.sleep(0.05)
            
            # Calculer normalisations
            valid_pairs = [p for p in futures_pairs if p.get('recentVolume', 0) > 0]
            max_volume = max([p['recentVolume'] for p in valid_pairs], default=1)
            max_depth = max([p['bookDepth'] for p in valid_pairs], default=1)
            
            # Calculer scores
            for pair in futures_pairs:
                pair['score'] = self.calculate_score(pair, max_volume, max_depth)
            
            # Filtrer et trier
            scored_pairs = [p for p in futures_pairs if p.get('score', 0) > 0]
            scored_pairs.sort(key=lambda x: x['score'], reverse=True)
            top_pairs = scored_pairs[:n]
            
            logger.info(f"{len(top_pairs)} paires scalables classees")
            
            return top_pairs
            
        except Exception as e:
            logger.error(f"Erreur scanner scalabilite: {e}")
            return []
        finally:
            self.is_scanning = False
    
    async def close(self):
        """Ferme les connexions"""
        await self.client.close()

