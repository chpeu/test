import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],

	server: {
		port: 3000,
		host: '0.0.0.0', // 🔥 Permettre l'accès depuis l'extérieur (iPhone, etc.)
		proxy: {
			// Proxy API et Socket.IO vers FastAPI backend
			'/api': {
				target: 'http://localhost:5000',
				changeOrigin: true,
				ws: false
			},
			'/socket.io': {
				target: 'http://localhost:5000',
				changeOrigin: true,
				ws: true // WebSocket support
			}
		}
	},

	build: {
		// Optimisation production
		minify: 'esbuild', // esbuild est plus rapide et inclus par défaut
		sourcemap: false,
		rollupOptions: {
			output: {
				manualChunks: (id) => {
					// Séparer Chart.js en chunk séparé
					if (id.includes('chart.js')) {
						return 'charts';
					}
					// Ne pas mettre socket.io-client dans manualChunks
					// Il sera géré automatiquement par SvelteKit
				}
			}
		}
	}
});
