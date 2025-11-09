# Script PowerShell pour configurer le firewall Windows pour Trade Cursor
# Permet l'accès depuis iPhone et autres appareils sur le réseau local

param(
    [int[]]$Ports = @(5000, 3000)  # 🔥 Ports 5000 (Backend) et 3000 (Frontend)
)

Write-Host "🔥 Configuration du Firewall Windows pour Trade Cursor" -ForegroundColor Cyan
Write-Host "Ports: $($Ports -join ', ')" -ForegroundColor Yellow
Write-Host ""

# Vérifier si on est administrateur
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "❌ ERREUR: Ce script nécessite des droits administrateur!" -ForegroundColor Red
    Write-Host "   Veuillez exécuter PowerShell en tant qu'administrateur" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   Clic droit sur PowerShell → Exécuter en tant qu'administrateur" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Droits administrateur détectés." -ForegroundColor Green
Write-Host ""

# 🔥 Configurer le firewall pour chaque port
foreach ($Port in $Ports) {
    Write-Host "🔧 Configuration du port $Port..." -ForegroundColor Cyan
    
    # Nom de la règle de firewall
    $ruleName = "TradeCursor_Port_$Port"
    
    # Vérifier si la règle existe déjà
    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    
    if ($existingRule) {
        Write-Host "ℹ️ Règle de firewall '$ruleName' existe déjà. Suppression..." -ForegroundColor Yellow
        Remove-NetFirewallRule -DisplayName $ruleName -Confirm:$false
        Write-Host "✅ Règle existante supprimée." -ForegroundColor Green
    }
    
    Write-Host "➕ Ajout de la règle de firewall '$ruleName' pour le port TCP $Port..." -ForegroundColor Yellow
    try {
        $description = if ($Port -eq 5000) {
            "Permet l'accès au serveur Trade Cursor (FastAPI Backend) sur le port $Port"
        } else {
            "Permet l'accès au serveur Trade Cursor (SvelteKit Frontend) sur le port $Port"
        }
        
        New-NetFirewallRule -DisplayName $ruleName `
                            -Direction Inbound `
                            -Action Allow `
                            -Protocol TCP `
                            -LocalPort $Port `
                            -Profile Any `
                            -EdgeTraversalPolicy Allow `
                            -Description $description
        Write-Host "✅ Règle de firewall '$ruleName' ajoutée avec succès." -ForegroundColor Green
    } catch {
        Write-Host "❌ ERREUR lors de l'ajout de la règle de firewall: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

Write-Host "🎉 Configuration du firewall terminée pour Trade Cursor sur les ports $($Ports -join ', ')." -ForegroundColor Green
Write-Host "   Le bot devrait maintenant être accessible depuis d'autres appareils sur votre réseau local." -ForegroundColor Green
Write-Host ""
Write-Host "Ports configurés:" -ForegroundColor Yellow
Write-Host "  - Port 5000: Backend FastAPI" -ForegroundColor Gray
Write-Host "  - Port 3000: Frontend SvelteKit (dev)" -ForegroundColor Gray
Write-Host ""
Write-Host "Pour vérifier l'état des règles, exécutez:" -ForegroundColor DarkGray
foreach ($Port in $Ports) {
    Write-Host "Get-NetFirewallRule -DisplayName 'TradeCursor_Port_$Port'" -ForegroundColor DarkGray
}
