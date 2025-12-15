<script>
	export let activeSubTab = 'dashboard';
	export let tradesCount = 0;

	const tabs = [
		{
			id: 'dashboard',
			label: 'Dashboard',
			icon: '📊',
			enabled: true
		},
		{
			id: 'predictions',
			label: 'Prédictions Live',
			icon: '🔮',
			enabled: tradesCount >= 50,
			minTrades: 50
		},
		{
			id: 'features',
			label: 'Features',
			icon: '🔍',
			enabled: tradesCount >= 30,
			minTrades: 30
		},
		{
			id: 'models',
			label: 'Modèles',
			icon: '🤖',
			enabled: true
		},
		{
			id: 'correlations',
			label: 'Corrélations',
			icon: '🔗',
			enabled: tradesCount >= 20,
			minTrades: 20
		},
		{
			id: 'exploratory',
			label: 'Exploratoire',
			icon: '📈',
			enabled: tradesCount >= 10,
			minTrades: 10
		},
		{
			id: 'backtesting',
			label: 'Backtesting',
			icon: '🎯',
			enabled: tradesCount >= 50,
			minTrades: 50
		}
	];
</script>

<div class="ml-tabs">
	{#each tabs as tab}
		<button
			class="tab"
			class:active={activeSubTab === tab.id}
			class:disabled={!tab.enabled}
			disabled={!tab.enabled}
			on:click={() => {
				if (tab.enabled) {
					activeSubTab = tab.id;
				}
			}}
			title={!tab.enabled && tab.minTrades
				? `Nécessite ${tab.minTrades} trades (${tradesCount}/${tab.minTrades})`
				: ''}
		>
			<span class="icon">{tab.icon}</span>
			<span class="label">{tab.label}</span>
			{#if !tab.enabled && tab.minTrades}
				<span class="lock">🔒</span>
			{/if}
		</button>
	{/each}
</div>

<style>
	.ml-tabs {
		display: flex;
		gap: 0.5rem;
		border-bottom: 2px solid #e5e7eb;
		margin-bottom: 2rem;
		overflow-x: auto;
	}

	.tab {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem 1.5rem;
		background: none;
		border: none;
		border-bottom: 3px solid transparent;
		color: #6b7280;
		font-size: 0.95rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
		white-space: nowrap;
	}

	.tab:hover:not(.disabled) {
		color: #667eea;
		background: #f3f4f6;
	}

	.tab.active {
		color: #667eea;
		border-bottom-color: #667eea;
	}

	.tab.disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.icon {
		font-size: 1.2rem;
	}

	.lock {
		font-size: 0.9rem;
		margin-left: 0.25rem;
	}
</style>
