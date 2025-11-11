"""
🔥 PHASE 8: Gestion base de données SQLite pour historique trades
Persistance illimitée avec requêtes rapides
"""
import sqlite3
import logging
import json
import os
import sys
import threading
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TradeDatabase:
    """Gestion base de données SQLite pour historique trades"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialiser base de données

        Args:
            db_path: Chemin vers fichier DB (si None, utilise instance-specific)
        """
        if db_path is None:
            # 🔥 FIX: Fichier DB par instance pour éviter conflits multi-instances
            port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
            db_path = f"trades_instance_{port}.db"

        self.db_path = db_path
        self.conn = None
        # 🔥 FIX: Thread lock pour éviter race conditions avec check_same_thread=False
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialiser base de données et tables"""
        # 🔥 NOTE: check_same_thread=False est utilisé mais protégé par un lock
        # TODO: Migrer vers aiosqlite pour une meilleure compatibilité async
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Retourner dict
        
        cursor = self.conn.cursor()
        
        # Table trades
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry REAL NOT NULL,
                exit REAL NOT NULL,
                gross_pnl_pct REAL NOT NULL,
                gross_pnl_usdt REAL NOT NULL,
                net_pnl_pct REAL NOT NULL,
                net_pnl_usdt REAL NOT NULL,
                fees REAL DEFAULT 0,
                slippage REAL DEFAULT 0,
                total_costs REAL DEFAULT 0,
                reason TEXT,
                duration INTEGER,
                condition_types TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index pour performances
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON trades(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON trades(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON trades(timestamp)')
        
        self.conn.commit()
        logger.info(f"✅ Base de données initialisée: {self.db_path}")
    
    def insert_trade(self, trade: Dict) -> int:
        """Insérer un trade"""
        with self._lock:
            cursor = self.conn.cursor()

            condition_types_json = json.dumps(trade.get('condition_types', []))
            metadata_json = json.dumps(trade.get('metadata', {}))

            cursor.execute('''
                INSERT INTO trades (
                    timestamp, date, time, symbol, direction, entry, exit,
                    gross_pnl_pct, gross_pnl_usdt, net_pnl_pct, net_pnl_usdt,
                    fees, slippage, total_costs, reason, duration,
                    condition_types, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade.get('timestamp'),
                trade.get('date'),
                trade.get('time'),
                trade.get('symbol'),
                trade.get('direction'),
                trade.get('entry'),
                trade.get('exit'),
                trade.get('gross_pnl_pct'),
                trade.get('gross_pnl_usdt'),
                trade.get('net_pnl_pct'),
                trade.get('net_pnl_usdt'),
                trade.get('fees', 0),
                trade.get('slippage', 0),
                trade.get('total_costs', 0),
                trade.get('reason'),
                trade.get('duration'),
                condition_types_json,
                metadata_json
            ))

            self.conn.commit()
            return cursor.lastrowid
    
    def get_all_trades(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict]:
        """Récupérer tous les trades"""
        with self._lock:
            cursor = self.conn.cursor()

            query = 'SELECT * FROM trades ORDER BY timestamp DESC'
            if limit:
                query += f' LIMIT {limit} OFFSET {offset}'

            cursor.execute(query)
            rows = cursor.fetchall()

            trades = []
            for row in rows:
                trade = dict(row)
                trade['condition_types'] = json.loads(trade.get('condition_types', '[]'))
                trade['metadata'] = json.loads(trade.get('metadata', '{}'))
                trades.append(trade)

            return trades
    
    def get_trades_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Récupérer trades par plage de dates"""
        with self._lock:
            cursor = self.conn.cursor()

            cursor.execute('''
                SELECT * FROM trades
                WHERE date BETWEEN ? AND ?
                ORDER BY timestamp DESC
            ''', (start_date, end_date))

            rows = cursor.fetchall()

            trades = []
            for row in rows:
                trade = dict(row)
                trade['condition_types'] = json.loads(trade.get('condition_types', '[]'))
                trade['metadata'] = json.loads(trade.get('metadata', '{}'))
                trades.append(trade)

            return trades
    
    def get_trades_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Récupérer trades par symbole"""
        with self._lock:
            cursor = self.conn.cursor()

            cursor.execute('''
                SELECT * FROM trades
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (symbol, limit))

            rows = cursor.fetchall()

            trades = []
            for row in rows:
                trade = dict(row)
                trade['condition_types'] = json.loads(trade.get('condition_types', '[]'))
                trade['metadata'] = json.loads(trade.get('metadata', '{}'))
                trades.append(trade)

            return trades
    
    def get_statistics(self) -> Dict:
        """Calculer statistiques globales"""
        with self._lock:
            cursor = self.conn.cursor()

            cursor.execute('''
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN gross_pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN gross_pnl_pct <= 0 THEN 1 ELSE 0 END) as losses,
                    AVG(gross_pnl_pct) as avg_pnl_pct,
                    SUM(gross_pnl_usdt) as total_pnl_usdt,
                    AVG(fees) as avg_fees,
                    AVG(slippage) as avg_slippage,
                    AVG(duration) as avg_duration
                FROM trades
            ''')

            row = cursor.fetchone()
            return dict(row) if row else {}
    
    def close(self):
        """Fermer connexion"""
        if self.conn:
            self.conn.close()

