# 🖥️ Desktop App Guide - Trade Cursor v7.0

Déployer Trade Cursor comme application desktop native avec Tauri.

---

## 📋 Vue d'ensemble

**Tauri** permet de créer des applications desktop natives (Windows, macOS, Linux) ultra-légères avec le frontend SvelteKit existant.

### Avantages vs Electron

| Feature | Tauri | Electron |
|---------|-------|----------|
| **Taille binaire** | ~5-10 MB | ~150 MB |
| **RAM usage** | ~50 MB | ~200 MB |
| **Backend** | Rust 🦀 | Node.js |
| **Sécurité** | ✅ Excellente | ⚠️ Moyenne |
| **Performance** | 🚀 Excellente | 🐢 Moyenne |

---

## 🚀 Installation

### 1. Prérequis

#### Windows
```powershell
# Installer Rust
winget install Rustlang.Rust.MSVC

# Installer Visual Studio C++ Build Tools
# https://visualstudio.microsoft.com/downloads/
```

#### macOS
```bash
# Installer Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Installer Xcode Command Line Tools
xcode-select --install
```

#### Linux (Ubuntu/Debian)
```bash
# Installer Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Installer dépendances
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

### 2. Installer Tauri CLI

```bash
cd frontend

# Installer @tauri-apps/cli
npm install --save-dev @tauri-apps/cli

# Créer config Tauri
npm install @tauri-apps/api
```

### 3. Initialiser Tauri

```bash
npx tauri init
```

**Répondre aux questions**:
- App name: `Trade Cursor`
- Window title: `Trade Cursor v7.0`
- Web assets location: `../build`
- Dev server URL: `http://localhost:3000`
- Frontend dev command: `npm run dev`
- Frontend build command: `npm run build`

---

## ⚙️ Configuration

### 1. `tauri.conf.json`

```json
{
  "build": {
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build",
    "devPath": "http://localhost:3000",
    "distDir": "../build",
    "withGlobalTauri": false
  },
  "package": {
    "productName": "Trade Cursor",
    "version": "7.0.0"
  },
  "tauri": {
    "allowlist": {
      "all": false,
      "shell": {
        "all": false,
        "open": true
      },
      "window": {
        "all": false,
        "close": true,
        "hide": true,
        "show": true,
        "maximize": true,
        "minimize": true,
        "unmaximize": true,
        "unminimize": true,
        "startDragging": true
      },
      "notification": {
        "all": true
      },
      "fs": {
        "all": false,
        "readFile": true,
        "writeFile": true,
        "readDir": true,
        "copyFile": true,
        "createDir": true,
        "removeDir": true,
        "removeFile": true,
        "scope": ["$APPDATA/*", "$APPCONFIG/*", "$APPLOCALDATA/*"]
      },
      "path": {
        "all": true
      },
      "dialog": {
        "all": false,
        "ask": true,
        "confirm": true,
        "message": true,
        "open": true,
        "save": true
      },
      "http": {
        "all": false,
        "request": true,
        "scope": ["http://localhost:5000/*", "https://api.mexc.com/*"]
      },
      "globalShortcut": {
        "all": true
      }
    },
    "bundle": {
      "active": true,
      "targets": "all",
      "identifier": "com.tradecursor.app",
      "icon": [
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/128x128@2x.png",
        "icons/icon.icns",
        "icons/icon.ico"
      ],
      "resources": [],
      "externalBin": [],
      "copyright": "",
      "category": "Finance",
      "shortDescription": "MEXC Smart Scalping Scanner",
      "longDescription": "Advanced trading bot for MEXC Futures with smart scalping strategies",
      "deb": {
        "depends": []
      },
      "macOS": {
        "frameworks": [],
        "minimumSystemVersion": "10.15",
        "exceptionDomain": "",
        "signingIdentity": null,
        "providerShortName": null,
        "entitlements": null
      },
      "windows": {
        "certificateThumbprint": null,
        "digestAlgorithm": "sha256",
        "timestampUrl": ""
      }
    },
    "security": {
      "csp": "default-src 'self'; connect-src 'self' http://localhost:5000 ws://localhost:5000 https://api.mexc.com; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    },
    "windows": [
      {
        "fullscreen": false,
        "resizable": true,
        "title": "Trade Cursor v7.0",
        "width": 1400,
        "height": 900,
        "minWidth": 1200,
        "minHeight": 700,
        "center": true,
        "decorations": true,
        "transparent": false,
        "alwaysOnTop": false
      }
    ],
    "systemTray": {
      "iconPath": "icons/icon.png",
      "iconAsTemplate": true,
      "menuOnLeftClick": false
    }
  }
}
```

