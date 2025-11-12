# Guide : Vérifier les Indicateurs d'Entrée dans PostgreSQL

## 1. Attendre qu'un Trade soit Ouvert et Fermé

1. Laissez le bot tourner et attendre qu'une position soit ouverte automatiquement
2. Attendez que la position soit fermée (TP, SL, ou manuellement)
3. Une fois la position fermée, les données sont loggées dans PostgreSQL

## 2. Se Connecter à PostgreSQL

### Option A : Via psql (ligne de commande)
```bash
psql -U postgres -d trade_cursor_ml
```

### Option B : Via pgAdmin ou autre outil graphique
- Connectez-vous à la base `trade_cursor_ml`

## 3. Vérifier les Indicateurs d'Entrée

### Requête 1 : Voir tous les trades avec leurs indicateurs d'entrée
```sql
SELECT 
    id,
    symbol,
    direction,
    timestamp_entry,
    timestamp_exit,
    -- Indicateurs RSI
    entry_rsi_1m,
    entry_rsi_5m,
    entry_rsi_prev_1m,
    entry_rsi_prev_5m,
    -- Indicateurs MACD
    entry_macd_1m,
    entry_macd_signal_1m,
    entry_macd_hist_1m,
    entry_macd_hist_prev_1m,
    entry_macd_5m,
    entry_macd_signal_5m,
    entry_macd_hist_5m,
    entry_macd_hist_prev_5m,
    -- Indicateurs ADX
    entry_adx_1m,
    entry_adx_5m,
    entry_di_plus_1m,
    entry_di_minus_1m,
    entry_di_gap_1m,
    entry_di_plus_5m,
    entry_di_minus_5m,
    entry_di_gap_5m,
    -- Indicateurs EMA
    entry_ema9_1m,
    entry_ema21_1m,
    entry_ema_diff_pct_1m,
    entry_ema9_5m,
    entry_ema21_5m,
    entry_ema_diff_pct_5m,
    -- Indicateurs ATR
    entry_atr_1m,
    entry_atr_pct_1m,
    entry_atr_5m,
    entry_atr_pct_5m,
    -- Score
    entry_score,
    -- Conditions
    entry_conditions,
    entry_condition_count
FROM trades
ORDER BY timestamp_entry DESC
LIMIT 10;
```

### Requête 2 : Compter combien de trades ont des indicateurs remplis
```sql
SELECT 
    COUNT(*) as total_trades,
    -- Compter les trades avec RSI 1m
    COUNT(entry_rsi_1m) FILTER (WHERE entry_rsi_1m IS NOT NULL) as trades_with_rsi_1m,
    COUNT(entry_rsi_5m) FILTER (WHERE entry_rsi_5m IS NOT NULL) as trades_with_rsi_5m,
    -- Compter les trades avec MACD 1m
    COUNT(entry_macd_hist_1m) FILTER (WHERE entry_macd_hist_1m IS NOT NULL) as trades_with_macd_hist_1m,
    COUNT(entry_macd_hist_5m) FILTER (WHERE entry_macd_hist_5m IS NOT NULL) as trades_with_macd_hist_5m,
    -- Compter les trades avec ADX 1m
    COUNT(entry_adx_1m) FILTER (WHERE entry_adx_1m IS NOT NULL) as trades_with_adx_1m,
    COUNT(entry_adx_5m) FILTER (WHERE entry_adx_5m IS NOT NULL) as trades_with_adx_5m,
    -- Compter les trades avec EMA 1m
    COUNT(entry_ema9_1m) FILTER (WHERE entry_ema9_1m IS NOT NULL) as trades_with_ema9_1m,
    COUNT(entry_ema21_1m) FILTER (WHERE entry_ema21_1m IS NOT NULL) as trades_with_ema21_1m,
    -- Compter les trades avec ATR 1m
    COUNT(entry_atr_1m) FILTER (WHERE entry_atr_1m IS NOT NULL) as trades_with_atr_1m,
    COUNT(entry_atr_5m) FILTER (WHERE entry_atr_5m IS NOT NULL) as trades_with_atr_5m,
    -- Compter les trades avec score
    COUNT(entry_score) FILTER (WHERE entry_score IS NOT NULL) as trades_with_score,
    -- Compter les trades avec conditions
    COUNT(entry_conditions) FILTER (WHERE entry_conditions IS NOT NULL AND array_length(entry_conditions, 1) > 0) as trades_with_conditions
FROM trades;
```

