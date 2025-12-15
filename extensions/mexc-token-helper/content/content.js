/**
 * MEXC Token Helper - Content Script
 * Injecté sur les pages MEXC pour détecter la connexion
 */

// Détecter si l'utilisateur est connecté en cherchant des éléments UI
function checkLoginStatus() {
  // Chercher des indicateurs de connexion sur la page
  const indicators = [
    // Bouton de profil/compte
    '[class*="user"]',
    '[class*="avatar"]',
    '[class*="account"]',
    '[class*="profile"]',
    // Menu utilisateur
    '.user-center',
    '.account-info'
  ];
  
  for (const selector of indicators) {
    const element = document.querySelector(selector);
    if (element) {
      console.log('🔐 MEXC Token Helper: Utilisateur connecté détecté');
      notifyBackground('connected');
      return true;
    }
  }
  
  return false;
}

// Notifier le background script
function notifyBackground(status) {
  try {
    browser.runtime.sendMessage({ 
      action: 'pageStatus', 
      status: status,
      url: window.location.href
    });
  } catch (e) {
    // Extension peut être rechargée
  }
}

// Observer les changements DOM pour détecter la connexion
const observer = new MutationObserver((mutations) => {
  checkLoginStatus();
});

// Vérifier au chargement
if (document.readyState === 'complete') {
  checkLoginStatus();
} else {
  window.addEventListener('load', checkLoginStatus);
}

// Observer les changements (SPA)
observer.observe(document.body || document.documentElement, {
  childList: true,
  subtree: true
});

console.log('🚀 MEXC Token Helper: Content script loaded on', window.location.hostname);
