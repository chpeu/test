import { beforeEach } from 'vitest';

beforeEach(() => {
	window.localStorage.clear();
	window.history.replaceState({}, '', 'http://localhost:3000/');
});
