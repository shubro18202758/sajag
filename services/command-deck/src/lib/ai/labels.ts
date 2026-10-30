/**
 * Honest labels for the AI services (PLAN rule 2): every number the console shows from forecast, hydro or the
 * twin carries where it came from — visibly, quietly (a small tag, never a banner):
 *
 *   live         a real live feed (the Open-Meteo rain nowcast — a model product, not a gauge, and the tag's tip
 *                says so)
 *   observed     a measured record (the IMD observatory's totals in the replay: Santacruz / Colaba for Mumbai)
 *   modelled     computed by a model (the tide, the ponding, V/C from speed, the twin's metrics)
 *   emulated     a feed stand-in (the BMC storm-water pumping-station adapter until access is granted)
 *   simulated    a scenario (the forecast's traffic history until Mumbai traffic is recorded; the twin's demand)
 *   hindsight    observed rain replayed as if it had been a perfect nowcast (the 19 Aug 2025 snapshot)
 *   archive      a gridded reanalysis archive (the replay's Open-Meteo run)
 *   unavailable  the feed did not answer (never shown as zero)
 *
 * The services spell their labels in capitals ("MODELLED (approximate)", "RAIN-UNAVAILABLE"); provOf() reads
 * any of them. Pure: no store, no DOM (tests/ai-ops.unit.mjs).
 */

export type Prov = 'live' | 'observed' | 'modelled' | 'emulated' | 'simulated' | 'hindsight' | 'archive' | 'unavailable';

export const PROVS: readonly Prov[] = ['live', 'observed', 'archive', 'modelled', 'hindsight', 'emulated', 'simulated', 'unavailable'];

/** A raw service label → its kind (null for anything unrecognised: never guessed). */
export function provOf(raw: string | null | undefined): Prov | null {
	const s = String(raw ?? '')
		.trim()
		.toUpperCase();
	if (!s) return null;
	if (s.includes('UNAVAILABLE')) return 'unavailable';
	if (s.startsWith('HINDSIGHT')) return 'hindsight';
	if (s.startsWith('SIMULATED') || s.startsWith('SYNTHETIC')) return 'simulated';
	if (s.startsWith('EMULATED')) return 'emulated';
	if (s.startsWith('MODELLED') || s.startsWith('MODELED')) return 'modelled';
	if (s.startsWith('ARCHIVE')) return 'archive';
	if (s.startsWith('OBSERVED')) return 'observed';
	if (s.startsWith('LIVE')) return 'live';
	return null;
}

/** How a label looks: its pack key (and tooltip key), the V3 tag tone and glyph. Measured ones stay plain. */
export const PROV_LOOK: Readonly<Record<Prov, { key: string; tip: string; tone: 'neutral' | 'dashed' | 'ghost'; glyph: string | null }>> = {
	live: { key: 'ai_prov_live', tip: 'ai_prov_live_tip', tone: 'neutral', glyph: null },
	observed: { key: 'ai_prov_observed', tip: 'ai_prov_observed_tip', tone: 'neutral', glyph: 'eye' },
	archive: { key: 'ai_prov_archive', tip: 'ai_prov_archive_tip', tone: 'ghost', glyph: 'history' },
	modelled: { key: 'ai_prov_modelled', tip: 'ai_prov_modelled_tip', tone: 'dashed', glyph: 'graph' },
	hindsight: { key: 'ai_prov_hindsight', tip: 'ai_prov_hindsight_tip', tone: 'dashed', glyph: 'history' },
	emulated: { key: 'ai_prov_emulated', tip: 'ai_prov_emulated_tip', tone: 'dashed', glyph: 'flask' },
	simulated: { key: 'ai_prov_simulated', tip: 'ai_prov_simulated_tip', tone: 'dashed', glyph: 'shuffle' },
	unavailable: { key: 'ai_prov_unavailable', tip: 'ai_prov_unavailable_tip', tone: 'ghost', glyph: 'alert' },
};

/** The distinct kinds in a label list, weakest last (an unrecognised label is dropped, never invented). */
export function provList(labels: readonly (string | null | undefined)[]): Prov[] {
	const seen = new Set<Prov>();
	for (const l of labels) {
		const p = provOf(l);
		if (p) seen.add(p);
	}
	return PROVS.filter((p) => seen.has(p));
}

/** The weakest kind in a list: what a combined figure must say about itself (a simulated input makes it simulated). */
export function weakest(labels: readonly (string | null | undefined)[]): Prov | null {
	const list = provList(labels);
	return list.length ? list[list.length - 1] : null;
}
