/**
 * Typed mirror of tokens.css — for code that cannot read CSS custom
 * properties: Cesium colour constructors, SVG attributes, canvas 2D, and
 * tests. Everything else consumes var(--v-*) directly.
 *
 * PARITY CONTRACT: every key here exists in tokens.css under BOTH
 * [data-theme='command'] and [data-theme='daylight'] with the same value
 * (tests/design-tokens.mjs asserts it — extend both files together, never
 * one). Values are written to match the CSS text after whitespace
 * collapsing; hex is lowercase in both. Hex values live only in these two
 * files.
 *
 * Colour values from Blueprint (@blueprintjs/colors 5.1.16), Copyright
 * Palantir Technologies, Inc., Apache-2.0 — see LICENSE-blueprint.txt.
 */

export type Band = 'GREEN' | 'AMBER' | 'RED' | 'BLACK';

export type ThemeName = 'command' | 'daylight';

export type AuditColorLevel = 'info' | 'decision' | 'tool' | 'model' | 'band' | 'error';

export const TOKENS: Record<ThemeName, Record<string, string>> = {
	command: {
		'--v-canvas': '#000000',
		'--v-surface-1': '#111111',
		'--v-surface-2': '#1a1a1a',
		'--v-surface-3': '#242424',
		'--v-surface-sink': '#0a0a0a',
		'--v-paper': '#242424',
		'--v-line-1': 'rgba(255, 255, 255, 0.1)',
		'--v-line-2': 'rgba(255, 255, 255, 0.2)',
		'--v-line-select': 'rgba(138, 187, 255, 0.752)',
		'--v-ink-1': '#ffffff',
		'--v-ink-2': '#cbcbcb',
		'--v-ink-3': '#a6a6a6',
		'--v-ink-4': '#6b6b6b',
		'--v-act': '#ff9f43',
		'--v-act-2': '#c87619',
		'--v-act-focus': 'rgba(138, 187, 255, 0.752)',
		'--v-act-veil': 'rgba(200, 118, 25, 0.2)',
		'--v-act-text': '#fbb360',
		'--v-band-green': '#32a467',
		'--v-band-amber': '#ffb257',
		'--v-band-red': '#e76a6e',
		'--v-band-black-fill': 'rgba(17, 17, 17, 0.85)',
		'--v-band-black-hairline': '#e76a6e',
		'--v-band-veil': 'rgba(255, 178, 87, 0.14)',
		'--v-data': '#4c90f0',
		'--v-tool': '#5b91f5',
		'--v-glass-bg': '#242424',
		'--v-glass-border': 'rgba(255, 255, 255, 0.2)',
		'--v-glass-blur': '0px',
		'--v-glow-act': 'transparent',
		'--v-flow-light': '#c5cbd3',
		'--v-veil': 'rgba(17, 20, 24, 0.08)',
		'--v-font-ui':
			"Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans', 'Noto Sans Devanagari', 'Helvetica Neue', Arial, sans-serif",
		'--v-font-display':
			"Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans', 'Noto Sans Devanagari', 'Helvetica Neue', Arial, sans-serif",
		'--v-font-mono':
			"'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace",
		'--v-text-2xs': '12px',
		'--v-text-xs': '12px',
		'--v-text-sm': '12px',
		'--v-text-base': '14px',
		'--v-text-md': '16px',
		'--v-text-lg': '18px',
		'--v-text-xl': '22px',
		'--v-weight-status': '600',
		'--v-tracking-status': '0',
		'--v-space-1': '4px',
		'--v-space-2': '8px',
		'--v-space-3': '12px',
		'--v-space-4': '16px',
		'--v-space-5': '20px',
		'--v-space-6': '24px',
		'--v-space-7': '32px',
		'--v-space-8': '40px',
		'--v-ctl-sm': '24px',
		'--v-ctl-md': '30px',
		'--v-ctl-lg': '40px',
		'--v-ctl-touch': '44px',
		'--v-radius-chip': '4px',
		'--v-radius-btn': '4px',
		'--v-radius-panel': '4px',
		'--v-radius-modal': '4px',
		'--v-radius-pill': '999px',
		'--v-pad-panel': '12px',
		'--v-gap-panel': '8px',
		'--v-ease': 'cubic-bezier(0.4, 1, 0.75, 0.9)',
		'--v-dur-out': '100ms',
		'--v-dur-in': '200ms',
		'--v-dur-wipe': '600ms',
		'--v-dur-trace': '1200ms',
		'--v-dur-comet': '300ms',
		'--v-dur-stagger': '0ms',
		'--v-dur-pulse': '0ms',
		'--v-dur-lift': '0ms',
		'--v-dur-breathe': '0ms',
		'--v-dur-sweep': '0ms',
		'--v-surface-4': '#3d3d3d',
		'--v-hover': 'rgba(160, 160, 160, 0.15)',
		'--v-row-hover': 'rgba(110, 110, 110, 0.3)',
		'--v-minimal-hover': 'rgba(110, 110, 110, 0.24)',
		'--v-minimal-active': 'rgba(110, 110, 110, 0.49)',
		'--v-line-strong': 'rgba(255, 255, 255, 0.3)',
		'--v-popover-line': '#5e6064',
		'--v-focus': 'rgba(138, 187, 255, 0.752)',
		'--v-ink-disabled': 'rgba(175, 175, 175, 0.6)',
		'--v-primary': '#276ef1',
		'--v-primary-hover': '#1e54b7',
		'--v-primary-active': '#174291',
		'--v-primary-text': '#7fa8f7',
		'--v-primary-veil': 'rgba(39, 110, 241, 0.2)',
		'--v-success': '#238551',
		'--v-success-hover': '#1c6e42',
		'--v-success-active': '#165a36',
		'--v-success-text': '#72ca9b',
		'--v-success-veil': 'rgba(35, 133, 81, 0.2)',
		'--v-warning': '#c87619',
		'--v-warning-hover': '#935610',
		'--v-warning-active': '#77450d',
		'--v-warning-text': '#fbb360',
		'--v-warning-veil': 'rgba(200, 118, 25, 0.2)',
		'--v-danger': '#cd4246',
		'--v-danger-hover': '#ac2f33',
		'--v-danger-active': '#8e292c',
		'--v-danger-text': '#fa999c',
		'--v-danger-veil': 'rgba(205, 66, 70, 0.2)',
		'--v-neutral-veil': 'rgba(150, 150, 150, 0.15)',
		'--v-ai': '#5b91f5',
		'--v-ai-text': '#8db4f9',
		'--v-ai-veil': 'rgba(91, 145, 245, 0.2)',
		'--v-elev-0': 'inset 0 0 0 1px rgba(255, 255, 255, 0.2), 0 0 10px 0 rgba(0, 0, 0, 0.2)',
		'--v-elev-1': 'inset 0 0 0 1px rgba(255, 255, 255, 0.2), 0 1px 10px 0 rgba(0, 0, 0, 0.2)',
		'--v-elev-2':
			'inset 0 0 0 1px rgba(255, 255, 255, 0.2), 0 4px 6px -4px rgba(0, 0, 0, 0.5), 0 10px 30px -5px rgba(0, 0, 0, 0.5)',
		'--v-elev-3':
			'inset 0 0 0 1px rgba(255, 255, 255, 0.2), 0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 30px -5px rgba(0, 0, 0, 0.3)',
		'--v-elev-4': 'inset 0 0 0 1px rgba(255, 255, 255, 0.2), 0 25px 60px -12px rgba(0, 0, 0, 0.85)',
		'--v-map-select': '#ffffff',
		'--v-map-decision': '#ff9f43',
		'--v-map-alert': '#ff5c61',
		'--v-map-route': '#2dd4bf',
		'--v-map-event': '#5b91f5',
		'--v-map-water': '#38bdf8',
		'--v-map-marker': '#c5cbd3',
		'--v-map-marker-fill': 'rgba(17, 17, 17, 0.88)',
		'--v-map-casing': 'rgba(17, 17, 17, 0.8)',
		'--v-map-label-bg': 'rgba(17, 17, 17, 0.86)',
		'--v-map-label-ink': '#f6f7f9',
		'--v-flow-1': '#c4c4c4',
		'--v-flow-2': '#d6d6d6',
		'--v-flow-3': '#e6e6e6',
		'--v-flow-4': '#f3f3f3',
		'--v-flow-5': '#ffffff',
		'--v-flow-width-1': '3px',
		'--v-flow-width-2': '3.5px',
		'--v-flow-width-3': '4px',
		'--v-flow-width-4': '5px',
		'--v-flow-width-5': '6px',
		'--v-z-content': '10',
		'--v-z-overlay': '20',
		'--v-z-dialog': '30',
		'--v-z-toast': '40',
		'--v-z-tooltip': '50',
		'--v-ws-navbar': '50px',
		'--v-ws-strip': '36px',
		'--v-ws-rail': '44px',
		'--v-ws-left': '300px',
		'--v-ws-right': '400px',
		'--v-ws-right-md': '368px',
		'--v-ws-right-sm': '344px',
		'--v-ws-pane-head': '40px',
		'--v-ws-row': '28px',
		'--v-ws-row-2': '44px',
		'--v-ws-row-head': '30px',
		'--v-ws-tag': '20px',
		'--v-ws-icon-col': '32px',
		'--v-ws-timeline': '124px',
		'--v-ws-audit': '220px',
		'--v-ws-audit-compact': '172px',
		'--v-on-fill': '#ffffff',
		'--v-tooltip-bg': '#eeeeee',
		'--v-tooltip-ink': '#333333',
		'--v-backdrop': 'rgba(0, 0, 0, 0.7)',
	},
	daylight: {
		'--v-canvas': '#edeae3',
		'--v-surface-1': '#ffffff',
		'--v-surface-2': '#f6f3ee',
		'--v-surface-3': '#fcfbf8',
		'--v-surface-sink': '#e5e1d8',
		'--v-paper': '#faf9f7',
		'--v-line-1': 'rgba(26, 31, 46, 0.12)',
		'--v-line-2': 'rgba(26, 31, 46, 0.2)',
		'--v-line-select': 'rgba(194, 65, 12, 0.35)',
		'--v-ink-1': '#1a1f2e',
		'--v-ink-2': '#4a5468',
		'--v-ink-3': '#5b6478',
		'--v-ink-4': '#98a0b3',
		'--v-act': '#ea580c',
		'--v-act-2': '#c2410c',
		'--v-act-focus': '#c2410c',
		'--v-act-veil': 'rgba(234, 88, 12, 0.1)',
		'--v-act-text': '#c2410c',
		'--v-band-green': '#2f9e6f',
		'--v-band-amber': '#b27a1e',
		'--v-band-red': '#c24444',
		'--v-band-black-fill': 'rgba(26, 31, 46, 0.4)',
		'--v-band-black-hairline': '#c24444',
		'--v-band-veil': 'rgba(178, 122, 30, 0.12)',
		'--v-data': '#2e6fae',
		'--v-tool': '#1e54b7',
		'--v-glass-bg': 'rgba(255, 255, 255, 0.92)',
		'--v-glass-border': 'rgba(26, 31, 46, 0.18)',
		'--v-glass-blur': '10px',
		'--v-glow-act': 'rgba(194, 65, 12, 0.16)',
		'--v-flow-light': '#5f8f2a',
		'--v-veil': 'rgba(26, 31, 46, 0.08)',
		'--v-font-ui': "Inter, 'Noto Sans', 'Noto Sans Devanagari', system-ui, sans-serif",
		'--v-font-display':
			"Inter, 'Noto Sans', 'Noto Sans Devanagari', system-ui, sans-serif",
		'--v-font-mono': "'JetBrains Mono', 'Noto Sans Mono', ui-monospace, monospace",
		'--v-text-2xs': '13px',
		'--v-text-xs': '13px',
		'--v-text-sm': '14px',
		'--v-text-base': '16px',
		'--v-text-md': '16px',
		'--v-text-lg': '20px',
		'--v-text-xl': '28px',
		'--v-weight-status': '600',
		'--v-tracking-status': '0',
		'--v-space-1': '4px',
		'--v-space-2': '8px',
		'--v-space-3': '12px',
		'--v-space-4': '16px',
		'--v-space-5': '20px',
		'--v-space-6': '24px',
		'--v-space-7': '32px',
		'--v-space-8': '40px',
		'--v-ctl-sm': '24px',
		'--v-ctl-md': '28px',
		'--v-ctl-lg': '32px',
		'--v-ctl-touch': '44px',
		'--v-radius-chip': '4px',
		'--v-radius-btn': '6px',
		'--v-radius-panel': '10px',
		'--v-radius-modal': '14px',
		'--v-radius-pill': '999px',
		'--v-pad-panel': '16px',
		'--v-gap-panel': '12px',
		'--v-ease': 'cubic-bezier(0.2, 0, 0, 1)',
		'--v-dur-out': '150ms',
		'--v-dur-in': '300ms',
		'--v-dur-wipe': '600ms',
		'--v-dur-trace': '1200ms',
		'--v-dur-comet': '300ms',
		'--v-dur-stagger': '120ms',
		'--v-dur-pulse': '200ms',
		'--v-dur-lift': '2s',
		'--v-dur-breathe': '2s',
		'--v-dur-sweep': '3.5s',
		'--v-surface-4': '#dce0e5',
		'--v-hover': 'rgba(143, 153, 168, 0.15)',
		'--v-row-hover': 'rgba(143, 153, 168, 0.15)',
		'--v-minimal-hover': 'rgba(143, 153, 168, 0.15)',
		'--v-minimal-active': 'rgba(143, 153, 168, 0.3)',
		'--v-line-strong': 'rgba(17, 20, 24, 0.3)',
		'--v-popover-line': 'rgba(17, 20, 24, 0.1)',
		'--v-focus': 'rgba(33, 93, 176, 0.752)',
		'--v-ink-disabled': 'rgba(95, 107, 124, 0.6)',
		'--v-primary': '#2d72d2',
		'--v-primary-hover': '#215db0',
		'--v-primary-active': '#184a90',
		'--v-primary-text': '#215db0',
		'--v-primary-veil': 'rgba(45, 114, 210, 0.1)',
		'--v-success': '#238551',
		'--v-success-hover': '#1c6e42',
		'--v-success-active': '#165a36',
		'--v-success-text': '#1c6e42',
		'--v-success-veil': 'rgba(35, 133, 81, 0.1)',
		'--v-warning': '#c87619',
		'--v-warning-hover': '#935610',
		'--v-warning-active': '#77450d',
		'--v-warning-text': '#935610',
		'--v-warning-veil': 'rgba(200, 118, 25, 0.1)',
		'--v-danger': '#cd4246',
		'--v-danger-hover': '#ac2f33',
		'--v-danger-active': '#8e292c',
		'--v-danger-text': '#ac2f33',
		'--v-danger-veil': 'rgba(205, 66, 70, 0.1)',
		'--v-neutral-veil': 'rgba(143, 153, 168, 0.15)',
		'--v-ai': '#1e54b7',
		'--v-ai-text': '#1e54b7',
		'--v-ai-veil': 'rgba(39, 110, 241, 0.1)',
		'--v-elev-0': '0 0 0 1px rgba(17, 20, 24, 0.15)',
		'--v-elev-1': '0 0 0 1px rgba(17, 20, 24, 0.1), 0 1px 1px rgba(17, 20, 24, 0.2)',
		'--v-elev-2':
			'0 0 0 1px rgba(17, 20, 24, 0.1), 0 1px 1px rgba(17, 20, 24, 0.2), 0 2px 6px rgba(17, 20, 24, 0.2)',
		'--v-elev-3':
			'0 0 0 1px rgba(17, 20, 24, 0.1), 0 2px 4px rgba(17, 20, 24, 0.2), 0 8px 24px rgba(17, 20, 24, 0.2)',
		'--v-elev-4':
			'0 0 0 1px rgba(17, 20, 24, 0.1), 0 4px 8px rgba(17, 20, 24, 0.2), 0 18px 46px 6px rgba(17, 20, 24, 0.2)',
		'--v-map-select': '#000000',
		'--v-map-decision': '#c87619',
		'--v-map-alert': '#cd4246',
		'--v-map-route': '#00a396',
		'--v-map-event': '#276ef1',
		'--v-map-water': '#0369a1',
		'--v-map-marker': '#5f6b7c',
		'--v-map-marker-fill': 'rgba(255, 255, 255, 0.9)',
		'--v-map-casing': 'rgba(255, 255, 255, 0.85)',
		'--v-map-label-bg': 'rgba(255, 255, 255, 0.9)',
		'--v-map-label-ink': '#1c2127',
		'--v-flow-1': '#238551',
		'--v-flow-2': '#8eb125',
		'--v-flow-3': '#d1980b',
		'--v-flow-4': '#c87619',
		'--v-flow-5': '#cd4246',
		'--v-flow-width-1': '3px',
		'--v-flow-width-2': '3.5px',
		'--v-flow-width-3': '4px',
		'--v-flow-width-4': '5px',
		'--v-flow-width-5': '6px',
		'--v-z-content': '10',
		'--v-z-overlay': '20',
		'--v-z-dialog': '30',
		'--v-z-toast': '40',
		'--v-z-tooltip': '50',
		'--v-ws-navbar': '50px',
		'--v-ws-strip': '36px',
		'--v-ws-rail': '44px',
		'--v-ws-left': '300px',
		'--v-ws-right': '400px',
		'--v-ws-right-md': '368px',
		'--v-ws-right-sm': '344px',
		'--v-ws-pane-head': '40px',
		'--v-ws-row': '28px',
		'--v-ws-row-2': '44px',
		'--v-ws-row-head': '30px',
		'--v-ws-tag': '20px',
		'--v-ws-icon-col': '32px',
		'--v-ws-timeline': '124px',
		'--v-ws-audit': '220px',
		'--v-ws-audit-compact': '172px',
		'--v-on-fill': '#ffffff',
		'--v-tooltip-bg': '#404854',
		'--v-tooltip-ink': '#f6f7f9',
		'--v-backdrop': 'rgba(17, 20, 24, 0.5)',
	}
};

