/**
 * Sajag V3 tokens (V3-SPEC §4.2) — the TypeScript mirror of src/lib/v3/tokens.css.
 *
 * tests/v3-tokens.unit.mjs pins the two files to each other (same keys, same values, both themes) and
 * proves every text ink is ≥ 4.5:1 on every surface of its theme (`TEXT_INKS` × `SURFACES`, plus each
 * role's ink on its own veil composited over surface 1, the primary and brand buttons and the badge).
 *
 * Components read the CSS custom properties; this module is for code that needs a value as a number
 * or a string outside CSS (the map grade, a canvas fill, the tests).
 */

export type V3Theme = 'night' | 'day';

/** Keys whose value differs per theme (every one is in both theme blocks of tokens.css). */
export const V3_COLOURS = {
	night: {
		'--v3-bg': '#000000',
		'--v3-s1': '#111111',
		'--v3-s2': '#1A1A1A',
		'--v3-s3': '#242424',
		'--v3-s4': '#2E2E2E',
		'--v3-map-bg': '#0A0A0A',
		'--v3-line-1': 'rgba(255, 255, 255, 0.07)',
		'--v3-line-2': 'rgba(255, 255, 255, 0.12)',
		'--v3-line-3': 'rgba(255, 255, 255, 0.2)',
		'--v3-t1': '#FFFFFF',
		'--v3-t2': '#CBCBCB',
		'--v3-t3': '#A6A6A6',
		'--v3-brand': '#276EF1',
		'--v3-brand-strong': '#276EF1',
		'--v3-brand-text': '#7FA8F7',
		'--v3-brand-veil': 'rgba(39, 110, 241, 0.18)',
		'--v3-on-brand': '#FFFFFF',
		'--v3-primary-bg': '#FFFFFF',
		'--v3-primary-hover': '#E2E2E2',
		'--v3-primary-ink': '#000000',
		'--v3-decide': '#FF9F43',
		'--v3-decide-text': '#FFBB7A',
		'--v3-decide-veil': 'rgba(255, 159, 67, 0.14)',
		'--v3-decide-line': 'rgba(255, 159, 67, 0.45)',
		'--v3-on-decide': '#1A1206',
		'--v3-alert': '#FF5C61',
		'--v3-alert-text': '#FF9A9D',
		'--v3-alert-veil': 'rgba(255, 92, 97, 0.14)',
		'--v3-ok': '#3CCB7F',
		'--v3-ok-text': '#7BE0A6',
		'--v3-ok-veil': 'rgba(60, 203, 127, 0.14)',
		'--v3-ai': '#5B91F5',
		'--v3-ai-text': '#8DB4F9',
		'--v3-ai-veil': 'rgba(91, 145, 245, 0.14)',
		'--v3-route': '#2DD4BF',
		'--v3-route-text': '#7EEADB',
		'--v3-route-veil': 'rgba(45, 212, 191, 0.16)',
		'--v3-route-done': 'rgba(45, 212, 191, 0.38)',
		'--v3-dashed': 'rgba(166, 166, 166, 0.55)',
		'--v3-redact-bg': 'rgba(255, 255, 255, 0.06)',
		'--v3-glass': 'rgba(20, 20, 20, 0.82)',
		// the floating-panel glass: the SAME values as the map's own glass (its GLASS constant; tests/v3-tokens.unit.mjs
		// pins the parity), so the Decide sheet, Home's inset and the map's panels are one material
		'--v3-glass-bg': 'rgba(24, 24, 24, 0.9)',
		'--v3-glass-solid': 'rgb(24, 24, 24)',
		'--v3-glass-border': 'rgba(255, 255, 255, 0.14)',
		'--v3-glass-blur': 'blur(14px) saturate(140%)',
		'--v3-scrim': 'rgba(0, 0, 0, 0.98)',
		'--v3-scrim-mid': 'rgba(0, 0, 0, 0.92)',
		'--v3-scrim-soft': 'rgba(0, 0, 0, 0.45)',
		'--v3-scrim-none': 'rgba(0, 0, 0, 0)',
		'--v3-photo-scrim': 'rgba(0, 0, 0, 0.82)',
		'--v3-photo-scrim-soft': 'rgba(0, 0, 0, 0.4)',
		'--v3-photo-scrim-none': 'rgba(0, 0, 0, 0)',
		'--v3-photo-ink': '#FFFFFF',
		'--v3-map-water': '#1B2B3A',
		'--v3-map-park': '#1A2A22',
		'--v3-elev-1': '0 1px 2px rgba(0, 0, 0, 0.35), 0 8px 24px rgba(0, 0, 0, 0.28)',
		'--v3-elev-2': '0 2px 6px rgba(0, 0, 0, 0.4), 0 24px 64px rgba(0, 0, 0, 0.45)',
	},
	day: {
		'--v3-bg': '#F6F6F6',
		'--v3-s1': '#FFFFFF',
		'--v3-s2': '#F3F3F3',
		'--v3-s3': '#EEEEEE',
		'--v3-s4': '#E2E2E2',
		'--v3-map-bg': '#EEEEEE',
		'--v3-line-1': 'rgba(0, 0, 0, 0.08)',
		'--v3-line-2': 'rgba(0, 0, 0, 0.14)',
		'--v3-line-3': 'rgba(0, 0, 0, 0.24)',
		'--v3-t1': '#000000',
		'--v3-t2': '#4B4B4B',
		'--v3-t3': '#545454',
		'--v3-brand': '#276EF1',
		'--v3-brand-strong': '#1E54B7',
		'--v3-brand-text': '#1E54B7',
		'--v3-brand-veil': 'rgba(39, 110, 241, 0.1)',
		'--v3-on-brand': '#FFFFFF',
		'--v3-primary-bg': '#000000',
		'--v3-primary-hover': '#333333',
		'--v3-primary-ink': '#FFFFFF',
		'--v3-decide': '#E07A1F',
		'--v3-decide-text': '#9C3F00',
		'--v3-decide-veil': 'rgba(224, 122, 31, 0.12)',
		'--v3-decide-line': 'rgba(181, 74, 0, 0.45)',
		'--v3-on-decide': '#1A1206',
		'--v3-alert': '#C62828',
		'--v3-alert-text': '#B42020',
		'--v3-alert-veil': 'rgba(198, 40, 40, 0.1)',
		'--v3-ok': '#1E9E5A',
		'--v3-ok-text': '#17703F',
		'--v3-ok-veil': 'rgba(30, 158, 90, 0.12)',
		'--v3-ai': '#276EF1',
		'--v3-ai-text': '#1E54B7',
		'--v3-ai-veil': 'rgba(39, 110, 241, 0.1)',
		'--v3-route': '#0F9F8E',
		'--v3-route-text': '#0A6B61',
		'--v3-route-veil': 'rgba(15, 159, 142, 0.12)',
		'--v3-route-done': 'rgba(15, 159, 142, 0.38)',
		'--v3-dashed': 'rgba(75, 75, 75, 0.55)',
		'--v3-redact-bg': 'rgba(0, 0, 0, 0.06)',
		'--v3-glass': 'rgba(255, 255, 255, 0.86)',
		'--v3-glass-bg': 'rgba(255, 255, 255, 0.9)',
		'--v3-glass-solid': 'rgb(255, 255, 255)',
		'--v3-glass-border': 'rgba(0, 0, 0, 0.1)',
		'--v3-glass-blur': 'blur(14px) saturate(140%)',
		'--v3-scrim': 'rgba(246, 246, 246, 0.98)',
		'--v3-scrim-mid': 'rgba(246, 246, 246, 0.92)',
		'--v3-scrim-soft': 'rgba(246, 246, 246, 0.45)',
		'--v3-scrim-none': 'rgba(246, 246, 246, 0)',
		'--v3-photo-scrim': 'rgba(0, 0, 0, 0.82)',
		'--v3-photo-scrim-soft': 'rgba(0, 0, 0, 0.4)',
		'--v3-photo-scrim-none': 'rgba(0, 0, 0, 0)',
		'--v3-photo-ink': '#FFFFFF',
		'--v3-map-water': '#CFDDEA',
		'--v3-map-park': '#DCE8DC',
		'--v3-elev-1': '0 1px 2px rgba(0, 0, 0, 0.08), 0 8px 24px rgba(0, 0, 0, 0.08)',
		'--v3-elev-2': '0 2px 6px rgba(0, 0, 0, 0.12), 0 24px 64px rgba(0, 0, 0, 0.16)',
	},
} as const;

