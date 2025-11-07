# 🏗️ ARCHITECTURE MONITORING & ARCHIVAGE COMPLET

**Date**: 2025-11-06  
**Version**: Trade Cursor v7.0  
**Objectif**: Historique complet pour analyse et optimisation

---

## 📊 ÉTAT ACTUEL (Existant)

### ✅ Ce qui est déjà stocké

| Type | Format | Fichier | Instance-aware | Contenu |
|------|--------|---------|----------------|---------|
| **Trades validés** | JSON | `trade_history_instance_{port}.json` | ✅ | Entry, exit, PnL, raison, durée, conditions |
| **Trades validés** | SQLite | `trades_instance_{port}.db` | ✅ | Même que JSON + indexes |
| **Métriques conditions** | Mémoire | - | ❌ | Winrate par condition (non persisté) |

### ❌ Ce qui manque

| Type | Impact | Priorité |
|------|--------|----------|
| **Setups rejetés** | Impossible d'analyser pourquoi aucun trade | 🔴 HAUTE |
| **Critères détaillés** | Impossible d'optimiser seuils | 🔴 HAUTE |
| **Comportement trade** | PnL au fil du temps, TP Escalier | 🟡 MOYENNE |
| **Archive centralisée** | Difficile d'analyser multi-instances | 🟡 MOYENNE |

---

## 🎯 PROPOSITION : ARCHITECTURE COMPLÈTE

### Architecture en 3 couches

