/**
 * The honest label of a board entry this stream creates — read from the event's metadata.source, which the oracle's
 * city picture exposes. Small on purpose: the object page and the public projection import it without the field model.
 */
/** metadata.source of a board entry this stream creates (the public projection drops both; the object page labels both). */
export const FIELD_SOURCES = { voice: 'field-voice', camera: 'camera-ai' } as const;
export const FIELD_VERIFICATION = { voice: 'UNVERIFIED-FIELD', camera: 'UNVERIFIED-CAMERA' } as const;

/** The field- or camera-sourced label an event row carries (its metadata.source), else null. */
export function fieldLabelOf(meta: unknown): 'UNVERIFIED-FIELD' | 'UNVERIFIED-CAMERA' | null {
	const src = typeof meta === 'object' && meta !== null && !Array.isArray(meta) ? (meta as Record<string, unknown>).source : null;
	if (src === FIELD_SOURCES.voice) return FIELD_VERIFICATION.voice;
	if (src === FIELD_SOURCES.camera) return FIELD_VERIFICATION.camera;
	return null;
}