/** Token name for a band's value color (BLACK's hairline is band-red). */
export const BAND_TOKEN: Record<Band, { fill: string; edge: string }> = {
	GREEN: { fill: '--v-band-green', edge: '--v-band-green' },
	AMBER: { fill: '--v-band-amber', edge: '--v-band-amber' },
	RED: { fill: '--v-band-red', edge: '--v-band-red' },
	BLACK: { fill: '--v-band-black-fill', edge: '--v-band-black-hairline' }
};

/** One token's value in a theme ('' when the key does not exist). */
function tok(theme: ThemeName, name: string): string {
	return TOKENS[theme]?.[name] ?? '';
}

/** Concrete band color for canvas code (CSS cannot cross into WebGL). */
export function bandColor(band: Band, theme: ThemeName = 'command'): string {
	if (band === 'BLACK') return tok(theme, '--v-band-black-fill');
	return tok(theme, BAND_TOKEN[band]?.fill ?? '--v-band-green');
}

/** Concrete edge/hairline color for a band (BLACK renders a red hairline). */
export function bandEdgeColor(band: Band, theme: ThemeName = 'command'): string {
	return tok(theme, BAND_TOKEN[band]?.edge ?? '--v-band-red') || tok(theme, '--v-band-red');
}

/**
 * Concrete color for an audit level (replaces the per-file maps):
 * decision→data · tool→tool · band→amber · model→ink-4 · info→ink-3 ·
 * error→band-red. Human-actor edges use --v-act by doctrine, not this map.
 */