### Requête 3 : Voir le dernier trade avec tous ses indicateurs
```sql
SELECT 
    id,
    symbol,
    direction,
    timestamp_entry,
    timestamp_exit,
    entry_price,
    exit_price,
    pnl_pct,
    -- RSI
    entry_rsi_1m,
    entry_rsi_5m,
    -- MACD
    entry_macd_hist_1m,
    entry_macd_hist_5m,
    -- ADX
    entry_adx_1m,
    entry_adx_5m,
    -- EMA
    entry_ema9_1m,
    entry_ema21_1m,
    entry_ema_diff_pct_1m,
    entry_ema9_5m,
    entry_ema21_5m,
    entry_ema_diff_pct_5m,
    -- ATR
    entry_atr_pct_1m,
    entry_atr_pct_5m,
    -- Score et conditions
    entry_score,
    entry_conditions,
    entry_condition_count
FROM trades
ORDER BY timestamp_entry DESC
LIMIT 1;
```

### Requête 4 : Vérifier les trades récents avec indicateurs manquants
```sql
SELECT 
    id,
    symbol,
    timestamp_entry,
    -- Compter les indicateurs NULL
    (
        CASE WHEN entry_rsi_1m IS NULL THEN 1 ELSE 0 END +
        CASE WHEN entry_rsi_5m IS NULL THEN 1 ELSE 0 END +
        CASE WHEN entry_macd_hist_1m IS NULL THEN 1 ELSE 0 END +
        CASE WHEN entry_macd_hist_5m IS NULL THEN 1 ELSE 0 END +
        CASE WHEN entry_adx_1m IS NULL THEN 1 ELSE 0 END +
        CASE WHEN entry_adx_5m IS NULL THEN 1 ELSE 0 END +
        CASE WHEN entry_ema9_1m IS NULL THEN 1 ELSE 0 END +
        CASE WHEN entry_ema21_1m IS NULL THEN 1 ELSE 0 END +
        CASE WHEN entry_atr_1m IS NULL THEN 1 ELSE 0 END +
        CASE WHEN entry_atr_5m IS NULL THEN 1 ELSE 0 END
    ) as indicateurs_manquants
FROM trades
WHERE timestamp_entry > NOW() - INTERVAL '1 hour'
ORDER BY timestamp_entry DESC;
```

## 4. Script Python pour Vérification Automatique

Créez un fichier `database/verifier_indicators.py` :

