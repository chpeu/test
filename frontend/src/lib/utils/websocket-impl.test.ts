import { describe, it, expect, beforeEach } from 'vitest';
import { BidirectionalWebSocket } from './websocket-impl';

const setUrl = (url: string) => {
	window.history.replaceState({}, '', url);
};

describe('BidirectionalWebSocket URL resolution', () => {
	beforeEach(() => {
		window.localStorage.clear();
		setUrl('http://localhost:3000/');
	});

	it('uses ws_url query param as the first candidate and normalizes protocol', () => {
		setUrl('http://localhost:3000/?ws_url=http://127.0.0.1:5001');
		const ws = new BidirectionalWebSocket('');
		const wsAny = ws as any;

		expect(wsAny.baseUrls[0]).toBe('ws://127.0.0.1:5001');
		expect(wsAny.url).toBe('ws://127.0.0.1:5001/ws');
	});

	it('adds localhost fallback ports on dev host', () => {
		const ws = new BidirectionalWebSocket('');
		const wsAny = ws as any;

		expect(wsAny.baseUrls).toContain('ws://localhost:5000');
		expect(wsAny.baseUrls).toContain('ws://localhost:5001');
		expect(wsAny.baseUrls).toContain('ws://127.0.0.1:5000');
		expect(wsAny.baseUrls).toContain('ws://127.0.0.1:5001');
	});

	it('prioritises localStorage override when present', () => {
		window.localStorage.setItem('ws_base_url', 'http://localhost:5001');
		const ws = new BidirectionalWebSocket('');
		const wsAny = ws as any;

		expect(wsAny.baseUrls[0]).toBe('ws://localhost:5001');
		expect(wsAny.url).toBe('ws://localhost:5001/ws');
	});

	it('rotates base URLs when multiple candidates exist', () => {
		const ws = new BidirectionalWebSocket('ws://localhost:5000');
		const wsAny = ws as any;

		wsAny.baseUrls = ['ws://localhost:5000', 'ws://localhost:5001'];
		wsAny.setActiveBaseUrl(0);
		const rotated = wsAny.rotateBaseUrl('test');

		expect(rotated).toBe(true);
		expect(wsAny.baseUrl).toBe('ws://localhost:5001');
		expect(wsAny.url).toBe('ws://localhost:5001/ws');

		wsAny.baseUrls = ['ws://localhost:5000'];
		wsAny.setActiveBaseUrl(0);
		expect(wsAny.rotateBaseUrl('single')).toBe(false);
	});
});