export function auditLevelColor(level: AuditColorLevel, theme: ThemeName = 'command'): string {
	switch (level) {
		case 'decision':
			return tok(theme, '--v-data');
		case 'tool':
			return tok(theme, '--v-tool');
		case 'band':
			return tok(theme, '--v-band-amber');
		case 'model':
			return tok(theme, '--v-ink-4');
		case 'error':
			return tok(theme, '--v-band-red');
		case 'info':
		default:
			return tok(theme, '--v-ink-3');
	}
}

/** The theme currently set on <html> (defaults to command). */
export function currentTheme(): ThemeName {
	if (typeof document !== 'undefined' && document.documentElement.dataset['theme'] === 'daylight') {
		return 'daylight';
	}
	return 'command';
}

/**
 * Threat-ladder color, expressed ONLY in existing token slots (no second
 * palette): nominal→band-green · guarded→data · moderate→band-amber ·
 * elevated→act · critical→band-red.
 */
export type ThreatLevel = 'nominal' | 'guarded' | 'moderate' | 'elevated' | 'critical';

export function threatColor(level: ThreatLevel, theme: ThemeName = 'command'): string {
	switch (level) {
		case 'nominal':
			return tok(theme, '--v-band-green');
		case 'guarded':
			return tok(theme, '--v-data');
		case 'moderate':
			return tok(theme, '--v-band-amber');
		case 'elevated':
			return tok(theme, '--v-act');
		case 'critical':
		default:
			return tok(theme, '--v-band-red');
	}
}

