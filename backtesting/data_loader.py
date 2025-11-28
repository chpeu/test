"""
📥 DATA LOADER - Chargeur de données historiques
Télécharge et stocke données OHLCV pour backtesting

Fonctionnalités :
- Téléchargement depuis MEXC (ccxt)
- Cache local (CSV)
- Multi-timeframes
- Validation données
- Gestion erreurs / rate limits
"""

import ccxt
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import time
import logging
from typing import Optional, List, Dict
import asyncio

logger = logging.getLogger(__name__)


class DataLoader:
    """
    Chargeur de données historiques
    
    Télécharge depuis MEXC et cache en local
    """
    
    def __init__(
        self,
        exchange_id: str = 'mexc',
        cache_dir: str = 'historical_data',
        rate_limit: bool = True
    ):
        """
        Initialiser Data Loader
        
        Args:
            exchange_id: ID exchange ccxt (ex: 'mexc', 'binance')
            cache_dir: Dossier cache
            rate_limit: Respecter rate limits exchange
        """
        self.exchange_id = exchange_id
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Init exchange
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({
            'enableRateLimit': rate_limit,
            'options': {'defaultType': 'swap'}  # Futures
        })
        
        logger.info(f"📥 Data Loader initialisé | Exchange: {exchange_id} | Cache: {cache_dir}")
    
    def download_ohlcv(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = '1m',
        save_to_cache: bool = True
    ) -> pd.DataFrame:
        """
        Télécharger données OHLCV
        
        Args:
            symbol: Symbole (ex: 'BTC/USDT:USDT')
            start_date: Date début (YYYY-MM-DD)
            end_date: Date fin (YYYY-MM-DD)
            timeframe: Timeframe (1m, 5m, 15m, 1h, etc.)
            save_to_cache: Sauvegarder dans cache
        
        Returns:
            DataFrame avec colonnes: timestamp, open, high, low, close, volume
        """
        logger.info(f"📥 Téléchargement: {symbol} | {timeframe} | {start_date} → {end_date}")
        
        # Convertir dates en timestamps
        since = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        until = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
        
        all_ohlcv = []
        current_since = since
        
        try:
            while current_since < until:
                # Télécharger batch (max 1000 candles ccxt)
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=current_since,
                    limit=1000
                )
                
                if not ohlcv:
                    break
                
                all_ohlcv.extend(ohlcv)
                
                # Avancer timestamp
                current_since = ohlcv[-1][0] + 1
                
                # Log progression
                current_date = datetime.fromtimestamp(current_since / 1000).strftime('%Y-%m-%d')
                logger.info(f"  → {len(all_ohlcv)} candles | Progression: {current_date}")
                
                # Rate limit respect
                time.sleep(self.exchange.rateLimit / 1000 if self.exchange.enableRateLimit else 0.1)
            
            # Convertir en DataFrame
            df = pd.DataFrame(
                all_ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Convertir timestamp en datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Filtrer période exacte
            df = df[
                (df['timestamp'] >= start_date) &
                (df['timestamp'] <= end_date)
            ]
            
            logger.info(f"✅ {len(df)} candles téléchargées | {symbol} {timeframe}")
            
            # Sauvegarder cache
            if save_to_cache and not df.empty:
                self._save_to_cache(df, symbol, start_date, end_date, timeframe)
            
            return df
        
        except Exception as e:
            logger.error(f"❌ Erreur téléchargement {symbol}: {e}")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    def load_from_cache(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = '1m'
    ) -> Optional[pd.DataFrame]:
        """
        Charger données depuis cache
        
        Args:
            symbol: Symbole
            start_date: Date début
            end_date: Date fin
            timeframe: Timeframe
        
        Returns:
            DataFrame si trouvé, None sinon
        """
        filename = self._get_cache_filename(symbol, start_date, end_date, timeframe)
        filepath = self.cache_dir / filename
        
        if filepath.exists():
            try:
                df = pd.read_csv(filepath)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                logger.info(f"✅ Chargé depuis cache: {filename} | {len(df)} candles")
                return df
            except Exception as e:
                logger.error(f"❌ Erreur lecture cache {filename}: {e}")
                return None
        else:
            logger.warning(f"⚠️ Cache non trouvé: {filename}")
            return None
    
    def get_or_download(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = '1m'
    ) -> pd.DataFrame:
        """
        Charger depuis cache ou télécharger si absent
        
        Args:
            symbol: Symbole
            start_date: Date début
            end_date: Date fin
            timeframe: Timeframe
        
        Returns:
            DataFrame
        """
        # Essayer cache d'abord
        df = self.load_from_cache(symbol, start_date, end_date, timeframe)
        
        if df is not None and not df.empty:
            return df
        
        # Télécharger
        return self.download_ohlcv(symbol, start_date, end_date, timeframe)
    
    def download_multiple_symbols(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        timeframe: str = '1m'
    ) -> Dict[str, pd.DataFrame]:
        """
        Télécharger plusieurs symboles
        
        Args:
            symbols: Liste symboles
            start_date: Date début
            end_date: Date fin
            timeframe: Timeframe
        
        Returns:
            Dict {symbol: DataFrame}
        """
        logger.info(f"📥 Téléchargement batch: {len(symbols)} symboles | {start_date} → {end_date}")
        
        results = {}
        
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"\n[{i}/{len(symbols)}] {symbol}")
            
            df = self.get_or_download(symbol, start_date, end_date, timeframe)
            
            if not df.empty:
                results[symbol] = df
            
            # Pause entre symboles
            time.sleep(1)
        
        logger.info(f"✅ {len(results)}/{len(symbols)} symboles téléchargés")
        
        return results
    
    def _save_to_cache(
        self,
        df: pd.DataFrame,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str
    ):
        """Sauvegarder DataFrame dans cache"""
        filename = self._get_cache_filename(symbol, start_date, end_date, timeframe)
        filepath = self.cache_dir / filename
        
        try:
            df.to_csv(filepath, index=False)
            logger.info(f"💾 Sauvegardé: {filename}")
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde cache: {e}")
    
    def _get_cache_filename(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str
    ) -> str:
        """Générer nom fichier cache"""
        safe_symbol = symbol.replace('/', '_').replace(':', '_')
        return f"{safe_symbol}_{timeframe}_{start_date}_{end_date}.csv"
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Valider données
        
        Args:
            df: DataFrame à valider
        
        Returns:
            True si valide, False sinon
        """
        if df.empty:
            logger.warning("⚠️ DataFrame vide")
            return False
        
        # Vérifier colonnes requises
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing = set(required_cols) - set(df.columns)
        if missing:
            logger.error(f"❌ Colonnes manquantes: {missing}")
            return False
        
        # Vérifier valeurs nulles
        if df[required_cols].isnull().any().any():
            logger.warning("⚠️ Valeurs nulles détectées")
            return False
        
        # Vérifier high >= low
        invalid_candles = df[df['high'] < df['low']]
        if not invalid_candles.empty:
            logger.warning(f"⚠️ {len(invalid_candles)} candles invalides (high < low)")
            return False
        
        # Vérifier duplicates timestamp
        duplicates = df[df['timestamp'].duplicated()]
        if not duplicates.empty:
            logger.warning(f"⚠️ {len(duplicates)} timestamps dupliqués")
            return False
        
        logger.info(f"✅ Données valides: {len(df)} candles")
        return True
    
    def get_available_symbols(self) -> List[str]:
        """
        Obtenir liste symboles disponibles sur exchange
        
        Returns:
            Liste symboles futures USDT
        """
        try:
            markets = self.exchange.load_markets()
            
            # Filtrer futures USDT
            futures_symbols = [
                symbol for symbol, market in markets.items()
                if market.get('type') == 'swap' and 'USDT' in symbol
            ]
            
            logger.info(f"✅ {len(futures_symbols)} symboles futures USDT disponibles")
            
            return sorted(futures_symbols)
        
        except Exception as e:
            logger.error(f"❌ Erreur récupération symboles: {e}")
            return []


# ==================== CLI HELPER ====================

def download_data_cli():
    """CLI pour télécharger données"""
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python data_loader.py <symbol> <start_date> <end_date> [timeframe]")
        print("Ex: python data_loader.py BTC/USDT:USDT 2025-01-01 2025-02-01 1m")
        sys.exit(1)
    
    symbol = sys.argv[1]
    start_date = sys.argv[2]
    end_date = sys.argv[3]
    timeframe = sys.argv[4] if len(sys.argv) > 4 else '1m'
    
    loader = DataLoader()
    df = loader.download_ohlcv(symbol, start_date, end_date, timeframe)
    
    if not df.empty:
        print(f"\n✅ Téléchargé: {len(df)} candles")
        print(df.head())
        print(f"\nSauvegardé dans: historical_data/")
    else:
        print("❌ Échec téléchargement")


if __name__ == '__main__':
    download_data_cli()

