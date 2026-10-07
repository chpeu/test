<script>
	// Design system global — source unique (voir src/app.css)
	import '../app.css';
	// Typographie embarquée (pas de dépendance réseau au runtime)
	import '@fontsource-variable/inter';
	import '@fontsource/jetbrains-mono/400.css';
	import '@fontsource/jetbrains-mono/600.css';
	import '@fontsource/jetbrains-mono/700.css';

	import { theme } from '$lib/stores/theme';
	import { onMount } from 'svelte';

	// 🔥 FIX: SvelteKit passe automatiquement params, mais on ne l'utilise pas
	// On doit l'accepter explicitement pour éviter le warning
	export let params = {};

	// Synchroniser l'attribut data-theme avec le store (le store l'initialise
	// dès le chargement du module, et app.html le pose avant le premier paint)
	onMount(() => {
		document.documentElement.setAttribute('data-theme', $theme);
	});

	$: if (typeof document !== 'undefined') {
		document.documentElement.setAttribute('data-theme', $theme);
	}
</script>

<slot />