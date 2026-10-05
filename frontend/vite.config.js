import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

const resolveBackendUrl = () => {
	const directUrl = process.env.VITE_BACKEND_URL || process.env.BACKEND_URL;
	if (directUrl) {
		return /^https?:\/\//.test(directUrl) ? directUrl : `http://${directUrl}`;
	}
	const port = process.env.VITE_BACKEND_PORT || process.env.BACKEND_PORT || process.env.WS_PORT;
	if (port) {
		return `http://127.0.0.1:${port}`;
	}
	return 'http://127.0.0.1:5000';
};

const backendUrl = resolveBackendUrl();

export default defineConfig({
	plugins: [sveltekit()],

	server: {
		port: 3000,
		host: '0.0.0.0', // 🔥 Permettre l'accès depuis l'extérieur (iPhone, etc.)
		proxy: {
			// Proxy API vers FastAPI backend
			'/api': {
				target: backendUrl,
				changeOrigin: true,
				ws: false
			},
			// 🔥 REMPLACEMENT: WebSocket natif au lieu de Socket.IO
			'/ws': {
				target: backendUrl, // 🔥 FIX: Utiliser l'URL HTTP, Vite convertira en WebSocket
				changeOrigin: true,
				ws: true, // WebSocket support
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
