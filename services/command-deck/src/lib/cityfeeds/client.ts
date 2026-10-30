/**
 * The city-feeds client, through the deck origin only (/api/cityfeeds → services/cityfeeds, prefix stripped; a fixed
 * proxy rule in hooks.server.ts and vite.config.ts). The same typed failures as the AI clients ($lib/ai/client:
 * AiNotDeployed, AiSignIn, AiDown); a missing list is an empty list, never an invented value.
 */
import { aiJson } from '$lib/ai/client';
import type { AirView, AnyView, ChipId, CycloneView, FeedSummary } from './types';

export const FEEDS_PATH = '/api/cityfeeds';

/** The detailed answer behind each chip (the sheet reads it on open). */
export const CHIP_ROUTE: Readonly<Record<ChipId, string>> = Object.freeze({
	air: '/feeds/air',
	heat: '/feeds/heat',
	cyclone: '/feeds/cyclones',
	river: '/feeds/river',
	quake: '/feeds/quakes',
	tide: '/feeds/tide-table',
});

const arr = <T>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

export async function getSummary(): Promise<FeedSummary> {
	const d = await aiJson<FeedSummary>(`${FEEDS_PATH}/feeds/summary`, {}, 45_000);
	return { ...d, chips: d.chips ?? {} };
}

export async function getAir(): Promise<AirView> {
	const d = await aiJson<AirView>(`${FEEDS_PATH}/feeds/air`, {}, 45_000);
	return { ...d, stations: arr(d.stations) };
}

export async function getCyclones(): Promise<CycloneView> {
	const d = await aiJson<CycloneView>(`${FEEDS_PATH}/feeds/cyclones`, {}, 45_000);
	return { ...d, features: arr(d.features), active: arr(d.active) };
}

export async function getView(id: ChipId): Promise<AnyView> {
	return aiJson<AnyView>(`${FEEDS_PATH}${CHIP_ROUTE[id]}`, {}, 45_000);
}