```
┌─────────────────────────────────────────────────────────┐
│  COUCHE 1: CAPTURE (Temps réel)                        │
│  ↓ Chaque instance log ses données localement          │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  COUCHE 2: STOCKAGE (SQLite par instance)              │
│  ↓ 3 tables: setups_rejetes, setups_valides, trades    │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  COUCHE 3: AGRÉGATION (Script externe)                 │
│  ↓ Consolidation multi-instances + Analytics           │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 STRUCTURE DE DONNÉES PROPOSÉE

### 1️⃣ Table: `setups_rejected` (Setups rejetés)

**Pourquoi**: Comprendre pourquoi aucun trade n'est pris

```sql
CREATE TABLE setups_rejected (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT,
    
    -- Raisons de rejet
    rejection_reason TEXT NOT NULL,
    rejection_category TEXT NOT NULL,
    
    -- Critères techniques
    price REAL,
    volume_24h REAL,
    
    -- Indicateurs
    ema_fast REAL,
    ema_slow REAL,
    rsi REAL,
    macd REAL,
    macd_signal REAL,
    atr REAL,
    atr5m REAL,
    adx REAL,
    
    -- Scores & Seuils
    total_score REAL,
    min_score_required REAL,
    
    -- Filtres
    spread REAL,
    spread_threshold REAL,
    orderbook_ratio REAL,
    orderbook_threshold REAL,
    
    -- Confluence (si applicable)
    confluence_1m BOOLEAN,
    confluence_5m BOOLEAN,
    confluence_required BOOLEAN,
    
    -- Corrélation
    correlation_detected BOOLEAN,
    correlation_group TEXT,
    correlation_penalty REAL,
    
    -- Recovery Mode
    recovery_mode_active BOOLEAN,
    loss_streak INTEGER,
    recovery_level INTEGER,
    
    -- Scalability
    scalability_score REAL,
    
    -- Metadata
    instance_port INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes**:
```sql
CREATE INDEX idx_rejected_symbol ON setups_rejected(symbol);
CREATE INDEX idx_rejected_reason ON setups_rejected(rejection_reason);
CREATE INDEX idx_rejected_category ON setups_rejected(rejection_category);
CREATE INDEX idx_rejected_timestamp ON setups_rejected(timestamp);
```

---

### 2️⃣ Table: `setups_validated` (Setups validés)

**Pourquoi**: Détails complets du setup au moment de l'ouverture

```sql
CREATE TABLE setups_validated (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    
    -- Prix & Entry
    price REAL NOT NULL,
    entry REAL NOT NULL,
    sl REAL NOT NULL,
    tp REAL NOT NULL,
    
    -- Position
    position_size REAL NOT NULL,
    capital REAL,
    
    -- Indicateurs (mêmes que setups_rejected)
    ema_fast REAL,
    ema_slow REAL,
    rsi REAL,
    macd REAL,
    macd_signal REAL,
    atr REAL,
    atr5m REAL,
    adx REAL,
    di_plus REAL,
    di_minus REAL,
    
    -- Scores
    total_score REAL NOT NULL,
    ema_score REAL,
    rsi_score REAL,
    macd_score REAL,
    adx_score REAL,
    volume_score REAL,
    pattern_score REAL,
    
    -- Seuils appliqués
    tp_sl_mode TEXT,
    fixed_tp_pct REAL,
    fixed_sl_pct REAL,
    atr_mult_tp REAL,
    atr_mult_sl REAL,
    
    -- TP Escalier (si TP_MULTI)
    tp_escalier_enabled BOOLEAN,
    tp_escalier_levels TEXT,
    
    -- Confluence
    confluence_1m BOOLEAN,
    confluence_5m BOOLEAN,
    
    -- Conditions détectées
    condition_types TEXT,
    
    -- Recovery Mode
    recovery_mode_active BOOLEAN,
    loss_streak INTEGER,
    recovery_level INTEGER,
    position_size_reduction REAL,
    
    -- Scalability
    scalability_score REAL,
    spread REAL,
    orderbook_ratio REAL,
    
    -- Metadata
    instance_port INTEGER,
    trade_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);
```

---

### 3️⃣ Table: `trades` (Extension de l'existant)

**Ajouts proposés** à la table existante:

```sql
ALTER TABLE trades ADD COLUMN setup_id INTEGER;
ALTER TABLE trades ADD COLUMN tp_sl_mode TEXT;
ALTER TABLE trades ADD COLUMN break_even_triggered BOOLEAN;
ALTER TABLE trades ADD COLUMN trailing_stop_triggered BOOLEAN;
ALTER TABLE trades ADD COLUMN partial_tp_triggered BOOLEAN;

-- TP Escalier
ALTER TABLE trades ADD COLUMN tp_escalier_enabled BOOLEAN;
ALTER TABLE trades ADD COLUMN tp_escalier_levels_hit TEXT;
ALTER TABLE trades ADD COLUMN tp_escalier_profits TEXT;

-- Comportement du trade
ALTER TABLE trades ADD COLUMN pnl_history TEXT;
ALTER TABLE trades ADD COLUMN max_pnl_reached REAL;
ALTER TABLE trades ADD COLUMN min_pnl_reached REAL;
ALTER TABLE trades ADD COLUMN max_drawdown_intra REAL;

-- Early Invalidation
ALTER TABLE trades ADD COLUMN early_invalidation_threshold REAL;
ALTER TABLE trades ADD COLUMN early_invalidation_elapsed REAL;

-- Trailing Stop
ALTER TABLE trades ADD COLUMN trailing_stop_updates TEXT;

FOREIGN KEY (setup_id) REFERENCES setups_validated(id);
```

---

### 4️⃣ Table: `trade_behavior` (Nouveau)

**Pourquoi**: Suivre l'évolution du trade seconde par seconde

```sql
CREATE TABLE trade_behavior (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,
    
    -- Timestamp
    timestamp TEXT NOT NULL,
    elapsed_seconds INTEGER NOT NULL,
    
    -- Prix & PnL
    current_price REAL NOT NULL,
    pnl_pct REAL NOT NULL,
    pnl_usdt REAL NOT NULL,
    
    -- SL/TP actuel
    current_sl REAL NOT NULL,
    current_tp REAL NOT NULL,
    
    -- États
    break_even_set BOOLEAN,
    trailing_active BOOLEAN,
    partial_tp_sold BOOLEAN,
    
    -- TP Escalier
    tp_escalier_current_level INTEGER,
    tp_escalier_size_remaining REAL,
    
    -- Metadata
    instance_port INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);
```

**Fréquence de logging**: 
- ✅ Chaque `check_position()` (toutes les 0.1s actuellement)
- ⚠️ Peut générer BEAUCOUP de données (1 trade de 60s = 600 rows)
- 💡 **Optimisation**: Logger seulement si PnL change de >0.05% OU événement (BE, TP partiel, etc.)

---

## 🔧 IMPLÉMENTATION PROPOSÉE

### Fichier 1: `core/analytics_database.py`

**Nouveau fichier** pour gérer les 4 tables:

```python
"""
Base de données analytics complète pour monitoring et optimisation
"""
import sqlite3
import json
import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AnalyticsDatabase:
    """Base de données complète pour analytics"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Initialiser toutes les tables"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # Table setups_rejected
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS setups_rejected (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT,
                rejection_reason TEXT NOT NULL,
                rejection_category TEXT NOT NULL,
                price REAL,
                volume_24h REAL,
                ema_fast REAL,
                ema_slow REAL,
                rsi REAL,
                macd REAL,
                macd_signal REAL,
                atr REAL,
                atr5m REAL,
                adx REAL,
                total_score REAL,
                min_score_required REAL,
                spread REAL,
                spread_threshold REAL,
                orderbook_ratio REAL,
                orderbook_threshold REAL,
                confluence_1m BOOLEAN,
                confluence_5m BOOLEAN,
                confluence_required BOOLEAN,
                correlation_detected BOOLEAN,
                correlation_group TEXT,
                correlation_penalty REAL,
                recovery_mode_active BOOLEAN,
                loss_streak INTEGER,
                recovery_level INTEGER,
                scalability_score REAL,
                metadata TEXT,
                instance_port INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table setups_validated
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS setups_validated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                price REAL NOT NULL,
                entry REAL NOT NULL,
                sl REAL NOT NULL,
                tp REAL NOT NULL,
                position_size REAL NOT NULL,
                capital REAL,
                ema_fast REAL,
                ema_slow REAL,
                rsi REAL,
                macd REAL,
                macd_signal REAL,
                atr REAL,
                atr5m REAL,
                adx REAL,
                di_plus REAL,
                di_minus REAL,
                total_score REAL NOT NULL,
                ema_score REAL,
                rsi_score REAL,
                macd_score REAL,
                adx_score REAL,
                volume_score REAL,
                pattern_score REAL,
                tp_sl_mode TEXT,
                fixed_tp_pct REAL,
                fixed_sl_pct REAL,
                atr_mult_tp REAL,
                atr_mult_sl REAL,
                tp_escalier_enabled BOOLEAN,
                tp_escalier_levels TEXT,
                confluence_1m BOOLEAN,
                confluence_5m BOOLEAN,
                condition_types TEXT,
                recovery_mode_active BOOLEAN,
                loss_streak INTEGER,
                recovery_level INTEGER,
                position_size_reduction REAL,
                scalability_score REAL,
                spread REAL,
                orderbook_ratio REAL,
                metadata TEXT,
                instance_port INTEGER,
                trade_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table trade_behavior
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_behavior (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                elapsed_seconds INTEGER NOT NULL,
                current_price REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                pnl_usdt REAL NOT NULL,
                current_sl REAL NOT NULL,
                current_tp REAL NOT NULL,
                break_even_set BOOLEAN,
                trailing_active BOOLEAN,
                partial_tp_sold BOOLEAN,
                tp_escalier_current_level INTEGER,
                tp_escalier_size_remaining REAL,
                metadata TEXT,
                instance_port INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rejected_symbol ON setups_rejected(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rejected_reason ON setups_rejected(rejection_reason)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rejected_category ON setups_rejected(rejection_category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rejected_timestamp ON setups_rejected(timestamp)')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_validated_symbol ON setups_validated(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_validated_timestamp ON setups_validated(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_validated_trade_id ON setups_validated(trade_id)')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_behavior_trade_id ON trade_behavior(trade_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_behavior_timestamp ON trade_behavior(timestamp)')
        
        self.conn.commit()
        logger.info(f"✅ Analytics DB initialisée: {self.db_path}")
    
    def insert_rejected_setup(self, setup: Dict) -> int:
        """Insérer un setup rejeté"""
        cursor = self.conn.cursor()
        
        metadata_json = json.dumps(setup.get('metadata', {}))
        
        cursor.execute('''
            INSERT INTO setups_rejected (
                timestamp, symbol, direction, rejection_reason, rejection_category,
                price, volume_24h, ema_fast, ema_slow, rsi, macd, macd_signal,
                atr, atr5m, adx, total_score, min_score_required,
                spread, spread_threshold, orderbook_ratio, orderbook_threshold,
                confluence_1m, confluence_5m, confluence_required,
                correlation_detected, correlation_group, correlation_penalty,
                recovery_mode_active, loss_streak, recovery_level,
                scalability_score, metadata, instance_port
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            setup.get('timestamp'),
            setup.get('symbol'),
            setup.get('direction'),
            setup.get('rejection_reason'),
            setup.get('rejection_category'),
            setup.get('price'),
            setup.get('volume_24h'),
            setup.get('ema_fast'),
            setup.get('ema_slow'),
            setup.get('rsi'),
            setup.get('macd'),
            setup.get('macd_signal'),
            setup.get('atr'),
            setup.get('atr5m'),
            setup.get('adx'),
            setup.get('total_score'),
            setup.get('min_score_required'),
            setup.get('spread'),
            setup.get('spread_threshold'),
            setup.get('orderbook_ratio'),
            setup.get('orderbook_threshold'),
            setup.get('confluence_1m'),
            setup.get('confluence_5m'),
            setup.get('confluence_required'),
            setup.get('correlation_detected'),
            setup.get('correlation_group'),
            setup.get('correlation_penalty'),
            setup.get('recovery_mode_active'),
            setup.get('loss_streak'),
            setup.get('recovery_level'),
            setup.get('scalability_score'),
            metadata_json,
            setup.get('instance_port')
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def insert_validated_setup(self, setup: Dict) -> int:
        """Insérer un setup validé"""
        cursor = self.conn.cursor()
        
        condition_types_json = json.dumps(setup.get('condition_types', []))
        tp_escalier_levels_json = json.dumps(setup.get('tp_escalier_levels', []))
        metadata_json = json.dumps(setup.get('metadata', {}))
        
        cursor.execute('''
            INSERT INTO setups_validated (
                timestamp, symbol, direction, price, entry, sl, tp,
                position_size, capital,
                ema_fast, ema_slow, rsi, macd, macd_signal, atr, atr5m, adx,
                di_plus, di_minus,
                total_score, ema_score, rsi_score, macd_score, adx_score,
                volume_score, pattern_score,
                tp_sl_mode, fixed_tp_pct, fixed_sl_pct, atr_mult_tp, atr_mult_sl,
                tp_escalier_enabled, tp_escalier_levels,
                confluence_1m, confluence_5m, condition_types,
                recovery_mode_active, loss_streak, recovery_level, position_size_reduction,
                scalability_score, spread, orderbook_ratio,
                metadata, instance_port, trade_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            setup.get('timestamp'),
            setup.get('symbol'),
            setup.get('direction'),
            setup.get('price'),
            setup.get('entry'),
            setup.get('sl'),
            setup.get('tp'),
            setup.get('position_size'),
            setup.get('capital'),
            setup.get('ema_fast'),
            setup.get('ema_slow'),
            setup.get('rsi'),
            setup.get('macd'),
            setup.get('macd_signal'),
            setup.get('atr'),
            setup.get('atr5m'),
            setup.get('adx'),
            setup.get('di_plus'),
            setup.get('di_minus'),
            setup.get('total_score'),
            setup.get('ema_score'),
            setup.get('rsi_score'),
            setup.get('macd_score'),
            setup.get('adx_score'),
            setup.get('volume_score'),
            setup.get('pattern_score'),
            setup.get('tp_sl_mode'),
            setup.get('fixed_tp_pct'),
            setup.get('fixed_sl_pct'),
            setup.get('atr_mult_tp'),
            setup.get('atr_mult_sl'),
            setup.get('tp_escalier_enabled'),
            tp_escalier_levels_json,
            setup.get('confluence_1m'),
            setup.get('confluence_5m'),
            condition_types_json,
            setup.get('recovery_mode_active'),
            setup.get('loss_streak'),
            setup.get('recovery_level'),
            setup.get('position_size_reduction'),
            setup.get('scalability_score'),
            setup.get('spread'),
            setup.get('orderbook_ratio'),
            metadata_json,
            setup.get('instance_port'),
            setup.get('trade_id')
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def insert_trade_behavior(self, behavior: Dict) -> int:
        """Insérer snapshot comportement trade"""
        cursor = self.conn.cursor()
        
        metadata_json = json.dumps(behavior.get('metadata', {}))
        
        cursor.execute('''
            INSERT INTO trade_behavior (
                trade_id, timestamp, elapsed_seconds,
                current_price, pnl_pct, pnl_usdt,
                current_sl, current_tp,
                break_even_set, trailing_active, partial_tp_sold,
                tp_escalier_current_level, tp_escalier_size_remaining,
                metadata, instance_port
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            behavior.get('trade_id'),
            behavior.get('timestamp'),
            behavior.get('elapsed_seconds'),
            behavior.get('current_price'),
            behavior.get('pnl_pct'),
            behavior.get('pnl_usdt'),
            behavior.get('current_sl'),
            behavior.get('current_tp'),
            behavior.get('break_even_set'),
            behavior.get('trailing_active'),
            behavior.get('partial_tp_sold'),
            behavior.get('tp_escalier_current_level'),
            behavior.get('tp_escalier_size_remaining'),
            metadata_json,
            behavior.get('instance_port')
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_rejected_setups_summary(self) -> Dict:
        """Statistiques setups rejetés"""
        cursor = self.conn.cursor()
        
        # Total rejetés par catégorie
        cursor.execute('''
            SELECT rejection_category, COUNT(*) as count
            FROM setups_rejected
            GROUP BY rejection_category
            ORDER BY count DESC
        ''')
        by_category = dict(cursor.fetchall())
        
        # Total rejetés par raison (top 10)
        cursor.execute('''
            SELECT rejection_reason, COUNT(*) as count
            FROM setups_rejected
            GROUP BY rejection_reason
            ORDER BY count DESC
            LIMIT 10
        ''')
        by_reason = dict(cursor.fetchall())
        
        # Total rejetés par symbole (top 10)
        cursor.execute('''
            SELECT symbol, COUNT(*) as count
            FROM setups_rejected
            GROUP BY symbol
            ORDER BY count DESC
            LIMIT 10
        ''')
        by_symbol = dict(cursor.fetchall())
        
        return {
            'by_category': by_category,
            'by_reason': by_reason,
            'by_symbol': by_symbol
        }
    
    def get_trade_behavior_summary(self, trade_id: int) -> Dict:
        """Résumé comportement d'un trade"""
        cursor = self.conn.cursor()
        
        # Récupérer tous les snapshots
        cursor.execute('''
            SELECT * FROM trade_behavior
            WHERE trade_id = ?
            ORDER BY elapsed_seconds ASC
        ''', (trade_id,))
        
        snapshots = [dict(row) for row in cursor.fetchall()]
        
        if not snapshots:
            return {}
        
        # Calculer métriques
        max_pnl = max(s['pnl_pct'] for s in snapshots)
        min_pnl = min(s['pnl_pct'] for s in snapshots)
        max_drawdown = max_pnl - min_pnl if max_pnl > 0 else 0
        
        return {
            'snapshots': snapshots,
            'max_pnl': max_pnl,
            'min_pnl': min_pnl,
            'max_drawdown_intra': max_drawdown,
            'total_snapshots': len(snapshots)
        }
    
    def close(self):
        """Fermer connexion"""
        if self.conn:
            self.conn.close()
```

---

### Fichier 2: `aggregate_multi_instances.py`

**Script externe** pour agréger toutes les instances:

```python
"""
Agrégation multi-instances pour analytics centralisée
"""
import sqlite3
import glob
import pandas as pd
from datetime import datetime

def aggregate_all_instances(output_db: str = "analytics_consolidated.db"):
    """
    Agréger toutes les instances dans une DB consolidée
    
    Args:
        output_db: Fichier DB de sortie
    """
    # Trouver toutes les DB d'instances
    instance_dbs = glob.glob("analytics_instance_*.db")
    
    print(f"📊 Agrégation de {len(instance_dbs)} instances...")
    
    # Connexion à la DB consolidée
    conn_out = sqlite3.connect(output_db)
    cursor_out = conn_out.cursor()
    
    # Créer tables consolidées (mêmes structures + colonne instance_id)
    # ... (créer tables) ...
    
    # Pour chaque instance
    for instance_db in instance_dbs:
        print(f"  Traitement: {instance_db}")
        
        conn_in = sqlite3.connect(instance_db)
        
        # Copier setups_rejected
        df_rejected = pd.read_sql("SELECT * FROM setups_rejected", conn_in)
        df_rejected.to_sql("setups_rejected", conn_out, if_exists='append', index=False)
        
        # Copier setups_validated
        df_validated = pd.read_sql("SELECT * FROM setups_validated", conn_in)
        df_validated.to_sql("setups_validated", conn_out, if_exists='append', index=False)
        
        # Copier trade_behavior
        df_behavior = pd.read_sql("SELECT * FROM trade_behavior", conn_in)
        df_behavior.to_sql("trade_behavior", conn_out, if_exists='append', index=False)
        
        conn_in.close()
    
    conn_out.commit()
    conn_out.close()
    
    print(f"✅ Agrégation terminée: {output_db}")


if __name__ == "__main__":
    aggregate_all_instances()
```

---

### Fichier 3: `analyze_full_history.py`

**Script d'analyse** complet:

```python
"""
Analyse complète de l'historique
"""
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List

def analyze_rejection_patterns(db_path: str = "analytics_consolidated.db"):
    """Analyser les patterns de rejet"""
    conn = sqlite3.connect(db_path)
    
    # Top raisons de rejet
    df = pd.read_sql('''
        SELECT rejection_category, rejection_reason, COUNT(*) as count
        FROM setups_rejected
        GROUP BY rejection_category, rejection_reason
        ORDER BY count DESC
        LIMIT 20
    ''', conn)
    
    print("\n🔴 TOP 20 RAISONS DE REJET")
    print(df.to_string(index=False))
    
    # Visualisation
    fig, ax = plt.subplots(figsize=(12, 6))
    df.plot(x='rejection_reason', y='count', kind='bar', ax=ax, color='red', alpha=0.7)
    ax.set_title('Top Raisons de Rejet')
    ax.set_ylabel('Nombre de rejets')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig('rejection_patterns.png')
    print("📊 Graphique sauvegardé: rejection_patterns.png")
    
    conn.close()


def analyze_optimal_thresholds(db_path: str = "analytics_consolidated.db"):
    """Analyser les seuils optimaux"""
    conn = sqlite3.connect(db_path)
    
    # Récupérer setups validés + trades
    df = pd.read_sql('''
        SELECT 
            sv.*,
            t.net_pnl_pct,
            CASE WHEN t.net_pnl_pct > 0 THEN 1 ELSE 0 END as won
        FROM setups_validated sv
        LEFT JOIN trades t ON sv.trade_id = t.id
        WHERE t.id IS NOT NULL
    ''', conn)
    
    print(f"\n📈 ANALYSE {len(df)} SETUPS VALIDÉS")
    
    # Analyse par score
    bins = [0, 7, 8, 9, 10, 12, 20]
    df['score_range'] = pd.cut(df['total_score'], bins=bins)
    
    score_analysis = df.groupby('score_range').agg({
        'won': ['count', 'sum', 'mean']
    })
    score_analysis.columns = ['total', 'wins', 'winrate']
    score_analysis['winrate'] = score_analysis['winrate'] * 100
    
    print("\n📊 WINRATE PAR SCORE")
    print(score_analysis.to_string())
    
    # Recommandations
    print("\n💡 RECOMMANDATIONS")
    for score_range, row in score_analysis.iterrows():
        if row['total'] >= 10:  # Au moins 10 échantillons
            if row['winrate'] < 60:
                print(f"  ⚠️ Score {score_range}: Winrate faible ({row['winrate']:.1f}%) → Augmenter min_score_required")
            elif row['winrate'] > 80:
                print(f"  ✅ Score {score_range}: Winrate excellent ({row['winrate']:.1f}%) → Conserver")
    
    conn.close()


def analyze_trade_behavior_patterns(db_path: str = "analytics_consolidated.db"):
    """Analyser les patterns de comportement des trades"""
    conn = sqlite3.connect(db_path)
    
    # Récupérer tous les trades avec comportement
    df_trades = pd.read_sql("SELECT * FROM trades WHERE id IN (SELECT DISTINCT trade_id FROM trade_behavior)", conn)
    
    print(f"\n📈 ANALYSE COMPORTEMENT {len(df_trades)} TRADES")
    
    for _, trade in df_trades.head(10).iterrows():  # Exemple sur 10 premiers
        trade_id = trade['id']
        
        # Récupérer snapshots
        df_behavior = pd.read_sql(f'''
            SELECT * FROM trade_behavior
            WHERE trade_id = {trade_id}
            ORDER BY elapsed_seconds ASC
        ''', conn)
        
        if len(df_behavior) > 0:
            max_pnl = df_behavior['pnl_pct'].max()
            min_pnl = df_behavior['pnl_pct'].min()
            final_pnl = df_behavior.iloc[-1]['pnl_pct']
            
            print(f"\n  Trade #{trade_id} ({trade['symbol']} {trade['direction']})")
            print(f"    Max PnL: {max_pnl:+.2f}% | Min PnL: {min_pnl:+.2f}% | Final: {final_pnl:+.2f}%")
            
            # Identifier si SL/TP prématuré
            if max_pnl > 0.5 and final_pnl < 0:
                print(f"    ⚠️ Potentiel SL prématuré (max: {max_pnl:+.2f}%, final: {final_pnl:+.2f}%)")
    
    conn.close()


if __name__ == "__main__":
    # Étape 1: Agréger toutes les instances
    from aggregate_multi_instances import aggregate_all_instances
    aggregate_all_instances()
    
    # Étape 2: Analyser
    analyze_rejection_patterns()
    analyze_optimal_thresholds()
    analyze_trade_behavior_patterns()
```

---

## 🚀 WORKFLOW PROPOSÉ

### Étape 1: Implémentation dans le code

**Modifications nécessaires**:

1. **`main.py`**: Initialiser `AnalyticsDatabase`
2. **`core/analyzer.py`**: Logger setups rejetés
3. **`core/position_manager.py`**: Logger setups validés + comportement trade

### Étape 2: Utilisation

```bash
# Lancer le bot (chaque instance log automatiquement)
python main.py

# Après 1-2 jours de trading, agréger
python aggregate_multi_instances.py

# Analyser
python analyze_full_history.py
```

---

## 📊 EXEMPLES DE REQUÊTES ANALYTIQUES

### Top raisons de rejet par symbole
```sql
SELECT symbol, rejection_reason, COUNT(*) as count
FROM setups_rejected
WHERE symbol IN ('BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT')
GROUP BY symbol, rejection_reason
ORDER BY symbol, count DESC;
```

### Winrate par condition technique
```sql
SELECT 
    sv.condition_types,
    COUNT(*) as total,
    SUM(CASE WHEN t.net_pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
    AVG(CASE WHEN t.net_pnl_pct > 0 THEN 1.0 ELSE 0.0 END) * 100 as winrate
FROM setups_validated sv
LEFT JOIN trades t ON sv.trade_id = t.id
WHERE t.id IS NOT NULL
GROUP BY sv.condition_types
HAVING total >= 10
ORDER BY winrate DESC;
```

### Évolution PnL d'un trade
```sql
SELECT 
    elapsed_seconds,
    current_price,
    pnl_pct,
    break_even_set,
    trailing_active
FROM trade_behavior
WHERE trade_id = 42
ORDER BY elapsed_seconds ASC;
```

### Corrélation spread/winrate
```sql
SELECT 
    CASE 
        WHEN spread < 0.02 THEN '< 0.02%'
        WHEN spread < 0.03 THEN '0.02-0.03%'
        WHEN spread < 0.04 THEN '0.03-0.04%'
        ELSE '> 0.04%'
    END as spread_range,
    COUNT(*) as total,
    AVG(CASE WHEN t.net_pnl_pct > 0 THEN 1.0 ELSE 0.0 END) * 100 as winrate
FROM setups_validated sv
LEFT JOIN trades t ON sv.trade_id = t.id
WHERE t.id IS NOT NULL
GROUP BY spread_range
ORDER BY spread_range;
```

---

## 💾 GESTION STOCKAGE

### Estimation taille données

| Table | Rows/jour (1 instance) | Taille/row | Taille/jour | Taille/mois |
|-------|------------------------|-----------|-------------|-------------|
| `setups_rejected` | ~500 | ~1 KB | ~500 KB | ~15 MB |
| `setups_validated` | ~20 | ~2 KB | ~40 KB | ~1.2 MB |
| `trades` | ~20 | ~1 KB | ~20 KB | ~600 KB |
| `trade_behavior` | ~6,000 | ~0.5 KB | ~3 MB | ~90 MB |
| **Total (1 instance)** | - | - | **~3.5 MB** | **~107 MB** |
| **Total (7 instances)** | - | - | **~25 MB** | **~750 MB** |

**Recommandations**:
- ✅ Archiver mensuellement (déplacer vers `archives/`)
- ✅ Compresser fichiers archivés (`.db.gz`)
- ✅ Conserver 6 mois en ligne, reste archivé

---

## 🎯 BÉNÉFICES ATTENDUS

### Analyses possibles

1. **Pourquoi peu de trades ?**
   - Top raisons de rejet
   - Seuils trop restrictifs identifiés

2. **Quels réglages optimaux ?**
   - Winrate par score
   - Corrélation seuils/performance

3. **Quels indicateurs fiables ?**
   - Winrate par condition
   - Combinaisons gagnantes

4. **Quel comportement des trades ?**
   - PnL max vs final (SL prématuré ?)
   - Efficacité TP Escalier

5. **Quelle gestion optimale ?**
   - Breakeven trop tôt/tard ?
   - Trailing stop efficace ?

---

## 📋 CHECKLIST IMPLÉMENTATION

- [ ] Créer `core/analytics_database.py`
- [ ] Modifier `main.py`: Initialiser `AnalyticsDatabase`
- [ ] Modifier `core/analyzer.py`: Logger setups rejetés
- [ ] Modifier `core/position_manager.py`: Logger setups validés + behavior
- [ ] Créer `aggregate_multi_instances.py`
- [ ] Créer `analyze_full_history.py`
- [ ] Tester sur 1 instance
- [ ] Déployer sur toutes instances
- [ ] Analyser après 1 semaine

---

**Prêt à implémenter ?** J'attends votre accord pour modifier le code.

---

**Date**: 2025-11-06  
**Version**: Trade Cursor v7.0 Analytics  
**Statut**: 📝 Proposition (non implémenté)

