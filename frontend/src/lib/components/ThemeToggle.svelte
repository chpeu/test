<script>
	import { theme, toggleTheme } from '$lib/stores/theme';

	function handleToggle() {
		toggleTheme();
	}
</script>

<button class="theme-toggle" on:click={handleToggle} title="Toggle theme">
	{#if $theme === 'dark'}
		<span class="icon">🌙</span>
		<span class="label">Dark</span>
	{:else}
		<span class="icon">☀️</span>
		<span class="label">Light</span>
	{/if}
</button>

<style>
	.theme-toggle {
		display: flex;
		align-items: center;
		gap: 8px;
		background: var(--bg-secondary);
		border: 1px solid var(--bg-tertiary);
		border-radius: 8px;
		padding: 10px 16px;
		cursor: pointer;
		transition: all 0.3s ease;
		color: var(--text-primary);
		font-size: 14px;
		font-weight: 500;
	}

	.theme-toggle:hover {
		background: var(--bg-tertiary);
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
	}

	.theme-toggle:active {
		transform: translateY(0);
	}

	.icon {
		font-size: 20px;
		line-height: 1;
		transition: transform 0.3s ease;
	}

	.theme-toggle:hover .icon {
		transform: rotate(20deg) scale(1.1);
	}

	.label {
		font-family: 'Courier New', monospace;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	@media (max-width: 768px) {
		.label {
			display: none;
		}

		.theme-toggle {
			padding: 10px;
		}
	}
</style>
