<script>
	import { onMount, onDestroy, createEventDispatcher } from 'svelte';
	import { browser } from '$app/environment';

	const dispatch = createEventDispatcher();

	// Props reçus du parent
	export let config;
	export let triggerAutoSave;
	
	// ========== PERSISTANCE & CONNEXION ==========
	const STORAGE_KEY = 'ml_auto_optimize_state';
	let heartbeatInterval = null;
	let connectionStatus = 'connected';
	let externalWindow = null;

	let mlMetricsGB = {
		test_accuracy: 66.2,
		test_f1: 0.567,
		test_precision: 0.694,
		overfitting_gap: 5.3,
		trades_count: 1328
	};
	
	// Auto-Optimisation complète
	let showAutoOptimizePopup = false;
	let autoOptimizing = false;
	let autoOptimizeProgress = 0;
	let autoOptimizeStatus = '';
	let autoOptimizeResults = null;
	let autoOptimizePollingInterval = null;
	
	// Popup draggable
	let popupPosition = { x: 100, y: 100 };
	let popupMinimized = false;
	let isDragging = false;
	let dragOffset = { x: 0, y: 0 };
	
	function startDrag(e) {
		isDragging = true;
		dragOffset = {
			x: e.clientX - popupPosition.x,
			y: e.clientY - popupPosition.y
		};
		window.addEventListener('mousemove', onDrag);
		window.addEventListener('mouseup', stopDrag);
	}
	
	function onDrag(e) {
		if (!isDragging) return;
		popupPosition = {
			x: Math.max(0, e.clientX - dragOffset.x),
			y: Math.max(0, e.clientY - dragOffset.y)
		};
	}
	
	function stopDrag() {
		isDragging = false;
		window.removeEventListener('mousemove', onDrag);
		window.removeEventListener('mouseup', stopDrag);
	}
	
	// ========== PERSISTANCE ÉTAT OPTIMISATION ==========
	
	function saveOptimizationState() {
		if (!browser) return;
		const state = {
			showPopup: showAutoOptimizePopup,
			optimizing: autoOptimizing,
			progress: autoOptimizeProgress,
			status: autoOptimizeStatus,
			results: autoOptimizeResults,
			taskId: currentTaskId,
			position: popupPosition,
			minimized: popupMinimized,
			timestamp: Date.now()
		};
		localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
	}
	
	function loadOptimizationState() {
		if (!browser) return null;
		try {
			const saved = localStorage.getItem(STORAGE_KEY);
			if (!saved) return null;
			
			const state = JSON.parse(saved);
			// Ignorer si plus vieux que 2 heures
			if (Date.now() - state.timestamp > 2 * 60 * 60 * 1000) {
				localStorage.removeItem(STORAGE_KEY);
				return null;
			}
			return state;
		} catch {
			return null;
		}
	}
	
	function clearOptimizationState() {
		if (browser) {
			localStorage.removeItem(STORAGE_KEY);
		}
	}
	
	// Variable pour stocker le task_id courant
	let currentTaskId = null;
	
	// ========== HEARTBEAT & CONNEXION ==========
	
	async function heartbeat() {
		try {
			const response = await fetch('/api/live/health', { 
				method: 'GET',
				signal: AbortSignal.timeout(5000)
			});
			if (response.ok) {
				connectionStatus = 'connected';
			} else {
				connectionStatus = 'error';
			}
		} catch {
			connectionStatus = 'disconnected';
			console.warn('⚠️ Heartbeat failed - backend may be busy');
		}
	}
	
	function startHeartbeat() {
		if (heartbeatInterval) return;
		heartbeat(); // Immédiat
		// Heartbeat toutes les 30s (moins agressif pendant l'optimisation)
		heartbeatInterval = setInterval(heartbeat, 30000);
	}
	
	function stopHeartbeat() {
		if (heartbeatInterval) {
			clearInterval(heartbeatInterval);
			heartbeatInterval = null;
		}
	}
	
	// ========== FENÊTRE EXTERNE ==========
	
	function openInExternalWindow() {
		if (externalWindow && !externalWindow.closed) {
			externalWindow.focus();
			return;
		}
		
		// Ouvrir une nouvelle fenêtre
		const width = 650;
		const height = 500;
		const left = window.screenX + 50;
		const top = window.screenY + 50;
		
		externalWindow = window.open(
			'',
			'ml_optimize_popup',
			`width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
		);
		
		if (externalWindow) {
			updateExternalWindow();
		}
	}
	
	function updateExternalWindow() {
		if (!externalWindow || externalWindow.closed) return;
		
		// Générer les étapes
		const steps = [
			{ threshold: 10, label: 'Initialisation' },
			{ threshold: 25, label: 'Chargement features' },
			{ threshold: 40, label: 'Sélection features (RF)' },
			{ threshold: 55, label: 'Grid search' },
			{ threshold: 70, label: 'Entraînement modèle' },
			{ threshold: 80, label: 'Analyse seuils' },
			{ threshold: 90, label: 'Validation croisée' },
			{ threshold: 100, label: 'Sauvegarde' }
		];
		
		let stepsHtml = '';
		steps.forEach((step, i) => {
			const prevThreshold = i === 0 ? 0 : steps[i-1].threshold;
			const isDone = autoOptimizeProgress >= step.threshold;
			const isActive = autoOptimizeProgress >= prevThreshold && autoOptimizeProgress < step.threshold;
			const icon = isDone ? '✅' : isActive ? '⏳' : '⬜';
			const color = isDone ? '#4ade80' : isActive ? '#60a5fa' : '#64748b';
			const bg = isActive ? 'rgba(59,130,246,0.2)' : 'rgba(30,41,59,0.4)';
			stepsHtml += `<div style="display:flex;align-items:center;gap:10px;padding:6px 10px;margin:4px 0;background:${bg};border-radius:6px;opacity:${isDone||isActive?1:0.5};">
				<span>${icon}</span><span style="color:${color};font-size:13px;">${step.label}</span>
			</div>`;
		});
		
		const progressBar = autoOptimizing ? `
			<div style="margin: 20px 0;">
				<div style="background: #1e293b; border-radius: 10px; height: 20px; overflow: hidden;">
					<div style="background: linear-gradient(90deg, #8b5cf6, #06b6d4); height: 100%; width: ${autoOptimizeProgress}%; transition: width 0.3s;"></div>
				</div>
				<p style="text-align: center; margin-top: 10px; color: #60a5fa;">${autoOptimizeProgress}% - ${autoOptimizeStatus}</p>
			</div>
		` : '';
		
		// Générer le tableau des seuils pour la popup externe
		let thresholdTableHtml = '';
		if (autoOptimizeResults?.threshold_analysis) {
			const rows = autoOptimizeResults.threshold_analysis.map(th => {
				const isOptimal = th.threshold === autoOptimizeResults.optimal_threshold;
				const bgColor = isOptimal ? 'rgba(139, 92, 246, 0.3)' : 'transparent';
				const border = isOptimal ? 'border-left: 3px solid #8b5cf6;' : '';
				return `<tr style="background:${bgColor};${border}">
					<td style="padding:6px;border-bottom:1px solid #1e293b;">${(th.threshold * 100).toFixed(0)}%</td>
					<td style="padding:6px;border-bottom:1px solid #1e293b;">${(th.accuracy * 100).toFixed(1)}%</td>
					<td style="padding:6px;border-bottom:1px solid #1e293b;">${th.f1_score.toFixed(3)}</td>
					<td style="padding:6px;border-bottom:1px solid #1e293b;">${th.precision.toFixed(3)}</td>
					<td style="padding:6px;border-bottom:1px solid #1e293b;">${th.recall.toFixed(3)}</td>
					<td style="padding:6px;border-bottom:1px solid #1e293b;">${th.predicted_wins || 0}</td>
				</tr>`;
			}).join('');
			
			thresholdTableHtml = `
				<div style="margin-top:20px;overflow-x:auto;">
					<h4 style="color:#94a3b8;margin:0 0 10px 0;font-size:13px;">📈 Analyse des Seuils</h4>
					<table style="width:100%;border-collapse:collapse;font-size:11px;">
						<thead>
							<tr style="background:rgba(0,0,0,0.3);">
								<th style="padding:8px;color:#94a3b8;text-align:left;">Seuil</th>
								<th style="padding:8px;color:#94a3b8;text-align:left;">Accuracy</th>
								<th style="padding:8px;color:#94a3b8;text-align:left;">F1</th>
								<th style="padding:8px;color:#94a3b8;text-align:left;">Precision</th>
								<th style="padding:8px;color:#94a3b8;text-align:left;">Recall</th>
								<th style="padding:8px;color:#94a3b8;text-align:left;">Prédits WIN</th>
							</tr>
						</thead>
						<tbody style="color:#e2e8f0;">${rows}</tbody>
					</table>
					<div style="margin-top:10px;padding:10px;background:rgba(139,92,246,0.15);border-radius:6px;text-align:center;color:#c4b5fd;font-size:12px;">
						🎯 Seuil recommandé: ${((autoOptimizeResults.optimal_threshold || 0.45) * 100).toFixed(0)}%
					</div>
				</div>
			`;
		}
		
		const resultsHtml = autoOptimizeResults ? `
			<div style="margin-top: 20px; padding: 15px; background: rgba(16, 185, 129, 0.1); border-radius: 8px;">
				<h3 style="color: #10b981; margin: 0 0 10px 0;">✅ Optimisation Terminée</h3>
				<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:15px;">
					<div style="text-align:center;padding:8px;background:rgba(0,0,0,0.2);border-radius:6px;">
						<div style="color:#94a3b8;font-size:10px;">ACCURACY</div>
						<div style="color:#f8fafc;font-size:16px;font-weight:600;">${((autoOptimizeResults.metrics?.test_accuracy || 0) * 100).toFixed(1)}%</div>
					</div>
					<div style="text-align:center;padding:8px;background:rgba(0,0,0,0.2);border-radius:6px;">
						<div style="color:#94a3b8;font-size:10px;">F1 SCORE</div>
						<div style="color:#f8fafc;font-size:16px;font-weight:600;">${(autoOptimizeResults.metrics?.f1_score || 0).toFixed(3)}</div>
					</div>
					<div style="text-align:center;padding:8px;background:rgba(0,0,0,0.2);border-radius:6px;">
						<div style="color:#94a3b8;font-size:10px;">ROC-AUC</div>
						<div style="color:#f8fafc;font-size:16px;font-weight:600;">${(autoOptimizeResults.metrics?.roc_auc || 0).toFixed(3)}</div>
					</div>
					<div style="text-align:center;padding:8px;background:rgba(0,0,0,0.2);border-radius:6px;">
						<div style="color:#94a3b8;font-size:10px;">PRECISION</div>
						<div style="color:#f8fafc;font-size:16px;font-weight:600;">${(autoOptimizeResults.metrics?.precision || 0).toFixed(3)}</div>
					</div>
					<div style="text-align:center;padding:8px;background:rgba(0,0,0,0.2);border-radius:6px;">
						<div style="color:#94a3b8;font-size:10px;">RECALL</div>
						<div style="color:#f8fafc;font-size:16px;font-weight:600;">${(autoOptimizeResults.metrics?.recall || 0).toFixed(3)}</div>
					</div>
					<div style="text-align:center;padding:8px;background:rgba(0,0,0,0.2);border-radius:6px;">
						<div style="color:#94a3b8;font-size:10px;">OVERFITTING</div>
						<div style="color:#f8fafc;font-size:16px;font-weight:600;">${((autoOptimizeResults.metrics?.overfitting || 0) * 100).toFixed(1)}%</div>
					</div>
				</div>
				${thresholdTableHtml}
				<p style="margin-top: 15px; color: #94a3b8; font-size: 11px; text-align:center;">Retournez à l'application principale pour appliquer les résultats.</p>
			</div>
		` : '';
		
		externalWindow.document.body.innerHTML = `
			<div style="font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; min-height: 100vh; padding: 20px;">
				<h2 style="margin: 0 0 20px 0;">🚀 Optimisation ML</h2>
				${progressBar}
				<div style="max-width: 300px; margin: 20px auto;">
					${stepsHtml}
				</div>
				${resultsHtml}
				<p style="color: #64748b; margin-top: 20px; font-size: 11px; text-align: center;">
					Mise à jour automatique • Application principale accessible
				</p>
			</div>
		`;
		externalWindow.document.title = `ML Optimize - ${autoOptimizeProgress}%`;
	}
	
	// ========== LIFECYCLE ==========
	
	onMount(async () => {
		// Restaurer l'état si existant
		const savedState = loadOptimizationState();
		if (savedState && savedState.optimizing && savedState.taskId) {
			console.log('🔄 Vérification état optimisation:', savedState);
			
			// Vérifier si la tâche existe encore sur le backend
			try {
				const response = await fetch(`/api/ml/task/${savedState.taskId}`, {
					signal: AbortSignal.timeout(5000)
				});
				
				if (response.ok) {
					const taskStatus = await response.json();
					
					// Si la tâche est encore en cours, restaurer l'état
					if (taskStatus.status === 'running' || taskStatus.status === 'pending') {
						console.log('✅ Tâche encore active, restauration état');
						showAutoOptimizePopup = savedState.showPopup;
						autoOptimizing = true;
						autoOptimizeProgress = taskStatus.progress || savedState.progress;
						autoOptimizeStatus = taskStatus.message || savedState.status;
						// NE PAS restaurer les anciens résultats si optimisation en cours
						autoOptimizeResults = null;
						currentTaskId = savedState.taskId;
						popupPosition = savedState.position || { x: 100, y: 100 };
						popupMinimized = savedState.minimized || false;
						
						// Reprendre le polling
						autoOptimizePollingInterval = setInterval(() => pollAutoOptimizeStatus(currentTaskId), 5000);
					} else if (taskStatus.status === 'completed') {
						// Tâche terminée, afficher les résultats
						console.log('✅ Tâche terminée, affichage résultats');
						showAutoOptimizePopup = true;
						autoOptimizing = false;
						autoOptimizeResults = taskStatus.results;
						autoOptimizeStatus = 'Optimisation terminée!';
						autoOptimizeProgress = 100;
						clearOptimizationState();
					} else {
						// Tâche échouée ou inconnue, nettoyer
						console.log('❌ Tâche invalide, nettoyage état');
						clearOptimizationState();
					}
				} else {
					// Tâche n'existe plus sur le backend
					console.log('❌ Tâche non trouvée sur backend, nettoyage état');
					clearOptimizationState();
				}
			} catch (err) {
				// Backend non accessible, nettoyer l'état pour éviter blocage
				console.log('⚠️ Backend non accessible, nettoyage état:', err);
				clearOptimizationState();
			}
		} else if (savedState && !savedState.optimizing && savedState.results) {
			// Résultats à afficher mais pas en cours
			showAutoOptimizePopup = savedState.showPopup;
			autoOptimizeResults = savedState.results;
			popupPosition = savedState.position || { x: 100, y: 100 };
		}
		
		// Démarrer le heartbeat
		startHeartbeat();
		
		// Écouter les changements de visibilité pour maintenir le polling
		document.addEventListener('visibilitychange', handleVisibilityChange);
		
		// Charger les métriques et données
		await loadMLMetricsGB();
		await loadMLTradesStats();
		await loadLastOptunaResults();
	});
	
	onDestroy(() => {
		stopHeartbeat();
		if (autoOptimizePollingInterval) {
			clearInterval(autoOptimizePollingInterval);
		}
		document.removeEventListener('visibilitychange', handleVisibilityChange);
	});
	
	function handleVisibilityChange() {
		if (document.visibilityState === 'visible') {
			// Page redevient visible - vérifier l'état
			if (autoOptimizing && currentTaskId && !autoOptimizePollingInterval) {
				console.log('🔄 Reprise du polling après retour sur la page');
				autoOptimizePollingInterval = setInterval(() => pollAutoOptimizeStatus(currentTaskId), 5000);
				// Poll immédiat pour mise à jour rapide
				pollAutoOptimizeStatus(currentTaskId);
			}
			heartbeat();
		}
	}
	
	let loadingMLMetrics = false;
	
	// 🔢 Stats trades ML filtrés
	let mlTradesStats = null;
	let loadingTradesStats = false;
	let retrainingML = false;
	let verifyingML = false;
	let verifyResult = null;
	
	// Optuna
	let optimizingOptuna = false;
	let optunaProgress = 0;
	let optunaStatus = { status: 'idle', message: 'Prêt à lancer l\'optimisation' };
	let optunaPollingInterval = null;
	let lastOptunaResults = null; // Derniers résultats chargés depuis l'API
	
	// Vérification complète
	let verifyingComplete = false;
	let verifyCompleteResult = null;
	
	// Type de modèle: 'gb' = GradientBoosting, 'histgb' = HistGradientBoosting (10x plus rapide)
	let modelType = config.gb_model_type || 'gb';
	
	// 🔄 Charger les derniers résultats d'optimisation Optuna
	async function loadLastOptunaResults() {
		try {
			const response = await fetch('/api/ml/optimize/gb/results');
			if (!response.ok) return;
			
			const results = await response.json();
			if (results && results.best_params) {
				lastOptunaResults = results;
				// Mettre à jour optunaStatus pour afficher les résultats
				optunaStatus = {
					status: 'completed',
					best_params: results.best_params,
					best_score: results.best_score_composite,
					metrics_holdout: results.metrics_holdout,
					message: `✅ Dernière optimisation: Accuracy=${((results.metrics_holdout?.test_accuracy || 0) * 100).toFixed(1)}%\n` +
						`F1=${(results.metrics_holdout?.f1_score || 0).toFixed(3)}\n` +
						`Overfitting=${((results.metrics_holdout?.overfitting_gap || 0) * 100).toFixed(1)}%`
				};
				console.log('📊 Résultats Optuna chargés:', results);
			}
		} catch (err) {
			console.log('⚠️ Pas de résultats Optuna précédents');
		}
	}
	
	// 🔢 Charger stats trades ML filtrés
	async function loadMLTradesStats() {
		if (loadingTradesStats) return;
		loadingTradesStats = true;
		
		try {
			const response = await fetch('/api/ml/dashboard/ml_trades_count');
			if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
			mlTradesStats = await response.json();
		} catch (err) {
			console.error('❌ Erreur chargement stats trades ML:', err);
			mlTradesStats = null;
		} finally {
			loadingTradesStats = false;
		}
	}
	
	function setModelType(type) {
		modelType = type;
		config.gb_model_type = type;
		triggerAutoSave('gb_model_type', type === 'histgb' ? 'HistGradientBoosting (Rapide)' : 'GradientBoosting (Standard)');
	}

	async function loadMLMetricsGB() {
		if (loadingMLMetrics) return;

		loadingMLMetrics = true;

		try {
			const response = await fetch('/api/ml/models/overview');
			if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);

			const data = await response.json();
			// Chercher le modèle GradientBoosting optimisé
			const gbModel = data.models?.find(m => 
				m.name === 'optimized_classifier' || 
				m.name === 'best_classifier' ||
				m.name === 'gradientboosting'
			);

			if (gbModel && gbModel.metrics) {
				const testMetrics = gbModel.metrics.test || {};
				mlMetricsGB = {
					test_accuracy: (testMetrics.accuracy || 0.643) * 100,
					test_accuracy_std: (testMetrics.accuracy_std || 0) * 100, // Pour afficher ±
					test_f1: testMetrics.f1_score || 0.415,
					test_precision: testMetrics.precision || 0.629,
					overfitting_gap: gbModel.overfitting_gap || 12.7,
					trades_count: gbModel.dataset_info?.total_samples || 2893,
					// 🔬 Flag pour indiquer que c'est du CV
					is_cv: testMetrics.accuracy_std !== undefined && testMetrics.accuracy_std > 0
				};
			}
		} catch (err) {
			console.error('❌ Erreur chargement métriques GradientBoosting:', err);
			// Utiliser les valeurs par défaut (modèle actuel)
		} finally {
			loadingMLMetrics = false;
		}
	}

	async function handleParamsApplied() {
		dispatch('paramsApplied');
	}

	async function retrainModelGB() {
		retrainingML = true;

		try {
			const response = await fetch('/api/ml/train_gb', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					n_estimators: config.gb_n_estimators,
					max_depth: config.gb_max_depth,
					learning_rate: config.gb_learning_rate,
					min_samples_split: config.gb_min_samples_split,
					min_samples_leaf: config.gb_min_samples_leaf,
					subsample: config.gb_subsample,
					max_features: config.gb_max_features
				})
			});

			if (!response.ok) throw new Error('Erreur réentraînement GradientBoosting');

			const result = await response.json();
			
			if (result.status === 'success' || result.task_id) {
				// Polling si task async
				if (result.task_id) {
					let completed = false;
					let attempts = 0;
					const maxAttempts = 120;

					while (!completed && attempts < maxAttempts) {
						await new Promise(resolve => setTimeout(resolve, 1000));
						attempts++;

						try {
							const statusRes = await fetch(`/api/ml/task/${result.task_id}`);
							if (!statusRes.ok) continue;

							const taskData = await statusRes.json();
							
							if (taskData.status === 'completed') {
								completed = true;
								alert(`✅ Modèle GradientBoosting réentraîné!\n\nAccuracy: ${(taskData.accuracy * 100).toFixed(1)}%\nF1: ${taskData.f1?.toFixed(3) || 'N/A'}`);
								await loadMLMetricsGB();
							} else if (taskData.status === 'error') {
								throw new Error(taskData.error || 'Erreur inconnue');
							}
						} catch (pollErr) {
							console.warn('Poll attempt failed:', pollErr);
						}
					}
				} else {
					alert(`✅ Modèle GradientBoosting réentraîné!\n\nAccuracy: ${(result.accuracy * 100).toFixed(1)}%`);
					await loadMLMetricsGB();
				}
			}

		} catch (err) {
			alert(`❌ Erreur: ${err.message}`);
		} finally {
			retrainingML = false;
		}
	}

	async function verifyModel() {
		verifyingML = true;
		verifyResult = null;

		try {
			const response = await fetch('/api/ml/verify_gb', {
				method: 'POST'
			});

			if (!response.ok) throw new Error('Erreur vérification');

			verifyResult = await response.json();
		} catch (err) {
			verifyResult = { status: 'error', message: err.message };
		} finally {
			verifyingML = false;
		}
	}
	
	// 🔬 Optimisation Optuna
	async function startOptunaOptimization() {
		optimizingOptuna = true;
		optunaProgress = 0;
		optunaStatus = { status: 'starting', message: 'Démarrage de l\'optimisation...' };
		
		try {
			// 🔥 Nouvel endpoint GradientBoosting avec validation rigoureuse
			// Utiliser HistGradientBoosting si sélectionné (10x plus rapide)
			const useHistGB = modelType === 'histgb';
			
			optunaStatus = { ...optunaStatus, status: 'fetching', message: 'Contact du serveur...' };
			
			const response = await fetch(`/api/ml/optimize/gb/start?n_trials=100&timeout_minutes=30&timeframe_days=365&use_histgb=${useHistGB}`, {
				method: 'POST'
			});
			
			optunaStatus = { ...optunaStatus, status: 'parsing', message: 'Analyse de la réponse...' };
			
			// Vérifier le statut HTTP
			console.log('📊 Response status:', response.status);
			if (!response.ok) {
				const errorText = await response.text();
				console.error('❌ Response error:', errorText);
				throw new Error(`HTTP ${response.status}: ${errorText}`);
			}
			
			const result = await response.json();
			console.log('📊 Response JSON:', result);
			
			// Mettre à jour optunaStatus avec la réponse pour debug
			optunaStatus = { ...optunaStatus, ...result, status: 'received', message: 'Réponse reçue' };
			
			if (result.task_id) {
				// Stocker le task_id pour le polling
				optunaStatus.task_id = result.task_id;
				optunaStatus.total_trials = 100;
				optunaStatus.status = 'polling';
				optunaStatus.message = 'Polling en cours...';
				// Démarrer le polling
				optunaPollingInterval = setInterval(pollOptunaStatus, 3000);
			} else {
				throw new Error(result.error || 'Erreur inconnue - pas de task_id dans la réponse');
			}
		} catch (err) {
			console.error('❌ Erreur complète:', err);
			optunaStatus = { status: 'error', message: `Erreur: ${err.message}` };
			optimizingOptuna = false;
		}
	}
	
	async function pollOptunaStatus() {
		try {
			// 🔥 Utiliser le task_id pour polling
			const taskId = optunaStatus?.task_id;
			if (!taskId) return;
			
			const response = await fetch(`/api/ml/task/${taskId}`);
			if (!response.ok) return;
			
			const status = await response.json();
			console.log('📊 Polling response:', status); // DEBUG
			
			optunaProgress = status.progress || 0;
			optunaStatus = { ...optunaStatus, ...status };
			
			console.log('📊 Updated optunaStatus:', optunaStatus); // DEBUG
			
			if (status.status === 'completed') {
				clearInterval(optunaPollingInterval);
				optimizingOptuna = false;
				
				// Extraire métriques holdout
				const metrics = status.metrics_holdout || {};
				optunaStatus = {
					...status,
					best_score: metrics.test_accuracy || status.best_score,
					metrics_holdout: metrics,
					message: `✅ Optimisation terminée!\nAccuracy=${((metrics.test_accuracy || 0) * 100).toFixed(1)}%\nOverfit Gap=${((metrics.overfitting_gap || 0) * 100).toFixed(1)}%`
				};
				
				// Rafraîchir les métriques
				await loadMLMetricsGB();
				
				// 🔄 Rafraîchir les sliders ET sauvegarder automatiquement
				if (status.best_params) {
					const paramMapping = {
						'n_estimators': 'gb_n_estimators',
						'max_depth': 'gb_max_depth',
						'learning_rate': 'gb_learning_rate',
						'min_samples_split': 'gb_min_samples_split',
						'min_samples_leaf': 'gb_min_samples_leaf',
						'subsample': 'gb_subsample',
						'max_features': 'gb_max_features'
					};
					
					// Mettre à jour le config local ET sauvegarder
					Object.entries(status.best_params).forEach(([key, value]) => {
						const configKey = paramMapping[key];
						if (configKey && config[configKey] !== undefined) {
							console.log(`📊 Mise à jour ${configKey}: ${config[configKey]} -> ${value}`);
							config[configKey] = value;
							// 🔥 SAUVEGARDER automatiquement chaque paramètre
							triggerAutoSave(configKey, value);
						}
					});
					
					// Forcer la réactivité
					config = {...config};
					
					optunaStatus.message += '\n📊 Sliders mis à jour et SAUVEGARDÉS!';
					optunaStatus.applied = true;
				}
			} else if (status.status === 'failed') {
				clearInterval(optunaPollingInterval);
				optimizingOptuna = false;
				optunaStatus = { ...status, message: `❌ Erreur: ${status.error}` };
			}
		} catch (err) {
			console.error('Erreur polling Optuna:', err);
		}
	}
	
	async function applyOptunaParams() {
		try {
			// 🔥 Utiliser le nouvel endpoint avec les params trouvés
			const paramsToApply = optunaStatus?.best_params || {};
			
			console.log('📊 Paramètres à appliquer:', paramsToApply);
			
			const response = await fetch('/api/ml/optimize/gb/apply', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(paramsToApply)
			});
			
			if (!response.ok) throw new Error('Erreur application paramètres');
			
			const result = await response.json();
			
			if (result.success) {
				// 🔄 Mapping des paramètres optimisés vers les clés des sliders
				const paramMapping = {
					'n_estimators': 'gb_n_estimators',
					'max_depth': 'gb_max_depth',
					'learning_rate': 'gb_learning_rate',
					'min_samples_split': 'gb_min_samples_split',
					'min_samples_leaf': 'gb_min_samples_leaf',
					'subsample': 'gb_subsample',
					'max_features': 'gb_max_features'
				};
				
				// Mettre à jour les sliders avec les nouveaux params
				Object.entries(paramsToApply).forEach(([key, value]) => {
					const configKey = paramMapping[key];
					if (configKey && config[configKey] !== undefined) {
						console.log(`📊 Mise à jour slider ${configKey}: ${config[configKey]} -> ${value}`);
						config[configKey] = value;
					}
				});
				
				// Forcer la réactivité Svelte
				config = {...config};
				
				optunaStatus = {
					...optunaStatus,
					applied: true,
					message: `✅ Paramètres appliqués aux sliders!\nLes changements sont visibles immédiatement.`
				};
				
				// Notifier le parent pour sauvegarder
				dispatch('paramsApplied');
				
				// Aussi appeler triggerAutoSave pour chaque param
				Object.entries(paramsToApply).forEach(([key, value]) => {
					const configKey = paramMapping[key];
					if (configKey) {
						triggerAutoSave(configKey, value);
					}
				});
				
				alert('✅ Paramètres appliqués aux sliders!\n\nPour réentraîner le modèle avec ces paramètres, cliquez sur "Réentraîner le modèle".');
			}
		} catch (err) {
			console.error('Erreur application params:', err);
			alert(`❌ Erreur: ${err.message}`);
		}
	}
	
	// 🔍 Vérification complète
	async function runCompleteVerification() {
		verifyingComplete = true;
		verifyCompleteResult = null;
		
		try {
			const response = await fetch('/api/ml/verify_gb/complete');
			if (!response.ok) throw new Error('Erreur vérification');
			
			verifyCompleteResult = await response.json();
		} catch (err) {
			verifyCompleteResult = { overall_status: 'ERROR', errors: [err.message] };
		} finally {
			verifyingComplete = false;
		}
	}
	
	// ========== AUTO-OPTIMISATION COMPLETE ==========
	
	async function startAutoOptimization() {
		// IMPORTANT: Reset complet de l'état AVANT tout
		autoOptimizeResults = null;
		autoOptimizeProgress = 0;
		autoOptimizeStatus = 'Démarrage de l\'optimisation complète...';
		currentTaskId = null;
		
		// Arrêter tout polling existant
		if (autoOptimizePollingInterval) {
			clearInterval(autoOptimizePollingInterval);
			autoOptimizePollingInterval = null;
		}
		
		// Forcer la réactivité Svelte
		showAutoOptimizePopup = true;
		autoOptimizing = true;
		
		// Nettoyer l'ancien état stocké
		clearOptimizationState();
		
		// Sauvegarder le nouvel état
		saveOptimizationState();
		
		// Mettre à jour la fenêtre externe immédiatement
		updateExternalWindow();
		
		try {
			const response = await fetch('/api/ml/optimize/auto/start', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					n_splits: 15,
					timeframe_days: 365,
					min_trades: 100
				})
			});
			
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			
			const result = await response.json();
			
			if (result.task_id) {
				currentTaskId = result.task_id;
				saveOptimizationState(); // Sauvegarder avec le task_id
				// Polling toutes les 5s (moins agressif pour le backend)
				autoOptimizePollingInterval = setInterval(() => pollAutoOptimizeStatus(result.task_id), 5000);
			} else {
				throw new Error('Pas de task_id reçu');
			}
		} catch (err) {
			autoOptimizeStatus = `Erreur: ${err.message}`;
			autoOptimizing = false;
			saveOptimizationState();
		}
	}
	
	async function pollAutoOptimizeStatus(taskId) {
		try {
			const response = await fetch(`/api/ml/task/${taskId}`, {
				signal: AbortSignal.timeout(10000) // Timeout 10s pour éviter blocage
			});
			if (!response.ok) return;
			
			const status = await response.json();
			
			autoOptimizeProgress = status.progress || 0;
			autoOptimizeStatus = status.message || 'Optimisation en cours...';
			
			// Sauvegarder l'état à chaque mise à jour
			saveOptimizationState();
			
			// Mettre à jour la fenêtre externe si ouverte
			updateExternalWindow();
			
			if (status.status === 'completed') {
				clearInterval(autoOptimizePollingInterval);
				autoOptimizePollingInterval = null;
				autoOptimizing = false;
				autoOptimizeResults = status.results;
				autoOptimizeStatus = 'Optimisation terminée!';
				
				// Sauvegarder les résultats
				saveOptimizationState();
				updateExternalWindow();
				
				// Rafraîchir les métriques
				await loadMLMetricsGB();
			} else if (status.status === 'failed') {
				clearInterval(autoOptimizePollingInterval);
				autoOptimizePollingInterval = null;
				autoOptimizing = false;
				autoOptimizeStatus = `Erreur: ${status.error}`;
				saveOptimizationState();
				updateExternalWindow();
			}
		} catch (err) {
			console.error('Erreur polling auto-optimize:', err);
			// Ne pas arrêter le polling en cas d'erreur réseau temporaire
			connectionStatus = 'reconnecting';
		}
	}
	
	async function applyAutoOptimizeResults() {
		if (!autoOptimizeResults) return;
		
		try {
			const response = await fetch('/api/ml/optimize/auto/apply', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(autoOptimizeResults)
			});
			
			if (!response.ok) throw new Error('Erreur application');
			
			const result = await response.json();
			
			if (result.success) {
				// Mettre à jour les sliders
				if (result.params) {
					// Le backend retourne les clés avec préfixe gb_ directement
					const validKeys = [
						'gb_max_depth',
						'gb_learning_rate', 
						'gb_n_estimators',
						'gb_min_samples_leaf',
						'gb_l2_regularization',
						'gb_n_features',
						'gb_min_confidence'
					];
					
					Object.entries(result.params).forEach(([key, value]) => {
						if (validKeys.includes(key) && config[key] !== undefined) {
							console.log(`Updating slider: ${key} = ${value}`);
							config[key] = value;
							triggerAutoSave(key, value);
						}
					});
					
					// Mettre à jour le seuil de confiance (si pas déjà dans params)
					if (result.optimal_threshold && !result.params.gb_min_confidence) {
						config.gb_min_confidence = result.optimal_threshold;
						triggerAutoSave('gb_min_confidence', result.optimal_threshold);
					}
					
					// Force reactivity
					config = {...config};
				}
				
				// Mettre à jour les métriques locales
				if (result.metrics) {
					mlMetricsGB = {
						test_accuracy: (result.metrics.test_accuracy || 0) * 100,
						test_f1: result.metrics.f1_score || 0,
						test_precision: result.metrics.precision || 0,
						overfitting_gap: (result.metrics.overfitting || 0) * 100,
						trades_count: result.metrics.n_train + result.metrics.n_test || mlMetricsGB.trades_count
					};
				}
				
				alert('✅ Nouveaux paramètres appliqués avec succès!');
				showAutoOptimizePopup = false;
			}
		} catch (err) {
			alert(`❌ Erreur: ${err.message}`);
		}
	}
	
	function closeAutoOptimizePopup() {
		if (autoOptimizing) {
			const choice = confirm(
				'L\'optimisation est en cours.\n\n' +
				'• OK = Masquer la fenêtre (l\'optimisation continue en arrière-plan)\n' +
				'• Annuler = Garder la fenêtre ouverte'
			);
			if (!choice) return;
			
			// Ne pas arrêter le polling, juste masquer
			showAutoOptimizePopup = false;
			saveOptimizationState();
			return;
		}
		
		// Si terminé, nettoyer l'état
		showAutoOptimizePopup = false;
		autoOptimizing = false;
		clearOptimizationState();
		
		// Fermer la fenêtre externe si ouverte
		if (externalWindow && !externalWindow.closed) {
			externalWindow.close();
		}
	}
</script>

<div class="ml-gb-wrapper">
	<!-- Info Banner -->
	<div class="info-banner">
		<div class="banner-icon">🎯</div>
		<div class="banner-content">
			<h4>GradientBoosting Optimisé</h4>
			<p>Ce modèle a été optimisé pour atteindre <strong>64-69% d'accuracy</strong> (vs ~50% pour XGBoost V1). 
			Il utilise des features temporelles (heures favorables) et une forte régularisation pour éviter l'overfitting.</p>
		</div>
	</div>

	<!-- Sélection Type de Modèle -->
	<section class="variable-section model-type-section">
		<h3>⚡ Type de Modèle</h3>
		<p class="section-desc">
			Choisissez l'algorithme d'entraînement. HistGradientBoosting est <strong>10x plus rapide</strong> avec des performances similaires.
		</p>
		
		<div class="model-type-selector">
			<button 
				class="model-type-btn" 
				class:active={modelType === 'gb'}
				on:click={() => setModelType('gb')}
			>
				<span class="model-icon">🌳</span>
				<div class="model-info">
					<span class="model-name">GradientBoosting</span>
					<span class="model-desc">Standard - Plus précis sur petits datasets</span>
				</div>
				<span class="model-speed">1x</span>
			</button>
			
			<button 
				class="model-type-btn" 
				class:active={modelType === 'histgb'}
				on:click={() => setModelType('histgb')}
			>
				<span class="model-icon">⚡</span>
				<div class="model-info">
					<span class="model-name">HistGradientBoosting</span>
					<span class="model-desc">Rapide - Idéal pour Optuna (100+ trials)</span>
				</div>
				<span class="model-speed">10x</span>
			</button>
		</div>
		
		<div class="model-comparison">
			<div class="comparison-item">
				<span class="comp-label">Vitesse entraînement</span>
				<div class="comp-bars">
					<div class="comp-bar gb" style="width: {modelType === 'gb' ? '30%' : '15%'}">GB</div>
					<div class="comp-bar histgb" style="width: {modelType === 'histgb' ? '100%' : '50%'}">HistGB</div>
				</div>
			</div>
			<div class="comparison-item">
				<span class="comp-label">Optuna 100 trials</span>
				<span class="comp-value">{modelType === 'histgb' ? '~2-5 min' : '~15-30 min'}</span>
			</div>
			<div class="comparison-item">
				<span class="comp-label">Accuracy attendue</span>
				<span class="comp-value">~64% (équivalent)</span>
			</div>
		</div>
	</section>

	<!-- Filtrage ML -->
	<section class="variable-section">
		<h3>🎯 Filtrage ML GradientBoosting</h3>
		<p class="section-desc">
			Activez le filtre pour bloquer automatiquement les trades avec faible probabilité de succès.
		</p>

		<div class="variable-item toggle-item">
			<div class="var-header">
				<label for="gb_filter_enabled">
					<span class="var-name">Activer Filtrage GradientBoosting</span>
					<span class="var-desc">Bloquer les trades avec confiance &lt; seuil</span>
				</label>
			</div>
			<label class="toggle">
				<input
					type="checkbox"
					id="gb_filter_enabled"
					bind:checked={config.gb_filter_enabled}
					on:change={() => triggerAutoSave('gb_filter_enabled', config.gb_filter_enabled ? 'Activé' : 'Désactivé')}
				/>
				<span class="toggle-slider"></span>
			</label>
		</div>

		<div class="variable-item" class:disabled={!config.gb_filter_enabled}>
			<div class="var-header">
				<label for="gb_min_confidence">
					<span class="var-name">Seuil de Confiance Minimum</span>
					<span class="var-desc">Probabilité minimale de WIN pour accepter le trade (25-80%, pas: 1%)</span>
				</label>
			</div>
			<div class="slider-container">
				<input
					type="range"
					id="gb_min_confidence"
					min="0.25"
					max="0.80"
					step="0.01"
					bind:value={config.gb_min_confidence}
					on:change={() => triggerAutoSave('gb_min_confidence', Math.round(config.gb_min_confidence * 100) + '%')}
					disabled={!config.gb_filter_enabled}
				/>
				<span class="slider-value">{Math.round(config.gb_min_confidence * 100)}%</span>
			</div>
		</div>
	</section>

	<!-- Métriques -->
	<section class="variable-section metrics-section">
		<h3>📊 Métriques du Modèle GradientBoosting</h3>
		{#if loadingMLMetrics}
			<div class="loading-message">⏳ Chargement des métriques...</div>
		{:else}
			<div class="ml-metrics-grid">
				<div class="metric-card" class:good={mlMetricsGB.test_accuracy >= 60} class:ok={mlMetricsGB.test_accuracy >= 55 && mlMetricsGB.test_accuracy < 60} class:warning={mlMetricsGB.test_accuracy < 55}>
					<span class="metric-label">{mlMetricsGB.is_cv ? '🔬 CV Accuracy' : 'Test Accuracy'}</span>
					<strong class="metric-value">
						{mlMetricsGB.test_accuracy.toFixed(1)}%
						{#if mlMetricsGB.is_cv && mlMetricsGB.test_accuracy_std > 0}
							<span class="std-badge">± {mlMetricsGB.test_accuracy_std.toFixed(1)}%</span>
						{/if}
					</strong>
					<span class="metric-hint">{mlMetricsGB.test_accuracy >= 60 ? '🎉 Excellent' : mlMetricsGB.test_accuracy >= 55 ? '✅ Bon' : '⚠️ À améliorer'}</span>
				</div>
				<div class="metric-card" class:good={mlMetricsGB.test_f1 >= 0.4} class:warning={mlMetricsGB.test_f1 < 0.4}>
					<span class="metric-label">F1 Score</span>
					<strong class="metric-value">{mlMetricsGB.test_f1.toFixed(3)}</strong>
					<span class="metric-hint">{mlMetricsGB.test_f1 >= 0.4 ? 'Bon équilibre' : 'Modéré'}</span>
				</div>
				<div class="metric-card" class:good={mlMetricsGB.test_precision >= 0.6}>
					<span class="metric-label">Precision</span>
					<strong class="metric-value">{mlMetricsGB.test_precision.toFixed(3)}</strong>
					<span class="metric-hint">{mlMetricsGB.test_precision >= 0.6 ? 'Peu de faux positifs' : 'OK'}</span>
				</div>
				<div class="metric-card" class:good={mlMetricsGB.overfitting_gap <= 15} class:warning={mlMetricsGB.overfitting_gap > 15 && mlMetricsGB.overfitting_gap <= 25} class:danger={mlMetricsGB.overfitting_gap > 25}>
					<span class="metric-label">Overfitting Gap</span>
					<strong class="metric-value">{mlMetricsGB.overfitting_gap.toFixed(1)}%</strong>
					<span class="metric-hint">{mlMetricsGB.overfitting_gap <= 15 ? 'Stable' : mlMetricsGB.overfitting_gap <= 25 ? 'Modéré' : 'Élevé'}</span>
				</div>
				<div class="metric-card" class:good={mlMetricsGB.trades_count >= 1000} class:ok={mlMetricsGB.trades_count >= 500} class:warning={mlMetricsGB.trades_count < 500}>
					<span class="metric-label">Dataset</span>
					<strong class="metric-value">{mlMetricsGB.trades_count.toLocaleString()}</strong>
					<span class="metric-hint">{mlMetricsGB.trades_count >= 1000 ? '👍 Excellent' : mlMetricsGB.trades_count >= 500 ? 'Suffisant' : 'Besoin de plus'}</span>
				</div>
			</div>
		{/if}
	</section>

	<!-- 🔢 Stats Trades ML -->
	<section class="variable-section trades-stats-section">
		<h3>🔢 Données ML Disponibles</h3>
		<p class="section-desc">
			Nombre de trades utilisables pour l'entraînement ML après filtrage (exclusion des trades manuels et configs différentes).
		</p>
		
		{#if loadingTradesStats}
			<div class="loading-message">⏳ Chargement des stats...</div>
		{:else if mlTradesStats}
			<div class="trades-stats-grid">
				<div class="stat-card total">
					<span class="stat-icon">📊</span>
					<div class="stat-content">
						<span class="stat-value">{mlTradesStats.total_trades?.toLocaleString() || 0}</span>
						<span class="stat-label">Trades Total</span>
					</div>
				</div>
				
				<div class="stat-card excluded">
					<span class="stat-icon">🚫</span>
					<div class="stat-content">
						<span class="stat-value">-{mlTradesStats.manual_excluded || 0}</span>
						<span class="stat-label">Manuels exclus</span>
					</div>
				</div>
				
				<div class="stat-card excluded">
					<span class="stat-icon">⚙️</span>
					<div class="stat-content">
						<span class="stat-value">-{mlTradesStats.different_config_excluded || 0}</span>
						<span class="stat-label">Configs différentes</span>
					</div>
				</div>
				
				<div class="stat-card final" class:good={mlTradesStats.config_filtered_trades >= 500} class:warning={mlTradesStats.config_filtered_trades < 500}>
					<span class="stat-icon">✅</span>
					<div class="stat-content">
						<span class="stat-value">{mlTradesStats.config_filtered_trades?.toLocaleString() || 0}</span>
						<span class="stat-label">Trades ML utilisables</span>
					</div>
				</div>
			</div>
			
			{#if mlTradesStats.current_config}
				<div class="config-info">
					<strong>Config actuelle (setup):</strong>
					min_score={mlTradesStats.current_config.min_score}, 
					snr={mlTradesStats.current_config.snr_threshold}, 
					vol_mult={mlTradesStats.current_config.volume_mult},
					confluence={mlTradesStats.current_config.use_confluence ? 'ON' : 'OFF'}
				</div>
				<div class="config-info-atr">
					<small>ATR: 1m=[{mlTradesStats.current_config.atr_min_1m}-{mlTradesStats.current_config.atr_max_1m}], 5m=[{mlTradesStats.current_config.atr_min_5m}-{mlTradesStats.current_config.atr_max_5m}]</small>
				</div>
				<div class="config-info-tpsl">
					<small>TP/SL: mode={mlTradesStats.current_config.tp_sl_mode}, TP={mlTradesStats.current_config.tp_percent}%, SL={mlTradesStats.current_config.sl_percent}%</small>
				</div>
			{/if}
			<button class="refresh-btn" on:click={loadMLTradesStats} disabled={loadingTradesStats}>
				🔄 Rafraîchir
			</button>
		{:else}
			<div class="error-message">❌ Impossible de charger les stats</div>
		{/if}
	</section>

	<!-- Hyperparamètres -->
	<section class="variable-section">
		<h3>⚙️ Hyperparamètres GradientBoosting</h3>
		<p class="section-desc">
			Ces paramètres ont été optimisés pour réduire l'overfitting tout en gardant une bonne accuracy.
		</p>

		<div class="subsection-grid">
			<div class="subsection-card">
				<h4>🌳 Configuration Arbres</h4>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_n_estimators">
							<span class="var-name">N Estimators</span>
							<span class="var-desc">Nombre total d'arbres</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_n_estimators" min="50" max="500" step="25" bind:value={config.gb_n_estimators} on:change={() => triggerAutoSave('gb_n_estimators', config.gb_n_estimators)} />
						<span class="slider-value">{config.gb_n_estimators}</span>
					</div>
				</div>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_max_depth">
							<span class="var-name">Max Depth</span>
							<span class="var-desc">Profondeur max des arbres (↓ réduit overfitting)</span>
						</label>
					</div>
					<select id="gb_max_depth" bind:value={config.gb_max_depth} on:change={() => triggerAutoSave('gb_max_depth', config.gb_max_depth)} class="select-input">
						<option value={2}>2 (très conservateur)</option>
						<option value={3}>3 (conservateur)</option>
						<option value={4}>4 (modéré)</option>
						<option value={5}>5 (agressif)</option>
						<option value={6}>6 (optimisé ⭐)</option>
					</select>
				</div>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_learning_rate">
							<span class="var-name">Learning Rate</span>
							<span class="var-desc">Taux d'apprentissage (↓ plus stable)</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_learning_rate" min="0.01" max="0.3" step="0.01" bind:value={config.gb_learning_rate} on:change={() => triggerAutoSave('gb_learning_rate', config.gb_learning_rate.toFixed(2))} />
						<span class="slider-value">{config.gb_learning_rate.toFixed(2)}</span>
					</div>
				</div>
			</div>

			<div class="subsection-card">
				<h4>🛡️ Régularisation</h4>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_min_samples_split">
							<span class="var-name">Min Samples Split</span>
							<span class="var-desc">Samples minimum pour diviser un noeud</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_min_samples_split" min="10" max="120" step="10" bind:value={config.gb_min_samples_split} on:change={() => triggerAutoSave('gb_min_samples_split', config.gb_min_samples_split)} />
						<span class="slider-value">{config.gb_min_samples_split}</span>
					</div>
				</div>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_min_samples_leaf">
							<span class="var-name">Min Samples Leaf</span>
							<span class="var-desc">Samples minimum par feuille</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_min_samples_leaf" min="10" max="80" step="10" bind:value={config.gb_min_samples_leaf} on:change={() => triggerAutoSave('gb_min_samples_leaf', config.gb_min_samples_leaf)} />
						<span class="slider-value">{config.gb_min_samples_leaf}</span>
					</div>
				</div>
			</div>

			<div class="subsection-card">
				<h4>🎲 Sampling</h4>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_subsample">
							<span class="var-name">Subsample</span>
							<span class="var-desc">% de données par arbre</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_subsample" min="0.5" max="1.0" step="0.05" bind:value={config.gb_subsample} on:change={() => triggerAutoSave('gb_subsample', config.gb_subsample.toFixed(2))} />
						<span class="slider-value">{config.gb_subsample.toFixed(2)}</span>
					</div>
				</div>
				<div class="variable-item">
					<div class="var-header">
						<label for="gb_max_features">
							<span class="var-name">Max Features</span>
							<span class="var-desc">% de features par split</span>
						</label>
					</div>
					<div class="slider-container">
						<input type="range" id="gb_max_features" min="0.3" max="1.0" step="0.1" bind:value={config.gb_max_features} on:change={() => triggerAutoSave('gb_max_features', typeof config.gb_max_features === 'number' ? config.gb_max_features.toFixed(1) : config.gb_max_features)} />
						<span class="slider-value">{typeof config.gb_max_features === 'number' ? config.gb_max_features.toFixed(1) : config.gb_max_features}</span>
					</div>
				</div>
			</div>
		</div>

		<div class="action-buttons">
			<div class="retrain-card">
				<div>
					<h4>🚀 Réentraîner Modèle</h4>
					<p>Génère un nouveau modèle avec les paramètres ci-dessus.</p>
				</div>
				<button class="btn-retrain" on:click={retrainModelGB} disabled={retrainingML}>
					{retrainingML ? '⏳ Réentraînement...' : 'Réentraîner'}
				</button>
			</div>

			<div class="verify-card">
				<div>
					<h4>🔍 Vérifier Modèle</h4>
					<p>Teste le modèle sur les données récentes.</p>
				</div>
				<button class="btn-verify" on:click={verifyModel} disabled={verifyingML}>
					{verifyingML ? '⏳ Vérification...' : 'Vérifier'}
				</button>
			</div>
		</div>
		
		<!-- 🔬 Optuna Optimization -->
		<div class="optuna-section">
			<div class="optuna-header">
				<h4>🔬 Optimisation Automatique (Optuna)</h4>
				<p>Recherche automatique des meilleurs hyperparamètres (~100 trials, ~15-30 min)</p>
			</div>
			
			<div class="optuna-actions">
				<button 
					class="btn-optuna" 
					on:click={startOptunaOptimization} 
					disabled={optimizingOptuna}
				>
					{#if optimizingOptuna}
						⏳ Optimisation en cours... ({optunaProgress}%)
					{:else}
						🔬 Lancer Optimisation Optuna
					{/if}
				</button>
				
				{#if optunaStatus?.status === 'completed'}
					<button class="btn-apply-optuna" on:click={applyOptunaParams}>
						{optunaStatus?.applied ? '🔄 Ré-appliquer les paramètres' : '✅ Appliquer les meilleurs paramètres'}
					</button>
					{#if optunaStatus?.applied}
						<button class="btn-retrain" on:click={retrainModelGB}>
							🎯 Réentraîner avec ces paramètres
						</button>
					{/if}
				{/if}
				
				{#if optunaStatus?.message}
					<div class="optuna-message">
						{optunaStatus.message}
					</div>
				{/if}
			</div>
			
			{#if optimizingOptuna}
				<div class="optuna-progress">
					<div class="progress-bar">
						<div class="progress-fill" style="width: {optunaProgress}%"></div>
					</div>
					<span class="progress-text">Trial {optunaStatus?.current_trial || 0}/{optunaStatus?.total_trials || 100}</span>
				</div>
			{/if}
			
			{#if optunaStatus?.best_params}
				<div class="optuna-result" class:success={optunaStatus.status === 'completed'}>
					<h5>🎯 Meilleurs paramètres trouvés</h5>
					
					<!-- Métriques Optuna -->
					{#if optunaStatus.metrics_holdout}
						<div class="optuna-metrics-box">
							<div class="metric-item">
								<span class="metric-label">Test Accuracy (Optuna)</span>
								<span class="metric-value">{((optunaStatus.metrics_holdout.test_accuracy || 0) * 100).toFixed(1)}%</span>
							</div>
							<div class="metric-item">
								<span class="metric-label">F1 Score</span>
								<span class="metric-value">{(optunaStatus.metrics_holdout.f1_score || 0).toFixed(3)}</span>
							</div>
							<div class="metric-item">
								<span class="metric-label">Overfitting Gap</span>
								<span class="metric-value">{((optunaStatus.metrics_holdout.overfitting_gap || 0) * 100).toFixed(1)}%</span>
							</div>
						</div>
					{/if}
					
					<div class="params-grid">
						{#each Object.entries(optunaStatus.best_params) as [key, value]}
							<div class="param-item">
								<span class="param-key">{key}</span>
								<span class="param-value">{typeof value === 'number' ? (Number.isInteger(value) ? value : value.toFixed(4)) : value}</span>
							</div>
						{/each}
					</div>
					{#if optunaStatus.applied}
						<div class="applied-badge">✅ Paramètres appliqués aux sliders</div>
					{/if}
				</div>
				
				<!-- Explication des métriques -->
				<div class="metrics-explanation">
					<details>
						<summary>ℹ️ Pourquoi les métriques diffèrent entre Optuna et l'UI ?</summary>
						<div class="explanation-content">
							<p><strong>Métriques Optuna</strong> = calculées pendant l'optimisation sur un split 80/20</p>
							<p><strong>Métriques UI (Config B)</strong> = calculées après ré-entraînement complet</p>
							<p>Les différences sont normales car :</p>
							<ul>
								<li>Le split train/test change à chaque entraînement</li>
								<li>L'UI peut utiliser un filtrage de données différent</li>
								<li>La cross-validation (~63%) est plus représentative</li>
							</ul>
							<p><strong>Conseil :</strong> Fiez-vous à la Cross-Validation plutôt qu'au holdout test.</p>
						</div>
					</details>
				</div>
			{/if}
		</div>
		
		<!-- 🔍 Vérification Complète -->
		<div class="verify-complete-section">
			<div class="verify-header">
				<h4>🔍 Boucle de Vérification Complète</h4>
				<p>Vérifie la configuration, le modèle, et la cohérence du système</p>
			</div>
			
			<button 
				class="btn-verify-complete" 
				on:click={runCompleteVerification} 
				disabled={verifyingComplete}
			>
				{verifyingComplete ? '⏳ Vérification...' : '🔍 Lancer Vérification Complète'}
			</button>
			
			{#if verifyCompleteResult}
				<div class="verify-complete-result" class:ok={verifyCompleteResult.overall_status === 'OK'} class:warning={verifyCompleteResult.overall_status === 'WARNING'} class:error={verifyCompleteResult.overall_status === 'ERROR'}>
					<div class="result-header">
						{#if verifyCompleteResult.overall_status === 'OK'}
							✅ Système OK
						{:else if verifyCompleteResult.overall_status === 'WARNING'}
							⚠️ Avertissements détectés
						{:else}
							❌ Erreurs détectées
						{/if}
						<span class="result-summary">
							{verifyCompleteResult.summary?.ok || 0} OK / {verifyCompleteResult.summary?.warnings || 0} Warn / {verifyCompleteResult.summary?.errors || 0} Err
						</span>
					</div>
					
					<div class="checks-list">
						{#each verifyCompleteResult.checks || [] as check}
							<div class="check-item" class:ok={check.status === 'OK'} class:warning={check.status === 'WARNING'} class:error={check.status === 'ERROR'}>
								<span class="check-icon">
									{#if check.status === 'OK'}✅{:else if check.status === 'WARNING'}⚠️{:else}❌{/if}
								</span>
								<span class="check-name">{check.name}</span>
								<span class="check-details">{check.details}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>

		{#if verifyResult}
			<div class="verify-result" class:success={verifyResult.status === 'PASS'} class:error={verifyResult.status === 'error' || verifyResult.status === 'FAIL'}>
				{#if verifyResult.status === 'PASS'}
					<span>✅ Modèle valide - Accuracy: {(verifyResult.accuracy * 100).toFixed(1)}%</span>
				{:else if verifyResult.status === 'error'}
					<span>❌ Erreur: {verifyResult.message}</span>
				{:else}
					<span>⚠️ Modèle non performant: {verifyResult.message}</span>
				{/if}
			</div>
		{/if}
	</section>

	<!-- Features Info -->
	<section class="variable-section info-section">
		<h3>ℹ️ Features Importantes</h3>
		<div class="features-grid">
			<div class="feature-card">
				<span class="feature-icon">🕐</span>
				<div>
					<h5>Heures Favorables (UTC)</h5>
					<p class="good">2h, 12h, 16h → Win rate ~55%</p>
				</div>
			</div>
			<div class="feature-card">
				<span class="feature-icon">⚠️</span>
				<div>
					<h5>Heures Défavorables (UTC)</h5>
					<p class="bad">4h, 18h, 23h → Win rate ~35%</p>
				</div>
			</div>
			<div class="feature-card">
				<span class="feature-icon">📈</span>
				<div>
					<h5>RSI Momentum</h5>
					<p>Différence RSI 1m vs 5m</p>
				</div>
			</div>
			<div class="feature-card">
				<span class="feature-icon">📊</span>
				<div>
					<h5>MACD Aligné</h5>
					<p>MACD 1m et 5m même signe</p>
				</div>
			</div>
		</div>
	</section>
	
	<!-- 🚀 Auto-Optimisation Complète -->
	<section class="variable-section auto-optimize-section">
		<div class="auto-optimize-header">
			<h3>🚀 Optimisation Automatique Complète</h3>
			<p class="section-desc">
				Lance une recherche exhaustive pour trouver les meilleurs hyperparamètres, 
				sélection de features et seuil de confiance optimal.
			</p>
		</div>
		
		<div class="auto-optimize-features">
			<div class="feature-tag">✓ Sélection features (RF importance)</div>
			<div class="feature-tag">✓ Grid search hyperparamètres</div>
			<div class="feature-tag">✓ Analyse seuils de confiance</div>
			<div class="feature-tag">✓ Cross-validation 5-fold</div>
			<div class="feature-tag">✓ Comparaison ancien/nouveau</div>
		</div>
		
		<button 
			class="btn-auto-optimize" 
			on:click={startAutoOptimization}
			disabled={autoOptimizing}
		>
			{#if autoOptimizing}
				⏳ Optimisation en cours...
			{:else}
				🚀 Lancer Optimisation Complète
			{/if}
		</button>
	</section>
</div>

<!-- Popup Auto-Optimisation (Déplaçable et Non-Bloquant) -->
{#if showAutoOptimizePopup}
	<div 
		class="popup-floating auto-optimize-popup"
		style="left: {popupPosition.x}px; top: {popupPosition.y}px;"
	>
		<div 
			class="popup-header draggable"
			on:mousedown={startDrag}
		>
			<div class="popup-title-row">
				<h2>🚀 Optimisation Automatique ML</h2>
				<span class="connection-indicator {connectionStatus}" title="Connexion: {connectionStatus}">
					{connectionStatus === 'connected' ? '🟢' : connectionStatus === 'reconnecting' ? '🟡' : '🔴'}
				</span>
			</div>
			<div class="popup-header-actions">
				<button class="popup-external" on:click={openInExternalWindow} title="Ouvrir dans une fenêtre séparée">
					↗️
				</button>
				<button class="popup-minimize" on:click={() => popupMinimized = !popupMinimized} title={popupMinimized ? 'Agrandir' : 'Réduire'}>
					{popupMinimized ? '🔼' : '🔽'}
				</button>
				<button class="popup-close" on:click={closeAutoOptimizePopup} title="Fermer">×</button>
			</div>
		</div>
		
		{#if !popupMinimized}
			<div class="popup-content">
				{#if autoOptimizing}
					<div class="optimize-progress-section">
						<div class="progress-bar-large">
							<div class="progress-fill" style="width: {autoOptimizeProgress}%"></div>
						</div>
						<div class="progress-info">
							<span class="progress-percent">{autoOptimizeProgress}%</span>
							<span class="progress-status">{autoOptimizeStatus}</span>
						</div>
						
						<!-- Liste des étapes avec statut -->
						<div class="progress-steps">
							<div class="step" class:done={autoOptimizeProgress >= 10} class:active={autoOptimizeProgress >= 5 && autoOptimizeProgress < 15}>
								<span class="step-icon">{autoOptimizeProgress >= 10 ? '✅' : autoOptimizeProgress >= 5 ? '⏳' : '⬜'}</span>
								<span class="step-text">Initialisation</span>
							</div>
							<div class="step" class:done={autoOptimizeProgress >= 25} class:active={autoOptimizeProgress >= 15 && autoOptimizeProgress < 25}>
								<span class="step-icon">{autoOptimizeProgress >= 25 ? '✅' : autoOptimizeProgress >= 15 ? '⏳' : '⬜'}</span>
								<span class="step-text">Chargement features</span>
							</div>
							<div class="step" class:done={autoOptimizeProgress >= 40} class:active={autoOptimizeProgress >= 25 && autoOptimizeProgress < 40}>
								<span class="step-icon">{autoOptimizeProgress >= 40 ? '✅' : autoOptimizeProgress >= 25 ? '⏳' : '⬜'}</span>
								<span class="step-text">Sélection features (RF)</span>
							</div>
							<div class="step" class:done={autoOptimizeProgress >= 55} class:active={autoOptimizeProgress >= 40 && autoOptimizeProgress < 55}>
								<span class="step-icon">{autoOptimizeProgress >= 55 ? '✅' : autoOptimizeProgress >= 40 ? '⏳' : '⬜'}</span>
								<span class="step-text">Grid search hyperparamètres</span>
							</div>
							<div class="step" class:done={autoOptimizeProgress >= 70} class:active={autoOptimizeProgress >= 55 && autoOptimizeProgress < 70}>
								<span class="step-icon">{autoOptimizeProgress >= 70 ? '✅' : autoOptimizeProgress >= 55 ? '⏳' : '⬜'}</span>
								<span class="step-text">Entraînement modèle</span>
							</div>
							<div class="step" class:done={autoOptimizeProgress >= 80} class:active={autoOptimizeProgress >= 70 && autoOptimizeProgress < 80}>
								<span class="step-icon">{autoOptimizeProgress >= 80 ? '✅' : autoOptimizeProgress >= 70 ? '⏳' : '⬜'}</span>
								<span class="step-text">Analyse seuils confiance</span>
							</div>
							<div class="step" class:done={autoOptimizeProgress >= 90} class:active={autoOptimizeProgress >= 80 && autoOptimizeProgress < 90}>
								<span class="step-icon">{autoOptimizeProgress >= 90 ? '✅' : autoOptimizeProgress >= 80 ? '⏳' : '⬜'}</span>
								<span class="step-text">Validation croisée</span>
							</div>
							<div class="step" class:done={autoOptimizeProgress >= 100} class:active={autoOptimizeProgress >= 90 && autoOptimizeProgress < 100}>
								<span class="step-icon">{autoOptimizeProgress >= 100 ? '✅' : autoOptimizeProgress >= 90 ? '⏳' : '⬜'}</span>
								<span class="step-text">Sauvegarde résultats</span>
							</div>
						</div>
						
						<div class="loading-spinner"></div>
					</div>
				{:else if autoOptimizeResults}
					<!-- Résultats de l'optimisation -->
					<div class="results-section">
						<h3>📊 Résultats de l'Optimisation</h3>
						
						<!-- Comparaison Ancien vs Nouveau -->
						<div class="comparison-table">
							<h4>Comparaison Ancien ↔ Nouveau Modèle</h4>
							
							<!-- Légende métriques principales -->
							<div class="metrics-legend compact">
								<div class="legend-item" title="Pourcentage de prédictions correctes (WIN prédit = WIN réel ou LOSS prédit = LOSS réel)">
									<span class="legend-label">Accuracy</span>
									<span class="legend-desc">% prédictions correctes</span>
								</div>
								<div class="legend-item" title="Moyenne harmonique entre Precision et Recall - équilibre les deux">
									<span class="legend-label">F1 Score</span>
									<span class="legend-desc">Équilibre precision/recall</span>
								</div>
								<div class="legend-item" title="Aire sous la courbe ROC - mesure la capacité à distinguer WIN de LOSS">
									<span class="legend-label">ROC-AUC</span>
									<span class="legend-desc">Discrimination (0.5=hasard)</span>
								</div>
								<div class="legend-item" title="Parmi les prédictions WIN, combien sont vraiment des WIN - évite les faux positifs">
									<span class="legend-label">Precision</span>
									<span class="legend-desc">% WIN prédits vrais</span>
								</div>
								<div class="legend-item" title="Parmi tous les vrais WIN, combien ont été détectés - évite de rater des opportunités">
									<span class="legend-label">Recall</span>
									<span class="legend-desc">% vrais WIN détectés</span>
								</div>
								<div class="legend-item" title="Différence entre performance train et test - un gap élevé indique du surapprentissage">
									<span class="legend-label">Overfitting</span>
									<span class="legend-desc">Écart train/test (bas=mieux)</span>
								</div>
							</div>
							
							<table>
								<thead>
									<tr>
										<th>Métrique</th>
										<th>Ancien</th>
										<th>Nouveau</th>
										<th>Diff</th>
									</tr>
								</thead>
								<tbody>
									<tr class:improved={autoOptimizeResults.metrics?.test_accuracy > autoOptimizeResults.baseline?.accuracy}>
										<td title="Pourcentage de prédictions correctes">Accuracy</td>
										<td>{((autoOptimizeResults.baseline?.accuracy || 0) * 100).toFixed(2)}%</td>
										<td>{((autoOptimizeResults.metrics?.test_accuracy || 0) * 100).toFixed(2)}%</td>
										<td class:positive={(autoOptimizeResults.metrics?.test_accuracy - autoOptimizeResults.baseline?.accuracy) > 0}>
											{((autoOptimizeResults.metrics?.test_accuracy - autoOptimizeResults.baseline?.accuracy) * 100).toFixed(2)}%
										</td>
									</tr>
									<tr class:improved={autoOptimizeResults.metrics?.f1_score > autoOptimizeResults.baseline?.f1}>
										<td title="Moyenne harmonique entre Precision et Recall">F1 Score</td>
										<td>{(autoOptimizeResults.baseline?.f1 || 0).toFixed(4)}</td>
										<td>{(autoOptimizeResults.metrics?.f1_score || 0).toFixed(4)}</td>
										<td class:positive={(autoOptimizeResults.metrics?.f1_score - autoOptimizeResults.baseline?.f1) > 0}>
											{(autoOptimizeResults.metrics?.f1_score - autoOptimizeResults.baseline?.f1).toFixed(4)}
										</td>
									</tr>
									<tr class:improved={autoOptimizeResults.metrics?.roc_auc > autoOptimizeResults.baseline?.roc_auc}>
										<td title="Aire sous la courbe ROC - qualité de discrimination">ROC-AUC</td>
										<td>{(autoOptimizeResults.baseline?.roc_auc || 0).toFixed(4)}</td>
										<td>{(autoOptimizeResults.metrics?.roc_auc || 0).toFixed(4)}</td>
										<td class:positive={(autoOptimizeResults.metrics?.roc_auc - autoOptimizeResults.baseline?.roc_auc) > 0}>
											{(autoOptimizeResults.metrics?.roc_auc - autoOptimizeResults.baseline?.roc_auc).toFixed(4)}
										</td>
									</tr>
									<tr class:improved={(autoOptimizeResults.metrics?.precision || 0) > 0.5}>
										<td title="% des prédictions WIN qui sont vraies">Precision</td>
										<td>-</td>
										<td>{(autoOptimizeResults.metrics?.precision || 0).toFixed(4)}</td>
										<td></td>
									</tr>
									<tr class:improved={(autoOptimizeResults.metrics?.recall || 0) > 0.5}>
										<td title="% des vrais WIN détectés">Recall</td>
										<td>-</td>
										<td>{(autoOptimizeResults.metrics?.recall || 0).toFixed(4)}</td>
										<td></td>
									</tr>
									<tr>
										<td title="Écart entre performance train et test - plus bas = mieux">Overfitting</td>
										<td>{((autoOptimizeResults.baseline?.overfitting || 0) * 100).toFixed(2)}%</td>
										<td>{((autoOptimizeResults.metrics?.overfitting || 0) * 100).toFixed(2)}%</td>
										<td class:positive={(autoOptimizeResults.baseline?.overfitting - autoOptimizeResults.metrics?.overfitting) > 0}>
											{((autoOptimizeResults.baseline?.overfitting - autoOptimizeResults.metrics?.overfitting) * 100).toFixed(2)}%
										</td>
									</tr>
								</tbody>
							</table>
						</div>
						
						<!-- Analyse des Seuils -->
						{#if autoOptimizeResults.threshold_analysis}
							<div class="threshold-table">
								<h4>📈 Analyse des Seuils de Confiance</h4>
								
								<!-- Légende des métriques -->
								<div class="metrics-legend">
									<div class="legend-item" title="Pourcentage de prédictions correctes (WIN ou LOSS)">
										<span class="legend-label">Accuracy</span>
										<span class="legend-desc">% prédictions correctes</span>
									</div>
									<div class="legend-item" title="Moyenne harmonique entre Precision et Recall - équilibre les deux">
										<span class="legend-label">F1</span>
										<span class="legend-desc">Équilibre precision/recall</span>
									</div>
									<div class="legend-item" title="Parmi les prédictions WIN, combien sont réellement des WIN">
										<span class="legend-label">Precision</span>
										<span class="legend-desc">% WIN prédits qui sont vrais</span>
									</div>
									<div class="legend-item" title="Parmi tous les vrais WIN, combien ont été détectés">
										<span class="legend-label">Recall</span>
										<span class="legend-desc">% vrais WIN détectés</span>
									</div>
									<div class="legend-item" title="Nombre de trades prédits comme gagnants à ce seuil">
										<span class="legend-label">Prédits WIN</span>
										<span class="legend-desc">Nb signaux générés</span>
									</div>
								</div>
								
								<table>
									<thead>
										<tr>
											<th>Seuil</th>
											<th>Accuracy</th>
											<th>F1</th>
											<th>Precision</th>
											<th>Recall</th>
											<th>Prédits WIN</th>
										</tr>
									</thead>
									<tbody>
										{#each autoOptimizeResults.threshold_analysis as th}
											<tr class:optimal={th.threshold === autoOptimizeResults.optimal_threshold}>
												<td>{(th.threshold * 100).toFixed(0)}%</td>
												<td>{(th.accuracy * 100).toFixed(1)}%</td>
												<td>{th.f1_score.toFixed(3)}</td>
												<td>{th.precision.toFixed(3)}</td>
												<td>{th.recall.toFixed(3)}</td>
												<td>{th.predicted_wins || 0}</td>
											</tr>
										{/each}
									</tbody>
								</table>
								<div class="optimal-threshold-info">
									<strong>🎯 Seuil optimal recommandé:</strong> {((autoOptimizeResults.optimal_threshold || 0.45) * 100).toFixed(0)}%
								</div>
							</div>
						{/if}
						
						<!-- Nouveaux Paramètres -->
						<div class="new-params">
							<h4>⚙️ Nouveaux Hyperparamètres</h4>
							<div class="params-grid">
								{#if autoOptimizeResults.params}
									{#each Object.entries(autoOptimizeResults.params) as [key, value]}
										<div class="param-item">
											<span class="param-key">{key}</span>
											<span class="param-value">{typeof value === 'number' ? (Number.isInteger(value) ? value : value.toFixed(4)) : value}</span>
										</div>
									{/each}
								{/if}
							</div>
						</div>
						
						<!-- Features sélectionnées -->
						{#if autoOptimizeResults.feature_names}
							<div class="selected-features">
								<h4>🎯 Top Features ({autoOptimizeResults.n_features || autoOptimizeResults.feature_names.length})</h4>
								<div class="features-list">
									{#each autoOptimizeResults.feature_names.slice(0, 10) as fname, i}
										<span class="feature-chip">{i+1}. {fname}</span>
									{/each}
									{#if autoOptimizeResults.feature_names.length > 10}
										<span class="feature-chip more">+{autoOptimizeResults.feature_names.length - 10} autres</span>
									{/if}
								</div>
							</div>
						{/if}
					</div>
					
					<div class="popup-actions">
						<button class="btn-apply-results" on:click={applyAutoOptimizeResults}>
							✅ Appliquer ces paramètres
						</button>
						<button class="btn-cancel" on:click={closeAutoOptimizePopup}>
							Annuler
						</button>
					</div>
				{:else}
					<div class="error-section">
						<p>{autoOptimizeStatus || 'En attente...'}</p>
					</div>
				{/if}
			</div>
		{/if}
	</div>
{/if}

<style>
	.ml-gb-wrapper {
		display: flex;
		flex-direction: column;
		gap: 24px;
	}

	.info-banner {
		display: flex;
		gap: 16px;
		padding: 20px;
		background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(59, 130, 246, 0.1));
		border: 1px solid rgba(16, 185, 129, 0.3);
		border-radius: 12px;
	}

	.banner-icon {
		font-size: 32px;
	}

	.banner-content h4 {
		margin: 0 0 8px 0;
		color: #10b981;
		font-size: 18px;
	}

	.banner-content p {
		margin: 0;
		color: #94a3b8;
		font-size: 14px;
		line-height: 1.5;
	}

	.variable-section {
		background: rgba(7, 11, 30, 0.85);
		border: 1px solid rgba(255, 255, 255, 0.05);
		border-radius: 12px;
		padding: 24px;
		box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
	}

	.variable-section h3 {
		margin: 0 0 8px 0;
		font-size: 18px;
		color: #f8fafc;
	}

	.section-desc {
		color: #94a3b8;
		font-size: 14px;
		margin-bottom: 20px;
	}

	.subsection-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 16px;
		margin-top: 16px;
	}

	.subsection-card {
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.05);
		border-radius: 10px;
		padding: 16px;
	}

	.subsection-card h4 {
		margin: 0 0 16px 0;
		color: #e2e8f0;
		font-size: 15px;
	}

	.variable-item {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-bottom: 16px;
	}

	.variable-item.toggle-item {
		flex-direction: row;
		align-items: center;
		justify-content: space-between;
	}

	.var-header {
		display: flex;
		gap: 4px;
		flex-direction: column;
	}

	.var-name {
		font-weight: 600;
		color: #f8fafc;
		font-size: 14px;
	}

	.var-desc {
		font-size: 12px;
		color: #7f8ba7;
	}

	.slider-container {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px 14px;
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.05);
	}

	.slider-container input[type="range"] {
		flex: 1;
	}

	.slider-value {
		min-width: 50px;
		font-family: 'Space Mono', monospace;
		text-align: right;
		padding: 3px 10px;
		border-radius: 999px;
		background: rgba(16, 185, 129, 0.1);
		border: 1px solid rgba(16, 185, 129, 0.4);
		color: #6ee7b7;
		font-size: 0.85rem;
		font-weight: 500;
	}

	.select-input {
		padding: 10px 14px;
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.1);
		color: #f8fafc;
		font-size: 14px;
	}

	.toggle {
		position: relative;
		width: 50px;
		height: 26px;
	}

	.toggle input {
		opacity: 0;
		width: 0;
		height: 0;
	}

	.toggle-slider {
		position: absolute;
		cursor: pointer;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: rgba(255, 255, 255, 0.1);
		transition: 0.3s;
		border-radius: 26px;
	}

	.toggle-slider:before {
		position: absolute;
		content: "";
		height: 20px;
		width: 20px;
		left: 3px;
		bottom: 3px;
		background-color: white;
		transition: 0.3s;
		border-radius: 50%;
	}

	.toggle input:checked + .toggle-slider {
		background-color: #10b981;
	}

	.toggle input:checked + .toggle-slider:before {
		transform: translateX(24px);
	}

	.ml-metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 16px;
	}

	.metric-card {
		background: rgba(0, 0, 0, 0.25);
		border-radius: 10px;
		padding: 14px;
		border: 1px solid rgba(255, 255, 255, 0.05);
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.metric-card .metric-label {
		color: #9ca3af;
		font-size: 13px;
	}

	.metric-card .metric-value {
		font-size: 22px;
		color: #f8fafc;
	}

	.metric-card .metric-hint {
		font-size: 12px;
		color: #94a3b8;
	}

	.metric-card.good {
		border-color: rgba(16, 185, 129, 0.4);
	}

	.metric-card.ok {
		border-color: rgba(59, 130, 246, 0.4);
	}

	.metric-card.warning {
		border-color: rgba(250, 204, 21, 0.4);
	}

	.metric-card.danger {
		border-color: rgba(248, 113, 113, 0.4);
	}

	.action-buttons {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 16px;
		margin-top: 20px;
	}

	.retrain-card, .verify-card {
		padding: 16px;
		border-radius: 10px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}

	.retrain-card {
		background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(16, 185, 129, 0.12));
		border: 1px solid rgba(59, 130, 246, 0.3);
	}

	.verify-card {
		background: linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(59, 130, 246, 0.12));
		border: 1px solid rgba(139, 92, 246, 0.3);
	}

	.retrain-card h4, .verify-card h4 {
		margin: 0 0 4px 0;
		font-size: 15px;
		color: #f8fafc;
	}

	.retrain-card p, .verify-card p {
		margin: 0;
		font-size: 13px;
		color: #94a3b8;
	}

	.btn-retrain, .btn-verify {
		padding: 0.75rem 1.5rem;
		border: none;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
		transition: transform 0.2s ease;
		white-space: nowrap;
	}

	.btn-retrain {
		background: linear-gradient(135deg, #22d3ee, #0ea5e9);
		color: #0f172a;
	}

	.btn-verify {
		background: linear-gradient(135deg, #a78bfa, #8b5cf6);
		color: #0f172a;
	}

	.btn-retrain:disabled, .btn-verify:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-retrain:not(:disabled):hover, .btn-verify:not(:disabled):hover {
		transform: translateY(-2px);
	}

	.verify-result {
		margin-top: 16px;
		padding: 12px 16px;
		border-radius: 8px;
		font-size: 14px;
	}

	.verify-result.success {
		background: rgba(16, 185, 129, 0.1);
		border: 1px solid rgba(16, 185, 129, 0.3);
		color: #6ee7b7;
	}

	.verify-result.error {
		background: rgba(248, 113, 113, 0.1);
		border: 1px solid rgba(248, 113, 113, 0.3);
		color: #fca5a5;
	}

	.features-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 12px;
	}

	.feature-card {
		display: flex;
		gap: 12px;
		padding: 12px;
		background: rgba(255, 255, 255, 0.02);
		border-radius: 8px;
		border: 1px solid rgba(255, 255, 255, 0.05);
	}

	.feature-icon {
		font-size: 24px;
	}

	.feature-card h5 {
		margin: 0 0 4px 0;
		font-size: 14px;
		color: #e2e8f0;
	}

	.feature-card p {
		margin: 0;
		font-size: 13px;
		color: #94a3b8;
	}

	.feature-card p.good {
		color: #6ee7b7;
	}

	.feature-card p.bad {
		color: #fca5a5;
	}

	.disabled {
		opacity: 0.5;
		pointer-events: none;
	}

	/* Model Type Selector */
	.model-type-section {
		background: linear-gradient(135deg, rgba(34, 211, 238, 0.08), rgba(59, 130, 246, 0.05));
		border: 1px solid rgba(34, 211, 238, 0.2);
	}

	.model-type-selector {
		display: flex;
		gap: 12px;
		margin-bottom: 16px;
	}

	.model-type-btn {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 16px;
		background: rgba(0, 0, 0, 0.3);
		border: 2px solid rgba(255, 255, 255, 0.1);
		border-radius: 12px;
		cursor: pointer;
		transition: all 0.2s ease;
		text-align: left;
	}

	.model-type-btn:hover {
		border-color: rgba(34, 211, 238, 0.4);
		background: rgba(34, 211, 238, 0.1);
	}

	.model-type-btn.active {
		border-color: #22d3ee;
		background: rgba(34, 211, 238, 0.15);
		box-shadow: 0 0 20px rgba(34, 211, 238, 0.2);
	}

	.model-icon {
		font-size: 28px;
	}

	.model-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.model-name {
		font-weight: 600;
		color: #f8fafc;
		font-size: 15px;
	}

	.model-desc {
		font-size: 12px;
		color: #94a3b8;
	}

	.model-speed {
		padding: 4px 10px;
		background: rgba(16, 185, 129, 0.2);
		border-radius: 20px;
		font-size: 12px;
		font-weight: 700;
		color: #10b981;
	}

	.model-type-btn.active .model-speed {
		background: rgba(34, 211, 238, 0.3);
		color: #22d3ee;
	}

	.model-comparison {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 12px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 8px;
	}

	.comparison-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 13px;
	}

	.comp-label {
		color: #94a3b8;
	}

	.comp-value {
		color: #22d3ee;
		font-weight: 600;
	}

	.comp-bars {
		display: flex;
		gap: 8px;
		flex: 1;
		margin-left: 16px;
	}

	.comp-bar {
		height: 20px;
		border-radius: 4px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 10px;
		font-weight: 600;
		transition: width 0.3s ease;
	}

	.comp-bar.gb {
		background: linear-gradient(90deg, #6366f1, #8b5cf6);
		color: white;
	}

	.comp-bar.histgb {
		background: linear-gradient(90deg, #10b981, #22d3ee);
		color: #0f172a;
	}

	/* Optuna Section */
	.optuna-section {
		margin-top: 24px;
		padding: 20px;
		background: linear-gradient(135deg, rgba(234, 179, 8, 0.1), rgba(245, 158, 11, 0.05));
		border: 1px solid rgba(234, 179, 8, 0.3);
		border-radius: 12px;
	}

	.optuna-header h4 {
		margin: 0 0 8px 0;
		color: #fbbf24;
		font-size: 16px;
	}

	.optuna-header p {
		margin: 0 0 16px 0;
		color: #94a3b8;
		font-size: 13px;
	}

	.optuna-actions {
		display: flex;
		gap: 12px;
		flex-wrap: wrap;
	}

	.btn-optuna {
		padding: 0.75rem 1.5rem;
		background: linear-gradient(135deg, #f59e0b, #d97706);
		border: none;
		border-radius: 8px;
		color: #0f172a;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-optuna:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	.btn-optuna:not(:disabled):hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
	}

	.btn-apply-optuna {
		padding: 0.75rem 1.5rem;
		background: linear-gradient(135deg, #10b981, #059669);
		border: none;
		border-radius: 8px;
		color: white;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-apply-optuna:hover {
		transform: translateY(-2px);
	}

	.btn-retrain {
		padding: 0.75rem 1.5rem;
		background: linear-gradient(135deg, #3b82f6, #2563eb);
		border: none;
		border-radius: 8px;
		color: white;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-retrain:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
	}

	.optuna-message {
		margin-top: 12px;
		padding: 12px 16px;
		background: rgba(16, 185, 129, 0.15);
		border: 1px solid rgba(16, 185, 129, 0.3);
		border-radius: 8px;
		color: #10b981;
		font-size: 14px;
		white-space: pre-line;
	}

	.optuna-metrics-box {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 12px;
		margin-bottom: 16px;
		padding: 12px;
		background: rgba(59, 130, 246, 0.1);
		border-radius: 8px;
	}

	.optuna-metrics-box .metric-item {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.optuna-metrics-box .metric-label {
		font-size: 11px;
		color: #94a3b8;
		text-transform: uppercase;
	}

	.optuna-metrics-box .metric-value {
		font-size: 18px;
		font-weight: 700;
		color: #3b82f6;
	}

	.metrics-explanation {
		margin-top: 16px;
	}

	.metrics-explanation summary {
		cursor: pointer;
		color: #94a3b8;
		font-size: 13px;
		padding: 8px;
		background: rgba(255, 255, 255, 0.03);
		border-radius: 6px;
	}

	.metrics-explanation summary:hover {
		background: rgba(255, 255, 255, 0.05);
	}

	.explanation-content {
		padding: 12px;
		margin-top: 8px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 6px;
		font-size: 13px;
		color: #94a3b8;
	}

	.explanation-content p {
		margin: 8px 0;
	}

	.explanation-content ul {
		margin: 8px 0;
		padding-left: 20px;
	}

	.explanation-content li {
		margin: 4px 0;
	}

	.std-badge {
		font-size: 12px;
		font-weight: 400;
		color: #94a3b8;
		margin-left: 4px;
	}

	.optuna-progress {
		margin-top: 16px;
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.progress-bar {
		flex: 1;
		height: 8px;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 4px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, #f59e0b, #10b981);
		border-radius: 4px;
		transition: width 0.3s ease;
	}

	.progress-text {
		font-size: 13px;
		color: #94a3b8;
		white-space: nowrap;
	}

	.optuna-result {
		margin-top: 16px;
		padding: 16px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 8px;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.optuna-result.success {
		border-color: rgba(16, 185, 129, 0.3);
		background: rgba(16, 185, 129, 0.1);
	}

	.optuna-result h5 {
		margin: 0 0 12px 0;
		color: #10b981;
		font-size: 14px;
	}

	.params-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 8px;
	}

	.param-item {
		display: flex;
		justify-content: space-between;
		padding: 6px 10px;
		background: rgba(255, 255, 255, 0.05);
		border-radius: 4px;
		font-size: 12px;
	}

	.param-key {
		color: #94a3b8;
	}

	.param-value {
		color: #10b981;
		font-weight: 600;
	}

	.applied-badge {
		margin-top: 12px;
		padding: 8px 12px;
		background: rgba(16, 185, 129, 0.2);
		border-radius: 6px;
		color: #6ee7b7;
		font-weight: 600;
		text-align: center;
	}

	/* Vérification Complète */
	.verify-complete-section {
		margin-top: 24px;
		padding: 20px;
		background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.05));
		border: 1px solid rgba(99, 102, 241, 0.3);
		border-radius: 12px;
	}

	.verify-header h4 {
		margin: 0 0 8px 0;
		color: #818cf8;
		font-size: 16px;
	}

	.verify-header p {
		margin: 0 0 16px 0;
		color: #94a3b8;
		font-size: 13px;
	}

	.btn-verify-complete {
		padding: 0.75rem 1.5rem;
		background: linear-gradient(135deg, #6366f1, #8b5cf6);
		border: none;
		border-radius: 8px;
		color: white;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-verify-complete:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	.btn-verify-complete:not(:disabled):hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
	}

	.verify-complete-result {
		margin-top: 16px;
		padding: 16px;
		border-radius: 8px;
	}

	.verify-complete-result.ok {
		background: rgba(16, 185, 129, 0.1);
		border: 1px solid rgba(16, 185, 129, 0.3);
	}

	.verify-complete-result.warning {
		background: rgba(234, 179, 8, 0.1);
		border: 1px solid rgba(234, 179, 8, 0.3);
	}

	.verify-complete-result.error {
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid rgba(239, 68, 68, 0.3);
	}

	.result-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 12px;
		font-weight: 600;
	}

	.result-summary {
		font-size: 12px;
		color: #94a3b8;
		font-weight: normal;
	}

	.checks-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.check-item {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 12px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 6px;
		font-size: 13px;
	}

	.check-item.ok {
		border-left: 3px solid #10b981;
	}

	.check-item.warning {
		border-left: 3px solid #f59e0b;
	}

	.check-item.error {
		border-left: 3px solid #ef4444;
	}

	.check-icon {
		font-size: 14px;
	}

	.check-name {
		font-weight: 600;
		color: #e2e8f0;
	}

	.check-details {
		color: #94a3b8;
		margin-left: auto;
		font-size: 12px;
	}

	/* 🔢 Stats Trades ML */
	.trades-stats-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 12px;
		margin-bottom: 16px;
	}

	.stat-card {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 16px;
		background: rgba(30, 41, 59, 0.6);
		border-radius: 10px;
		border: 1px solid rgba(148, 163, 184, 0.1);
	}

	.stat-card.total {
		background: rgba(59, 130, 246, 0.1);
		border-color: rgba(59, 130, 246, 0.3);
	}

	.stat-card.excluded {
		background: rgba(239, 68, 68, 0.1);
		border-color: rgba(239, 68, 68, 0.2);
	}

	.stat-card.final {
		background: rgba(16, 185, 129, 0.1);
		border-color: rgba(16, 185, 129, 0.3);
	}

	.stat-card.final.warning {
		background: rgba(234, 179, 8, 0.1);
		border-color: rgba(234, 179, 8, 0.3);
	}

	.stat-icon {
		font-size: 24px;
	}

	.stat-content {
		display: flex;
		flex-direction: column;
	}

	.stat-value {
		font-size: 20px;
		font-weight: 700;
		color: #f1f5f9;
	}

	.stat-label {
		font-size: 12px;
		color: #94a3b8;
	}

	.config-info {
		padding: 12px 16px;
		background: rgba(30, 41, 59, 0.4);
		border-radius: 8px;
		font-size: 13px;
		color: #94a3b8;
		margin-bottom: 12px;
	}

	.config-info strong {
		color: #e2e8f0;
	}

	.refresh-btn {
		padding: 8px 16px;
		background: rgba(59, 130, 246, 0.2);
		border: 1px solid rgba(59, 130, 246, 0.4);
		border-radius: 6px;
		color: #60a5fa;
		font-size: 13px;
		cursor: pointer;
		transition: all 0.2s;
	}

	.refresh-btn:hover:not(:disabled) {
		background: rgba(59, 130, 246, 0.3);
	}

	.refresh-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.error-message {
		padding: 12px;
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid rgba(239, 68, 68, 0.3);
		border-radius: 8px;
		color: #fca5a5;
	}

	@media (max-width: 768px) {
		.trades-stats-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	/* ========== AUTO-OPTIMIZE SECTION ========== */
	.auto-optimize-section {
		background: linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(16, 185, 129, 0.08));
		border: 1px solid rgba(139, 92, 246, 0.3);
	}

	.auto-optimize-features {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin: 16px 0;
	}

	.feature-tag {
		padding: 6px 12px;
		background: rgba(16, 185, 129, 0.15);
		border: 1px solid rgba(16, 185, 129, 0.3);
		border-radius: 20px;
		font-size: 12px;
		color: #6ee7b7;
	}

	.btn-auto-optimize {
		width: 100%;
		padding: 16px 24px;
		background: linear-gradient(135deg, #8b5cf6, #6366f1);
		border: none;
		border-radius: 10px;
		color: white;
		font-size: 16px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.3s;
	}

	.btn-auto-optimize:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 8px 25px rgba(139, 92, 246, 0.4);
	}

	.btn-auto-optimize:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	/* ========== POPUP FLOATING (Déplaçable et Non-Bloquant) ========== */
	.popup-floating {
		position: fixed;
		z-index: 1000;
		background: linear-gradient(135deg, #0f172a, #1e293b);
		border: 1px solid rgba(139, 92, 246, 0.4);
		border-radius: 16px;
		width: 600px;
		max-width: 90vw;
		max-height: 80vh;
		overflow-y: auto;
		box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5), 0 0 30px rgba(139, 92, 246, 0.2);
		resize: both;
	}

	.popup-floating.auto-optimize-popup {
		min-width: 400px;
	}

	.popup-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px 20px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(139, 92, 246, 0.15);
		border-radius: 16px 16px 0 0;
	}

	.popup-header.draggable {
		cursor: move;
		user-select: none;
	}

	.popup-header h2 {
		margin: 0;
		font-size: 18px;
		color: #f8fafc;
	}

	.popup-header-actions {
		display: flex;
		gap: 8px;
	}

	.popup-minimize, .popup-close {
		background: none;
		border: none;
		font-size: 20px;
		color: #94a3b8;
		cursor: pointer;
		padding: 4px 8px;
		line-height: 1;
		border-radius: 4px;
		transition: all 0.2s;
	}

	.popup-minimize:hover, .popup-close:hover {
		color: #f8fafc;
		background: rgba(255, 255, 255, 0.1);
	}

	.popup-close:hover {
		background: rgba(239, 68, 68, 0.3);
		color: #fca5a5;
	}

	.popup-external {
		background: none;
		border: none;
		font-size: 16px;
		color: #94a3b8;
		cursor: pointer;
		padding: 4px 8px;
		border-radius: 4px;
		transition: all 0.2s;
	}

	.popup-external:hover {
		color: #60a5fa;
		background: rgba(96, 165, 250, 0.2);
	}

	.popup-title-row {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.connection-indicator {
		font-size: 12px;
		opacity: 0.8;
	}

	.connection-indicator.disconnected {
		animation: pulse 1s infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.4; }
	}

	.popup-content {
		padding: 24px;
	}

	.optimize-progress-section {
		text-align: center;
		padding: 30px 20px;
	}

	.progress-steps {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-top: 20px;
		text-align: left;
		max-width: 300px;
		margin-left: auto;
		margin-right: auto;
	}

	.progress-steps .step {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 6px 10px;
		border-radius: 6px;
		background: rgba(30, 41, 59, 0.4);
		transition: all 0.3s ease;
		opacity: 0.5;
	}

	.progress-steps .step.active {
		background: rgba(59, 130, 246, 0.2);
		border: 1px solid rgba(59, 130, 246, 0.4);
		opacity: 1;
	}

	.progress-steps .step.done {
		opacity: 0.8;
	}

	.progress-steps .step-icon {
		font-size: 14px;
		width: 20px;
		text-align: center;
	}

	.progress-steps .step-text {
		font-size: 12px;
		color: #94a3b8;
	}

	.progress-steps .step.active .step-text {
		color: #60a5fa;
		font-weight: 500;
	}

	.progress-steps .step.done .step-text {
		color: #4ade80;
	}

	.progress-bar-large {
		height: 20px;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 10px;
		overflow: hidden;
		margin-bottom: 16px;
	}

	.progress-bar-large .progress-fill {
		height: 100%;
		background: linear-gradient(90deg, #8b5cf6, #6366f1, #10b981);
		border-radius: 10px;
		transition: width 0.3s;
	}

	.progress-info {
		display: flex;
		justify-content: space-between;
		margin-bottom: 20px;
	}

	.progress-percent {
		font-size: 24px;
		font-weight: 700;
		color: #8b5cf6;
	}

	.progress-status {
		color: #94a3b8;
	}

	.loading-spinner {
		width: 40px;
		height: 40px;
		border: 3px solid rgba(139, 92, 246, 0.2);
		border-top-color: #8b5cf6;
		border-radius: 50%;
		animation: spin 1s linear infinite;
		margin: 20px auto;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.results-section h3 {
		margin: 0 0 20px 0;
		color: #f8fafc;
		font-size: 18px;
	}

	.comparison-table, .threshold-table {
		margin-bottom: 24px;
	}

	.comparison-table h4, .threshold-table h4, .new-params h4, .selected-features h4 {
		margin: 0 0 12px 0;
		font-size: 15px;
		color: #e2e8f0;
	}

	.comparison-table table, .threshold-table table {
		width: 100%;
		border-collapse: collapse;
		font-size: 13px;
	}

	.comparison-table th, .threshold-table th {
		padding: 10px;
		background: rgba(0, 0, 0, 0.3);
		color: #94a3b8;
		text-align: left;
		font-weight: 600;
	}

	.comparison-table td, .threshold-table td {
		padding: 10px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.05);
		color: #e2e8f0;
	}

	.comparison-table tr.improved {
		background: rgba(16, 185, 129, 0.1);
	}

	.comparison-table td.positive {
		color: #10b981;
		font-weight: 600;
	}

	.threshold-table tr.optimal {
		background: rgba(139, 92, 246, 0.2);
		border-left: 3px solid #8b5cf6;
	}

	.optimal-threshold-info {
		margin-top: 12px;
		padding: 12px;
		background: rgba(139, 92, 246, 0.15);
		border: 1px solid rgba(139, 92, 246, 0.3);
		border-radius: 8px;
		color: #c4b5fd;
		text-align: center;
	}

	.metrics-legend {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-bottom: 12px;
		padding: 10px;
		background: rgba(0, 0, 0, 0.2);
		border-radius: 8px;
	}

	.legend-item {
		display: flex;
		flex-direction: column;
		padding: 6px 10px;
		background: rgba(30, 41, 59, 0.6);
		border-radius: 6px;
		cursor: help;
		flex: 1;
		min-width: 100px;
	}

	.legend-item:hover {
		background: rgba(59, 130, 246, 0.2);
	}

	.legend-label {
		font-weight: 600;
		font-size: 11px;
		color: #60a5fa;
		text-transform: uppercase;
	}

	.legend-desc {
		font-size: 10px;
		color: #94a3b8;
		margin-top: 2px;
	}

	.metrics-legend.compact {
		margin-bottom: 8px;
		padding: 8px;
	}

	.metrics-legend.compact .legend-item {
		padding: 4px 8px;
		min-width: 120px;
	}

	.metrics-legend.compact .legend-desc {
		font-size: 9px;
	}

	.new-params, .selected-features {
		margin-bottom: 24px;
	}

	.selected-features .features-list {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.feature-chip {
		padding: 6px 12px;
		background: rgba(59, 130, 246, 0.15);
		border: 1px solid rgba(59, 130, 246, 0.3);
		border-radius: 20px;
		font-size: 12px;
		color: #93c5fd;
	}

	.feature-chip.more {
		background: rgba(148, 163, 184, 0.1);
		border-color: rgba(148, 163, 184, 0.3);
		color: #94a3b8;
	}

	.popup-actions {
		display: flex;
		gap: 12px;
		margin-top: 24px;
		padding-top: 20px;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
	}

	.btn-apply-results {
		flex: 1;
		padding: 14px 24px;
		background: linear-gradient(135deg, #10b981, #059669);
		border: none;
		border-radius: 8px;
		color: white;
		font-size: 15px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
	}

	.btn-apply-results:hover {
		transform: translateY(-1px);
		box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
	}

	.btn-cancel {
		padding: 14px 24px;
		background: rgba(255, 255, 255, 0.1);
		border: 1px solid rgba(255, 255, 255, 0.2);
		border-radius: 8px;
		color: #94a3b8;
		font-size: 15px;
		cursor: pointer;
		transition: all 0.2s;
	}

	.btn-cancel:hover {
		background: rgba(255, 255, 255, 0.15);
		color: #f8fafc;
	}

	.error-section {
		text-align: center;
		padding: 40px;
		color: #94a3b8;
	}
</style>
