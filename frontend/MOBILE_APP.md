# 📱 Mobile App Guide - Trade Cursor v7.0

Déployer Trade Cursor comme application mobile native avec Capacitor.

---

## 📋 Vue d'ensemble

**Capacitor** permet de transformer le frontend SvelteKit en application mobile native pour iOS et Android, tout en conservant le code web existant.

### Avantages

- ✅ Code unique pour web + mobile
- ✅ Accès aux APIs natives (notifications, caméra, etc.)
- ✅ Performance native
- ✅ Distribution via App Store / Play Store
- ✅ Fonctionnalités offline

---

## 🚀 Installation

### 1. Installer Capacitor

```bash
cd frontend

# Installer Capacitor
npm install @capacitor/core @capacitor/cli
npm install @capacitor/ios @capacitor/android

# Initialiser Capacitor
npx cap init
```

**Répondre aux questions**:
- App name: `Trade Cursor`
- App ID: `com.tradecursor.app`
- Web directory: `build`

### 2. Configuration (`capacitor.config.ts`)

```typescript
// frontend/capacitor.config.ts

import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.tradecursor.app',
  appName: 'Trade Cursor',
  webDir: 'build',
  server: {
    // En développement, pointer vers le serveur local
    url: 'http://192.168.1.10:3000', // Remplacer par votre IP locale
    cleartext: true
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      backgroundColor: '#0a0e27',
      showSpinner: false
    },
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert']
    },
    LocalNotifications: {
      smallIcon: 'ic_stat_icon',
      iconColor: '#00ff88'
    }
  }
};

export default config;
```

### 3. Build et Ajout des Plateformes

```bash
# Build le frontend SvelteKit
npm run build

# Ajouter les plateformes
npx cap add android
npx cap add ios  # Nécessite macOS + Xcode
```

---

## 📱 Android

### 1. Prérequis

- **Android Studio** installé
- **JDK 11+**
- **Android SDK** (API 21+)

### 2. Configuration Android

```bash
# Ouvrir le projet Android
npx cap open android
```

**Dans Android Studio**:

1. Modifier `android/app/src/main/AndroidManifest.xml`:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- Permissions -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:theme="@style/AppTheme"
        android:usesCleartextTraffic="true">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:launchMode="singleTask"
            android:screenOrientation="portrait">

            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

2. Modifier `android/app/build.gradle`:

```gradle
android {
    compileSdkVersion 33

    defaultConfig {
        applicationId "com.tradecursor.app"
        minSdkVersion 21
        targetSdkVersion 33
        versionCode 1
        versionName "7.0.0"
    }

    buildTypes {
        release {
            minifyEnabled true
            proguardFiles getDefaultProguardFile('proguard-android.txt'), 'proguard-rules.pro'
        }
    }
}
```

### 3. Icons et Splash Screen

```bash
# Installer le plugin resources
npm install @capacitor/assets --save-dev

# Générer les assets (icons, splash screens)
npx capacitor-assets generate
```

**Placer vos images sources**:
- `assets/icon.png` (1024x1024)
- `assets/splash.png` (2732x2732)

### 4. Build et Run

```bash
# Sync les modifications
npx cap sync android

# Run sur émulateur/device
npx cap run android

# Build APK release
cd android
./gradlew assembleRelease
# APK: android/app/build/outputs/apk/release/app-release.apk
```

---

## 🍎 iOS

### 1. Prérequis

- **macOS** avec **Xcode 14+**
- **CocoaPods** installé: `sudo gem install cocoapods`
- **Apple Developer Account** (pour distribution)

### 2. Configuration iOS

```bash
# Installer pods
cd ios/App
pod install
cd ../..

# Ouvrir Xcode
npx cap open ios
```

**Dans Xcode**:

1. Sélectionner le projet `App.xcworkspace`
2. Configurer **Signing & Capabilities**:
   - Team: Votre équipe Apple Developer
   - Bundle Identifier: `com.tradecursor.app`