```python
#!/usr/bin/env python3
"""Script pour vérifier les indicateurs d'entrée dans PostgreSQL"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

def verify_indicators():
    """Vérifie les indicateurs d'entrée dans la table trades"""
    
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Requête pour compter les indicateurs remplis
    query = """
        SELECT 
            COUNT(*) as total_trades,
            COUNT(entry_rsi_1m) FILTER (WHERE entry_rsi_1m IS NOT NULL) as trades_with_rsi_1m,
            COUNT(entry_rsi_5m) FILTER (WHERE entry_rsi_5m IS NOT NULL) as trades_with_rsi_5m,
            COUNT(entry_macd_hist_1m) FILTER (WHERE entry_macd_hist_1m IS NOT NULL) as trades_with_macd_hist_1m,
            COUNT(entry_macd_hist_5m) FILTER (WHERE entry_macd_hist_5m IS NOT NULL) as trades_with_macd_hist_5m,
            COUNT(entry_adx_1m) FILTER (WHERE entry_adx_1m IS NOT NULL) as trades_with_adx_1m,
            COUNT(entry_adx_5m) FILTER (WHERE entry_adx_5m IS NOT NULL) as trades_with_adx_5m,
            COUNT(entry_ema9_1m) FILTER (WHERE entry_ema9_1m IS NOT NULL) as trades_with_ema9_1m,
            COUNT(entry_ema21_1m) FILTER (WHERE entry_ema21_1m IS NOT NULL) as trades_with_ema21_1m,
            COUNT(entry_atr_1m) FILTER (WHERE entry_atr_1m IS NOT NULL) as trades_with_atr_1m,
            COUNT(entry_atr_5m) FILTER (WHERE entry_atr_5m IS NOT NULL) as trades_with_atr_5m,
            COUNT(entry_score) FILTER (WHERE entry_score IS NOT NULL) as trades_with_score
        FROM trades;
    """
    
    cur.execute(query)
    result = cur.fetchone()
    
    print("=" * 60)
    print("VÉRIFICATION DES INDICATEURS D'ENTRÉE")
    print("=" * 60)
    print(f"Total trades: {result['total_trades']}")
    print(f"\nIndicateurs RSI:")
    print(f"  - RSI 1m: {result['trades_with_rsi_1m']}/{result['total_trades']} ({result['trades_with_rsi_1m']/result['total_trades']*100 if result['total_trades'] > 0 else 0:.1f}%)")
    print(f"  - RSI 5m: {result['trades_with_rsi_5m']}/{result['total_trades']} ({result['trades_with_rsi_5m']/result['total_trades']*100 if result['total_trades'] > 0 else 0:.1f}%)")
    print(f"\nIndicateurs MACD:")
    print(f"  - MACD Hist 1m: {result['trades_with_macd_hist_1m']}/{result['total_trades']} ({result['trades_with_macd_hist_1m']/result['total_trades']*100 if result['total_trades'] > 0 else 0:.1f}%)")
    print(f"  - MACD Hist 5m: {result['trades_with_macd_hist_5m']}/{result['total_trades']} ({result['trades_with_macd_hist_5m']/result['total_trades']*100 if result['total_trades'] > 0 else 0:.1f}%)")
    print(f"\nIndicateurs ADX:")
    print(f"  - ADX 1m: {result['trades_with_adx_1m']}/{result['total_trades']} ({result['trades_with_adx_1m']/result['total_trades']*100 if result['total_trades'] > 0 else 0:.1f}%)")
    print(f"  - ADX 5m: {result['trades_with_adx_5m']}/{result['total_trades']} ({result['trades_with_adx_5m']/result['total_trades']*100 if result['total_trades'] > 0 else 0:.1f}%)")
    print(f"\nIndicateurs EMA:")
    print(f"  - EMA9 1m: {result['trades_with_ema9_1m']}/{result['total_trades']} ({result['trades_with_ema9_1m']/result['total_trades']*100 if result['total_trades'] > 0 else 0:.1f}%)")
    print(f"  - EMA21 1m: {result['trades_with_ema21_1m']}/{result['total_trades']} ({result['trades_with_ema21_1m']/result['total_trades']*100 if result['total_trades'] > 0 else 0:.1f}%)")
    print(f"\nIndicateurs ATR:")
    print(f"  - ATR 1m: {result['trades_with_atr_1m']}/{result['total_trades']} ({result['trades_with_atr_1m']/result['total_trades']*100 if result['total_trades'] > 0 else 0:.1f}%)")
    print(f"  - ATR 5m: {result['trades_with_atr_5m']}/{result['total_trades']} ({result['trades_with_atr_5m']/result['total_trades']*100 if result['total_trades'] > 0 else 0:.1f}%)")
    print(f"\nScore:")
    print(f"  - Score: {result['trades_with_score']}/{result['total_trades']} ({result['trades_with_score']/result['total_trades']*100 if result['total_trades'] > 0 else 0:.1f}%)")
    
    # Voir le dernier trade
    query_last = """
        SELECT 
            id,
            symbol,
            direction,
            timestamp_entry,
            entry_rsi_1m,
            entry_rsi_5m,
            entry_macd_hist_1m,
            entry_macd_hist_5m,
            entry_adx_1m,
            entry_adx_5m,
            entry_score,
            entry_conditions
        FROM trades
        ORDER BY timestamp_entry DESC
        LIMIT 1;
    """
    
    cur.execute(query_last)
    last_trade = cur.fetchone()
    
    if last_trade:
        print("\n" + "=" * 60)
        print("DERNIER TRADE")
        print("=" * 60)
        print(f"ID: {last_trade['id']}")
        print(f"Symbol: {last_trade['symbol']}")
        print(f"Direction: {last_trade['direction']}")
        print(f"Timestamp: {last_trade['timestamp_entry']}")
        print(f"\nIndicateurs:")
        print(f"  - RSI 1m: {last_trade['entry_rsi_1m']}")
        print(f"  - RSI 5m: {last_trade['entry_rsi_5m']}")
        print(f"  - MACD Hist 1m: {last_trade['entry_macd_hist_1m']}")
        print(f"  - MACD Hist 5m: {last_trade['entry_macd_hist_5m']}")
        print(f"  - ADX 1m: {last_trade['entry_adx_1m']}")
        print(f"  - ADX 5m: {last_trade['entry_adx_5m']}")
        print(f"  - Score: {last_trade['entry_score']}")
        print(f"  - Conditions: {last_trade['entry_conditions']}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    verify_indicators()
```

## 5. Utilisation

### Via psql :
```bash
cd "C:\Users\sebta\Documents\clone github\test\test"
psql -U postgres -d trade_cursor_ml -f database/VERIFIER_INDICATEURS_ENTREE.md
```

### Via Python :
```bash
cd "C:\Users\sebta\Documents\clone github\test\test"
python database/verifier_indicators.py
```

## 6. Résultat Attendu

Après qu'un trade soit fermé, vous devriez voir :
- `entry_rsi_1m` et `entry_rsi_5m` remplis
- `entry_macd_hist_1m` et `entry_macd_hist_5m` remplis
- `entry_adx_1m` et `entry_adx_5m` remplis
- `entry_ema9_1m`, `entry_ema21_1m` remplis
- `entry_atr_1m` et `entry_atr_5m` remplis
- `entry_score` rempli
- `entry_conditions` rempli (array de strings)

Si certains indicateurs sont NULL, c'est normal si le timeframe correspondant a été rejeté (par exemple, si `analysis_1m` a été rejeté, `entry_rsi_1m` sera NULL).

