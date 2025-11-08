import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],

	server: {
		port: 3000,
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
		minify: 'terser',
		sourcemap: false,
		rollupOptions: {
			output: {
				manualChunks: {
					// Séparer Socket.IO et Chart.js en chunks
					'socket': ['socket.io-client'],
					'charts': ['chart.js']
				}
			}
		}
	}
});
