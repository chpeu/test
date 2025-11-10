import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],

	server: {
		port: 3000,
		host: '0.0.0.0', // 🔥 Permettre l'accès depuis l'extérieur (iPhone, etc.)
		proxy: {
			// Proxy API vers FastAPI backend
			'/api': {
				target: 'http://localhost:5000',
				changeOrigin: true,
				ws: false
			},
			// 🔥 REMPLACEMENT: WebSocket natif au lieu de Socket.IO
			'/ws': {
				target: 'ws://localhost:5000',
				changeOrigin: true,
				ws: true, // WebSocket support
				rewrite: (path) => path,
				configure: (proxy, _options) => {
					// Gérer les erreurs de connexion WebSocket
					proxy.on('error', (err, _req, _res) => {
						console.log('Proxy WebSocket error (normal if backend not running):', err.message);
					});
					proxy.on('proxyReqWs', (proxyReq, req, socket) => {
						// Gérer les reconnexions WebSocket
						socket.on('error', (err) => {
							console.log('WebSocket connection error (normal if backend not running):', err.message);
						});
					});
				}
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
					// 🔥 REMPLACEMENT: Plus besoin de socket.io-client (WebSocket natif)
				}
			}
		}
	}
});
