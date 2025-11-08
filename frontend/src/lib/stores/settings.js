import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

// Paramètres par défaut
const defaultSettings = {
	// Trading
	maxPositionSize: 100, // USDT
	stopLossPercent: 2.0, // %
	takeProfitPercent: 4.0, // %
	trailingStopPercent: 1.5, // %
	maxDailyLoss: 50, // USDT
	maxDailyTrades: 20,

	// Scanner
	scanInterval: 60, // secondes
	minVolume: 1000000, // USDT
	maxSpread: 0.5, // %
	topPairsCount: 10,

	// Interface
	autoRefresh: true,
	refreshInterval: 5000, // ms
	showAdvancedStats: false,
	compactMode: false,
	soundEnabled: true,

	// Notifications
	notifyOnPosition: true,
	notifyOnSetup: false,
	notifyOnError: true,
	notifyOnMilestone: true,

	// Charts
	chartAnimations: true,
	chartMaxTrades: 20,
	showPnLChart: true,
	showWinLossChart: true,
	showVolumeChart: true
};

// Charger les settings depuis localStorage
function loadSettings() {
	if (!browser) return defaultSettings;

	const saved = localStorage.getItem('settings');
	if (saved) {
		try {
			const parsed = JSON.parse(saved);
			// Merger avec defaults pour avoir les nouveaux paramètres
			return { ...defaultSettings, ...parsed };
		} catch (e) {
			console.error('Error loading settings:', e);
			return defaultSettings;
		}
	}

	return defaultSettings;
}

// Store principal
export const settings = writable(loadSettings());

// Sauvegarder dans localStorage à chaque changement
settings.subscribe(value => {
	if (browser) {
		localStorage.setItem('settings', JSON.stringify(value));
	}
});

// Stores dérivés pour accès rapide
export const tradingSettings = derived(settings, $settings => ({
	maxPositionSize: $settings.maxPositionSize,
	stopLossPercent: $settings.stopLossPercent,
	takeProfitPercent: $settings.takeProfitPercent,
	trailingStopPercent: $settings.trailingStopPercent,
	maxDailyLoss: $settings.maxDailyLoss,
	maxDailyTrades: $settings.maxDailyTrades
}));

export const scannerSettings = derived(settings, $settings => ({
	scanInterval: $settings.scanInterval,
	minVolume: $settings.minVolume,
	maxSpread: $settings.maxSpread,
	topPairsCount: $settings.topPairsCount
}));

export const uiSettings = derived(settings, $settings => ({
	autoRefresh: $settings.autoRefresh,
	refreshInterval: $settings.refreshInterval,
	showAdvancedStats: $settings.showAdvancedStats,
	compactMode: $settings.compactMode,
	soundEnabled: $settings.soundEnabled
}));

// Fonctions utilitaires
export function updateSetting(key, value) {
	settings.update(s => ({ ...s, [key]: value }));
}

export function resetSettings() {
	settings.set(defaultSettings);
}

export function exportSettings() {
	const current = loadSettings();
	const json = JSON.stringify(current, null, 2);
	const blob = new Blob([json], { type: 'application/json' });
	const url = URL.createObjectURL(blob);

	const a = document.createElement('a');
	a.href = url;
	a.download = `trade-cursor-settings-${new Date().toISOString().split('T')[0]}.json`;
	a.click();

	URL.revokeObjectURL(url);
}

export function importSettings(file) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();

		reader.onload = e => {
			try {
				const imported = JSON.parse(e.target.result);
				settings.set({ ...defaultSettings, ...imported });
				resolve(true);
			} catch (error) {
				reject(error);
			}
		};

		reader.onerror = () => reject(new Error('Failed to read file'));
		reader.readAsText(file);
	});
}
