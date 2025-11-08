import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.tradecursor.app',
  appName: 'Trade Cursor',
  webDir: 'build',
  server: {
    // En développement, pointer vers le serveur local
    // Remplacer par votre IP locale (ex: 192.168.1.10)
    // url: 'http://192.168.1.10:3000',
    // cleartext: true
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      backgroundColor: '#0a0e27',
      showSpinner: false,
      androidSpinnerStyle: 'small',
      iosSpinnerStyle: 'small',
      splashFullScreen: true,
      splashImmersive: true
    },
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert']
    },
    LocalNotifications: {
      smallIcon: 'ic_stat_icon',
      iconColor: '#00ff88',
      sound: 'beep.wav'
    },
    StatusBar: {
      style: 'dark',
      backgroundColor: '#0a0e27'
    }
  },
  android: {
    allowMixedContent: true,
    captureInput: true,
    webContentsDebuggingEnabled: true
  },
  ios: {
    contentInset: 'automatic',
    scrollEnabled: true
  }
};

export default config;
