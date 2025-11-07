#!/usr/bin/env python3
"""Script de nettoyage de la documentation obsolète"""
import os
import shutil
from pathlib import Path

# Guides essentiels à garder
ESSENTIAL_GUIDES = {
    'GUIDE_INSTALLATION_V66.md',
    'GUIDE_TELEGRAM.md',
    'GUIDE_MULTI_INSTANCES.md',
    'GUIDE_UTILISATION_RAPIDE.md'
}

# Documentation essentielle à garder à la racine
ESSENTIAL_DOCS = {
    'README.md',
    'README_ARCHITECTURE_V2.md',
    'DOCUMENTATION_COMPLETE.md',
    'DEMARRAGE_RAPIDE.md',
    'DOCUMENTATION_INVALIDATION.md',
    'DOCUMENTATION_PHASE_8.md',
    '.gitignore',
    'cleanup_docs.py'
}

# Patterns de fichiers à archiver
ARCHIVE_PATTERNS = [
    'VERIFICATION_*.md', 'STATUS_*.md', 'STATUT_*.md', 'MIGRATION_*.md',
    'TEST_*.md', 'URGENT_*.md', 'NOTE_*.md', 'MODIFICATION_*.md',
    'INTEGRATION_*.md', 'INVALIDATION_*.md', 'PATTERNS_*.md',
    'RESTAURATION_*.md', 'SCAN_*.md', 'SERVEUR_*.md', 'AUTRES_*.md',
    'IMPACT_*.md', 'LIMITES_*.md', 'REGLAGES_*.md', 'REGLES_*.md',
    'REPONSES_*.md', 'SEUILS_*.md', 'URLS_*.md', 'PROCHAINES_*.md',
    'OPTIONS_*.md', 'INDEX_*.md', 'INSTRUCTIONS_*.md', 'REDEMARRER_*.md',
    'DOCUMENTATION_COMPLETE_DEPUIS_RESTAURATION.md',
    'DOCUMENTATION_MODIFICATIONS_POST_COMMIT.md'
]

def main():
    base_dir = Path('.')
    archive_dir = Path('docs/archive/autres')

    # Déplacer les guides secondaires
    moved_count = 0
    for guide_file in base_dir.glob('GUIDE_*.md'):
        if guide_file.name not in ESSENTIAL_GUIDES:
            dest = archive_dir / guide_file.name
            print(f"Déplacement : {guide_file.name}")
            shutil.move(str(guide_file), str(dest))
            moved_count += 1

    # Déplacer fichiers selon patterns
    for pattern in ARCHIVE_PATTERNS:
        for f in base_dir.glob(pattern):
            if f.name not in ESSENTIAL_DOCS and f.name not in ESSENTIAL_GUIDES:
                dest = archive_dir / f.name
                if not dest.exists():  # Éviter les doublons
                    print(f"Déplacement : {f.name}")
                    try:
                        shutil.move(str(f), str(dest))
                        moved_count += 1
                    except Exception as e:
                        print(f"Erreur : {f.name} - {e}")

    print(f"\n✓ {moved_count} fichiers déplacés vers docs/archive/autres/")
    print(f"✓ Total archive : {len(list(archive_dir.glob('*.md')))} fichiers")

    # Afficher documentation restante
    remaining = [f.name for f in base_dir.glob('*.md')]
    print(f"\n📄 Documentation restante à la racine : {len(remaining)} fichiers")
    for doc in sorted(remaining):
        print(f"  - {doc}")

if __name__ == '__main__':
    main()
