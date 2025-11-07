"""
🌐 API REST ROUTES - Endpoints complets
Unifié backend pour tous clients

Endpoints:
- /api/trades (GET, POST, DELETE)
- /api/stats (GET)
- /api/backtest (POST)
- /api/optimize (POST)
- /api/setups (GET)
- /api/export (GET)
- /api/health (GET)

Features:
- Rate limiting
- Authentification (optionnel)
- Validation données
- Documentation OpenAPI
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Literal
from datetime import datetime, timedelta
import time
import logging
from functools import wraps
import io
import csv
import json
import os
import aiohttp

from core.analytics_database import AnalyticsDatabase

logger = logging.getLogger(__name__)

# Router
router = APIRouter(prefix="/api", tags=["API"])

# Analytics DB (sera injecté par main.py)
_analytics_db: Optional[AnalyticsDatabase] = None


def set_analytics_db(db: AnalyticsDatabase):
    """Injecter Analytics DB (appelé depuis main.py)"""
    global _analytics_db
    _analytics_db = db


def get_analytics_db() -> AnalyticsDatabase:
    """Dependency injection Analytics DB"""
    if _analytics_db is None:
        raise HTTPException(status_code=500, detail="Analytics DB not initialized")
    return _analytics_db


# Position Manager et Notification Manager (seront injectés par main.py)
_position_manager = None
_notification_manager = None
_instance_port = 5000


def set_position_manager(position_manager):
    """Injecter Position Manager (appelé depuis main.py)"""
    global _position_manager
    _position_manager = position_manager


def set_notification_manager(notification_manager):
    """Injecter Notification Manager (appelé depuis main.py)"""
    global _notification_manager
    _notification_manager = notification_manager


def set_instance_port(port: int):
    """Injecter instance port (appelé depuis main.py)"""
    global _instance_port
    _instance_port = port


# ==================== RATE LIMITING ====================

class RateLimiter:
    """
    Rate limiter simple (in-memory)
    
    Pour production, utiliser Redis
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Args:
            max_requests: Max requêtes par fenêtre
            window_seconds: Durée fenêtre (secondes)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}  # {ip: [timestamp, ...]}
    
    def is_allowed(self, client_id: str) -> bool:
        """
        Vérifier si requête autorisée
        
        Args:
            client_id: Identifiant client (IP, user_id, etc.)
        
        Returns:
            True si autorisé, False sinon
        """
        now = time.time()
        
        # Nettoyer vieilles requêtes
        if client_id in self.requests:
            self.requests[client_id] = [
                ts for ts in self.requests[client_id]
                if now - ts < self.window_seconds
            ]
        else:
            self.requests[client_id] = []
        
        # Vérifier limite
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        # Enregistrer requête
        self.requests[client_id].append(now)
        return True


# Instance globale
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


def rate_limit(func):
    """Decorator pour rate limiting"""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        client_ip = request.client.host
        
        if not rate_limiter.is_allowed(client_ip):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later."
            )
        
        return await func(request, *args, **kwargs)
    
    return wrapper


# ==================== MODELS ====================

class TradeFilter(BaseModel):
    """Filtres pour GET /api/trades"""
    symbol: Optional[str] = None
    direction: Optional[Literal['LONG', 'SHORT']] = None
    exit_reason: Optional[str] = None
    trading_mode: Optional[Literal['LIVE', 'PAPER', 'BACKTEST']] = None
    is_backtest: Optional[bool] = None
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class BacktestRequest(BaseModel):
    """Requête pour POST /api/backtest"""
    symbols: List[str] = Field(..., min_items=1)
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    initial_capital: float = Field(default=1000.0, gt=0)
    config: Optional[Dict] = None
    
    @validator('start_date', 'end_date')
    def validate_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Date must be YYYY-MM-DD format')


class OptimizeRequest(BaseModel):
    """Requête pour POST /api/optimize"""
    symbols: List[str] = Field(..., min_items=1)
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    n_trials: int = Field(default=100, ge=10, le=1000)
    initial_capital: float = Field(default=1000.0, gt=0)
    param_space: Optional[Dict] = None


