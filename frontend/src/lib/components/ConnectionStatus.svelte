<script>
	import { connectionIcon, connectionStatus, connectionColor } from '$lib/stores/connection';
</script>

<div class="connection-status" style="border-color: {$connectionColor}" data-debug-name="connectionStatus">
	<span class="connection-icon" data-debug-name="connectionIcon">{$connectionIcon}</span>
	<span class="connection-text" style="color: {$connectionColor}" data-debug-name="connectionStatus">{$connectionStatus}</span>
</div>

<style>
	/* Pilule de statut glass, liseré coloré par la couleur de connexion */
	.connection-status {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		padding: 7px 14px;
		background: var(--glass-bg);
		backdrop-filter: var(--glass-blur);
		-webkit-backdrop-filter: var(--glass-blur);
		border-radius: 999px;
		border: 1px solid var(--border-soft);
		outline: 1px solid transparent;
		box-shadow: var(--shadow-sm);
		font-size: 12.5px;
		font-weight: 700;
		transition: all 0.3s;
	}

	.connection-icon {
		font-size: 13px;
		line-height: 1;
		animation: breathe 2.4s ease-in-out infinite;
	}

	.connection-text {
		text-transform: uppercase;
		letter-spacing: 0.08em;
		font-size: 11.5px;
	}

	@keyframes breathe {
		0%,
		100% {
			opacity: 1;
			filter: drop-shadow(0 0 4px currentColor);
		}
		50% {
			opacity: 0.65;
			filter: drop-shadow(0 0 0 transparent);
		}
	}

	/* Mobile */
	@media (max-width: 768px) {
		.connection-status {
			padding: 6px 12px;
			font-size: 12px;
		}

		.connection-icon {
			font-size: 14px;
		}
	}
</style>
