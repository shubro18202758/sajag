/**
 * What a City vitals variant renders (the card or the Info tab). The root,
 * gods-eye/hud/CityVitals.svelte, derives it once from the stores and
 * publishes the same figures to window.__GODS_EYE__.vitals; the variants
 * only draw it. Every figure is a count of fused rows or a server health
 * field; a rung that cannot answer says so, never as zero-and-green.
 */
import type { BandCode, BrainHealth, EmulatorRunRow, IngestHealth, LivingCityStatus, RetentionHealth } from '$lib/gods-eye/city-api';
import type { SignalPlansDoc } from '$lib/ops/types';
import type { Rung } from '$lib/gods-eye/hud/vitals.svelte';
import type { CardFigures } from './figures';

export interface PostureView {
	band: BandCode | null;
	urn: string | null;
	label: string;
	events: number;
	at: number | null;
	basis: 'reading' | 'transition' | 'none';
	source: 'events' | 'city-band';
	simulated: boolean;
	emulated: boolean;
	heldSince: number | null;
	engineStale: boolean;
	staleSince: number | null;
	/** Seconds since the newest reading; null when unknown. */
	ageSec: number | null;
	/** Older than the stale threshold (10 min). */
	stale: boolean;
	/** Seconds the band has held; null when unknown. */
	heldSec: number | null;
}

export interface CountLink {
	n: number;
	/** The first object behind the count (a click selects it), or null. */
	urn: string | null;
	/** Its id for the /ops deep link, or null. */
	id: string | null;
}

export interface VitalsView {
	now: number;
	replay: boolean;
	registry: { size: number; ageSec: number | null; status: string; note: string | null; tookMs: number | null };
	/** The card's figures (the card variant only; the Info tab never builds the object model). */
	card: CardFigures | null;
	posture: PostureView | null;
	events: { total: number; kinds: { kind: string; total: number; active: number; emulated: number; urn: string }[] };
	decisions: {
		/** Rows waiting (the snapshot's decisions.total). */
		total: number;
		/** Decision units waiting: the Inbox's and the card's count (SPEC §7.4). */
		units: number;
		/** True when `units` is decisionUnits() (a unit source is registered). */
		fromUnits: boolean;
		escortProposals: number;
		echallans: CountLink;
		stolen: CountLink;
		withheld: CountLink;
		requested: CountLink;
		ambulance: CountLink;
	};
	units: { out: number; enRoute: number; onScene: number; urn: string | null };
	anpr: { hits: number; reads: number; reporting: number; cameras: number; urn: string | null };
	ethics: {
		retention: Rung<RetentionHealth>;
		lawful: [string, number][];
		officer: string | null;
	};
	signals: {
		plans: SignalPlansDoc | null;
		note: string | null;
		programs: number;
		green: number;
		amber: number;
		red: number;
	};
	brain: Rung<BrainHealth>;
	feeds: {
		ingest: Rung<IngestHealth>;
		trafficSimulated: boolean;
		roads: { traced: number; schematic: number; known: boolean };
		sightingAgeSec: number | null;
		runs: Rung<EmulatorRunRow[]>;
		living: Rung<LivingCityStatus>;
	};
}