### 2. Custom Window Title Bar (Optionnel)

Pour une barre de titre custom comme VS Code:

```json
// tauri.conf.json
{
  "tauri": {
    "windows": [
      {
        "decorations": false,
        "transparent": true
      }
    ]
  }
}
```

Puis créer composant custom title bar:

```svelte
<!-- frontend/src/lib/components/TitleBar.svelte -->

<script>
  import { appWindow } from '@tauri-apps/api/window';

  async function minimizeWindow() {
    await appWindow.minimize();
  }

  async function maximizeWindow() {
    await appWindow.toggleMaximize();
  }

  async function closeWindow() {
    await appWindow.close();
  }
</script>

<div class="titlebar" data-tauri-drag-region>
  <div class="titlebar-title">Trade Cursor v7.0</div>

  <div class="titlebar-controls">
    <button on:click={minimizeWindow}>—</button>
    <button on:click={maximizeWindow}>□</button>
    <button on:click={closeWindow} class="close">×</button>
  </div>
</div>

<style>
  .titlebar {
    height: 32px;
    background: #1e2749;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 10px;
    user-select: none;
  }

  .titlebar-title {
    color: var(--accent-green);
    font-size: 13px;
    font-weight: 500;
  }

  .titlebar-controls {
    display: flex;
    gap: 10px;
  }

  .titlebar-controls button {
    width: 32px;
    height: 32px;
    border: none;
    background: transparent;
    color: white;
    font-size: 16px;
    cursor: pointer;
    transition: background 0.2s;
  }

  .titlebar-controls button:hover {
    background: rgba(255, 255, 255, 0.1);
  }

  .titlebar-controls button.close:hover {
    background: #e81123;
  }
</style>
```

---

## 🔌 Tauri APIs

### 1. System Tray

```rust
// src-tauri/src/main.rs

use tauri::{CustomMenuItem, SystemTray, SystemTrayMenu, SystemTrayEvent};
use tauri::Manager;

fn main() {
    let quit = CustomMenuItem::new("quit".to_string(), "Quit");
    let show = CustomMenuItem::new("show".to_string(), "Show");
    let tray_menu = SystemTrayMenu::new()
        .add_item(show)
        .add_item(quit);

    let system_tray = SystemTray::new().with_menu(tray_menu);

    tauri::Builder::default()
        .system_tray(system_tray)
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::MenuItemClick { id, .. } => {
                match id.as_str() {
                    "quit" => {
                        std::process::exit(0);
                    }
                    "show" => {
                        let window = app.get_window("main").unwrap();
                        window.show().unwrap();
                    }
                    _ => {}
                }
            }
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

### 2. Native Notifications

```typescript
// frontend/src/lib/utils/notifications.ts

import { isPermissionGranted, requestPermission, sendNotification } from '@tauri-apps/api/notification';

export async function sendDesktopNotification(title: string, body: string) {
  // Vérifier permission
  let permissionGranted = await isPermissionGranted();

  if (!permissionGranted) {
    const permission = await requestPermission();
    permissionGranted = permission === 'granted';
  }

  if (permissionGranted) {
    sendNotification({ title, body });
  }
}
```

### 3. Global Shortcuts

```rust
// src-tauri/src/main.rs

