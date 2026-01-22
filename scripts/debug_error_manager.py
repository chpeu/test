"""
Script pour diagnostiquer le problème avec ErrorHistoryManager
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.error_history import get_error_history

print("=" * 80)
print("🔍 DIAGNOSTIC ERROR HISTORY MANAGER")
print("=" * 80)

# 1. Obtenir l'instance
error_history = get_error_history()
print(f"\n📋 Instance: {error_history}")
print(f"Max errors: {error_history.max_errors}")

# 2. Vérifier l'état actuel
current_errors = error_history.get_errors()
print(f"\n📊 Erreurs actuelles: {len(current_errors)}")

if current_errors:
    print("\n📋 Erreurs existantes:")
    for i, error in enumerate(current_errors[:3], 1):
        print(f"  {i}. {error['level']} - {error['message']}")
else:
    print("⚠️ Aucune erreur trouvée")

# 3. Ajouter une erreur de test
print("\n🧪 Test d'ajout d'erreur...")
error_history.add_error(
    level="ERROR",
    message="Test direct ErrorHistoryManager",
    detail="Erreur ajoutée directement via le script de diagnostic",
    raw_message="DIAGNOSTIC_SCRIPT: Test direct"
)

# 4. Vérifier après ajout
current_errors = error_history.get_errors()
print(f"📊 Erreurs après ajout: {len(current_errors)}")

if current_errors:
    print("\n📋 Dernières erreurs:")
    for i, error in enumerate(current_errors[:3], 1):
        print(f"  {i}. {error}")
        print()

print("\n" + "=" * 80)
print("✅ Diagnostic terminé")
print("=" * 80)
