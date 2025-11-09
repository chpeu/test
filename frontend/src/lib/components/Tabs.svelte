<script>
	export let tabs = [];
	export let activeTab = '';

	function selectTab(tabId) {
		activeTab = tabId;
	}
</script>

<div class="tabs-container">
	<div class="tabs">
		{#each tabs as tab}
			<button
				class="tab"
				class:active={activeTab === tab.id}
				on:click={() => selectTab(tab.id)}
			>
				<span class="tab-icon">{tab.icon}</span>
				<span class="tab-label">{tab.label}</span>
			</button>
		{/each}
	</div>
</div>

<style>
	.tabs-container {
		margin-bottom: 20px;
		border-bottom: 2px solid #2a3a6b;
	}

	.tabs {
		display: flex;
		gap: 5px;
		overflow-x: auto;
		padding: 0 5px 5px;
	}

	/* Custom scrollbar for tabs */
	.tabs::-webkit-scrollbar {
		height: 6px;
	}

	.tabs::-webkit-scrollbar-track {
		background: #0a0e27;
		border-radius: 3px;
	}

	.tabs::-webkit-scrollbar-thumb {
		background: #2a3a6b;
		border-radius: 3px;
	}

	.tabs::-webkit-scrollbar-thumb:hover {
		background: #00ff88;
	}

	.tab {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 12px 20px;
		background: #1e2749;
		border: 2px solid #2a3a6b;
		border-bottom: none;
		border-radius: 10px 10px 0 0;
		color: #888;
		font-size: 14px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
		white-space: nowrap;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.tab:hover {
		background: rgba(0, 255, 136, 0.05);
		color: #00ff88;
		border-color: #00ff88;
	}

	.tab.active {
		background: #0a0e27;
		color: #00ff88;
		border-color: #00ff88;
		box-shadow: 0 -4px 15px rgba(0, 255, 136, 0.2);
	}

	.tab-icon {
		font-size: 18px;
		line-height: 1;
	}

	.tab-label {
		font-size: 13px;
	}

	/* Mobile responsive */
	@media (max-width: 768px) {
		.tabs {
			gap: 3px;
			padding: 0 3px 3px;
		}

		.tab {
			padding: 10px 15px;
			gap: 6px;
		}

		.tab-icon {
			font-size: 16px;
		}

		.tab-label {
			font-size: 11px;
		}
	}

	@media (max-width: 480px) {
		.tab {
			flex-direction: column;
			gap: 4px;
			padding: 8px 12px;
		}

		.tab-icon {
			font-size: 20px;
		}

		.tab-label {
			font-size: 10px;
		}
	}
</style>
