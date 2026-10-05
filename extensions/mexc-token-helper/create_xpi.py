#!/usr/bin/env python3
"""
Script pour créer une extension Firefox XPI fonctionnelle pour MEXC Token Helper
Supprime l'ancienne archive et crée une nouvelle version propre
"""

import os
import zipfile
import shutil
from pathlib import Path

def create_mexc_extension():
    """Crée l'extension Firefox XPI pour MEXC Token Helper"""
    
    # Chemin du dossier de l'extension
    extension_dir = Path(__file__).parent
    
    # Nom du fichier XPI
    xpi_filename = "mexc-token-helper.xpi"
    xpi_path = extension_dir / xpi_filename
    old_xpi = extension_dir / "firefox mexc.xpi"
    
    print("CREATION EXTENSION FIREFOX MEXC TOKEN HELPER")
    print("=" * 50)
    
    # 1. Supprimer l'ancienne archive si elle existe
    if old_xpi.exists():
        old_xpi.unlink()
        print("OK Ancienne archive 'firefox mexc.xpi' supprimee")
    
    if xpi_path.exists():
        xpi_path.unlink()
        print("OK Archive existante supprimee")
    
    # 2. Fichiers et dossiers à inclure
    files_to_include = [
        "manifest.json",
        "background/background.js",
        "content/content.js", 
        "popup/popup.html",
        "popup/popup.css",
        "popup/popup.js",
        "icons/icon-48.png",
        "icons/icon-96.png",
        "icons/icon.svg"
    ]
    
    # 3. Vérifier que tous les fichiers existent
    missing_files = []
    for file_path in files_to_include:
        full_path = extension_dir / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("ERREUR: Fichiers manquants:")
        for missing in missing_files:
            print(f"   - {missing}")
        return False
    
    # 4. Créer l'archive XPI
    print("\nCreation de l'archive XPI...")
    
    try:
        with zipfile.ZipFile(xpi_path, 'w', zipfile.ZIP_DEFLATED) as xpi:
            for file_path in files_to_include:
                full_path = extension_dir / file_path
                # Ajouter le fichier avec son chemin relatif
                xpi.write(full_path, file_path)
                print(f"   OK Ajoute: {file_path}")
        
        print(f"\nSUCCESS! Extension creee: {xpi_filename}")
        print(f"Emplacement: {xpi_path}")
        print(f"Taille: {xpi_path.stat().st_size} bytes")
        
        return True
        
    except Exception as e:
        print(f"ERREUR lors de la creation: {e}")
        return False

def print_installation_instructions():
    """Affiche les instructions d'installation"""
    
    print("\n" + "="*60)
    print("INSTRUCTIONS D'INSTALLATION FIREFOX")
    print("="*60)
    
    print("\nMETHODE 1 - Installation XPI (Recommandee)")
    print("-" * 40)
    print("1. Ouvrir Firefox")
    print("2. Aller sur: about:addons")
    print("3. Cliquer sur la roue dentee")
    print("4. 'Installer un module depuis un fichier...'")
    print("5. Selectionner: mexc-token-helper.xpi")
    print("6. Confirmer l'installation")
    
    print("\nMETHODE 2 - Mode Developpeur (Alternative)")
    print("-" * 40)  
    print("1. Ouvrir Firefox")
    print("2. Aller sur: about:debugging")
    print("3. Cliquer 'Ce Firefox'")
    print("4. 'Charger un module temporaire...'")
    print("5. Selectionner: manifest.json")
    
    print("\nUTILISATION")
    print("-" * 40)
    print("- L'extension apparaitra dans la barre d'outils")
    print("- Aller sur futures.mexc.com")
    print("- Se connecter a votre compte")
    print("- Cliquer sur l'icone de l'extension")
    print("- Le token sera automatiquement extrait et copie")
    
    print("\nSECURITE")
    print("-" * 40)
    print("- Extension non signee = avertissement Firefox normal")
    print("- Code source visible dans les fichiers")
    print("- Aucune donnee envoyee vers l'exterieur")
    print("- Token uniquement copie dans le presse-papiers")

if __name__ == "__main__":
    success = create_mexc_extension()
    print_installation_instructions()
    
    if success:
        print(f"\nExtension Firefox prete a installer!")
    else:
        print(f"\nEchec de la creation de l'extension")
