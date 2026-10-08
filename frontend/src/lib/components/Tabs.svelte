<script>
	export let tabs = [];
	export let activeTab = tabs[0]?.id || '';

	$: currentTab = tabs.find(t => t.id === activeTab) || tabs[0];

	function selectTab(tabId) {
		// 🔥 FIX: Toujours mettre à jour activeTab pour déclencher la réactivité Svelte
		activeTab = tabId;
	}
</script>

<div class="tabs-container" data-debug-name="tabsContainer" role="tablist" aria-label="Navigation principale">
	<div class="tabs-header" data-debug-name="tabsHeader">
		{#each tabs as tab}
			<button
				class="tab-button"
				class:active={activeTab === tab.id}
				on:click|stopPropagation={(e) => {
					e.stopPropagation();
					selectTab(tab.id);
				}}
				role="tab"
				aria-selected={activeTab === tab.id}
				type="button"
				data-debug-name="tabButton.{tab.id}"
			>
				{#if tab.icon}
					<span class="tab-icon" data-debug-name="tabIcon.{tab.id}" aria-hidden="true">{tab.icon}</span>
				{/if}
				<span class="tab-label" data-debug-name="tabLabel.{tab.id}">{tab.label}</span>
			</button>
		{/each}
	</div>

	<!-- Tab content is rendered by parent component -->
</div>

<style>
	/* Barre segmentée « flottante » façon app native 2025 */
	.tabs-container {
		background: var(--glass-bg);
		backdrop-filter: var(--glass-blur);
		-webkit-backdrop-filter: var(--glass-blur);
		border-radius: var(--radius-xl);
		border: 1px solid var(--border-soft);
		box-shadow: var(--shadow-md);
		overflow: visible; /* 🔥 FIX: Permettre aux onglets d'être cliquables même avec overflow */
		margin-bottom: 16px;
		position: relative;
		z-index: 1; /* 🔥 FIX: S'assurer que les onglets sont au-dessus du contenu */
		padding: 5px;
	}

	.tabs-header {
		display: flex;
		gap: 2px;
		background: transparent;
		border: none;
		overflow-x: auto;
		overflow-y: visible; /* 🔥 FIX: Permettre les clics même avec scroll */
		scrollbar-width: none;
		position: relative;
		z-index: 1002; /* 🔥 FIX: Au-dessus de tout le reste */
		border-radius: calc(var(--radius-xl) - 4px);
	}

	.tabs-header::-webkit-scrollbar {
		height: 0;
	}

	.tab-button {
		padding: 9px 16px;
		background: transparent;
		border: none;
		border-radius: calc(var(--radius-xl) - 6px);
		color: var(--text-secondary);
		font-family: var(--font-ui);
		font-size: 13px;
		font-weight: 600;
		letter-spacing: 0.01em;
		cursor: pointer;
		transition:
			color 0.2s ease,
			background-color 0.2s ease,
			box-shadow 0.2s ease,
			transform 0.2s var(--ease-spring);
		white-space: nowrap;
		display: flex;
		align-items: center;
		gap: 7px;
		position: relative;
		z-index: 1001; /* 🔥 FIX: Au-dessus du modal pour permettre les clics */
		pointer-events: auto; /* 🔥 FIX: Permettre les clics même si modal ouvert */
	}

	.tab-button:hover {
		background: rgba(var(--accent-green-rgb), 0.07);
		color: var(--text-primary);
	}

	.tab-button:active {
		transform: scale(0.97);
	}

	.tab-button.active {
		background: linear-gradient(180deg, rgba(var(--accent-green-rgb), 0.18) 0%, rgba(var(--accent-green-rgb), 0.10) 100%);
		color: var(--accent-green);
		box-shadow:
			inset 0 0 0 1px rgba(var(--accent-green-rgb), 0.35),
			0 2px 10px rgba(var(--accent-green-rgb), 0.12);
		text-shadow: none;
	}

	.tab-icon {
		font-size: 15px;
		line-height: 1;
		filter: saturate(1.15);
	}

	.tab-label {
		font-size: 12.5px;
	}	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	/* Mobile */
	@media (max-width: 768px) {
		.tabs-container {
			border-radius: var(--radius-lg);
			padding: 4px;
		}

		.tab-button {
			padding: 8px 12px;
			font-size: 11.5px;
			border-radius: var(--radius-md);
		}

		.tab-icon {
			font-size: 13px;
		}	}
</style>