/**
 * LEGACY congestion colour (the pre-redesign green → red flow chips; the
 * canvas layers move to flowStyle() in slice S3): free→band-green ·
 * light→flow-light · moderate→band-amber · heavy→act · severe→band-red.
 * Accepts a 0..1 congestion index; thresholds as flowStop().
 *
 * The legacy comparisons are kept exactly, so its behaviour is unchanged:
 * a NaN index falls through every `<=` to severe (band-red), as it did
 * before the redesign. (flowStop(), the new ramp's helper, reads NaN as
 * free; the two differ only there.)
 */
export function flowColor(congestionIdx: number, theme: ThemeName = 'command'): string {
	const c = congestionIdx;
	const key =
		c <= 0.2
			? '--v-band-green'
			: c <= 0.4
				? '--v-flow-light'
				: c <= 0.6
					? '--v-band-amber'
					: c <= 0.8
						? '--v-act'
						: '--v-band-red';
	return tok(theme, key);
}

// ── map colours and the traffic-flow ramp (SPEC §2.3, §2.4) ──────────────────

/** The map's colour roles (each one a --v-map-* key). */
export type MapRole =
	| 'select'
	| 'decision'
	| 'alert'
	| 'route'
	| 'event'
	| 'marker'
	| 'marker-fill'
	| 'casing'
	| 'label-bg'
	| 'label-ink';

