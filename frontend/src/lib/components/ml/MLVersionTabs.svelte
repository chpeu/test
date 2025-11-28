<script>
	import MLDashboard from './MLDashboard.svelte';
	import MLDashboardV2 from './MLDashboardV2.svelte';

	let activeVersion = 'v1'; // 'v1' ou 'v2'
</script>

<div class="ml-version-container">
	<!-- Version Selector -->
	<div class="version-tabs">
		<button
			class="version-tab"
			class:active={activeVersion === 'v1'}
			on:click={() => (activeVersion = 'v1')}
		>
			<span class="icon">📊</span>
			<span class="label">XGBoost V1</span>
			<span class="badge">Legacy</span>
		</button>

		<button
			class="version-tab"
			class:active={activeVersion === 'v2'}
			on:click={() => (activeVersion = 'v2')}
		>
			<span class="icon">🚀</span>
			<span class="label">XGBoost V2</span>
			<span class="badge new">Nouveau</span>
		</button>
	</div>

	<!-- Version Content -->
	<div class="version-content">
		{#if activeVersion === 'v1'}
			<MLDashboard />
		{:else if activeVersion === 'v2'}
			<MLDashboardV2 />
		{/if}
	</div>
</div>

<style>
	.ml-version-container {
		height: 100%;
		display: flex;
		flex-direction: column;
	}

	.version-tabs {
		display: flex;
		gap: 1rem;
		padding: 1rem 1.5rem;
		background: linear-gradient(to bottom, #f9fafb, #ffffff);
		border-bottom: 2px solid #e5e7eb;
	}

	.version-tab {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.875rem 1.75rem;
		background: white;
		border: 2px solid #e5e7eb;
		border-radius: 12px;
		color: #6b7280;
		font-size: 1rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.3s;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
	}

	.version-tab:hover {
		border-color: #667eea;
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
	}

	.version-tab.active {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		border-color: #667eea;
		box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
	}

	.icon {
		font-size: 1.5rem;
	}

	.label {
		font-size: 1rem;
	}

	.badge {
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: 600;
		background: rgba(0, 0, 0, 0.1);
		color: white;
	}

	.version-tab:not(.active) .badge {
		background: #f3f4f6;
		color: #6b7280;
	}

	.badge.new {
		background: linear-gradient(135deg, #10b981 0%, #059669 100%);
		color: white;
		animation: pulse 2s infinite;
	}

	.version-tab:not(.active) .badge.new {
		background: #10b981;
		color: white;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.7;
		}
	}

	.version-content {
		flex: 1;
		overflow-y: auto;
		padding: 1.5rem;
	}

	@media (max-width: 768px) {
		.version-tabs {
			flex-direction: column;
			gap: 0.5rem;
		}

		.version-tab {
			padding: 0.75rem 1.25rem;
		}

		.label {
			font-size: 0.9rem;
		}
	}
</style>
