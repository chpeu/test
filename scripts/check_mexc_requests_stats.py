#!/usr/bin/env python3
"""
Script pour vérifier les statistiques des requêtes MEXC
Affiche le nombre total de requêtes, erreurs 429/403, et rate actuel
"""
import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    try:
        # Importer le rate limiter global
        from trading.mexc_futures_bypass import _rate_limiter
        
        # Récupérer les statistiques
        stats = _rate_limiter.get_stats()
        
        print("🔍 STATISTIQUES DES REQUÊTES MEXC")
        print("=" * 50)
        print(f"📊 Total requêtes envoyées : {stats['total_requests']:,}")
        print(f"⚡ Rate actuel           : {stats['current_rate']:.2f} req/s")
        print(f"⚠️  Erreurs 429 (rate limit): {stats['total_429']:,}")
        print(f"❌ Erreurs 403 (accès)     : {stats['total_403']:,}")
        print(f"✅ Succès consécutifs      : {stats['consecutive_success']:,}")
        print(f"🚫 Rate limiter désactivé  : {'OUI' if stats['disabled'] else 'NON'}")
        
        # Calculs supplémentaires
        total_errors = stats['total_429'] + stats['total_403']
        if stats['total_requests'] > 0:
            error_rate = (total_errors / stats['total_requests']) * 100
            success_rate = ((stats['total_requests'] - total_errors) / stats['total_requests']) * 100
            print(f"📈 Taux de succès          : {success_rate:.2f}%")
            print(f"📉 Taux d'erreur           : {error_rate:.2f}%")
        
        # Statut global
        print("\n" + "=" * 50)
        if stats['disabled']:
            print("🔴 STATUT: BLOQUÉ (token expiré ou IP bannie)")
        elif stats['total_403'] > 0:
            print("🟡 STATUT: PROBLÈME D'AUTHENTIFICATION")
        elif stats['total_429'] > stats['total_requests'] * 0.1:
            print("🟠 STATUT: RATE LIMITING ÉLEVÉ")
        else:
            print("✅ STATUT: NORMAL")
            
    except ImportError as e:
        print(f"❌ Erreur import: {e}")
        print("Assurez-vous que le bot est démarré et que les modules sont disponibles")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
