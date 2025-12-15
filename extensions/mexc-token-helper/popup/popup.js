/**
 * MEXC Token Helper - Popup Script
 * Récupère et affiche le token d'authentification MEXC
 */

// Noms des cookies à rechercher (par ordre de priorité)
const TOKEN_COOKIE_NAMES = [
  'uc_token',
  'u_id', 
  'token',
  'access_token',
  'mexc_token'
];

// Domaines MEXC
const MEXC_DOMAINS = [
  '.mexc.com',
  'futures.mexc.com',
  'www.mexc.com'
];

// Éléments DOM
let statusEl, statusIcon, statusText;
let tokenSection, tokenValue, tokenLength;
let copyBtn, refreshBtn, sendBtn;
let sendSection, botUrlInput, saveUrlBtn;
let messageEl;

document.addEventListener('DOMContentLoaded', () => {
  // Initialiser les références DOM
  statusEl = document.getElementById('status');
  statusIcon = statusEl.querySelector('.status-icon');
  statusText = statusEl.querySelector('.status-text');
  
  tokenSection = document.getElementById('token-section');
  tokenValue = document.getElementById('token-value');
  tokenLength = document.getElementById('token-length');
  
  copyBtn = document.getElementById('copy-btn');
  refreshBtn = document.getElementById('refresh-btn');
  sendBtn = document.getElementById('send-btn');
  
  sendSection = document.getElementById('send-section');
  botUrlInput = document.getElementById('bot-url');
  saveUrlBtn = document.getElementById('save-url-btn');
  
  messageEl = document.getElementById('message');
  
  // Charger l'URL du bot sauvegardée
  loadSavedUrl();
  
  // Event listeners
  copyBtn.addEventListener('click', copyToken);
  refreshBtn.addEventListener('click', fetchToken);
  sendBtn.addEventListener('click', sendToBot);
  saveUrlBtn.addEventListener('click', saveUrl);
  
  // Récupérer le token au chargement
  fetchToken();
});

/**
 * Récupère le token depuis les cookies MEXC
 */
async function fetchToken() {
  setStatus('loading', '⏳', 'Recherche du token...');
  hideMessage();
  
  try {
    let foundToken = null;
    let foundCookieName = null;
    
    // Chercher dans tous les domaines MEXC
    for (const domain of MEXC_DOMAINS) {
      if (foundToken) break;
      
      // Récupérer tous les cookies du domaine
      const cookies = await browser.cookies.getAll({ domain: domain });
      
      // Chercher les cookies token par nom
      for (const cookieName of TOKEN_COOKIE_NAMES) {
        const cookie = cookies.find(c => c.name === cookieName);
        if (cookie && cookie.value) {
          foundToken = cookie.value;
          foundCookieName = cookie.name;
          break;
        }
      }
      
      // Si pas trouvé par nom, chercher par pattern dans la valeur
      if (!foundToken) {
        for (const cookie of cookies) {
          // Token typique: long string alphanumérique ou JWT
          if (cookie.value && cookie.value.length > 50 && 
              (cookie.value.includes('eyJ') || /^[a-zA-Z0-9_-]{50,}$/.test(cookie.value))) {
            foundToken = cookie.value;
            foundCookieName = cookie.name;
            break;
          }
        }
      }
    }
    
    if (foundToken) {
      displayToken(foundToken, foundCookieName);
    } else {
      setStatus('disconnected', '❌', 'Non connecté à MEXC');
      tokenSection.classList.add('hidden');
      sendBtn.classList.add('hidden');
      showMessage('Connectez-vous sur futures.mexc.com puis rafraîchissez', 'error');
    }
    
  } catch (error) {
    console.error('Erreur récupération token:', error);
    setStatus('disconnected', '❌', 'Erreur');
    showMessage('Erreur: ' + error.message, 'error');
  }
}

/**
 * Affiche le token trouvé
 */
function displayToken(token, cookieName) {
  setStatus('connected', '✅', 'Connecté à MEXC');
  
  // Afficher le token (masqué partiellement)
  const maskedToken = token.substring(0, 20) + '...' + token.substring(token.length - 10);
  tokenValue.value = maskedToken;
  tokenValue.dataset.fullToken = token;
  
  tokenLength.textContent = `Cookie: ${cookieName} | Longueur: ${token.length} caractères`;
  
  tokenSection.classList.remove('hidden');
  sendBtn.classList.remove('hidden');
  sendSection.classList.remove('hidden');
}

/**
 * Copie le token dans le presse-papier
 */
async function copyToken() {
  const token = tokenValue.dataset.fullToken;
  if (!token) return;
  
  try {
    await navigator.clipboard.writeText(token);
    
    // Feedback visuel
    copyBtn.textContent = '✓';
    copyBtn.classList.add('copied');
    
    showMessage('Token copié dans le presse-papier !', 'success');
    
    setTimeout(() => {
      copyBtn.textContent = '📋';
      copyBtn.classList.remove('copied');
    }, 2000);
    
  } catch (error) {
    showMessage('Erreur copie: ' + error.message, 'error');
  }
}

/**
 * Envoie le token au bot de trading
 */
async function sendToBot() {
  const token = tokenValue.dataset.fullToken;
  const botUrl = botUrlInput.value.trim();
  
  if (!token) {
    showMessage('Pas de token à envoyer', 'error');
    return;
  }
  
  if (!botUrl) {
    showMessage('URL du bot non configurée', 'error');
    return;
  }
  
  sendBtn.textContent = '⏳ Envoi...';
  sendBtn.disabled = true;
  
  try {
    const response = await fetch(`${botUrl}/api/config/mexc-token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ token: token })
    });
    
    if (response.ok) {
      showMessage('Token envoyé au bot avec succès !', 'success');
    } else {
      const error = await response.text();
      showMessage(`Erreur serveur: ${error}`, 'error');
    }
    
  } catch (error) {
    // Si erreur réseau, proposer de copier à la place
    showMessage(`Impossible de joindre le bot. Token copié à la place.`, 'error');
    copyToken();
  } finally {
    sendBtn.textContent = '📤 Envoyer au Bot';
    sendBtn.disabled = false;
  }
}

/**
 * Sauvegarde l'URL du bot
 */
function saveUrl() {
  const url = botUrlInput.value.trim();
  browser.storage.local.set({ botUrl: url });
  showMessage('URL sauvegardée', 'success');
}

/**
 * Charge l'URL sauvegardée
 */
async function loadSavedUrl() {
  try {
    const data = await browser.storage.local.get('botUrl');
    if (data.botUrl) {
      botUrlInput.value = data.botUrl;
    }
  } catch (e) {
    console.log('Pas d\'URL sauvegardée');
  }
}

/**
 * Met à jour le statut
 */
function setStatus(type, icon, text) {
  statusEl.className = 'status ' + type;
  statusIcon.textContent = icon;
  statusText.textContent = text;
}

/**
 * Affiche un message
 */
function showMessage(text, type) {
  messageEl.textContent = text;
  messageEl.className = 'message ' + type;
  messageEl.classList.remove('hidden');
  
  // Auto-hide après 5s
  setTimeout(() => {
    messageEl.classList.add('hidden');
  }, 5000);
}

/**
 * Cache le message
 */
function hideMessage() {
  messageEl.classList.add('hidden');
}
