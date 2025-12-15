# MEXC Token Helper - Extension Firefox

Extension Firefox pour récupérer facilement le token d'authentification MEXC.

## Installation

### Méthode 1 : Installation temporaire (développement)

1. Ouvrir Firefox
2. Taper `about:debugging` dans la barre d'adresse
3. Cliquer sur **"Ce Firefox"** (ou "This Firefox")
4. Cliquer sur **"Charger un module complémentaire temporaire..."**
5. Naviguer vers ce dossier et sélectionner `manifest.json`

> ⚠️ L'extension sera supprimée au redémarrage de Firefox.

### Méthode 2 : Installation permanente

1. Créer un fichier `.xpi` :
   - Sélectionner tous les fichiers du dossier
   - Créer une archive ZIP
   - Renommer `.zip` en `.xpi`
2. Ouvrir Firefox et aller dans `about:addons`
3. Cliquer sur l'engrenage ⚙️ → "Installer un module depuis un fichier..."
4. Sélectionner le fichier `.xpi`

## Utilisation

1. **Se connecter sur MEXC** : Aller sur https://futures.mexc.com et se connecter
2. **Cliquer sur l'icône** de l'extension dans la barre d'outils
3. **Copier le token** : Cliquer sur 📋 pour copier dans le presse-papier
4. **Envoyer au bot** (optionnel) : Configurer l'URL et cliquer sur "Envoyer"

## Fonctionnalités

- ✅ Détection automatique de la connexion MEXC
- ✅ Récupération du token d'authentification
- ✅ Copie en un clic
- ✅ Envoi direct au trading bot (si configuré)
- ✅ Badge vert quand connecté
- ✅ Notification à la connexion

## Configuration du Bot

Pour que le bouton "Envoyer au Bot" fonctionne, le bot doit exposer un endpoint :

```
POST /api/config/mexc-token
Content-Type: application/json

{
  "token": "votre_token_ici"
}
```

## Icônes

Les icônes PNG doivent être générées depuis `icons/icon.svg` :

```bash
# Avec Inkscape
inkscape -w 48 -h 48 icons/icon.svg -o icons/icon-48.png
inkscape -w 96 -h 96 icons/icon.svg -o icons/icon-96.png

# Ou avec ImageMagick
convert -background none -resize 48x48 icons/icon.svg icons/icon-48.png
convert -background none -resize 96x96 icons/icon.svg icons/icon-96.png
```

## Structure

```
mexc-token-helper/
├── manifest.json          # Configuration extension
├── popup/
│   ├── popup.html        # Interface popup
│   ├── popup.css         # Styles
│   └── popup.js          # Logique
├── background/
│   └── background.js     # Script arrière-plan
├── content/
│   └── content.js        # Script injecté sur MEXC
├── icons/
│   ├── icon.svg          # Source icône
│   ├── icon-48.png       # Icône 48x48
│   └── icon-96.png       # Icône 96x96
└── README.md
```

## Sécurité

- L'extension n'envoie JAMAIS le token automatiquement
- Le token reste local sauf action explicite de l'utilisateur
- Pas de tracking, pas de collecte de données
