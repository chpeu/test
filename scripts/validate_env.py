#!/usr/bin/env python3
"""Validation des variables d'environnement requises"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "SECRET_KEY",
    "ENVIRONMENT",
]

OPTIONAL_VARS = [
    "MEXC_API_KEY",
    "MEXC_SECRET_KEY",
    "DATABASE_URL",
    "DEBUG",
]

def validate_env():
    """Valider les variables d'environnement"""
    errors = []
    warnings = []

    # Vérifier variables requises
    for var in REQUIRED_VARS:
        if not os.getenv(var):
            errors.append(f"❌ Variable requise manquante: {var}")

    # Vérifier variables optionnelles
    for var in OPTIONAL_VARS:
        if not os.getenv(var):
            warnings.append(f"⚠️  Variable optionnelle manquante: {var}")

    # Afficher résultats
    if errors:
        print("❌ ERREURS:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)

    if warnings:
        print("⚠️  AVERTISSEMENTS:")
        for warning in warnings:
            print(f"  {warning}")

    print("✅ Toutes les variables requises sont présentes")
    return True

if __name__ == "__main__":
    validate_env()