/** Keys shared by both themes (shape, motion, type, the landing page's poster scale) — the ≥ 1500 px values. */
export const V3_SHARED = {
	'--v3-radius-s': '8px',
	'--v3-radius-m': '12px',
	'--v3-radius-l': '16px',
	'--v3-radius-xl': '22px',
	'--v3-ctl': '36px',
	'--v3-ctl-lg': '44px',
	'--v3-ctl-xl': '56px',
	'--v3-rail': '88px',
	'--v3-top': '68px',
	'--v3-gut': '32px',
	'--v3-ease': 'cubic-bezier(0.2, 0.8, 0.2, 1)',
	'--v3-dur-1': '120ms',
	'--v3-dur-2': '200ms',
	'--v3-dur-3': '320ms',
	'--v3-text-display': '40px',
	'--v3-lh-display': '48px',
	'--v3-text-title': '28px',
	'--v3-lh-title': '36px',
	'--v3-text-heading': '20px',
	'--v3-lh-heading': '28px',
	'--v3-text-sub': '17px',
	'--v3-lh-sub': '24px',
	'--v3-text-body': '15px',
	'--v3-lh-body': '22px',
	'--v3-text-meta': '13px',
	'--v3-lh-meta': '18px',
	'--v3-text-micro': '12px',
	'--v3-lh-micro': '16px',
	'--v3-text-stat': '30px',
	'--v3-lh-stat': '36px',
	// the landing page (/welcome) only: a poster may exceed the console's type scale (V3-LANDING)
	'--v3-land-hero': '112px',
	'--v3-land-lh-hero': '112px',
	'--v3-land-section': '52px',
	'--v3-land-lh-section': '60px',
	'--v3-land-lead': '22px',
	'--v3-land-lh-lead': '34px',
	'--v3-land-figure': '80px',
	'--v3-land-lh-figure': '84px',
	'--v3-land-lockup': '80px',
	'--v3-land-max': '1440px',
} as const;

