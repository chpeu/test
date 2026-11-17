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

// Tunnel API + WebSocket partage par le serveur de dev ET par l'aperçu du build
// (`npm run preview`). Sans lui, le build servi seul ne joindrait pas le backend :
// l'interface resterait bloque sur « Connexion au backend... ».
const proxyPartage = {
	// Proxy API vers FastAPI backend
	'/api': {
		target: backendUrl,
		changeOrigin: true,
		ws: false
	},
	// REMPLACEMENT: WebSocket natif au lieu de Socket.IO
	'/ws': {
		target: backendUrl, // Vite convertit l'URL HTTP en WebSocket
		changeOrigin: true,
		ws: true,
		configure: (proxy, _options) => {
			proxy.on('error', (err, _req, _res) => {
				console.log('Proxy WebSocket error (normal if backend not running):', err.message);
			});
			proxy.on('proxyReqWs', (proxyReq, req, socket) => {
				socket.on('error', (err) => {
					console.log('WebSocket connection error (normal if backend not running):', err.message);
				});
			});
		}
	}
};

const hote = process.env.FRONTEND_HOST || '0.0.0.0';
const portFront = Number(process.env.FRONTEND_PORT || 3000);

export default defineConfig({
	plugins: [sveltekit()],

	server: {
		port: portFront,
		host: hote, // 🔥 Permettre l'accès depuis l'extérieur (iPhone, etc.)
		proxy: proxyPartage
	},

	// Aperçu du build de production (`npm run preview`) : memes regles de tunnel
	// que le serveur de dev, pour tester l'application construite et non la
	// version chaude (le serveur de dev perd parfois le fil apres une
	// reoptimisation des dependances : page blanche jusqu'au rechargement).
	preview: {
		port: portFront,
		host: hote,
		proxy: proxyPartage
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