const MAP_ROLES: readonly MapRole[] = [
	'select',
	'decision',
	'alert',
	'route',
	'event',
	'marker',
	'marker-fill',
	'casing',
	'label-bg',
	'label-ink'
];

/**
 * Concrete colour of a map role for canvas code: selection blue, a waiting
 * decision (orange), an alert (red: watchlisted or stolen), the convoy route
 * (turquoise), corridor events (violet); every other object is `marker`.
 * An unknown role answers the neutral marker colour, never throws.
 */
export function mapColor(role: MapRole, theme: ThemeName = 'command'): string {
	const r = MAP_ROLES.includes(role) ? role : 'marker';
	return tok(theme, `--v-map-${r}`);
}

/** A stop of the five-stop flow ramp: 1 free … 5 jammed. */
export type FlowStop = 1 | 2 | 3 | 4 | 5;

/**
 * The ramp stop of a 0..1 congestion index; thresholds 0.2 / 0.4 / 0.6 /
 * 0.8, upper bound inclusive (as the legacy flowColor). A non-finite or
 * negative index reads as free.
 */
export function flowStop(congestionIdx: number): FlowStop {
	const c = Number.isFinite(congestionIdx) ? congestionIdx : 0;
	if (c <= 0.2) return 1;
	if (c <= 0.4) return 2;
	if (c <= 0.6) return 3;
	if (c <= 0.8) return 4;
	return 5;
}

