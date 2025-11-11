/**
 * Utilitaire pour afficher les tooltips de debug
 * Affiche le nom de la variable correspondante au code quand le mode debug est actif
 */
import { get } from 'svelte/store';
import { debugMode } from '$lib/stores/debug';

let tooltipElement = null;
let currentDebugName = null; // Variable actuellement survolée

/**
 * Créer l'élément tooltip global
 */
function createTooltip() {
	if (tooltipElement) return tooltipElement;
	
	tooltipElement = document.createElement('div');
	tooltipElement.id = 'debug-tooltip';
	tooltipElement.style.cssText = `
		position: fixed;
		background: rgba(0, 0, 0, 0.9);
		color: #00ff88;
		padding: 6px 10px;
		border-radius: 4px;
		font-size: 12px;
		font-family: 'Courier New', monospace;
		pointer-events: none;
		z-index: 100000;
		border: 1px solid #00ff88;
		box-shadow: 0 2px 8px rgba(0, 255, 136, 0.3);
		display: none;
		white-space: nowrap;
	`;
	document.body.appendChild(tooltipElement);
	return tooltipElement;
}

/**
 * Afficher le tooltip
 */
function showTooltip(event, variableName) {
	if (!get(debugMode)) return;
	
	const tooltip = createTooltip();
	if (!tooltip) return;
	
	// Stocker la variable actuelle pour la copie
	currentDebugName = variableName;
	
	tooltip.textContent = variableName;
	tooltip.style.display = 'block';
	
	// Positionner le tooltip près du curseur
	const x = event.clientX + 10;
	const y = event.clientY - 30;
	
	tooltip.style.left = `${x}px`;
	tooltip.style.top = `${y}px`;
	
	// Ajuster si le tooltip sort de l'écran
	setTimeout(() => {
		const rect = tooltip.getBoundingClientRect();
		if (rect.right > window.innerWidth) {
			tooltip.style.left = `${event.clientX - rect.width - 10}px`;
		}
		if (rect.top < 0) {
			tooltip.style.top = `${event.clientY + 20}px`;
		}
	}, 0);
}

/**
 * Cacher le tooltip
 */
function hideTooltip() {
	if (tooltipElement) {
		tooltipElement.style.display = 'none';
	}
	// Ne pas réinitialiser currentDebugName ici pour permettre la copie même après avoir quitté l'élément
}

/**
 * Copier le nom de la variable dans le presse-papiers
 */
async function copyDebugNameToClipboard() {
	if (!get(debugMode) || !currentDebugName) return;
	
	try {
		await navigator.clipboard.writeText(currentDebugName);
		
		// Feedback visuel : modifier temporairement le tooltip
		if (tooltipElement) {
			const originalText = tooltipElement.textContent;
			tooltipElement.textContent = `✓ Copié: ${currentDebugName}`;
			tooltipElement.style.color = '#00ff88';
			tooltipElement.style.borderColor = '#00ff88';
			
			setTimeout(() => {
				if (tooltipElement) {
					tooltipElement.textContent = originalText;
				}
			}, 1000);
		}
	} catch (err) {
		console.error('Erreur lors de la copie dans le presse-papiers:', err);
		// Fallback pour les navigateurs qui ne supportent pas l'API Clipboard
		try {
			const textArea = document.createElement('textarea');
			textArea.value = currentDebugName;
			textArea.style.position = 'fixed';
			textArea.style.opacity = '0';
			document.body.appendChild(textArea);
			textArea.select();
			document.execCommand('copy');
			document.body.removeChild(textArea);
			
			// Feedback visuel
			if (tooltipElement) {
				const originalText = tooltipElement.textContent;
				tooltipElement.textContent = `✓ Copié: ${currentDebugName}`;
				setTimeout(() => {
					if (tooltipElement) {
						tooltipElement.textContent = originalText;
					}
				}, 1000);
			}
		} catch (fallbackErr) {
			console.error('Erreur lors de la copie (fallback):', fallbackErr);
		}
	}
}

/**
 * Initialiser les event listeners globaux pour les attributs data-debug-name
 */
export function initDebugTooltips() {
	if (typeof document === 'undefined') return;
	
	// Créer le tooltip
	createTooltip();
	
	// Event delegation pour tous les éléments avec data-debug-name
	// Utiliser mouseover au lieu de mouseenter pour capturer aussi les enfants
	document.addEventListener('mouseover', (event) => {
		if (!get(debugMode)) return;
		
		// Trouver l'élément le plus proche avec data-debug-name (en remontant dans le DOM)
		let target = event.target;
		let debugName = null;
		
		// Remonter dans le DOM jusqu'à trouver un élément avec data-debug-name
		while (target && target !== document.body) {
			debugName = target.getAttribute('data-debug-name');
			if (debugName) {
				showTooltip(event, debugName);
				return;
			}
			target = target.parentElement;
		}
	}, true);
	
	document.addEventListener('mouseout', (event) => {
		// Vérifier si on quitte un élément avec data-debug-name
		const relatedTarget = event.relatedTarget;
		if (!relatedTarget || !relatedTarget.closest('[data-debug-name]')) {
			hideTooltip();
			// Réinitialiser currentDebugName seulement si on ne survole plus aucun élément avec data-debug-name
			setTimeout(() => {
				// Vérifier si on survole toujours un élément avec data-debug-name
				const hoveredElement = document.elementFromPoint(event.clientX, event.clientY);
				if (!hoveredElement || !hoveredElement.closest('[data-debug-name]')) {
					currentDebugName = null;
				}
			}, 100);
		}
	}, true);
	
	// Gestionnaire pour Ctrl+C : copier le nom de la variable
	document.addEventListener('keydown', (event) => {
		// Vérifier si Ctrl+C (ou Cmd+C sur Mac) est pressé
		if ((event.ctrlKey || event.metaKey) && event.key === 'c') {
			// Vérifier que le mode debug est actif et qu'une variable est survolée
			if (get(debugMode) && currentDebugName) {
				// Empêcher la copie du texte sélectionné si on est en mode debug
				event.preventDefault();
				copyDebugNameToClipboard();
			}
		}
	}, true);
	
	// Mettre à jour la visibilité du tooltip quand le mode debug change
	debugMode.subscribe(isActive => {
		if (!isActive) {
			hideTooltip();
			currentDebugName = null; // Réinitialiser quand le mode debug est désactivé
		}
	});
}

/**
 * Helper pour ajouter facilement un attribut data-debug-name
 */
export function addDebugName(element, variableName) {
	if (element && variableName) {
		element.setAttribute('data-debug-name', variableName);
	}
}

