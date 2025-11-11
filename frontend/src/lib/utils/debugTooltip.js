/**
 * Utilitaire pour afficher les tooltips de debug
 * Affiche le nom de la variable correspondante au code quand le mode debug est actif
 */
import { get } from 'svelte/store';
import { debugMode } from '$lib/stores/debug';

let tooltipElement = null;

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
		}
	}, true);
	
	// Mettre à jour la visibilité du tooltip quand le mode debug change
	debugMode.subscribe(isActive => {
		if (!isActive) {
			hideTooltip();
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

