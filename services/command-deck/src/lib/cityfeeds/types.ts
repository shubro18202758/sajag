/**
 * The city-feeds service's answers (services/cityfeeds, /api/cityfeeds through the deck). Only the fields the deck
 * reads are typed; every one may be missing (the client never invents a value).
 */

export type FeedLabel = 'LIVE' | 'MODELLED' | 'EMULATED' | 'SIMULATED' | 'UNAVAILABLE' | 'AGGREGATE' | 'INDICATIVE' | 'RECORDED';

export interface FeedMeta {
	feed: string;
	mode: 'LIVE' | 'RECORDED' | 'UNAVAILABLE';
	stale: boolean;
	error: string | null;
	fetched_at: string | null;
	source: string;
	home: string;
}

export interface Chip {
	value: number | string | null;
	unit: string | null;
	band: string | null;
	label: FeedLabel;
	sub_label?: string;
	source: string;
	as_of: string | null;
	mode: FeedMeta['mode'];
	stale: boolean;
	detail: Record<string, unknown> | null;
	next_48h?: { aqi: number; band: string; band_en: string; band_mr: string; band_hi: string } | null;
	proposal?: boolean;
	/** Air only: the stations' OBSERVED National AQI (CPCB via data.gov.in), null until a keyed provider answers. */
	observed?: ObservedNaqi | null;
}

/** The worst CPCB station's National AQI from its own PM averages (label OBSERVED, sub-label INDICATIVE). */
export interface ObservedNaqi {
	aqi: number;
	band: string;
	site: string;
	prominent: string;
	at: string | null;
	label: 'OBSERVED';
	sub_label?: string;
	source: string;
}

export type ChipId = 'air' | 'heat' | 'cyclone' | 'river' | 'quake' | 'tide';

export interface FeedSummary {
	generated_at: string;
	city: string;
	chips: Partial<Record<ChipId, Chip>>;
}

export interface Naqi {
	aqi: number;
	band: string;
	band_en: string;
	band_mr: string;
	band_hi: string;
	prominent: string;
	health: string;
	label: string;
}

export interface AirStation {
	id: string;
	name: string;
	name_mr: string;
	lat: number;
	lon: number;
	coord_source: string;
	now: { at: string | null; pm25: number | null; pm10: number | null; no2: number | null; o3: number | null; us_aqi: number | null };
	pm25_24h: number | null;
	pm10_24h: number | null;
	naqi: Naqi | null;
	forecast: Array<{ window_h: [number, number]; naqi: Naqi | null }>;
}

export interface Proposal {
	proposal_id: string;
	kind: string;
	summary: string;
	state: 'proposed';
	text?: { en?: string; mr?: string; hi?: string };
	actions: Array<{ verb: string; target_urn: string; params: Record<string, unknown>; requires_officer: boolean }>;
	labels: string[];
}

export type ProposalOrNone = Proposal | { none: string };

export interface AirView {
	label: string;
	what: string;
	naqi_label: string;
	naqi_source: { publisher: string; document: string; url: string };
	grid_note: string;
	stations: AirStation[];
	city: (Naqi & { worst_site: string; worst_site_name: string; worst_site_mr: string; pm25_24h: number | null; pm10_24h: number | null }) | null;
	/** The stations' own measurements from the keyed services; label NONE when no provider has a key. */
	observed?: { label: 'OBSERVED' | 'NONE'; sites_observed: number; city_naqi: ObservedNaqi | null };
	feed: FeedMeta;
	proposal: ProposalOrNone;
}

export interface GeoFeature {
	type: 'Feature';
	geometry: { type: 'Point' | 'LineString' | 'Polygon'; coordinates: unknown };
	properties: Record<string, unknown> & { kind: string };
}

export interface CycloneView {
	type: 'FeatureCollection';
	features: GeoFeature[];
	label: string;
	active: Array<{
		name: string;
		alertlevel: string;
		distance_km: number;
		bearing: string;
		bearing_deg: number;
		position: { lat: number; lon: number; at: string | null };
		closest_approach: { distance_km: number } | null;
		/** The wind buffer (km/h) the city centre lies inside, or null (the service's older field name below). */
		city_in_wind_buffer_kmh?: number | null;
		kolkata_in_wind_buffer_kmh?: number | null;
		severity: string | null;
		report: string | null;
	}>;
	nearest: CycloneView['active'][number] | null;
	feed: FeedMeta;
	proposal: ProposalOrNone;
	sources: Record<string, { publisher: string; url: string; note?: string }>;
}

/** Any other feed view the sheet shows: its feed meta, sources and (maybe) a proposal. */
export interface AnyView {
	label?: string;
	what?: string;
	feed?: FeedMeta;
	proposal?: ProposalOrNone;
	sources?: unknown;
	[k: string]: unknown;
}