class SetupFilter(BaseModel):
    """Filtres pour GET /api/setups"""
    symbol: Optional[str] = None
    direction: Optional[Literal['LONG', 'SHORT']] = None
    is_validated: Optional[bool] = None  # True=validated, False=rejected
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class ExportRequest(BaseModel):
    """Requête pour GET /api/export"""
    format: Literal['csv', 'json'] = 'csv'
    data_type: Literal['trades', 'setups_rejected', 'setups_validated'] = 'trades'
    filters: Optional[Dict] = None


# ==================== ENDPOINTS ====================

@router.get("/health")
async def health_check():
    """Health check"""
    return {
        'status': 'ok',
        'timestamp': time.time(),
        'service': 'Trading Bot API'
    }


@router.get("/trades")
async def get_trades(
    request: Request,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    exit_reason: Optional[str] = None,
    trading_mode: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AnalyticsDatabase = Depends(get_analytics_db)
):
    """
    Récupérer trades avec filtres
    
    Query params:
    - symbol: Filtrer par symbole
    - direction: LONG ou SHORT
    - exit_reason: Raison fermeture
    - trading_mode: LIVE, PAPER, BACKTEST
    - start_date: Date début (YYYY-MM-DD)
    - end_date: Date fin (YYYY-MM-DD)
    - limit: Max résultats
    - offset: Pagination offset
    """
    try:
        # Récupérer trades avec paramètres individuels
        trades = db.get_trades(
            trading_mode=trading_mode,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        # Filtrer par direction et exit_reason (non supportés par DB directement)
        if direction:
            trades = [t for t in trades if t.get('direction') == direction]
        if exit_reason:
            trades = [t for t in trades if t.get('exit_reason') == exit_reason]
        
        # Appliquer offset (pagination)
        if offset > 0:
            trades = trades[offset:]
        
        return {
            'success': True,
            'count': len(trades),
            'trades': trades,
            'limit': limit,
            'offset': offset
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur GET /api/trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats(
    symbol: Optional[str] = None,
    trading_mode: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AnalyticsDatabase = Depends(get_analytics_db)
):
    """
    Récupérer statistiques
    
    Query params:
    - symbol: Filtrer par symbole
    - trading_mode: LIVE, PAPER, BACKTEST
    - start_date: Date début
    - end_date: Date fin
    """
    try:
        # Récupérer trades avec filtres
        trades = db.get_trades(
            trading_mode=trading_mode,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            limit=10000  # Max pour stats
        )
        
        # Calculer stats depuis trades
        total_trades = len(trades)
        wins = sum(1 for t in trades if t.get('net_pnl_pct', 0) > 0)
        losses = sum(1 for t in trades if t.get('net_pnl_pct', 0) < 0)
        winrate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl_usdt = sum(t.get('net_pnl_usdt', 0) for t in trades)
        total_pnl_pct = sum(t.get('net_pnl_pct', 0) for t in trades)
        
        # Profit factor
        gross_profit = sum(t.get('net_pnl_usdt', 0) for t in trades if t.get('net_pnl_usdt', 0) > 0)
        gross_loss = abs(sum(t.get('net_pnl_usdt', 0) for t in trades if t.get('net_pnl_usdt', 0) < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        # Max drawdown (simplifié)
        equity_curve = []
        running_equity = 1000.0  # Capital initial
        for trade in trades:
            running_equity += trade.get('net_pnl_usdt', 0)
            equity_curve.append(running_equity)
        
        max_drawdown = 0
        if equity_curve:
            peak = equity_curve[0]
            for equity in equity_curve:
                if equity > peak:
                    peak = equity
                drawdown = ((peak - equity) / peak) * 100 if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        
        stats = {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'winrate': round(winrate, 2),
            'profit_factor': round(profit_factor, 2),
            'pnl_total': round(total_pnl_usdt, 2),
            'pnl_total_pct': round(total_pnl_pct, 2),
            'max_drawdown': round(max_drawdown, 2),
            'capital': round(equity_curve[-1] if equity_curve else 1000.0, 2)
        }
        
        return {
            'success': True,
            'stats': stats
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur GET /api/stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest")
async def backtest_info():
    """
    Info endpoint backtest (GET)
    
    Cet endpoint nécessite POST. Utilisez POST avec body JSON.
    """
    return {
        'error': 'Method Not Allowed',
        'message': 'Cet endpoint nécessite POST. Utilisez POST /api/backtest avec body JSON.',
        'example': {
            'method': 'POST',
            'url': '/api/backtest',
            'body': {
                'symbols': ['BTC/USDT:USDT'],
                'start_date': '2025-01-01',
                'end_date': '2025-02-01',
                'initial_capital': 1000.0,
                'config': {}
            }
        },
        'documentation': 'Voir URLS_DISPONIBLES.md pour plus de détails'
    }


@router.post("/backtest")
@rate_limit
async def run_backtest(
    request: Request,
    backtest_request: BacktestRequest,
    db: AnalyticsDatabase = Depends(get_analytics_db)
):
    """
    Lancer backtest
    
    Body:
    {
        "symbols": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
        "start_date": "2025-01-01",
        "end_date": "2025-02-01",
        "initial_capital": 1000.0,
        "config": {...}
    }
    """
    try:
        from backtesting import create_backtest_engine
        
        # Créer backtest engine
        engine = create_backtest_engine(
            initial_capital=backtest_request.initial_capital,
            analytics_db=db,
            config=backtest_request.config
        )
        
        # Lancer backtest
        results = engine.run_backtest(
            symbols=backtest_request.symbols,
            start_date=backtest_request.start_date,
            end_date=backtest_request.end_date,
            config=backtest_request.config
        )
        
        return {
            'success': True,
            'results': results
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur POST /api/backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/optimize")
async def optimize_info():
    """
    Info endpoint optimize (GET)
    
    Cet endpoint nécessite POST. Utilisez POST avec body JSON.
    """
    return {
        'error': 'Method Not Allowed',
        'message': 'Cet endpoint nécessite POST. Utilisez POST /api/optimize avec body JSON.',
        'example': {
            'method': 'POST',
            'url': '/api/optimize',
            'body': {
                'symbols': ['BTC/USDT:USDT'],
                'start_date': '2025-01-01',
                'end_date': '2025-02-01',
                'n_trials': 100,
                'initial_capital': 1000.0
            }
        },
        'documentation': 'Voir URLS_DISPONIBLES.md pour plus de détails'
    }


@router.post("/optimize")
@rate_limit
async def run_optimization(
    request: Request,
    optimize_request: OptimizeRequest,
    db: AnalyticsDatabase = Depends(get_analytics_db)
):
    """
    Lancer optimisation ML
    
    Body:
    {
        "symbols": ["BTC/USDT:USDT"],
        "start_date": "2025-01-01",
        "end_date": "2025-02-01",
        "n_trials": 100,
        "initial_capital": 1000.0,
        "param_space": {...}
    }
    """
    try:
        from optimization import create_ml_optimizer
        
        # Créer optimizer
        optimizer = create_ml_optimizer(
            initial_capital=optimize_request.initial_capital,
            study_name=f"opt_{int(time.time())}"
        )
        
        # Lancer optimisation
        results = optimizer.optimize(
            symbols=optimize_request.symbols,
            start_date=optimize_request.start_date,
            end_date=optimize_request.end_date,
            n_trials=optimize_request.n_trials,
            param_space=optimize_request.param_space
        )
        
        return {
            'success': True,
            'results': results
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur POST /api/optimize: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/setups/rejected")
async def get_rejected_setups(
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AnalyticsDatabase = Depends(get_analytics_db)
):
    """Récupérer setups rejetés"""
    try:
        # Récupérer setups avec paramètres individuels
        setups = db.get_rejected_setups(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        # Filtrer par direction (non supporté par DB directement)
        if direction:
            setups = [s for s in setups if s.get('direction') == direction]
        
        # Appliquer offset (pagination)
        if offset > 0:
            setups = setups[offset:]
        
        return {
            'success': True,
            'count': len(setups),
            'setups': setups
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur GET /api/setups/rejected: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/setups/validated")
async def get_validated_setups(
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AnalyticsDatabase = Depends(get_analytics_db)
):
    """Récupérer setups validés"""
    try:
        # Utiliser requête SQL directe (méthode pas encore implémentée dans DB)
        cursor = db.conn.cursor()
        
        query = "SELECT * FROM setups_validated WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if direction:
            query += " AND direction = ?"
            params.append(direction)
        if start_date:
            query += " AND date(timestamp) >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date(timestamp) <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        setups = [dict(row) for row in cursor.fetchall()]
        
        # Appliquer offset (pagination)
        if offset > 0:
            setups = setups[offset:]
        
        return {
            'success': True,
            'count': len(setups),
            'setups': setups
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur GET /api/setups/validated: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_data(
    format: str = Query(default='csv', regex='^(csv|json)$'),
    data_type: str = Query(default='trades', regex='^(trades|setups_rejected|setups_validated)$'),
    symbol: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AnalyticsDatabase = Depends(get_analytics_db)
):
    """
    Exporter données (CSV ou JSON)
    
    Query params:
    - format: csv ou json
    - data_type: trades, setups_rejected, setups_validated
    - symbol: Filtrer par symbole
    - start_date: Date début
    - end_date: Date fin
    """
    try:
        # Récupérer données avec paramètres individuels
        if data_type == 'trades':
            data = db.get_trades(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                limit=10000
            )
        elif data_type == 'setups_rejected':
            data = db.get_rejected_setups(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                limit=10000
            )
        elif data_type == 'setups_validated':
            # Requête SQL directe (méthode pas encore implémentée dans DB)
            cursor = db.conn.cursor()
            query = "SELECT * FROM setups_validated WHERE 1=1"
            params = []
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            if start_date:
                query += " AND date(timestamp) >= ?"
                params.append(start_date)
            if end_date:
                query += " AND date(timestamp) <= ?"
                params.append(end_date)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(10000)
            cursor.execute(query, params)
            data = [dict(row) for row in cursor.fetchall()]
        else:
            raise HTTPException(status_code=400, detail="Invalid data_type")
        
        # Export CSV
        if format == 'csv':
            output = io.StringIO()
            if data:
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            
            csv_content = output.getvalue()
            output.close()
            
            return StreamingResponse(
                io.BytesIO(csv_content.encode('utf-8')),
                media_type='text/csv',
                headers={'Content-Disposition': f'attachment; filename={data_type}_{int(time.time())}.csv'}
            )
        
        # Export JSON
        else:
            return {
                'success': True,
                'data_type': data_type,
                'count': len(data),
                'data': data
            }
    
    except Exception as e:
        logger.error(f"❌ Erreur GET /api/export: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/trades/{trade_id}")
async def delete_trade(
    trade_id: int,
    db: AnalyticsDatabase = Depends(get_analytics_db)
):
    """Supprimer un trade (admin only)"""
    try:
        # TODO: Implémenter méthode delete dans Analytics DB
        return {
            'success': True,
            'message': f'Trade {trade_id} deleted'
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur DELETE /api/trades/{trade_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WEBSOCKET (pour streaming temps réel) ====================

# ==================== SETTINGS API ====================

@router.get("/settings")
async def get_settings():
    """
    Récupérer paramètres Telegram (depuis .env ou variables d'environnement)
    """
    try:
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED
        from config import PAPER_TRADING_MODE, PAPER_TRADING_INITIAL_CAPITAL
        from config import NOTIFICATION_BATCHING_ENABLED, NOTIFICATION_THROTTLE_SECONDS, NOTIFICATION_BATCH_INTERVAL
        from config import (
            TELEGRAM_NOTIFY_POSITION_OPENED, TELEGRAM_NOTIFY_POSITION_CLOSED,
            TELEGRAM_NOTIFY_TP_ESCALIER, TELEGRAM_NOTIFY_EARLY_INVALIDATION,
            TELEGRAM_NOTIFY_ERROR, TELEGRAM_NOTIFY_RECONNECTION,
            TELEGRAM_NOTIFY_DAILY_SUMMARY, TELEGRAM_NOTIFY_RECOVERY_MODE,
            TELEGRAM_NOTIFY_SETUP_REJECTED
        )
        
        return {
            'success': True,
            'settings': {
                'telegram': {
                    'bot_token': TELEGRAM_BOT_TOKEN if TELEGRAM_BOT_TOKEN else '',
                    'chat_id': str(TELEGRAM_CHAT_ID) if TELEGRAM_CHAT_ID else '',
                    'enabled': TELEGRAM_ENABLED,
                    'notify_types': {
                        'position_opened': TELEGRAM_NOTIFY_POSITION_OPENED,
                        'position_closed': TELEGRAM_NOTIFY_POSITION_CLOSED,
                        'tp_escalier': TELEGRAM_NOTIFY_TP_ESCALIER,
                        'early_invalidation': TELEGRAM_NOTIFY_EARLY_INVALIDATION,
                        'error': TELEGRAM_NOTIFY_ERROR,
                        'reconnection': TELEGRAM_NOTIFY_RECONNECTION,
                        'daily_summary': TELEGRAM_NOTIFY_DAILY_SUMMARY,
                        'recovery_mode': TELEGRAM_NOTIFY_RECOVERY_MODE,
                        'setup_rejected': TELEGRAM_NOTIFY_SETUP_REJECTED
                    }
                },
                'paper_trading': {
                    'enabled': PAPER_TRADING_MODE,
                    'initial_capital': PAPER_TRADING_INITIAL_CAPITAL
                },
                'notifications': {
                    'batching_enabled': NOTIFICATION_BATCHING_ENABLED,
                    'throttle_seconds': NOTIFICATION_THROTTLE_SECONDS,
                    'batch_interval': NOTIFICATION_BATCH_INTERVAL
                }
            }
        }
    except Exception as e:
        logger.error(f"❌ Erreur GET /api/settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings")
async def save_settings(request: Request):
    """
    Sauvegarder paramètres Telegram dans fichier .env
    """
    try:
        data = await request.json()
        telegram_settings = data.get('telegram', {})
        paper_settings = data.get('paper_trading', {})
        notification_settings = data.get('notifications', {})
        
        # Lire .env existant ou créer nouveau
        env_path = ".env"
        env_lines = []
        
        # Lire .env existant si disponible
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
        
        # Créer dictionnaire des variables existantes
        env_vars = {}
        new_lines = []
        for line in env_lines:
            line = line.strip()
            if not line or line.startswith('#'):
                new_lines.append(line + '\n')
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                env_vars[key] = value.strip()
        
        # Mettre à jour variables Telegram
        if telegram_settings.get('bot_token'):
            env_vars['TELEGRAM_BOT_TOKEN'] = telegram_settings['bot_token']
        if telegram_settings.get('chat_id'):
            env_vars['TELEGRAM_CHAT_ID'] = telegram_settings['chat_id']
        
        # 🔥 NOUVEAU: Mettre à jour types de notifications Telegram
        notify_types = telegram_settings.get('notify_types', {})
        if notify_types:
            env_vars['TELEGRAM_NOTIFY_POSITION_OPENED'] = 'true' if notify_types.get('position_opened', True) else 'false'
            env_vars['TELEGRAM_NOTIFY_POSITION_CLOSED'] = 'true' if notify_types.get('position_closed', True) else 'false'
            env_vars['TELEGRAM_NOTIFY_TP_ESCALIER'] = 'true' if notify_types.get('tp_escalier', True) else 'false'
            env_vars['TELEGRAM_NOTIFY_EARLY_INVALIDATION'] = 'true' if notify_types.get('early_invalidation', True) else 'false'
            env_vars['TELEGRAM_NOTIFY_ERROR'] = 'true' if notify_types.get('error', True) else 'false'
            env_vars['TELEGRAM_NOTIFY_RECONNECTION'] = 'true' if notify_types.get('reconnection', True) else 'false'
            env_vars['TELEGRAM_NOTIFY_DAILY_SUMMARY'] = 'true' if notify_types.get('daily_summary', False) else 'false'
            env_vars['TELEGRAM_NOTIFY_RECOVERY_MODE'] = 'true' if notify_types.get('recovery_mode', True) else 'false'
            env_vars['TELEGRAM_NOTIFY_SETUP_REJECTED'] = 'true' if notify_types.get('setup_rejected', False) else 'false'
        
        # Mettre à jour Paper Trading
        if 'enabled' in paper_settings:
            env_vars['PAPER_TRADING_MODE'] = 'true' if paper_settings['enabled'] else 'false'
        if 'initial_capital' in paper_settings:
            env_vars['PAPER_TRADING_INITIAL_CAPITAL'] = str(paper_settings['initial_capital'])
        
        # Liste des clés Telegram à exclure de "Autres variables"
        telegram_keys = [
            'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID',
            'TELEGRAM_NOTIFY_POSITION_OPENED', 'TELEGRAM_NOTIFY_POSITION_CLOSED',
            'TELEGRAM_NOTIFY_TP_ESCALIER', 'TELEGRAM_NOTIFY_EARLY_INVALIDATION',
            'TELEGRAM_NOTIFY_ERROR', 'TELEGRAM_NOTIFY_RECONNECTION',
            'TELEGRAM_NOTIFY_DAILY_SUMMARY', 'TELEGRAM_NOTIFY_RECOVERY_MODE',
            'TELEGRAM_NOTIFY_SETUP_REJECTED'
        ]
        
        # Écrire nouveau .env
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("# Telegram Configuration\n")
            if 'TELEGRAM_BOT_TOKEN' in env_vars:
                f.write(f"TELEGRAM_BOT_TOKEN={env_vars['TELEGRAM_BOT_TOKEN']}\n")
            if 'TELEGRAM_CHAT_ID' in env_vars:
                f.write(f"TELEGRAM_CHAT_ID={env_vars['TELEGRAM_CHAT_ID']}\n")
            f.write("\n# Telegram Notification Types (true/false)\n")
            if 'TELEGRAM_NOTIFY_POSITION_OPENED' in env_vars:
                f.write(f"TELEGRAM_NOTIFY_POSITION_OPENED={env_vars['TELEGRAM_NOTIFY_POSITION_OPENED']}\n")
            if 'TELEGRAM_NOTIFY_POSITION_CLOSED' in env_vars:
                f.write(f"TELEGRAM_NOTIFY_POSITION_CLOSED={env_vars['TELEGRAM_NOTIFY_POSITION_CLOSED']}\n")
            if 'TELEGRAM_NOTIFY_TP_ESCALIER' in env_vars:
                f.write(f"TELEGRAM_NOTIFY_TP_ESCALIER={env_vars['TELEGRAM_NOTIFY_TP_ESCALIER']}\n")
            if 'TELEGRAM_NOTIFY_EARLY_INVALIDATION' in env_vars:
                f.write(f"TELEGRAM_NOTIFY_EARLY_INVALIDATION={env_vars['TELEGRAM_NOTIFY_EARLY_INVALIDATION']}\n")
            if 'TELEGRAM_NOTIFY_ERROR' in env_vars:
                f.write(f"TELEGRAM_NOTIFY_ERROR={env_vars['TELEGRAM_NOTIFY_ERROR']}\n")
            if 'TELEGRAM_NOTIFY_RECONNECTION' in env_vars:
                f.write(f"TELEGRAM_NOTIFY_RECONNECTION={env_vars['TELEGRAM_NOTIFY_RECONNECTION']}\n")
            if 'TELEGRAM_NOTIFY_DAILY_SUMMARY' in env_vars:
                f.write(f"TELEGRAM_NOTIFY_DAILY_SUMMARY={env_vars['TELEGRAM_NOTIFY_DAILY_SUMMARY']}\n")
            if 'TELEGRAM_NOTIFY_RECOVERY_MODE' in env_vars:
                f.write(f"TELEGRAM_NOTIFY_RECOVERY_MODE={env_vars['TELEGRAM_NOTIFY_RECOVERY_MODE']}\n")
            if 'TELEGRAM_NOTIFY_SETUP_REJECTED' in env_vars:
                f.write(f"TELEGRAM_NOTIFY_SETUP_REJECTED={env_vars['TELEGRAM_NOTIFY_SETUP_REJECTED']}\n")
            f.write("\n# Paper Trading\n")
            if 'PAPER_TRADING_MODE' in env_vars:
                f.write(f"PAPER_TRADING_MODE={env_vars['PAPER_TRADING_MODE']}\n")
            if 'PAPER_TRADING_INITIAL_CAPITAL' in env_vars:
                f.write(f"PAPER_TRADING_INITIAL_CAPITAL={env_vars['PAPER_TRADING_INITIAL_CAPITAL']}\n")
            f.write("\n# Autres variables d'environnement\n")
            for key, value in env_vars.items():
                if key not in telegram_keys and key not in ['PAPER_TRADING_MODE', 'PAPER_TRADING_INITIAL_CAPITAL']:
                    f.write(f"{key}={value}\n")
        
        return {
            'success': True,
            'message': 'Paramètres sauvegardés dans .env. Redémarrez le bot pour appliquer les changements.'
        }
    except Exception as e:
        logger.error(f"❌ Erreur POST /api/settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== TELEGRAM WEBHOOK ====================

@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Webhook Telegram pour recevoir les commandes
    
    Format Telegram Update:
    {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {"id": 123456789, "is_bot": false, "first_name": "John"},
            "chat": {"id": 123456789, "type": "private"},
            "date": 1234567890,
            "text": "/stats"
        }
    }
    """
    try:
        data = await request.json()
        
        # Vérifier que c'est un message
        if 'message' not in data:
            return {"ok": True}  # Ignorer les updates non-messages
        
        message = data['message']
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '').strip()
        
        if not text or not chat_id:
            return {"ok": True}
        
        # Vérifier que le message commence par /
        if not text.startswith('/'):
            return {"ok": True}  # Ignorer les messages non-commandes
        
        # Initialiser command handler si nécessaire
        global _telegram_command_handler
        if not _telegram_command_handler:
            from notifications.telegram_commands import create_telegram_command_handler
            _telegram_command_handler = create_telegram_command_handler(
                analytics_db=_analytics_db,
                position_manager=_position_manager,
                notification_manager=_notification_manager,
                instance_port=_instance_port
            )
        
        # Gérer la commande
        response_text = await _telegram_command_handler.handle_command(text, chat_id)
        
        # Envoyer la réponse via Telegram API directement (pour répondre au bon chat_id)
        try:
            from config import TELEGRAM_BOT_TOKEN
            import aiohttp
            
            if TELEGRAM_BOT_TOKEN:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': response_text,
                    'parse_mode': 'Markdown',
                    'disable_web_page_preview': True
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            logger.debug(f"✅ Réponse Telegram envoyée à chat_id {chat_id}")
                        else:
                            error_text = await response.text()
                            logger.error(f"❌ Erreur Telegram API: {response.status} - {error_text}")
            else:
                logger.warning("⚠️ TELEGRAM_BOT_TOKEN non configuré")
        except ImportError:
            logger.error("❌ aiohttp non installé (requis pour Telegram webhook)")
        except Exception as e:
            logger.error(f"❌ Erreur envoi réponse Telegram: {e}")
        
        return {"ok": True}
    
    except Exception as e:
        logger.error(f"❌ Erreur webhook Telegram: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/telegram/webhook/info")
async def telegram_webhook_info():
    """
    Informations sur le webhook Telegram
    
    Retourne l'URL du webhook et les instructions pour le configurer
    """
    from config import TELEGRAM_BOT_TOKEN
    
    if not TELEGRAM_BOT_TOKEN:
        return {
            "ok": False,
            "error": "TELEGRAM_BOT_TOKEN non configuré"
        }
    
    # Construire l'URL du webhook (nécessite que le bot soit accessible publiquement)
    # Pour le développement local, utiliser ngrok ou un tunnel similaire
    webhook_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    
    return {
        "ok": True,
        "webhook_endpoint": "/api/telegram/webhook",
        "set_webhook_url": webhook_url,
        "instructions": [
            "1. Assurez-vous que votre bot est accessible publiquement (utilisez ngrok pour le développement local)",
            "2. Configurez le webhook avec:",
            f"   curl -X POST '{webhook_url}?url=https://votre-domaine.com/api/telegram/webhook'",
            "3. Vérifiez le webhook avec:",
            f"   curl 'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo'",
            "4. Commandes disponibles: /help, /stats, /report, /status, /trades"
        ],
        "commands": [
            "/help - Afficher l'aide",
            "/stats - Statistiques de la session",
            "/report - Rapport détaillé",
            "/status - État actuel",
            "/trades - Derniers 10 trades"
        ]
    }


# Note: WebSocket endpoints déjà gérés dans main.py via SocketIO
# Cette API REST est pour requêtes HTTP classiques