use tauri::GlobalShortcutManager;

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let mut shortcuts = app.global_shortcut_manager();

            // Ctrl+Shift+T pour toggle window
            shortcuts.register("CmdOrCtrl+Shift+T", move || {
                println!("Shortcut triggered!");
            })?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

Frontend:

```typescript
// frontend/src/lib/utils/shortcuts.ts

import { register, unregister } from '@tauri-apps/api/globalShortcut';

export async function registerShortcuts() {
  // Ctrl+R pour refresh
  await register('CmdOrCtrl+R', () => {
    console.log('Refresh shortcut pressed');
    location.reload();
  });

  // Ctrl+Q pour quit
  await register('CmdOrCtrl+Q', async () => {
    const { appWindow } = await import('@tauri-apps/api/window');
    await appWindow.close();
  });
}

export async function unregisterShortcuts() {
  await unregister('CmdOrCtrl+R');
  await unregister('CmdOrCtrl+Q');
}
```

### 4. File System

```typescript
// frontend/src/lib/utils/filesystem.ts

import { writeTextFile, readTextFile } from '@tauri-apps/api/fs';
import { appDataDir } from '@tauri-apps/api/path';

export async function saveSettings(settings: object) {
  const appDataDirPath = await appDataDir();
  const settingsPath = `${appDataDirPath}/settings.json`;

  await writeTextFile(settingsPath, JSON.stringify(settings, null, 2));
}

export async function loadSettings() {
  const appDataDirPath = await appDataDir();
  const settingsPath = `${appDataDirPath}/settings.json`;

  try {
    const contents = await readTextFile(settingsPath);
    return JSON.parse(contents);
  } catch (e) {
    return null;
  }
}
```

### 5. Dialog

```typescript
// frontend/src/lib/utils/dialogs.ts

import { save, open, message, ask } from '@tauri-apps/api/dialog';

export async function saveFileDialog() {
  const filePath = await save({
    filters: [{
      name: 'JSON',
      extensions: ['json']
    }]
  });

  return filePath;
}

export async function openFileDialog() {
  const selected = await open({
    multiple: false,
    filters: [{
      name: 'JSON',
      extensions: ['json']
    }]
  });

  return selected;
}

export async function showMessageDialog(msg: string) {
  await message(msg, { title: 'Trade Cursor', type: 'info' });
}

export async function confirmDialog(msg: string): Promise<boolean> {
  return await ask(msg, { title: 'Confirmation', type: 'warning' });
}
```

---

## 🎨 Auto-Update

### 1. Configuration

```json
// tauri.conf.json
{
  "tauri": {
    "updater": {
      "active": true,
      "endpoints": [
        "https://releases.tradecursor.com/{{target}}/{{current_version}}"
      ],
      "dialog": true,
      "pubkey": "YOUR_PUBLIC_KEY_HERE"
    }
  }
}
```

### 2. Frontend Auto-Update

```typescript
// frontend/src/lib/utils/updater.ts

import { checkUpdate, installUpdate } from '@tauri-apps/api/updater';
import { relaunch } from '@tauri-apps/api/process';

export async function checkForUpdates() {
  try {
    const { shouldUpdate, manifest } = await checkUpdate();

    if (shouldUpdate) {
      console.log(`Update available: v${manifest?.version}`);

      // Demander confirmation
      const confirmed = confirm(
        `New version available: v${manifest?.version}\n\nUpdate now?`
      );

      if (confirmed) {
        // Télécharger et installer
        await installUpdate();

        // Redémarrer l'app
        await relaunch();
      }
    }
  } catch (error) {
    console.error('Update check failed:', error);
  }
}

// Vérifier updates au démarrage
if (typeof window !== 'undefined') {
  setTimeout(checkForUpdates, 5000);
}
```

---

## 🏗️ Build

### Development

