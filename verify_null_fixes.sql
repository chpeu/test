-- Verification des corrections NULL sur trades recents
-- Trades des 6 dernieres heures
SELECT 'RECENT TRADES COUNT' as check_type, COUNT(*) as count
FROM trades 
WHERE timestamp_entry >= NOW() - INTERVAL '6 hours';

-- Colonnes critiques sur trades recents
SELECT 
  'setup_score' as column_name,
  COUNT(*) as total,
  COUNT(setup_score) as filled,
  COUNT(*) - COUNT(setup_score) as nulls,
  ROUND((COUNT(*) - COUNT(setup_score)) * 100.0 / COUNT(*), 2) as null_pct
FROM trades 
WHERE timestamp_entry >= NOW() - INTERVAL '6 hours'

UNION ALL

SELECT 
  'price_at_signal',
  COUNT(*),
  COUNT(price_at_signal),
  COUNT(*) - COUNT(price_at_signal),
  ROUND((COUNT(*) - COUNT(price_at_signal)) * 100.0 / COUNT(*), 2)
FROM trades 
WHERE timestamp_entry >= NOW() - INTERVAL '6 hours'

UNION ALL

SELECT 
  'ml_prediction',
  COUNT(*),
  COUNT(ml_prediction),
  COUNT(*) - COUNT(ml_prediction),
  ROUND((COUNT(*) - COUNT(ml_prediction)) * 100.0 / COUNT(*), 2)
FROM trades 
WHERE timestamp_entry >= NOW() - INTERVAL '6 hours'

UNION ALL

SELECT 
  'user_rating',
  COUNT(*),
  COUNT(user_rating),
  COUNT(*) - COUNT(user_rating),
  ROUND((COUNT(*) - COUNT(user_rating)) * 100.0 / COUNT(*), 2)
FROM trades 
WHERE timestamp_entry >= NOW() - INTERVAL '6 hours'

UNION ALL

SELECT 
  'scan_log_id',
  COUNT(*),
  COUNT(scan_log_id),
  COUNT(*) - COUNT(scan_log_id),
  ROUND((COUNT(*) - COUNT(scan_log_id)) * 100.0 / COUNT(*), 2)
FROM trades 
WHERE timestamp_entry >= NOW() - INTERVAL '6 hours'

UNION ALL

SELECT 
  'is_live_trade',
  COUNT(*),
  COUNT(is_live_trade),
  COUNT(*) - COUNT(is_live_trade),
  ROUND((COUNT(*) - COUNT(is_live_trade)) * 100.0 / COUNT(*), 2)
FROM trades 
WHERE timestamp_entry >= NOW() - INTERVAL '6 hours';

-- Detail des 3 trades les plus recents
SELECT 
  'RECENT TRADE DETAILS' as info,
  LEFT(id::text, 8) as trade_id,
  symbol,
  timestamp_entry,
  direction,
  CASE WHEN setup_score IS NULL THEN 'NULL' ELSE setup_score::text END as setup_score,
  CASE WHEN scan_log_id IS NULL THEN 'NULL' ELSE scan_log_id::text END as scan_log_id,
  CASE WHEN price_at_signal IS NULL THEN 'NULL' ELSE price_at_signal::text END as price_at_signal,
  CASE WHEN ml_prediction IS NULL THEN 'NULL' ELSE ml_prediction END as ml_prediction
FROM trades 
WHERE timestamp_entry >= NOW() - INTERVAL '6 hours'
ORDER BY timestamp_entry DESC 
LIMIT 3;

-- Scan_logs recents - colonnes contexte
SELECT 'RECENT SCANS COUNT' as check_type, COUNT(*) as count
FROM scan_logs 
WHERE timestamp >= NOW() - INTERVAL '2 hours';

SELECT 
  'market_regime' as column_name,
  COUNT(*) as total,
  COUNT(market_regime) as filled,
  ROUND(COUNT(market_regime) * 100.0 / COUNT(*), 2) as filled_pct
FROM scan_logs 
WHERE timestamp >= NOW() - INTERVAL '2 hours'

UNION ALL

SELECT 
  'session_market',
  COUNT(*),
  COUNT(session_market),
  ROUND(COUNT(session_market) * 100.0 / COUNT(*), 2)
FROM scan_logs 
WHERE timestamp >= NOW() - INTERVAL '2 hours'

UNION ALL

SELECT 
  'hour_utc',
  COUNT(*),
  COUNT(hour_utc),
  ROUND(COUNT(hour_utc) * 100.0 / COUNT(*), 2)
FROM scan_logs 
WHERE timestamp >= NOW() - INTERVAL '2 hours';
