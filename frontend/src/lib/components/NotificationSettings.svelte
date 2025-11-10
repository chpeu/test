<script>
	import { onMount } from 'svelte';
	import {
		notificationsEnabled,
		notificationPermission,
		requestNotificationPermission,
		toggleNotifications,
		sendNotification
	} from '$lib/utils/notifications';

	let telegramStatus = 'Vérification...';

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

	// 🔥 MIGRATION: Vérifier le statut Telegram via WebSocket (remplace fetch('/api/config'))
	async function checkTelegramStatus() {
		try {
			// 🔥 MIGRATION WebSocket: Utiliser command au lieu de fetch
			const { getWebSocket } = await import('$lib/utils/websocket');
			const ws = getWebSocket();

			if (!ws || !ws.connected) {
				// Fallback REST si WebSocket non connecté
				const res = await fetch('/api/config');
				if (res.ok) {
					const data = await res.json();
					telegramStatus = data.telegram_enabled ? '✅ Activé' : '❌ Désactivé (variables d\'environnement manquantes)';
				} else {
					telegramStatus = '❌ Erreur de vérification';
				}
				return;
			}

			const data = await ws.sendCommand('get_config');
			// Vérifier si Telegram est configuré (via backend)
			telegramStatus = data.telegram_enabled ? '✅ Activé' : '❌ Désactivé (variables d\'environnement manquantes)';
		} catch (err) {
			console.error('Erreur vérification Telegram:', err);
			telegramStatus = '❌ Erreur de connexion';
		}
	}

	onMount(() => {
		checkTelegramStatus();
	});
</script>

<div class="notification-settings">
	<div class="settings-header">
		<div class="title">
			<span class="icon">🔔</span>
			<h3>Notifications</h3>
		</div>

		{#if $notificationPermission === 'granted'}
			<button class="toggle-btn" class:active={$notificationsEnabled} on:click={handleToggle}>
				<span class="toggle-icon">{$notificationsEnabled ? '✅' : '⭕'}</span>
				{$notificationsEnabled ? 'Activées' : 'Désactivées'}
			</button>
		{/if}
	</div>

	{#if $notificationPermission === 'default'}
		<div class="permission-request">
			<p class="info">
				Les notifications vous permettent de recevoir des alertes en temps réel pour:
			</p>
			<ul class="features-list">
				<li>🟢 Positions ouvertes</li>
				<li>🔴 Positions fermées (TP/SL/TS)</li>
				<li>🔍 Setups détectés</li>
				<li>🏆 Milestones (winrate)</li>
				<li>❌ Erreurs critiques</li>
			</ul>
			<button class="request-btn" on:click={handleRequestPermission}>
				<span class="btn-icon">🔔</span>
				Activer les notifications
			</button>
		</div>
	{:else if $notificationPermission === 'denied'}
		<div class="permission-denied">
			<p class="warning">❌ Permission refusée</p>
			<p class="help">
				Pour activer les notifications, vous devez autoriser le site dans les paramètres de votre
				navigateur:
			</p>
			<ol class="steps">
				<li>Cliquez sur l'icône 🔒 ou ⓘ dans la barre d'adresse</li>
				<li>Cherchez "Notifications"</li>
				<li>Sélectionnez "Autoriser"</li>
				<li>Rechargez la page</li>
			</ol>
		</div>
	{:else}
		<div class="notification-types">
			<p class="description">
				Les notifications sont automatiquement envoyées pour les événements importants :
			</p>

			<!-- 🔥 FIX: Séparer les différents systèmes de notifications -->
			<div class="notification-systems">
				<!-- Système 1: Notifications Navigateur (Browser) -->
				<div class="system-section">
					<h4 class="system-title">🌐 Notifications Navigateur</h4>
					<div class="types-grid">
						<div class="type-card active">
							<div class="type-icon">🟢</div>
							<div class="type-name">Position Ouverte</div>
							<div class="type-desc">Alerte à l'ouverture d'une position</div>
						</div>

						<div class="type-card active">
							<div class="type-icon">🔴</div>
							<div class="type-name">Position Fermée</div>
							<div class="type-desc">TP, SL ou Trailing Stop</div>
						</div>

						<div class="type-card active">
							<div class="type-icon">🔍</div>
							<div class="type-name">Setup Détecté</div>
							<div class="type-desc">Conditions de trading remplies</div>
						</div>

						<div class="type-card active">
							<div class="type-icon">❌</div>
							<div class="type-name">Erreurs</div>
							<div class="type-desc">Erreurs critiques du système</div>
						</div>
					</div>
				</div>

				<!-- Système 2: Telegram -->
				<div class="system-section">
					<h4 class="system-title">📱 Notifications Telegram</h4>
					<div class="telegram-config">
						<p class="telegram-info">
							Les notifications Telegram sont configurées via le fichier <code>.env</code> à la racine du projet :
						</p>
						<div class="telegram-instructions">
							<ol class="telegram-steps">
								<li>Créez un fichier <code>.env</code> à la racine du projet</li>
								<li>Ajoutez vos identifiants Telegram :
									<pre class="env-example">TELEGRAM_BOT_TOKEN=votre_token_ici
TELEGRAM_CHAT_ID=votre_chat_id_ici</pre>
								</li>
								<li>Redémarrez le backend pour appliquer les changements</li>
							</ol>
							<div class="telegram-security">
								<strong>🔒 Sécurité :</strong> Le fichier <code>.env</code> est dans <code>.gitignore</code> et ne sera jamais commité sur GitHub.
							</div>
						</div>
						<div class="telegram-status">
							<span class="status-label">Statut:</span>
							<span class="status-value">{telegramStatus}</span>
						</div>
					</div>
				</div>
			</div>

			<div class="notification-note">
				<div class="note-icon">ℹ️</div>
				<div class="note-text">
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