/** Below 1500 px (§6.10): the overrides of the shared keys. */
export const V3_COMPACT = {
	'--v3-rail': '76px',
	'--v3-top': '60px',
	'--v3-gut': '24px',
	'--v3-text-display': '32px',
	'--v3-lh-display': '40px',
	'--v3-text-title': '24px',
	'--v3-lh-title': '32px',
	'--v3-text-stat': '26px',
	'--v3-lh-stat': '32px',
	'--v3-land-hero': '92px',
	'--v3-land-lh-hero': '92px',
	'--v3-land-section': '44px',
	'--v3-land-lh-section': '52px',
	'--v3-land-lead': '20px',
	'--v3-land-lh-lead': '30px',
	'--v3-land-figure': '64px',
	'--v3-land-lh-figure': '68px',
	'--v3-land-lockup': '64px',
	'--v3-land-max': '1240px',
} as const;

/** The width where the console steps down to the 1366-class layout. */
export const V3_COMPACT_BELOW = 1500;

/** The surfaces text sits on (every one is measured against every text ink). */
export const SURFACES = ['--v3-bg', '--v3-s1', '--v3-s2', '--v3-s3', '--v3-s4'] as const;

/** Every ink used for text on a surface. */
export const TEXT_INKS = [
	'--v3-t1',
	'--v3-t2',
	'--v3-t3',
	'--v3-brand-text',
	'--v3-decide-text',
	'--v3-alert-text',
	'--v3-ok-text',
	'--v3-ai-text',
	'--v3-route-text',
] as const;

/** Each role's text on its own veil (a tag), the veil composited over surface 1. */
export const VEIL_PAIRS = [
	['--v3-brand-text', '--v3-brand-veil'],
	['--v3-decide-text', '--v3-decide-veil'],
	['--v3-alert-text', '--v3-alert-veil'],
	['--v3-ok-text', '--v3-ok-veil'],
	['--v3-ai-text', '--v3-ai-veil'],
	['--v3-route-text', '--v3-route-veil'],
] as const;

/** Text on a filled control: [ink, fill]. */
export const FILL_PAIRS = [
	['--v3-primary-ink', '--v3-primary-bg'],
	['--v3-primary-ink', '--v3-primary-hover'],
	['--v3-on-brand', '--v3-brand-strong'],
	['--v3-on-decide', '--v3-decide'],
] as const;

/** Every key of a theme, resolved (colours of the theme + the shared keys). */
export function v3Tokens(theme: V3Theme): Record<string, string> {
	return { ...V3_SHARED, ...V3_COLOURS[theme] };
}

/**
 * The map grade's palette (V3-SPEC §4.6; redesign/v3/prototype/tools/grade.py, frozen): each ground class
 * as [dark end, light end] of its luminance ramp. map/tiles.ts applies it to every OSM tile.
 */
export const MAP_PALETTE = {
	night: {
		land: ['#0E0E0E', '#2C2C2C'],
		water: ['#0B1622', '#1B2B3A'],
		park: ['#0E1A15', '#1A2A22'],
		road: ['#2E2E2E', '#4D4D4D'],
		lo: 52,
		hi: 108,
		gamma: 1.15,
	},
	day: {
		land: ['#BDBDBD', '#F6F6F6'],
		water: ['#B7CFE2', '#D3E3F0'],
		park: ['#CFDCCF', '#E4ECE2'],
		road: ['#FFFFFF', '#FFFFFF'],
		lo: 52,
		hi: 108,
		gamma: 0.8,
	},
} as const;
