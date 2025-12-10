/**
 * MEXC Token Helper - Background Script
 * Gère les événements en arrière-plan et la détection automatique
 */

// Configuration
const MEXC_URL_PATTERNS = [
  '*://*.mexc.com/*',
  '*://futures.mexc.com/*'
];

const TOKEN_COOKIE_NAMES = ['uc_token', 'u_id', 'token', 'access_token'];

// État
let lastKnownToken = null;
let isConnected = false;

/**
 * Écoute les changements de cookies MEXC
 */
browser.cookies.onChanged.addListener((changeInfo) => {
  const { cookie, removed } = changeInfo;
  
  // Vérifier si c'est un cookie MEXC
  if (!cookie.domain.includes('mexc.com')) return;
  
  // Vérifier si c'est un cookie token
  if (TOKEN_COOKIE_NAMES.includes(cookie.name)) {
    if (removed) {
      console.log('🔓 Token MEXC supprimé - Déconnexion détectée');
      isConnected = false;
      lastKnownToken = null;
      updateBadge(false);
    } else {
      console.log('🔐 Nouveau token MEXC détecté');
      isConnected = true;
      lastKnownToken = cookie.value;
      updateBadge(true);
      
      // Notification optionnelle
      showNotification('Token MEXC détecté', 'Cliquez sur l\'extension pour le copier');
    }
  }
});

/**
 * Met à jour le badge de l'extension
 */
function updateBadge(connected) {
  if (connected) {
    browser.browserAction.setBadgeText({ text: '✓' });
    browser.browserAction.setBadgeBackgroundColor({ color: '#00ff88' });
  } else {
    browser.browserAction.setBadgeText({ text: '' });
  }
}

/**
 * Affiche une notification
 */
function showNotification(title, message) {
  browser.notifications.create({
    type: 'basic',
    iconUrl: browser.runtime.getURL('icons/icon-96.png'),
    title: title,
    message: message
  });
}

/**
 * Vérifie l'état initial au démarrage
 */
async function checkInitialState() {
  try {
    const cookies = await browser.cookies.getAll({ domain: '.mexc.com' });
    
    for (const cookieName of TOKEN_COOKIE_NAMES) {
      const cookie = cookies.find(c => c.name === cookieName);
      if (cookie && cookie.value) {
        isConnected = true;
        lastKnownToken = cookie.value;
        updateBadge(true);
        console.log('🔐 Token MEXC existant détecté au démarrage');
        return;
      }
    }
    
    updateBadge(false);
  } catch (error) {
    console.error('Erreur vérification initiale:', error);
  }
}

/**
 * Écoute les messages du popup
 */
browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'getStatus') {
    sendResponse({
      isConnected: isConnected,
      hasToken: !!lastKnownToken
    });
  }
  return true;
});

// Initialisation
checkInitialState();
console.log('🚀 MEXC Token Helper - Background script loaded');
