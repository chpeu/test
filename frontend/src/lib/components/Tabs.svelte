<script>
	export let tabs = [];
	export let activeTab = tabs[0]?.id || '';
	
	$: currentTab = tabs.find(t => t.id === activeTab) || tabs[0];
	
	function selectTab(tabId) {
		activeTab = tabId;
	}
</script>

<div class="tabs-container">
	<div class="tabs-header">
		{#each tabs as tab}
			<button
				class="tab-button"
				class:active={activeTab === tab.id}
				on:click={() => selectTab(tab.id)}
				role="tab"
				aria-selected={activeTab === tab.id}
			>
				<span class="tab-icon">{tab.icon || ''}</span>
				<span class="tab-label">{tab.label}</span>
			</button>
		{/each}
	</div>
	
	<!-- Tab content is rendered by parent component -->
</div>

<style>
	.tabs-container {
		background: #1e2749;
		border-radius: 10px;
		border: 2px solid #2a3a6b;
		overflow: hidden;
		margin-bottom: 15px;
	}
	
	.tabs-header {
		display: flex;
		gap: 0;
		background: #0a0e27;
		border-bottom: 2px solid #2a3a6b;
		overflow-x: auto;
		scrollbar-width: thin;
		scrollbar-color: #2a3a6b #0a0e27;
	}
	
	.tabs-header::-webkit-scrollbar {
		height: 6px;
	}
	
	.tabs-header::-webkit-scrollbar-track {
		background: #0a0e27;
	}
	
	.tabs-header::-webkit-scrollbar-thumb {
		background: #2a3a6b;
		border-radius: 3px;
	}
	
	.tab-button {
		padding: 12px 20px;
		background: transparent;
		border: none;
		border-bottom: 3px solid transparent;
		color: #888;
		font-family: 'Courier New', monospace;
		font-size: 13px;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.3s;
		white-space: nowrap;
		display: flex;
		align-items: center;
		gap: 8px;
		text-transform: uppercase;
		position: relative;
		z-index: 1001; /* 🔥 FIX: Au-dessus du modal pour permettre les clics */
		pointer-events: auto; /* 🔥 FIX: Permettre les clics même si modal ouvert */
	}
	
	.tab-button:hover {
		background: rgba(0, 255, 136, 0.05);
		color: #00ff88;
	}
	
	.tab-button.active {
		background: rgba(0, 255, 136, 0.1);
		color: #00ff88;
		border-bottom-color: #00ff88;
		text-shadow: 0 0 10px rgba(0, 255, 136, 0.5);
	}
	
	.tab-icon {
		font-size: 16px;
	}
	
	.tab-label {
		font-size: 12px;
	}
	
	.tabs-content {
		padding: 18px;
		min-height: 200px;
	}
	
	.tab-panel {
		animation: fadeIn 0.3s ease-in;
	}
	
	@keyframes fadeIn {
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
		.tab-button {
			padding: 10px 15px;
			font-size: 11px;
		}
		
		.tab-icon {
			font-size: 14px;
		}
		
		.tabs-content {
			padding: 12px;
		}
	}
</style>
