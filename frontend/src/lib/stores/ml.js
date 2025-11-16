/**
 * Store ML - État global Machine Learning
 * Gère stats, features, models, training progress
 */

import { writable, derived } from 'svelte/store';

// ========== STORES ==========

// Stats ML dashboard
export const mlStats = writable({
	trades_count: 0,
	target_trades: 500,
	progress_pct: 0,
	readiness: {},
	next_milestone: null,
	feature_stats: {},
	timestamp: null
});

// Qualité données
export const dataQuality = writable({
	status: 'unknown',
	trades_count: 0,
	win_loss_distribution: {},
	quality_score: 0
});

// Feature importance
export const featureImportance = writable({
	method: 'correlation',
	features: [],
	trades_count: 0,
	confidence: 'low'
});

// Models status
export const modelsStatus = writable({
	xgboost: { ready: false, trained: false },
	gru: { ready: false, trained: false },
	ppo: { ready: false, trained: false }
});

// Training progress (pour WebSocket live)
export const trainingProgress = writable({
	active: false,
	model_type: null,
	epoch: 0,
	total_epochs: 0,
	loss: null,
	accuracy: null,
	message: ''
});

// Experiments tracking
export const experiments = writable([]);

// ========== DERIVED STORES ==========

// ML ready for any model
export const mlReady = derived(mlStats, ($mlStats) => {
	return $mlStats.trades_count >= 10;
});

// Can train XGBoost
export const canTrainXGBoost = derived(mlStats, ($mlStats) => {
	return (
		$mlStats.readiness?.xgboost?.ready || false
	);
});

// Can train GRU
export const canTrainGRU = derived(mlStats, ($mlStats) => {
	return (
		$mlStats.readiness?.gru?.ready || false
	);
});

// ========== ACTIONS ==========

/**
 * Charger stats ML dashboard
 */
export async function loadMLStats() {
	try {
		const response = await fetch('/api/ml/dashboard/stats');
		if (!response.ok) throw new Error('Failed to load ML stats');

		const data = await response.json();
		mlStats.set(data);

		return data;
	} catch (error) {
		console.error('Error loading ML stats:', error);
		throw error;
	}
}

/**
 * Charger qualité données
 */
export async function loadDataQuality() {
	try {
		const response = await fetch('/api/ml/dashboard/data_quality');
		if (!response.ok) throw new Error('Failed to load data quality');

		const data = await response.json();
		dataQuality.set(data);

		return data;
	} catch (error) {
		console.error('Error loading data quality:', error);
		throw error;
	}
}

/**
 * Charger feature importance
 */
export async function loadFeatureImportance(method = 'correlation', nFeatures = 20) {
	try {
		const response = await fetch(
			`/api/ml/features/importance?method=${method}&n_features=${nFeatures}`
		);
		if (!response.ok) throw new Error('Failed to load feature importance');

		const data = await response.json();
		featureImportance.set(data);

		return data;
	} catch (error) {
		console.error('Error loading feature importance:', error);
		throw error;
	}
}

/**
 * Charger models status
 */
export async function loadModelsStatus() {
	try {
		const response = await fetch('/api/ml/models/status');
		if (!response.ok) throw new Error('Failed to load models status');

		const data = await response.json();
		modelsStatus.set(data.models || {});

		return data;
	} catch (error) {
		console.error('Error loading models status:', error);
		throw error;
	}
}

/**
 * Charger expériences ML
 */
export async function loadExperiments(limit = 10) {
	try {
		const response = await fetch(`/api/ml/models/experiments?limit=${limit}`);
		if (!response.ok) throw new Error('Failed to load experiments');

		const data = await response.json();
		experiments.set(data.experiments || []);

		return data;
	} catch (error) {
		console.error('Error loading experiments:', error);
		throw error;
	}
}

/**
 * Mettre à jour progression training (appelé par WebSocket)
 */
export function updateTrainingProgress(data) {
	trainingProgress.set({
		active: true,
		model_type: data.model_type || null,
		epoch: data.epoch || 0,
		total_epochs: data.total_epochs || 0,
		loss: data.loss || null,
		accuracy: data.accuracy || null,
		message: data.message || ''
	});
}

/**
 * Reset training progress
 */
export function resetTrainingProgress() {
	trainingProgress.set({
		active: false,
		model_type: null,
		epoch: 0,
		total_epochs: 0,
		loss: null,
		accuracy: null,
		message: ''
	});
}

/**
 * Charger toutes les données ML
 */
export async function loadAllMLData() {
	try {
		await Promise.all([
			loadMLStats(),
			loadModelsStatus()
		]);

		// Charger data quality si assez de trades
		const stats = await loadMLStats();
		if (stats.trades_count >= 10) {
			await loadDataQuality();
		}

		// Charger feature importance si assez de trades
		if (stats.trades_count >= 30) {
			await loadFeatureImportance();
		}

		return true;
	} catch (error) {
		console.error('Error loading all ML data:', error);
		return false;
	}
}