3. Ajouter capabilities:
   - Push Notifications
   - Background Modes (Remote notifications)

### 3. Info.plist

Modifier `ios/App/App/Info.plist`:

```xml
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>Trade Cursor</string>

    <key>CFBundleShortVersionString</key>
    <string>7.0.0</string>

    <!-- Permission notifications -->
    <key>UIBackgroundModes</key>
    <array>
        <string>remote-notification</string>
    </array>

    <!-- Permission réseau local -->
    <key>NSLocalNetworkUsageDescription</key>
    <string>Trade Cursor needs local network access to connect to your trading bot</string>
</dict>
</plist>
```

### 4. Build et Run

```bash
# Sync les modifications
npx cap sync ios

# Run sur simulateur/device
npx cap run ios

# Archive pour App Store
# Dans Xcode: Product > Archive
```

---

## 🔌 Plugins Capacitor Utiles

### 1. Push Notifications

```bash
npm install @capacitor/push-notifications
```

```typescript
// frontend/src/lib/utils/push.ts

import { PushNotifications } from '@capacitor/push-notifications';
import { Capacitor } from '@capacitor/core';

export async function initPushNotifications() {
  if (!Capacitor.isNativePlatform()) return;

  // Demander permission
  let permStatus = await PushNotifications.checkPermissions();

  if (permStatus.receive === 'prompt') {
    permStatus = await PushNotifications.requestPermissions();
  }

  if (permStatus.receive !== 'granted') {
    throw new Error('User denied permissions!');
  }

  // Enregistrer pour les notifications
  await PushNotifications.register();

  // Listener token
  await PushNotifications.addListener('registration', (token) => {
    console.log('Push registration success, token: ' + token.value);
    // Envoyer token au backend
  });

  // Listener notification reçue
  await PushNotifications.addListener('pushNotificationReceived', (notification) => {
    console.log('Push received: ', notification);
  });

  // Listener notification cliquée
  await PushNotifications.addListener('pushNotificationActionPerformed', (notification) => {
    console.log('Push action performed: ', notification);
  });
}
```

### 2. Local Notifications

```bash
npm install @capacitor/local-notifications
```

```typescript
// frontend/src/lib/utils/notifications.ts

import { LocalNotifications } from '@capacitor/local-notifications';

export async function scheduleNotification(title: string, body: string) {
  await LocalNotifications.schedule({
    notifications: [
      {
        title,
        body,
        id: Date.now(),
        schedule: { at: new Date(Date.now() + 1000) }, // Immédiat
        sound: 'default',
        attachments: undefined,
        actionTypeId: '',
        extra: null
      }
    ]
  });
}
```

### 3. Status Bar

```bash
npm install @capacitor/status-bar
```

```typescript
// frontend/src/routes/+layout.svelte

import { StatusBar, Style } from '@capacitor/status-bar';
import { Capacitor } from '@capacitor/core';
import { onMount } from 'svelte';

onMount(async () => {
  if (Capacitor.isNativePlatform()) {
    // Configurer la status bar
    await StatusBar.setStyle({ style: Style.Dark });
    await StatusBar.setBackgroundColor({ color: '#0a0e27' });
  }
});
```

### 4. Network

```bash
npm install @capacitor/network
```

```typescript
// frontend/src/lib/stores/network.ts

import { writable } from 'svelte/store';
import { Network } from '@capacitor/network';

export const networkStatus = writable({
  connected: true,
  connectionType: 'wifi'
});

// Listener network status
Network.addListener('networkStatusChange', (status) => {
  networkStatus.set({
    connected: status.connected,
    connectionType: status.connectionType
  });
});

// Vérifier status initial
Network.getStatus().then((status) => {
  networkStatus.set({
    connected: status.connected,
    connectionType: status.connectionType
  });
});
```

---

## 🎨 Adaptation Mobile UI

