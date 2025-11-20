# Script de vérification de la Data Quality ML
# Usage: .\check_ml_quality.ps1

Write-Host "`n=== Vérification Data Quality ML ===" -ForegroundColor Cyan

# 1. Vérifier API
Write-Host "`n1. API Data Quality:" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000/api/ml/dashboard/data_quality" -UseBasicParsing
    $data = $response.Content | ConvertFrom-Json
    
    Write-Host "   Trades: $($data.trades_count)" -ForegroundColor White
    Write-Host "   Score: $($data.quality_score)/100 ($($data.status))" -ForegroundColor $(if($data.quality_score -ge 70){"Green"}else{"Red"})
    Write-Host "   Features manquantes: $($data.missing_values.total_features_with_missing)" -ForegroundColor $(if($data.missing_values.total_features_with_missing -le 5){"Green"}else{"Red"})
    
    if ($data.missing_values.high_missing_features) {
        Write-Host "`n   Features critiques:" -ForegroundColor Red
        $data.missing_values.high_missing_features.PSObject.Properties | ForEach-Object {
            Write-Host "     - $($_.Name): $([math]::Round($_.Value, 1))% manquant" -ForegroundColor Red
        }
    }
} catch {
    Write-Host "   ❌ Erreur: Backend non accessible" -ForegroundColor Red
    Write-Host "   Veuillez redémarrer: python main.py" -ForegroundColor Yellow
    exit 1
}

# 2. Vérifier PostgreSQL (derniers scans)
Write-Host "`n2. PostgreSQL - Derniers 10 scans:" -ForegroundColor Yellow

$env:PGPASSWORD = "@Cmtr1di12345"
$query = @"
SELECT 
    TO_CHAR(timestamp, 'HH24:MI:SS') as time,
    symbol,
    CASE 
        WHEN snr_passed_1m IS NULL THEN '❌ NULL'
        WHEN snr_passed_1m = TRUE THEN '✅ TRUE'
        ELSE '❌ FALSE'
    END as snr_1m,
    CASE 
        WHEN breakout_passed_1m IS NULL THEN '❌ NULL'
        WHEN breakout_passed_1m = TRUE THEN '✅ TRUE'
        ELSE '❌ FALSE'
    END as breakout_1m,
    CASE 
        WHEN wick_passed_1m IS NULL THEN '❌ NULL'
        WHEN wick_passed_1m = TRUE THEN '✅ TRUE'
        ELSE '❌ FALSE'
    END as wick_1m,
    is_opportunity
FROM scan_logs
ORDER BY timestamp DESC
LIMIT 10;
"@

try {
    $result = & psql -h localhost -U postgres -d trade_cursor_ml -c $query -t 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host $result
        
        # Compter les NULL dans les derniers scans
        $nullCount = ($result | Select-String "NULL").Matches.Count
        if ($nullCount -eq 0) {
            Write-Host "`n   ✅ Aucun NULL détecté dans les derniers scans!" -ForegroundColor Green
        } else {
            Write-Host "`n   ⚠️  $nullCount NULL détectés - Redémarrage requis" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   ⚠️  psql non disponible ou erreur connexion" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ⚠️  Impossible de vérifier PostgreSQL" -ForegroundColor Yellow
}

# 3. Résumé
Write-Host "`n=== Résumé ===" -ForegroundColor Cyan
if ($data.quality_score -ge 70 -and $data.missing_values.total_features_with_missing -le 5) {
    Write-Host "✅ Data Quality: EXCELLENT" -ForegroundColor Green
    Write-Host "✅ Les modifications fonctionnent correctement" -ForegroundColor Green
} elseif ($data.quality_score -ge 50) {
    Write-Host "⚠️  Data Quality: MOYEN" -ForegroundColor Yellow
    Write-Host "→  Attendre plus de scans ou redémarrer le backend" -ForegroundColor Yellow
} else {
    Write-Host "❌ Data Quality: FAIBLE" -ForegroundColor Red
    Write-Host "→  Action requise: Redémarrer le backend (python main.py)" -ForegroundColor Red
}

Write-Host ""
