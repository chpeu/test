<script>
	import '$lib/utils/socket'; // Init Socket.IO
	import { theme } from '$lib/stores/theme'; // Init theme
	import { onMount } from 'svelte';

	// SvelteKit props
	export let params = {};

	// Appliquer le thème au chargement
	onMount(() => {
		document.documentElement.setAttribute('data-theme', $theme);
	});

	// Réagir aux changements de thème
	$: if (typeof document !== 'undefined') {
		document.documentElement.setAttribute('data-theme', $theme);
	}
</script>

<slot />

<style global>
	/* Global CSS Reset and Base Styles */
	/* Note: Some selectors below are marked as "unused" by Svelte but are used globally across the app */
	* {
		margin: 0;
		padding: 0;
		box-sizing: border-box;
	}

	:root {
		/* Dark Theme Colors (default) */
		--bg-primary: #0a0e27;
		--bg-secondary: #1e2749;
		--bg-tertiary: #2a3a6b;
		--text-primary: #ffffff;
		--text-secondary: #888888;
		--accent-green: #00ff88;
		--accent-blue: #00aaff;
		--accent-red: #ff4444;
		--accent-orange: #ffaa00;
	}

	/* Light Theme Colors */
	[data-theme='light'] {
		--bg-primary: #f5f7fa;
		--bg-secondary: #ffffff;
		--bg-tertiary: #e8ecf1;
		--text-primary: #1a1a1a;
		--text-secondary: #666666;
		--accent-green: #00cc6a;
		--accent-blue: #0088cc;
		--accent-red: #dd3333;
		--accent-orange: #dd8800;
	}

	body {
		font-family: 'Courier New', 'Consolas', monospace;
		background: var(--bg-primary);
		color: var(--text-primary);
		min-height: 100vh;
		line-height: 1.6;
		font-size: 14px;
		overflow-x: hidden;
	}

	/* Scrollbar styling */
	::-webkit-scrollbar {
		width: 10px;
		height: 10px;
	}

	::-webkit-scrollbar-track {
		background: var(--bg-secondary);
	}

	::-webkit-scrollbar-thumb {
		background: var(--accent-green);
		border-radius: 5px;
	}

	::-webkit-scrollbar-thumb:hover {
		background: #00cc6a;
	}

	/* Selection */
	::selection {
		background: var(--accent-green);
		color: var(--bg-primary);
	}

	/* Focus outlines */
	button:focus,
	input:focus,
	select:focus {
		outline: 2px solid var(--accent-green);
		outline-offset: 2px;
	}

	/* Utility classes */
	.container {
		max-width: 1400px;
		margin: 0 auto;
		padding: 20px;
	}

	.text-center {
		text-align: center;
	}

	.mt-4 {
		margin-top: 1rem;
	}

	.mb-4 {
		margin-bottom: 1rem;
	}

	/* Animations */
	@keyframes fadeIn {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}

	@keyframes slideUp {
		from {
			transform: translateY(20px);
			opacity: 0;
		}
		to {
			transform: translateY(0);
			opacity: 1;
		}
	}

	.fade-in {
		animation: fadeIn 0.3s ease-in;
	}

	.slide-up {
		animation: slideUp 0.4s ease-out;
	}
</style>