/** How one stop is drawn: colour, line width (px) and casing (null = none). */
export interface FlowStyle {
	color: string;
	width: number;
	casing: string | null;
}

/**
 * The drawing of a flow stop: free roads recede to thin dim lines, jammed
 * roads come forward thick and bright; a casing (--v-map-casing) from
 * "moderate" (stop 3) up. Command is the neutral luminance ramp; daylight
 * keeps the conventional green → red ramp for the public pages.
 */
export function flowStyle(stop: FlowStop, theme: ThemeName = 'command'): FlowStyle {
	const s = Math.min(5, Math.max(1, Math.round(Number(stop) || 1))) as FlowStop;
	return {
		color: tok(theme, `--v-flow-${s}`),
		width: Number.parseFloat(tok(theme, `--v-flow-width-${s}`)) || 1.5,
		casing: s >= 3 ? tok(theme, '--v-map-casing') : null
	};
}

/**
 * SPEC §16.3 fallback ramp, unused by default: a single-hue cool ramp
 * (Blueprint cerulean 1 → 5) with the neutral ramp's widths and casing rule,
 * for the case the user rejects the neutral luminance ramp. Swapping it in is
 * one change in the flow layer (S3); it sits close to the selection blue.
 */
export const FLOW_RAMP_FALLBACK: readonly Readonly<FlowStyle>[] = Object.freeze([
	{ color: '#c4c4c4', width: 3, casing: null },
	{ color: '#d6d6d6', width: 3.5, casing: null },
	{ color: '#e6e6e6', width: 4, casing: 'rgba(17, 17, 17, 0.8)' },
	{ color: '#f3f3f3', width: 5, casing: 'rgba(17, 17, 17, 0.8)' },
	{ color: '#ffffff', width: 6, casing: 'rgba(17, 17, 17, 0.8)' }
]);

/**
 * Resolve one CSS custom property at runtime — canvas/SVG code path.
 * In the browser this reads the live computed value (so theme flips are
 * honored); outside it falls back to the typed mirror.
 */
export function cssVar(name: string, theme?: ThemeName): string {
	if (typeof document !== 'undefined' && !theme) {
		const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
		if (v) return v;
	}
	return (TOKENS[theme ?? currentTheme()] ?? {})[name] ?? '';
}