```bash
# Lancer en mode dev
npm run tauri dev
```

### Production Build

```bash
# Build pour la plateforme actuelle
npm run tauri build
```

**Outputs**:

- **Windows**: `src-tauri/target/release/trade-cursor.exe` + installer `.msi`
- **macOS**: `src-tauri/target/release/bundle/macos/Trade Cursor.app` + `.dmg`
- **Linux**: `src-tauri/target/release/trade-cursor` + `.deb` / `.AppImage`

### Cross-Platform Build

#### Windows → macOS (non supporté directement)
Utiliser **GitHub Actions**:

```yaml
# .github/workflows/build.yml

name: Build

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    strategy:
      matrix:
        platform: [windows-latest, macos-latest, ubuntu-latest]

    runs-on: ${{ matrix.platform }}

    steps:
      - uses: actions/checkout@v3

      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: 18

      - name: Install Rust
        uses: dtolnay/rust-toolchain@stable

      - name: Install dependencies (Ubuntu only)
        if: matrix.platform == 'ubuntu-latest'
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.0-dev libssl-dev libgtk-3-dev

      - name: Install frontend dependencies
        run: cd frontend && npm install

      - name: Build Tauri
        run: cd frontend && npm run tauri build

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: ${{ matrix.platform }}
          path: frontend/src-tauri/target/release/bundle/
```

---

## 📦 Distribution

### Windows

1. **MSIX Package** (Microsoft Store):
   - Convertir `.msi` en `.msix` avec `MSIX Packaging Tool`
   - Soumettre sur **Microsoft Partner Center**

2. **Auto-signed installer**:
   - Utiliser `signtool.exe` pour signer `.msi`

### macOS

1. **Code Signing**:

```bash
# Signer l'app
codesign --force --options runtime --sign "Developer ID Application: YOUR NAME" --timestamp "Trade Cursor.app"

# Créer DMG notarié
hdiutil create -volname "Trade Cursor" -srcfolder "Trade Cursor.app" -ov -format UDZO trade-cursor.dmg

# Notarize DMG
xcrun notarytool submit trade-cursor.dmg --apple-id YOUR_APPLE_ID --password YOUR_APP_PASSWORD --team-id YOUR_TEAM_ID --wait

# Staple le ticket
xcrun stapler staple trade-cursor.dmg
```

2. **Distribution**:
   - Distribuer `.dmg` directement
   - Ou soumettre sur **Mac App Store**

### Linux

1. **AppImage** (universel):
   - Déjà généré par Tauri

2. **DEB** (Debian/Ubuntu):
   - Uploader sur **Launchpad PPA**

3. **Snap** (Ubuntu Store):

```yaml
# snap/snapcraft.yaml

name: trade-cursor
version: '7.0.0'
summary: MEXC Smart Scalping Scanner
description: Advanced trading bot for MEXC Futures

apps:
  trade-cursor:
    command: trade-cursor
    plugs: [network, network-bind, desktop]

parts:
  trade-cursor:
    plugin: dump
    source: ./src-tauri/target/release/bundle/appimage/
```

---

## 🎯 Roadmap Implementation

1. **Phase 1**: Setup Tauri + build test (1 jour)
2. **Phase 2**: Custom title bar + system tray (1 jour)
3. **Phase 3**: Native APIs integration (2 jours)
4. **Phase 4**: Auto-update system (1-2 jours)
5. **Phase 5**: Build pour toutes plateformes (1 jour)
6. **Phase 6**: Code signing + distribution (2-3 jours)

**Total: ~1-2 semaines**

---

## 📚 Ressources

- [Tauri Docs](https://tauri.app/v1/guides/)
- [Tauri Examples](https://github.com/tauri-apps/tauri/tree/dev/examples)
- [SvelteKit + Tauri](https://tauri.app/v1/guides/getting-started/setup/sveltekit)
- [Code Signing Guide](https://tauri.app/v1/guides/distribution/sign-windows)
