# 📱🖥️ Mobile & Desktop Setup Guide

Guide rapide pour builder les apps mobiles et desktop.

---

## 📱 Mobile App (Capacitor)

### Installation Capacitor

```bash
cd frontend

# Installer Capacitor
npm install @capacitor/core @capacitor/cli
npm install @capacitor/ios @capacitor/android

# Installer plugins
npm install @capacitor/push-notifications
npm install @capacitor/local-notifications
npm install @capacitor/status-bar
npm install @capacitor/network
```

### Configuration

La configuration est déjà présente dans `capacitor.config.ts`.

**Pour développement local**, décommenter et modifier dans `capacitor.config.ts`:

```typescript
server: {
  url: 'http://192.168.1.10:3000', // Votre IP locale
  cleartext: true
}
```

### Build & Run

```bash
# Build le frontend
npm run build

# Ajouter les plateformes (une seule fois)
npx cap add android
npx cap add ios  # macOS uniquement

# Sync les fichiers
npx cap sync

# Ouvrir Android Studio
npx cap open android

# Ouvrir Xcode (macOS)
npx cap open ios
```

### Build Production

**Android**:
1. Ouvrir dans Android Studio: `npx cap open android`
2. Build > Generate Signed Bundle / APK
3. Suivre l'assistant pour créer keystore
4. APK dans `android/app/build/outputs/apk/release/`

**iOS** (macOS):
1. Ouvrir dans Xcode: `npx cap open ios`
2. Product > Archive
3. Distribute App > App Store Connect
4. Suivre l'assistant

### Voir le guide complet

Consulter `MOBILE_APP.md` pour:
- Configuration AndroidManifest.xml
- Configuration Info.plist
- Plugins natifs (notifications, etc.)
- Distribution App Store / Play Store

---

## 🖥️ Desktop App (Tauri)

### Prérequis

**Windows**:
```powershell
# Installer Rust
winget install Rustlang.Rust.MSVC

# Visual Studio C++ Build Tools requis
# Télécharger: https://visualstudio.microsoft.com/downloads/
```

**macOS**:
```bash
# Installer Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Xcode Command Line Tools
xcode-select --install
```

**Linux (Ubuntu/Debian)**:
```bash
# Installer Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Dépendances système
sudo apt update
sudo apt install libwebkit2gtk-4.0-dev \
    build-essential \
    curl \
    wget \
    file \
    libssl-dev \
    libgtk-3-dev \
    libayatana-appindicator3-dev \
    librsvg2-dev
```

### Installation Tauri

```bash
cd frontend

# Installer Tauri CLI
npm install --save-dev @tauri-apps/cli
npm install @tauri-apps/api
```

### Configuration

Les configurations Tauri sont déjà créées:
- `src-tauri/tauri.conf.json` - Config principale
- `src-tauri/Cargo.toml` - Dépendances Rust
- `src-tauri/src/main.rs` - Code Rust principal

### Build & Run

```bash
# Mode développement
npm run tauri dev

# Build production
npm run tauri build
```

### Outputs

**Windows**:
- `src-tauri/target/release/trade-cursor.exe`
- `src-tauri/target/release/bundle/msi/Trade Cursor_7.0.0_x64_en-US.msi`

**macOS**:
- `src-tauri/target/release/bundle/macos/Trade Cursor.app`
- `src-tauri/target/release/bundle/dmg/Trade Cursor_7.0.0_x64.dmg`

**Linux**:
- `src-tauri/target/release/trade-cursor`
- `src-tauri/target/release/bundle/deb/trade-cursor_7.0.0_amd64.deb`
- `src-tauri/target/release/bundle/appimage/trade-cursor_7.0.0_amd64.AppImage`

### Fonctionnalités Tauri Configurées

✅ System Tray (icône dans la barre système)
✅ Hide to tray au lieu de fermer
✅ Raccourcis globaux (via allowlist)
✅ Notifications natives
✅ File System access (dans $APPDATA)
✅ Dialog boxes
✅ Clipboard access
✅ HTTP requests (localhost:5000 + api.mexc.com)

### Voir le guide complet

Consulter `DESKTOP_APP.md` pour:
- Custom title bar
- Auto-update system
- Code signing
- Cross-platform build avec GitHub Actions

---

## 🚀 Scripts package.json

Ajouter dans `package.json`:

```json
{
  "scripts": {
    "dev": "vite dev --port 3000",
    "build": "vite build",
    "preview": "vite preview --port 3000",
    "tauri": "tauri",
    "tauri:dev": "tauri dev",
    "tauri:build": "tauri build",
    "cap:sync": "cap sync",
    "cap:android": "cap open android",
    "cap:ios": "cap open ios"
  }
}
```

---

## 📦 Structure finale

```
frontend/
├── capacitor.config.ts       # ✅ Config Capacitor
├── src-tauri/               # ✅ Dossier Tauri
│   ├── tauri.conf.json      # ✅ Config Tauri
│   ├── Cargo.toml           # ✅ Dépendances Rust
│   ├── build.rs             # ✅ Build script
│   └── src/
│       └── main.rs          # ✅ Code Rust
├── android/                 # Créé par: npx cap add android
├── ios/                     # Créé par: npx cap add ios
├── src/                     # Code SvelteKit
├── build/                   # Output build
├── package.json
├── svelte.config.js
└── vite.config.js
```

---

## 🎯 Quick Start

### Pour Mobile

```bash
cd frontend
npm install
npm install @capacitor/core @capacitor/cli @capacitor/android @capacitor/ios
npm run build
npx cap add android
npx cap sync
npx cap open android
```

### Pour Desktop

```bash
cd frontend
npm install
npm install --save-dev @tauri-apps/cli
npm install @tauri-apps/api
npm run tauri dev
```

---

## ⚠️ Notes Importantes

### Mobile
- **iOS**: Requiert macOS avec Xcode
- **Android**: Fonctionne sur Windows/macOS/Linux
- Besoin d'un **Apple Developer account** ($99/an) pour iOS App Store
- Besoin d'un **Google Play Developer account** ($25 one-time) pour Play Store

### Desktop
- **Code signing** recommandé pour Windows/macOS
- **Rust** doit être installé sur la machine de build
- Premier build peut prendre 5-10 minutes (compilation Rust)
- Builds suivants sont plus rapides (cache)

---

## 📚 Documentation Complète

- Mobile: `MOBILE_APP.md` (28 KB, guide détaillé)
- Desktop: `DESKTOP_APP.md` (29 KB, guide détaillé)
- Multi-sessions: `MULTI_SESSIONS.md` (guide backend/frontend)
- Backtesting: `BACKTESTING.md` (guide complet)

---

## ✅ Statut Configuration

- [x] Capacitor config créée (`capacitor.config.ts`)
- [x] Tauri config créée (`src-tauri/tauri.conf.json`)
- [x] Tauri Cargo.toml créé
- [x] Tauri main.rs créé avec system tray
- [x] Guides complets disponibles
- [ ] Installer Capacitor (`npm install...`)
- [ ] Installer Tauri CLI (`npm install...`)
- [ ] Ajouter plateformes (`npx cap add...`)
- [ ] Premier build

**Temps estimé setup complet**:
- Mobile: ~30 minutes
- Desktop: ~15 minutes

**Temps estimé premier build**:
- Mobile Android: ~2-5 minutes
- Mobile iOS: ~5-10 minutes
- Desktop: ~5-10 minutes (compilation Rust initiale)
