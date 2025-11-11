<script>
	import { onMount } from 'svelte';
	import {
		notificationsEnabled,
		notificationPermission,
		requestNotificationPermission,
		toggleNotifications,
		sendNotification
	} from '$lib/utils/notifications';
	import { sendCommandViaWS } from '$lib/utils/websocket';

	let telegramStatus = 'Vérification...';
	let telegramEnabled = false;
	let telegramNotifySettings = {
		TELEGRAM_NOTIFY_POSITION_OPENED: false,
		TELEGRAM_NOTIFY_POSITION_CLOSED: true,
		TELEGRAM_NOTIFY_TP_ESCALIER: true,
		TELEGRAM_NOTIFY_EARLY_INVALIDATION: false,
		TELEGRAM_NOTIFY_ERROR: true,
		TELEGRAM_NOTIFY_RECONNECTION: true,
		TELEGRAM_NOTIFY_DAILY_SUMMARY: true,
		TELEGRAM_NOTIFY_RECOVERY_MODE: true,
		TELEGRAM_NOTIFY_SETUP_REJECTED: false
	};
	let testLoading = false;
	let saveLoading = false;

	async function handleToggle() {
		const enabled = await toggleNotifications();
		if (enabled) {
			// Test notification
			sendNotification('✅ Notifications activées!', {
				body: 'Vous recevrez des alertes pour les positions et setups'
			});
		}
	}

	async function handleRequestPermission() {
		const granted = await requestNotificationPermission();
		if (granted) {
			sendNotification('🎉 Permission accordée!', {
				body: 'Vous recevrez désormais des notifications'
			});
		}
	}

	// 🔥 NOUVEAU: Charger la configuration Telegram depuis le backend
	async function loadTelegramConfig() {
		try {
			const { getWebSocket, sendRequestViaWS } = await import('$lib/utils/websocket');
			const ws = getWebSocket();
			if (ws && ws.connected) {
				const response = await sendRequestViaWS('state', {});
				const stateData = response?.data || response;
				if (stateData && stateData.config) {
					telegramEnabled = stateData.config.telegram_enabled || false;
					telegramStatus = telegramEnabled ? '✅ Activé' : '❌ Désactivé (variables d\'environnement manquantes)';
					
					// Charger les types de notifications
					if (stateData.config.telegram_notify_position_opened !== undefined) {
						telegramNotifySettings.TELEGRAM_NOTIFY_POSITION_OPENED = stateData.config.telegram_notify_position_opened;
					}
					if (stateData.config.telegram_notify_position_closed !== undefined) {
						telegramNotifySettings.TELEGRAM_NOTIFY_POSITION_CLOSED = stateData.config.telegram_notify_position_closed;
					}
					if (stateData.config.telegram_notify_tp_escalier !== undefined) {
						telegramNotifySettings.TELEGRAM_NOTIFY_TP_ESCALIER = stateData.config.telegram_notify_tp_escalier;
					}
					if (stateData.config.telegram_notify_early_invalidation !== undefined) {
						telegramNotifySettings.TELEGRAM_NOTIFY_EARLY_INVALIDATION = stateData.config.telegram_notify_early_invalidation;
					}
					if (stateData.config.telegram_notify_error !== undefined) {
						telegramNotifySettings.TELEGRAM_NOTIFY_ERROR = stateData.config.telegram_notify_error;
					}
					if (stateData.config.telegram_notify_reconnection !== undefined) {
						telegramNotifySettings.TELEGRAM_NOTIFY_RECONNECTION = stateData.config.telegram_notify_reconnection;
					}
					if (stateData.config.telegram_notify_daily_summary !== undefined) {
						telegramNotifySettings.TELEGRAM_NOTIFY_DAILY_SUMMARY = stateData.config.telegram_notify_daily_summary;
					}
					if (stateData.config.telegram_notify_recovery_mode !== undefined) {
						telegramNotifySettings.TELEGRAM_NOTIFY_RECOVERY_MODE = stateData.config.telegram_notify_recovery_mode;
					}
					if (stateData.config.telegram_notify_setup_rejected !== undefined) {
						telegramNotifySettings.TELEGRAM_NOTIFY_SETUP_REJECTED = stateData.config.telegram_notify_setup_rejected;
					}
				} else {
					telegramStatus = '❌ Désactivé (variables d\'environnement manquantes)';
				}
			} else {
				telegramStatus = '❌ WebSocket non connecté';
			}
		} catch (err) {
			console.error('Erreur vérification Telegram:', err);
			telegramStatus = '❌ Erreur de connexion';
		}
	}

	// 🔥 NOUVEAU: Sauvegarder la configuration Telegram
	async function saveTelegramConfig() {
		saveLoading = true;
		try {
			const result = await sendCommandViaWS('update_telegram_config', telegramNotifySettings);
			if (result && result.success) {
				telegramNotifySettings = { ...telegramNotifySettings, ...result.updated };
				alert('✅ Configuration Telegram sauvegardée avec succès');
			} else {
				alert('❌ Erreur lors de la sauvegarde');
			}
		} catch (err) {
			console.error('Erreur sauvegarde Telegram:', err);
			alert(`❌ Erreur: ${err.message || 'Impossible de sauvegarder'}`);
		} finally {
			saveLoading = false;
		}
	}

	// 🔥 NOUVEAU: Tester la configuration Telegram
	async function testTelegram() {
		testLoading = true;
		try {
			const result = await sendCommandViaWS('test_telegram', {});
			if (result && result.success) {
				alert('✅ Message de test envoyé avec succès ! Vérifiez votre Telegram.');
			} else {
				alert(`❌ Erreur: ${result?.error || 'Impossible d\'envoyer le message de test'}`);
			}
		} catch (err) {
			console.error('Erreur test Telegram:', err);
			alert(`❌ Erreur: ${err.message || 'Impossible d\'envoyer le message de test'}`);
		} finally {
			testLoading = false;
		}
	}

	onMount(async () => {
		await loadTelegramConfig();
		// Écouter les mises à jour de config
		const { getWebSocket } = await import('$lib/utils/websocket');
		const ws = getWebSocket();
		if (ws) {
			ws.on('config_updated', (data) => {
				if (data.updated) {
					// Mettre à jour les paramètres Telegram si présents
					Object.keys(telegramNotifySettings).forEach(key => {
						if (data.updated[key] !== undefined) {
							telegramNotifySettings[key] = data.updated[key];
						}
					});
				}
			});
		}
	});
