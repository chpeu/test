# Script PowerShell pour configurer le firewall Windows pour Trade Cursor
# Permet l'accès depuis iPhone et autres appareils sur le réseau local

param(
    [int]$Port = 5000
)

Write-Host "🔥 Configuration du Firewall Windows pour Trade Cursor" -ForegroundColor Cyan
Write-Host "Port: $Port" -ForegroundColor Yellow
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

Write-Host "✅ Droits administrateur confirmés" -ForegroundColor Green
Write-Host ""

# Vérifier si la règle existe déjà
$ruleName = "Trade Cursor - Port $Port"
$existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

if ($existingRule) {
    Write-Host "⚠️  Règle existante trouvée: $ruleName" -ForegroundColor Yellow
    $remove = Read-Host "Voulez-vous la supprimer et la recréer? (O/N)"
    if ($remove -eq "O" -or $remove -eq "o") {
        Remove-NetFirewallRule -DisplayName $ruleName
        Write-Host "✅ Règle supprimée" -ForegroundColor Green
    } else {
        Write-Host "ℹ️  Règle conservée" -ForegroundColor Cyan
        exit 0
    }
}

# Créer la règle de firewall
Write-Host "🔧 Création de la règle de firewall..." -ForegroundColor Cyan

try {
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $Port `
        -Action Allow `
        -Profile Domain,Private,Public `
        -Description "Autorise l'accès au serveur Trade Cursor depuis le réseau local (iPhone, etc.)"

    Write-Host "✅ Règle de firewall créée avec succès!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📱 Vous pouvez maintenant accéder au serveur depuis votre iPhone:" -ForegroundColor Cyan
    Write-Host "   1. Assurez-vous que votre iPhone est sur le même réseau Wi-Fi" -ForegroundColor Yellow
    Write-Host "   2. Utilisez l'IP affichée au démarrage du serveur" -ForegroundColor Yellow
    Write-Host "   3. Format: http://[IP]:$Port/" -ForegroundColor Yellow
    Write-Host ""
} catch {
    Write-Host "❌ Erreur lors de la création de la règle: $_" -ForegroundColor Red
    exit 1
}

# Afficher les règles créées
Write-Host "📋 Règles de firewall pour Trade Cursor:" -ForegroundColor Cyan
Get-NetFirewallRule -DisplayName "*Trade Cursor*" | Format-Table DisplayName, Enabled, Direction, Action -AutoSize

