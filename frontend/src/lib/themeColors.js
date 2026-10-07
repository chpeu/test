// Couleurs pour Chart.js (le canvas ignore les variables CSS) : lues dans les tokens
// du thème courant, et ré-appliquées à chaque bascule dark/light.
import { theme } from '$lib/stores/theme';

const FALLBACK = {
	green: '#34d399',
	greenRgb: '52, 211, 153',
	red: '#f87171',
	redRgb: '248, 113, 113',
	blue: '#38bdf8',
	blueRgb: '56, 189, 248',
	orange: '#fbbf24',
	purple: '#8b5cf6',
	textPrimary: '#e8edf6',
	textSecondary: '#8fa0b8',
	grid: 'rgba(36, 48, 74, 0.35)',
	tooltipBg: '#121a2a'
};

export function tokens() {
	if (typeof document === 'undefined') return FALLBACK;
	const cs = getComputedStyle(document.documentElement);
	const v = (name, fb) => (cs.getPropertyValue(name) || fb).trim();
	return {
		green: v('--accent-green', FALLBACK.green),
		greenRgb: v('--accent-green-rgb', FALLBACK.greenRgb),
		red: v('--accent-red', FALLBACK.red),
		redRgb: v('--accent-red-rgb', FALLBACK.redRgb),
		blue: v('--accent-blue', FALLBACK.blue),
		blueRgb: v('--accent-blue-rgb', FALLBACK.blueRgb),
		orange: v('--accent-orange', FALLBACK.orange),
		purple: v('--accent-purple', FALLBACK.purple),
		textPrimary: v('--text-primary', FALLBACK.textPrimary),
		textSecondary: v('--text-secondary', FALLBACK.textSecondary),
		grid: `rgba(${v('--border-rgb', '36, 48, 74')}, 0.35)`,
		tooltipBg: v('--bg-secondary', FALLBACK.tooltipBg)
	};
}

export const alpha = (rgbTriplet, a) => `rgba(${rgbTriplet}, ${a})`;

/** Applique les couleurs du thème à un Chart.js existant (textes, grilles, tooltip). */
export function styleChart(chart, opts = {}) {
	if (!chart?.options) return;
	const t = tokens();
	const o = chart.options;
	if (o.plugins?.legend?.labels) o.plugins.legend.labels.color = t.textPrimary;
	if (o.plugins?.tooltip) {
		Object.assign(o.plugins.tooltip, {
			backgroundColor: t.tooltipBg,
			bodyColor: t.textPrimary,
			titleColor: opts.titleColor || t.green,
			borderColor: opts.borderColor || t.green
		});
	}
	for (const axis of Object.values(o.scales || {})) {
		if (axis.grid) axis.grid.color = t.grid;
		if (axis.ticks) axis.ticks.color = t.textSecondary;
	}
	chart.update('none');
}

/** Recompose les couleurs d'un dataset positif/négatif selon le thème. */
export function pnlColors(positive) {
	const t = tokens();
	return positive
		? {
				borderColor: t.green,
				backgroundColor: alpha(t.greenRgb, 0.12),
				pointBackgroundColor: t.green
			}
		: {
				borderColor: t.red,
				backgroundColor: alpha(t.redRgb, 0.12),
				pointBackgroundColor: t.red
			};
}

/** S'abonne au store thème ; à appeler dans onMount, retourner dans le cleanup. */
export function watchTheme(apply) {
	return theme.subscribe(() => apply());
}