### 1. Détection Plateforme

```svelte
<!-- frontend/src/lib/components/MobileHeader.svelte -->

<script>
  import { Capacitor } from '@capacitor/core';

  const isMobile = Capacitor.isNativePlatform();
  const platform = Capacitor.getPlatform(); // 'ios' ou 'android'
</script>

{#if isMobile}
  <div class="mobile-header" class:ios={platform === 'ios'}>
    <!-- Header mobile -->
  </div>
{:else}
  <div class="web-header">
    <!-- Header web -->
  </div>
{/if}

<style>
  .mobile-header {
    /* Styles mobile */
    padding-top: env(safe-area-inset-top); /* iOS notch */
  }

  .mobile-header.ios {
    /* Styles spécifiques iOS */
  }
</style>
```

### 2. Safe Area (iOS)

```css
/* frontend/src/routes/+layout.svelte */

body {
  padding-top: env(safe-area-inset-top);
  padding-bottom: env(safe-area-inset-bottom);
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
}
```

### 3. Gestures Mobiles

```svelte
<script>
  let startX = 0;
  let startY = 0;

  function handleTouchStart(e) {
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
  }

  function handleTouchEnd(e) {
    const endX = e.changedTouches[0].clientX;
    const endY = e.changedTouches[0].clientY;

    const diffX = endX - startX;
    const diffY = endY - startY;

    // Swipe gauche
    if (diffX < -100 && Math.abs(diffY) < 50) {
      console.log('Swipe left');
    }

    // Swipe droite
    if (diffX > 100 && Math.abs(diffY) < 50) {
      console.log('Swipe right');
    }
  }
</script>

<div
  on:touchstart={handleTouchStart}
  on:touchend={handleTouchEnd}
>
  <!-- Content -->
</div>
```

---

## 📦 Distribution

### Android (Google Play)

1. **Build signed APK**:

```bash
cd android
./gradlew assembleRelease
```

2. **Signer l'APK**:

```bash
# Générer keystore (une fois)
keytool -genkey -v -keystore trade-cursor.keystore -alias tradecursor -keyalg RSA -keysize 2048 -validity 10000

# Signer APK
jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 -keystore trade-cursor.keystore app-release-unsigned.apk tradecursor

# Aligner ZIP
zipalign -v 4 app-release-unsigned.apk trade-cursor-release.apk
```

3. **Upload sur Google Play Console**

### iOS (App Store)

1. **Archive dans Xcode**:
   - Product > Archive
   - Organizer > Distribute App
   - App Store Connect

2. **Upload via Xcode** ou **Transporter.app**

3. **Soumettre pour review** dans App Store Connect

---

## 🔄 Live Updates (OTA)

Utiliser **Capacitor Live Updates** pour mettre à jour l'app sans passer par les stores:

```bash
npm install @capacitor/live-updates
```

```typescript
// frontend/src/lib/utils/updates.ts

import { LiveUpdate } from '@capacitor/live-updates';

export async function checkForUpdates() {
  const result = await LiveUpdate.sync();

  if (result.liveUpdate) {
    console.log('Update available, reloading...');
    await LiveUpdate.reload();
  }
}
```

---

## 🎯 Roadmap Implementation

1. **Phase 1**: Setup Capacitor + build test (1 jour)
2. **Phase 2**: Adaptation UI mobile (2-3 jours)
3. **Phase 3**: Plugins natifs (notifications, etc.) (2 jours)
4. **Phase 4**: Tests sur devices réels (2-3 jours)
5. **Phase 5**: Distribution stores (1-2 semaines review)

**Total: ~2-3 semaines** (+ délai review stores)

---

## 📚 Ressources

- [Capacitor Docs](https://capacitorjs.com/docs)
- [iOS Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [Android Material Design](https://material.io/design)
- [SvelteKit + Capacitor](https://capacitorjs.com/solution/sveltekit)
