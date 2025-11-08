import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Consult https://kit.svelte.dev/docs/integrations#preprocessors
	preprocess: vitePreprocess(),

	kit: {
		// adapter-node pour production (Proxmox VM)
		adapter: adapter({
			out: 'build',
			precompress: true, // Brotli/gzip compression
			envPrefix: ''
		}),

		// Proxy API vers FastAPI backend
		alias: {
			$lib: './src/lib'
		}
	}
};

export default config;
