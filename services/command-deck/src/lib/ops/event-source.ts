/**
 * Whether a corridor event's metadata makes it EMULATED — the deck's mirror
 * of the oracle's `event_source` (traffic_oracle/city/common.py): the
 * emulator (or its living city) opened it, OR its authorising evidence is
 * emulated (`metadata.evidence_source`, stamped by the oracle — HON-4: a
 * pursuit of an emulated vehicle opened from an emulated sighting is
 * emulated whoever opened it). Pure; shared by the operator board
 * (ops/client.ts) and the citizen projection (citizen/public-api.server.ts),
 * so the two never disagree.
 */
export function emulatedByMetadata(metadata: unknown): boolean {
	if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) return false;
	const m = metadata as Record<string, unknown>;
	const src = String(m.source ?? '').toLowerCase();
	if (src === 'event-emulator' || src.includes('emulat')) return true;
	if (String(m.evidence_source ?? '').toLowerCase().includes('emulat')) return true;
	return String(m.mode ?? '').toLowerCase() === 'living_city';
}