</script>

<div class="notification-settings" data-debug-name="notificationSettings">
	<div class="settings-header" data-debug-name="settingsHeader">
		<div class="title" data-debug-name="title">
			<span class="icon" data-debug-name="icon">🔔</span>
			<h3 data-debug-name="notificationsTitle">Notifications</h3>
		</div>

		{#if $notificationPermission === 'granted'}
			<button class="toggle-btn" class:active={$notificationsEnabled} on:click={handleToggle} data-debug-name="toggleBtn">
				<span class="toggle-icon" data-debug-name="toggleIcon">{$notificationsEnabled ? '✅' : '⭕'}</span>
				<span data-debug-name="notificationsEnabled">{$notificationsEnabled ? 'Activées' : 'Désactivées'}</span>
			</button>
		{/if}
	</div>

	{#if $notificationPermission === 'default'}
		<div class="permission-request" data-debug-name="permissionRequest">
			<p class="info" data-debug-name="permissionRequest.info">
				Les notifications vous permettent de recevoir des alertes en temps réel pour:
			</p>
			<ul class="features-list" data-debug-name="permissionRequest.features">
				<li>🟢 Positions ouvertes</li>
				<li>🔴 Positions fermées (TP/SL/TS)</li>
				<li>🔍 Setups détectés</li>
				<li>🏆 Milestones (winrate)</li>
				<li>❌ Erreurs critiques</li>
			</ul>
			<button class="request-btn" on:click={handleRequestPermission} data-debug-name="requestBtn">
				<span class="btn-icon" data-debug-name="requestBtn.icon">🔔</span>
				<span data-debug-name="requestBtn.label">Activer les notifications</span>
			</button>
		</div>
	{:else if $notificationPermission === 'denied'}
		<div class="permission-denied" data-debug-name="permissionDenied">
			<p class="warning" data-debug-name="permissionDenied.warning">❌ Permission refusée</p>
			<p class="help" data-debug-name="permissionDenied.help">
				Pour activer les notifications, vous devez autoriser le site dans les paramètres de votre
				navigateur:
			</p>
			<ol class="steps" data-debug-name="permissionDenied.steps">
				<li>Cliquez sur l'icône 🔒 ou ⓘ dans la barre d'adresse</li>
				<li>Cherchez "Notifications"</li>
				<li>Sélectionnez "Autoriser"</li>
				<li>Rechargez la page</li>
			</ol>
		</div>
	{:else}
		<div class="notification-types" data-debug-name="notificationTypes">
			<p class="description" data-debug-name="notificationTypes.description">
				Les notifications sont automatiquement envoyées pour les événements importants :
			</p>

			<!-- 🔥 FIX: Séparer les différents systèmes de notifications -->
			<div class="notification-systems" data-debug-name="notificationSystems">
				<!-- Système 1: Notifications Navigateur (Browser) -->
				<div class="system-section" data-debug-name="systemSection.browser">
					<h4 class="system-title" data-debug-name="systemTitle.browser">🌐 Notifications Navigateur</h4>
					<div class="types-grid" data-debug-name="typesGrid.browser">
						<div class="type-card active" data-debug-name="typeCard.positionOpen">
							<div class="type-icon" data-debug-name="typeIcon.positionOpen">🟢</div>
							<div class="type-name" data-debug-name="typeName.positionOpen">Position Ouverte</div>
							<div class="type-desc" data-debug-name="typeDesc.positionOpen">Alerte à l'ouverture d'une position</div>
						</div>

						<div class="type-card active" data-debug-name="typeCard.positionClose">
							<div class="type-icon" data-debug-name="typeIcon.positionClose">🔴</div>
							<div class="type-name" data-debug-name="typeName.positionClose">Position Fermée</div>
							<div class="type-desc" data-debug-name="typeDesc.positionClose">TP, SL ou Trailing Stop</div>
						</div>

						<div class="type-card active" data-debug-name="typeCard.setupDetected">
							<div class="type-icon" data-debug-name="typeIcon.setupDetected">🔍</div>
							<div class="type-name" data-debug-name="typeName.setupDetected">Setup Détecté</div>
							<div class="type-desc" data-debug-name="typeDesc.setupDetected">Conditions de trading remplies</div>
						</div>

						<div class="type-card active" data-debug-name="typeCard.errors">
							<div class="type-icon" data-debug-name="typeIcon.errors">❌</div>
							<div class="type-name" data-debug-name="typeName.errors">Erreurs</div>
							<div class="type-desc" data-debug-name="typeDesc.errors">Erreurs critiques du système</div>
						</div>
					</div>
				</div>

				<!-- Système 2: Telegram -->
				<div class="system-section" data-debug-name="systemSection.telegram">
					<div class="telegram-header" data-debug-name="telegramHeader">
						<h4 class="system-title" data-debug-name="systemTitle.telegram">📱 Notifications Telegram</h4>
						<div class="telegram-toggle" data-debug-name="telegramToggle">
							<label class="toggle-switch" data-debug-name="telegramToggle.switch">
								<input
									type="checkbox"
									bind:checked={telegramEnabled}
									disabled
									data-debug-name="telegramEnabled"
								/>
								<span class="toggle-slider" data-debug-name="telegramEnabled.slider"></span>
							</label>
							<span class="toggle-label" data-debug-name="telegramEnabled.label">
								{telegramEnabled ? 'Activé' : 'Désactivé'}
							</span>
						</div>
					</div>
					
					<div class="telegram-enable-info" data-debug-name="telegramEnableInfo">
						<p class="info-text" data-debug-name="infoText">
							<strong>ℹ️ Note :</strong> Pour activer/désactiver Telegram, modifiez le fichier <code>.env</code> à la racine du projet et redémarrez le backend.
						</p>
					</div>
					
					<div class="telegram-status" data-debug-name="telegramStatus">
						<span class="status-label" data-debug-name="statusLabel">Statut:</span>
						<span class="status-value" data-debug-name="telegramStatus.value">{telegramStatus}</span>
					</div>

					{#if telegramEnabled}
						<div class="telegram-actions" data-debug-name="telegramActions">
							<button
								class="test-btn"
								on:click={testTelegram}
								disabled={testLoading}
								data-debug-name="testTelegramBtn"
							>
								{testLoading ? '⏳ Envoi...' : '🧪 Tester Telegram'}
							</button>
						</div>

						<div class="telegram-notify-types" data-debug-name="telegramNotifyTypes">
							<h5 class="notify-types-title" data-debug-name="notifyTypesTitle">Types de notifications :</h5>
							<div class="notify-types-list" data-debug-name="notifyTypesList">
								<label class="notify-type-item" data-debug-name="notifyType.positionOpened">
									<input
										type="checkbox"
										bind:checked={telegramNotifySettings.TELEGRAM_NOTIFY_POSITION_OPENED}
										on:change={saveTelegramConfig}
										data-debug-name="telegramNotifySettings.TELEGRAM_NOTIFY_POSITION_OPENED"
									/>
									<span class="notify-type-label" data-debug-name="notifyType.positionOpened.label">
										🟢 Position Ouverte
									</span>
								</label>

								<label class="notify-type-item" data-debug-name="notifyType.positionClosed">
									<input
										type="checkbox"
										bind:checked={telegramNotifySettings.TELEGRAM_NOTIFY_POSITION_CLOSED}
										on:change={saveTelegramConfig}
										data-debug-name="telegramNotifySettings.TELEGRAM_NOTIFY_POSITION_CLOSED"
									/>
									<span class="notify-type-label" data-debug-name="notifyType.positionClosed.label">
										🔴 Position Fermée
									</span>
								</label>

								<label class="notify-type-item" data-debug-name="notifyType.tpEscalier">
									<input
										type="checkbox"
										bind:checked={telegramNotifySettings.TELEGRAM_NOTIFY_TP_ESCALIER}
										on:change={saveTelegramConfig}
										data-debug-name="telegramNotifySettings.TELEGRAM_NOTIFY_TP_ESCALIER"
									/>
									<span class="notify-type-label" data-debug-name="notifyType.tpEscalier.label">
										💰 TP Escalier
									</span>
								</label>

								<label class="notify-type-item" data-debug-name="notifyType.earlyInvalidation">
									<input
										type="checkbox"
										bind:checked={telegramNotifySettings.TELEGRAM_NOTIFY_EARLY_INVALIDATION}
										on:change={saveTelegramConfig}
										data-debug-name="telegramNotifySettings.TELEGRAM_NOTIFY_EARLY_INVALIDATION"
									/>
									<span class="notify-type-label" data-debug-name="notifyType.earlyInvalidation.label">
										⏱️ Invalidation Précoce
									</span>
								</label>

								<label class="notify-type-item" data-debug-name="notifyType.error">
									<input
										type="checkbox"
										bind:checked={telegramNotifySettings.TELEGRAM_NOTIFY_ERROR}
										on:change={saveTelegramConfig}
										data-debug-name="telegramNotifySettings.TELEGRAM_NOTIFY_ERROR"
									/>
									<span class="notify-type-label" data-debug-name="notifyType.error.label">
										❌ Erreurs
									</span>
								</label>

								<label class="notify-type-item" data-debug-name="notifyType.reconnection">
									<input
										type="checkbox"
										bind:checked={telegramNotifySettings.TELEGRAM_NOTIFY_RECONNECTION}
										on:change={saveTelegramConfig}
										data-debug-name="telegramNotifySettings.TELEGRAM_NOTIFY_RECONNECTION"
									/>
									<span class="notify-type-label" data-debug-name="notifyType.reconnection.label">
										🔄 Reconnexion
									</span>
								</label>

								<label class="notify-type-item" data-debug-name="notifyType.dailySummary">
									<input
										type="checkbox"
										bind:checked={telegramNotifySettings.TELEGRAM_NOTIFY_DAILY_SUMMARY}
										on:change={saveTelegramConfig}
										data-debug-name="telegramNotifySettings.TELEGRAM_NOTIFY_DAILY_SUMMARY"
									/>
									<span class="notify-type-label" data-debug-name="notifyType.dailySummary.label">
										📊 Résumé Quotidien
									</span>
								</label>

								<label class="notify-type-item" data-debug-name="notifyType.recoveryMode">
									<input
										type="checkbox"
										bind:checked={telegramNotifySettings.TELEGRAM_NOTIFY_RECOVERY_MODE}
										on:change={saveTelegramConfig}
										data-debug-name="telegramNotifySettings.TELEGRAM_NOTIFY_RECOVERY_MODE"
									/>
									<span class="notify-type-label" data-debug-name="notifyType.recoveryMode.label">
										🔄 Mode Recovery
									</span>
								</label>

								<label class="notify-type-item" data-debug-name="notifyType.setupRejected">
									<input
										type="checkbox"
										bind:checked={telegramNotifySettings.TELEGRAM_NOTIFY_SETUP_REJECTED}
										on:change={saveTelegramConfig}
										data-debug-name="telegramNotifySettings.TELEGRAM_NOTIFY_SETUP_REJECTED"
									/>
									<span class="notify-type-label" data-debug-name="notifyType.setupRejected.label">
										🚫 Setup Rejeté
									</span>
								</label>
							</div>
						</div>
					{:else}
						<div class="telegram-info" data-debug-name="telegramInfo">
							<p data-debug-name="telegramInfo.text">
								Les notifications Telegram sont configurées via le fichier <code>.env</code> à la racine du projet :
							</p>
							<div class="telegram-instructions" data-debug-name="telegramInstructions">
								<ol class="telegram-steps" data-debug-name="telegramSteps">
									<li>Créez un fichier <code>.env</code> à la racine du projet</li>
									<li>Ajoutez vos identifiants Telegram :
										<pre class="env-example" data-debug-name="envExample">TELEGRAM_BOT_TOKEN=votre_token_ici
TELEGRAM_CHAT_ID=votre_chat_id_ici</pre>
									</li>
									<li>Redémarrez le backend pour appliquer les changements</li>
								</ol>
								<div class="telegram-security" data-debug-name="telegramSecurity">
									<strong>🔒 Sécurité :</strong> Le fichier <code>.env</code> est dans <code>.gitignore</code> et ne sera jamais commité sur GitHub.
								</div>
							</div>
						</div>
					{/if}
				</div>
			</div>

			<div class="notification-note" data-debug-name="notificationNote">
				<div class="note-icon" data-debug-name="noteIcon">ℹ️</div>
				<div class="note-text" data-debug-name="noteText">
					<strong>Note:</strong> Les notifications sont actives pour tous les événements importants.
					Vous recevrez également des alertes lorsque votre winrate atteint des seuils significatifs (50%, 60%, 70%).
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.notification-settings {
		background: #1e2749;
		border-radius: 12px;
		padding: 20px;
		border: 2px solid #2a3a6b;
	}

	.settings-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
	}

	.title {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.icon {
		font-size: 24px;
	}

	.title h3 {
		font-size: 20px;
		color: #00ff88;
		font-weight: bold;
	}

	.toggle-btn {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 20px;
		background: #0a0e27;
		border: 2px solid #2a3a6b;
		border-radius: 8px;
		color: #fff;
		font-size: 14px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
	}

	.toggle-btn.active {
		background: rgba(0, 255, 136, 0.1);
		border-color: #00ff88;
		color: #00ff88;
	}

	.toggle-btn:hover {
		transform: translateY(-2px);
	}

	.toggle-icon {
		font-size: 18px;
	}

	.permission-request {
		text-align: center;
		padding: 20px;
	}

	.info {
		font-size: 14px;
		color: #888;
		margin-bottom: 15px;
	}

	.features-list {
		list-style: none;
		padding: 0;
		margin: 20px 0;
	}

	.features-list li {
		font-size: 14px;
		padding: 8px;
		margin: 5px 0;
		background: rgba(0, 170, 255, 0.1);
		border-radius: 6px;
		border: 1px solid #00aaff;
	}

	.request-btn {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		padding: 15px 30px;
		background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
		color: #0a0e27;
		border: none;
		border-radius: 10px;
		font-size: 16px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
		box-shadow: 0 4px 15px rgba(0, 255, 136, 0.3);
	}

	.request-btn:hover {
		transform: translateY(-2px);
		box-shadow: 0 6px 20px rgba(0, 255, 136, 0.4);
	}

	.btn-icon {
		font-size: 20px;
	}

	.permission-denied {
		padding: 20px;
		background: rgba(255, 68, 68, 0.1);
		border-radius: 8px;
		border: 2px solid #ff4444;
	}

	.warning {
		font-size: 16px;
		font-weight: bold;
		color: #ff4444;
		margin-bottom: 15px;
	}

	.help {
		font-size: 14px;
		color: #888;
		margin-bottom: 15px;
	}

	.steps {
		text-align: left;
		margin: 15px 0;
		padding-left: 20px;
	}

	.steps li {
		font-size: 13px;
		color: #aaa;
		margin: 8px 0;
	}

	.notification-types {
		padding: 10px 0;
	}

	.description {
		font-size: 14px;
		color: #888;
		margin-bottom: 20px;
		text-align: center;
	}

	.types-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 15px;
	}

	.type-card {
		background: #0a0e27;
		padding: 20px;
		border-radius: 10px;
		text-align: center;
		border: 2px solid #2a3a6b;
		transition: all 0.3s;
		opacity: 0.6;
	}

	.type-card.active {
		opacity: 1;
		border-color: rgba(0, 255, 136, 0.5);
	}

	.type-card:hover {
		border-color: #00ff88;
		transform: translateY(-2px);
	}

	.notification-note {
		margin-top: 20px;
		padding: 15px;
		background: rgba(0, 170, 255, 0.1);
		border-radius: 8px;
		border: 1px solid rgba(0, 170, 255, 0.3);
		display: flex;
		gap: 12px;
		align-items: flex-start;
	}

	.note-icon {
		font-size: 20px;
		flex-shrink: 0;
	}

	.note-text {
		font-size: 13px;
		color: #aaa;
		line-height: 1.6;
	}

	.note-text strong {
		color: #00aaff;
	}

	.type-icon {
		font-size: 32px;
		margin-bottom: 10px;
	}

	.type-name {
		font-size: 14px;
		font-weight: bold;
		color: #00ff88;
		margin-bottom: 5px;
	}

	.type-desc {
		font-size: 12px;
		color: #888;
	}

	/* 🔥 FIX: Styles pour les systèmes de notifications séparés */
	.notification-systems {
		display: flex;
		flex-direction: column;
		gap: 25px;
		margin-bottom: 20px;
	}

	.system-section {
		background: #0a0e27;
		padding: 20px;
		border-radius: 10px;
		border: 2px solid #2a3a6b;
	}

	.system-title {
		font-size: 16px;
		color: #00ff88;
		font-weight: bold;
		margin-bottom: 15px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.telegram-config {
		padding: 15px;
		background: rgba(0, 170, 255, 0.05);
		border-radius: 8px;
		border: 1px solid rgba(0, 170, 255, 0.3);
	}

	.telegram-info {
		font-size: 13px;
		color: #aaa;
		margin-bottom: 15px;
		line-height: 1.6;
	}

	.telegram-vars {
		list-style: none;
		padding: 0;
		margin: 15px 0;
	}

	.telegram-instructions {
		margin: 15px 0;
	}

	.telegram-steps {
		list-style: decimal;
		padding-left: 25px;
		margin: 15px 0;
	}

	.telegram-steps li {
		font-size: 13px;
		color: #aaa;
		margin: 10px 0;
		line-height: 1.6;
	}

	.telegram-steps code {
		color: #00aaff;
		font-weight: bold;
		font-family: 'Courier New', monospace;
		background: rgba(0, 170, 255, 0.1);
		padding: 2px 6px;
		border-radius: 4px;
	}

	.env-example {
		background: #0a0e27;
		border: 1px solid #2a3a6b;
		border-radius: 6px;
		padding: 12px;
		margin: 10px 0;
		font-family: 'Courier New', monospace;
		font-size: 12px;
		color: #00ff88;
		overflow-x: auto;
		white-space: pre;
	}

	.telegram-security {
		margin-top: 15px;
		padding: 12px;
		background: rgba(0, 255, 136, 0.1);
		border-radius: 6px;
		border: 1px solid rgba(0, 255, 136, 0.3);
		font-size: 12px;
		color: #00ff88;
		line-height: 1.6;
	}

	.telegram-security strong {
		color: #00ff88;
	}

	.telegram-enable-info {
		margin-bottom: 15px;
		padding: 12px;
		background: rgba(0, 170, 255, 0.1);
		border-radius: 6px;
		border: 1px solid rgba(0, 170, 255, 0.3);
	}

	.telegram-enable-info .info-text {
		font-size: 12px;
		color: #aaa;
		line-height: 1.6;
		margin: 0;
	}

	.telegram-enable-info .info-text strong {
		color: #00aaff;
	}

	.telegram-enable-info .info-text code {
		color: #00ff88;
		font-weight: bold;
		font-family: 'Courier New', monospace;
		background: rgba(0, 255, 136, 0.1);
		padding: 2px 6px;
		border-radius: 4px;
	}

	.telegram-status {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-top: 15px;
		padding: 10px;
		background: rgba(0, 255, 136, 0.1);
		border-radius: 6px;
		border: 1px solid rgba(0, 255, 136, 0.3);
	}

	.status-label {
		font-size: 13px;
		color: #888;
		font-weight: bold;
	}

	.status-value {
		font-size: 13px;
		color: #00ff88;
		font-weight: bold;
	}

	/* Mobile */
	@media (max-width: 768px) {
		.types-grid {
			grid-template-columns: 1fr;
		}

		.settings-header {
			flex-direction: column;
			gap: 15px;
		}
	}
</style>
