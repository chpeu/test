import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit()],
	test: {
		environment: 'jsdom',
		environmentOptions: {
			url: 'http://localhost:3000/'
		},
		setupFiles: ['src/tests/setup.ts'],
		include: ['src/**/*.{test,spec}.{ts,js}'],
		clearMocks: true,
		restoreMocks: true,
		coverage: {
			provider: 'v8',
			reporter: ['text', 'html', 'json-summary'],
			include: ['src/lib/utils/websocket-impl.ts'],
			exclude: ['**/*.d.ts', '**/*.svelte', '**/node_modules/**', '**/.svelte-kit/**']
		}
	}
});
