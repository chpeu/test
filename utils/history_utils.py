"""
History Utilities - Trade history persistence and loading
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from core.state_manager import get_state_manager

logger = logging.getLogger(__name__)

def get_trade_history_file() -> str:
    """
    Retourner le nom du fichier historique selon le port de l'instance.
    """
    try:
        # Essayer de récupérer le port via les arguments de la ligne de commande (uvicorn port)
        # Format habituel: python main.py 5001
        port = 5000
        if len(sys.argv) > 1:
            for arg in sys.argv:
                if arg.isdigit():
                    port = int(arg)
                    break
        
        # S'assurer que le dossier data existe
        if not os.path.exists('data'):
            os.makedirs('data')
            
        return f"data/trade_history_{port}.json"
    except Exception as e:
        logger.warning(f"⚠️ Erreur get_trade_history_file: {e}, utilisation défaut")
        return "data/trade_history_5000.json"

def save_trade_history(file_path: Optional[str] = None) -> None:
    """Sauvegarder l'historique des trades dans un fichier JSON"""
    state = get_state_manager()
    
    if file_path is None:
        file_path = get_trade_history_file()
    
    try:
        # Écriture atomique avec fichier temporaire puis rename
        temp_file = file_path + ".tmp"
        trade_history = state.trade_history
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(trade_history, f, indent=2, ensure_ascii=False)
            
        # Renommer atomiquement
        if os.path.exists(file_path):
            os.replace(temp_file, file_path)
        else:
            os.rename(temp_file, file_path)
        logger.debug(f"✅ Historique sauvegardé: {len(trade_history)} trades (fichier: {file_path})")
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde historique JSON: {type(e).__name__}: {e}")
        if 'temp_file' in locals() and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass

def load_trade_history() -> None:
    """Charger l'historique des trades depuis PostgreSQL (priorité) ou JSON (fallback)"""
    state = get_state_manager()
    file_path = get_trade_history_file()
    
    # 1. Essayer de charger depuis PostgreSQL (source de vérité)
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        pg_logger = PostgreSQLDataLogger()
        if pg_logger.enabled:
            conn = pg_logger.pool.getconn()
            try:
                with conn.cursor() as cur:
                    # Charger les trades des dernières 24h pour l'UI
                    cur.execute("""
                        SELECT id, symbol, direction, entry_price, exit_price,
                               pnl_pct, pnl_usdt, net_pnl_pct, net_pnl_usdt,
                               exit_reason, duration_seconds, created_at,
                               size_usdt, session_id
                        FROM trades 
                        WHERE created_at > NOW() - INTERVAL '24 hours'
                        AND exit_reason IS NOT NULL
                        ORDER BY created_at DESC
                        LIMIT 100
                    """)
                    rows = cur.fetchall()
                    if rows:
                        trades = []
                        for r in rows:
                            trades.append({
                                'id': str(r[0]),
                                'symbol': r[1],
                                'direction': r[2],
                                'entry_price': float(r[3]) if r[3] else 0,
                                'exit_price': float(r[4]) if r[4] else 0,
                                'pnl_pct': float(r[5]) if r[5] else 0,
                                'pnl_usdt': float(r[6]) if r[6] else 0,
                                'net_pnl_pct': float(r[7]) if r[7] else 0,
                                'net_pnl_usdt': float(r[8]) if r[8] else 0,
                                'reason': r[9],
                                'close_reason': r[9],
                                'duration_seconds': float(r[10]) if r[10] else 0,
                                'closed_at': r[11].isoformat() if r[11] else None,
                                'size': float(r[12]) if r[12] else 0,
                                'session_id': str(r[13]) if r[13] else None
                            })
                        state.set_trade_history(trades)
                        logger.info(f"✅ Historique chargé depuis PostgreSQL: {len(trades)} trades (24h)")
                        return
            finally:
                pg_logger.pool.putconn(conn)
    except Exception as e:
        logger.warning(f"⚠️ Erreur chargement historique PostgreSQL: {e}, fallback JSON")

    # 2. Fallback JSON si PostgreSQL échoue ou vide
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                if isinstance(history, list):
                    state.set_trade_history(history)
                    logger.info(f"✅ Historique chargé depuis JSON: {len(history)} trades")
        except Exception as e:
            logger.error(f"❌ Erreur chargement historique JSON: {e}")
