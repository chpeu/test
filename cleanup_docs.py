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
    '.gitignore',
    'ACTION_PLAN.md',
    'CONFIG_POSTGRES.md',
    'DEMARRAGE_RAPIDE.md',
    'DOCUMENTATION_COMPLETE.md',
    'DOCUMENTATION_INVALIDATION.md',
    'DOCUMENTATION_PHASE_8.md',
    'FEATURES_ROADMAP.md',
    'FIX_DATALOGGER.md',
    'FRONTEND_CORRECTIONS_STATUS.md',
    'FRONTEND_STATUS_UPDATE.md',
    'GUIDE_INSTALLATION_V66.md',
    'GUIDE_MULTI_INSTANCES.md',
    'GUIDE_TELEGRAM.md',
    'GUIDE_UTILISATION_RAPIDE.md',
    'INVESTIGATION_SOLUTION.md',
    'PARAMETRES_VARIABLES_SCAN_SCALABLES.md',
    'PHASE3_DATALOGGER_OPTIMIZATIONS.md',
    'PR_EXPLANATION.md',
    'PRODUCTION_DEPLOYMENT.md',
    'RAPPORT_SYNCHRONISATION_WEBSOCKET.md',
    'README.md',
    'README_ARCHITECTURE_V2.md',
    'README_REFACTORING.md',
    'README_WINDOWS.md',
    'VARIABLES_FIX.md',
    'WORKFLOW_PR.md',
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
    archive_dir.mkdir(parents=True, exist_ok=True)

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

    print(f"\n[OK] {moved_count} fichiers déplacés vers docs/archive/autres/")
    print(f"[OK] Total archive : {len(list(archive_dir.glob('*.md')))} fichiers")

    # Deuxième passe: déplacer tout fichier Markdown non essentiel restant
    for md_file in base_dir.glob('*.md'):
        if md_file.name in ESSENTIAL_DOCS or md_file.name in ESSENTIAL_GUIDES:
            continue
        dest = archive_dir / md_file.name
        if dest.exists():
            continue
        print(f"Déplacement : {md_file.name}")
        shutil.move(str(md_file), str(dest))
        moved_count += 1

    # Recompter après la deuxième passe
    print(f"\n[OK] {moved_count} fichiers déplacés vers docs/archive/autres/")
    print(f"[OK] Total archive : {len(list(archive_dir.glob('*.md')))} fichiers")

    remaining = sorted(
        f.name for f in base_dir.glob('*.md')
        if f.name in ESSENTIAL_DOCS or f.name in ESSENTIAL_GUIDES
    )
    print(f"\n📄 Documentation restante à la racine : {len(remaining)} fichiers")
    for doc in remaining:
        print(f"  - {doc}")

if __name__ == '__main__':
    main()
