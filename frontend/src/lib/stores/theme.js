import { writable } from 'svelte/store';
import { browser } from '$app/environment';

// Détecter préférence système
function getInitialTheme() {
	if (!browser) return 'dark';

	// 1. Vérifier localStorage
	const saved = localStorage.getItem('theme');
	if (saved) return saved;

	// 2. Vérifier préférence système
	if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
		return 'light';
	}

	// 3. Par défaut: dark
	return 'dark';
}

// Store pour le thème actuel ('dark' | 'light')
export const theme = writable(getInitialTheme());

// Fonction pour toggle le thème
export function toggleTheme() {
	theme.update(current => {
		const newTheme = current === 'dark' ? 'light' : 'dark';
		if (browser) {
			localStorage.setItem('theme', newTheme);
			document.documentElement.setAttribute('data-theme', newTheme);
		}
		return newTheme;
	});
}

// Fonction pour set un thème spécifique
export function setTheme(newTheme) {
	if (newTheme !== 'dark' && newTheme !== 'light') return;

	theme.set(newTheme);
	if (browser) {
		localStorage.setItem('theme', newTheme);
		document.documentElement.setAttribute('data-theme', newTheme);
	}
}

// Initialiser le thème au chargement
if (browser) {
	const initialTheme = getInitialTheme();
	document.documentElement.setAttribute('data-theme', initialTheme);

	// Écouter les changements de préférence système
	window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
		const savedTheme = localStorage.getItem('theme');
		if (!savedTheme) {
			// Si pas de préférence sauvegardée, suivre le système
			setTheme(e.matches ? 'dark' : 'light');
		}
	});
}
