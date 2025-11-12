<script>
	import { connectionIcon, connectionStatus, connectionColor } from '$lib/stores/connection';
</script>

<div class="connection-status" style="border-color: {$connectionColor}" data-debug-name="connectionStatus">
	<span class="connection-icon" data-debug-name="connectionIcon">{$connectionIcon}</span>
	<span class="connection-text" style="color: {$connectionColor}" data-debug-name="connectionStatus">{$connectionStatus}</span>
</div>

<style>
	.connection-status {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		padding: 8px 16px;
		background: rgba(30, 39, 73, 0.8);
		border-radius: 20px;
		border: 2px solid;
		font-size: 14px;
		font-weight: bold;
		transition: all 0.3s;
	}

	.connection-icon {
		font-size: 16px;
		animation: pulse 2s ease-in-out infinite;
	}

	.connection-text {
		text-transform: uppercase;
		letter-spacing: 1px;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.5;
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
