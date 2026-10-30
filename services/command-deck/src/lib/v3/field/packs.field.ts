/**
 * The field AI string pack — the voice report sheet, the object page's road-state, forecast and waterlogging panels,
 * and the public pages' waterlogging card and Listen button. EN here; HI and MR in ./packs.field.hi.ts and
 * ./packs.field.mr.ts (complete for every key: tests/field.unit.mjs and tests/mr-script.unit.mjs check it). Registered
 * additively through registerPack(); no existing pack is edited. Every key starts with `fld_`. The five strings the
 * first paint needs (the top bar entry, the two honest tags) are ./packs.field.core.ts.
 *
 * Copy rules (as the object pack): sentence case, at most one " · " per string, say what happens, what does not and how
 * sure. Honest labels are words in a tag ("Unverified field report", "Simulated", "Modelled"), the code on a data
 * attribute. Numbers arrive already formatted (public pages pass the reader's digits; the console Latin digits).
 * Public copy addresses the reader politely ("Please …"; आपण in Marathi, आप in Hindi).
 */
import { registerPack } from '$lib/i18n/strings';
import { langChunks } from '$lib/i18n/load';

type Fn = (...args: unknown[]) => string;
type FieldPack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');

const en = {

	// ── the voice report sheet ──
	fld_sheet_title: 'Field report by voice',
	fld_sheet_lead: 'Say the place, what you see and how bad it is. It reaches the board as an unverified field report for an officer to confirm.',
	fld_lang_label: 'Spoken language',
	fld_hold: 'Hold to speak',
	fld_hold_hint: 'Press and hold, speak, then let go. Up to 60 seconds.',
	fld_listening: 'Listening',
	fld_release: 'Let go to send',
	fld_transcribing: 'Reading the report on this server',
	fld_mic_denied: 'The microphone is blocked for this page. Allow it in the browser, or type the report below.',
	fld_mic_none: 'This browser cannot record audio here. Type the report below.',
	fld_too_short: 'That was too short. Hold the button while you speak.',
	fld_or_type: 'Or type it',
	fld_text_label: 'Report in words',
	fld_text_ph: 'Type in Marathi or English',
	fld_text_go: 'Read the report',
	fld_example: 'Try saying',
	fld_privacy: 'Audio is not stored. Only the transcript is kept, and no voice is identified.',
	fld_busy: 'The speech model cannot load right now (memory). Try again in a minute.',
	fld_failed: 'The report could not be read. Try again.',
	fld_down: 'The speech service is not reachable right now.',
	fld_close: 'Close',

	// ── the reading ──
	fld_res_title: 'What the report says',
	fld_place: 'Place',
	fld_place_none: 'No place was certain. Pick the right one.',
	fld_place_match: (pct: unknown, said: unknown) => (said ? `Heard “${s(said)}” · ${s(pct)}% match` : `${s(pct)}% match`),
	fld_place_pick: 'Not this place?',
	fld_place_other: 'Another place',
	fld_place_chosen: 'Chosen by the officer',
	fld_kind: 'What',
	fld_severity: 'How bad',
	fld_sev_low: 'Low',
	fld_sev_medium: 'Medium',
	fld_sev_high: 'High',
	fld_kind_waterlogging: 'Waterlogging',
	fld_kind_jam: 'Traffic jam',
	fld_kind_accident: 'Accident',
	fld_kind_tree_fall: 'Tree fall',
	fld_kind_blockade: 'Road blocked',
	fld_kind_procession: 'Procession',
	fld_kind_fire: 'Fire',
	fld_kind_live_wire: 'Live wire',
	fld_kind_other: 'Other',
	fld_transcript: 'Transcript',
	fld_typed: 'Typed report',
	fld_cues: 'Words that decided it',
	fld_asr: (conf: unknown, secs: unknown) => `Speech model confidence ${s(conf)} · ${s(secs)} s of audio`,
	fld_send: 'As an unverified field report, for an officer to confirm.',
	fld_sending: 'Sending',
	fld_sent: 'On the board, awaiting an officer',
	fld_open: 'Open it',
	fld_discard: 'Discard',
	fld_again: 'New report',
	fld_need_officer: 'Name the duty officer first: every board entry carries a name.',
	fld_no_road: 'No road of the city network is within 1.5 km of this place, so it cannot be placed on the board.',
	fld_no_place: 'Pick the place first.',
	fld_send_failed: (detail: unknown) => `The board did not take it: ${s(detail)}`,
	fld_map_alt: (place: unknown) => `Map of ${s(place)}`,

	// ── the camera's road state (object page) ──
	fld_rs_title: 'Road state · AI reading',
	fld_rs_sample: 'Sample still · not live',
	fld_rs_upload: 'Upload a still',
	fld_rs_upload_short: 'Upload',
	fld_rs_uploaded: 'Your still, not stored',
	fld_rs_pick: 'Stills to read',
	fld_rs_read: 'Read road state',
	fld_rs_reading: 'Reading the road',
	fld_rs_no_live: 'No live frame from this camera reaches Sajag, so a credited sample still stands in.',
	fld_rs_credit: (author: unknown, licence: unknown) => `Photo: ${s(author)}, ${s(licence)}`,
	fld_rs_conf: (v: unknown) => `Confidence ${s(v)}`,
	fld_rs_conf_note: 'The model’s own number, not calibrated.',
	fld_rs_depth: 'Water depth',
	fld_rs_vehicles: 'Vehicles seen (rough)',
	fld_rs_rationale: 'Why',
	fld_rs_model: (model: unknown, secs: unknown) => `${s(model)} on this server · ${s(secs)} s`,
	fld_rs_send: 'As an unverified camera report, for an officer to confirm.',
	fld_send_board: 'Send to the board',
	fld_rs_rule: 'Roads and vehicles only: it never describes people and never reads number plates.',
	fld_rs_refused: 'Refused by policy',
	fld_rs_busy: 'The vision model cannot start right now (memory). Try again in a minute.',
	fld_rs_bad_image: 'That file is not an image the model can read. Use a photo from a camera or a phone.',
	fld_rs_filtered: 'A sentence about a person was removed from the answer.',
	fld_rs_modelled_site: 'Camera position is modelled, not a surveyed site.',
	fld_rs_nothing: 'A clear road is not sent to the board.',
	fld_rs_street: 'Nearby street photo',
	fld_rs_street_short: 'Street',
	fld_rs_street_label: 'Reference photo · not live',
	fld_rs_street_taken: (date: unknown) => `Taken ${s(date)}`,
	fld_rs_street_away: (m: unknown) => `${s(m)} m from the camera`,
	fld_rs_street_alt: 'A public street photo near this camera (Mapillary)',
	fld_rs_street_lead: 'A past public photo of the street near this camera stands in for a live frame. Check its date.',
	fld_rs_street_needs_key: 'Nearby street photo needs a Mapillary key on this server, so no call is made.',
	fld_rs_street_none: (m: unknown) => `No public street photo within ${s(m)} m of this camera.`,
	fld_rs_street_down: 'Nearby street photos cannot be reached right now.',
	fld_rs_street_no_position: 'This camera has no position, so there is no nearby street photo.',
	fld_rs_street_failed: 'The street photo did not load. Try again, or use a sample still.',
	fld_state_waterlogged: 'Waterlogged',
	fld_state_blocked: 'Road blocked',
	fld_state_tree_fall: 'Tree fall',
	fld_state_stalled_vehicle: 'Stalled vehicle',
	fld_state_crash_debris: 'Crash debris',
	fld_state_congested: 'Congested',
	fld_state_clear: 'Clear',
	fld_state_unknown: 'Unclear',
	fld_depth_none: 'No water',
	fld_depth_below_kerb: 'Below the kerb',
	fld_depth_up_to_wheel_hub: 'Up to the wheel hubs',
	fld_depth_above_wheel_hub: 'Above the wheel hubs',
	fld_depth_unknown: 'Depth unclear',
	fld_veh_cars: 'Cars',
	fld_veh_buses: 'Buses and trucks',
	fld_veh_two_wheelers: 'Two-wheelers',
	fld_veh_autos: 'Auto-rickshaws',

	// ── the corridor forecast (segment page) ──
	fld_fc_title: 'Next 2 hours · forecast',
	fld_fc_vc: 'Volume to capacity (V/C)',
	fld_fc_band: 'Likely range (p10 to p90)',
	fld_fc_median: 'Forecast',
	fld_fc_baseline: 'Seasonal baseline',
	fld_fc_threshold: 'Heavy at 0.8',
	fld_fc_now: 'Now',
	fld_fc_cross: (min: unknown) => `Crosses 0.8 in ${s(min)} min`,
	fld_fc_above: 'Already above 0.8',
	fld_fc_below: 'Stays below 0.8 for 2 hours',
	fld_fc_summary: (now: unknown, end: unknown, lo: unknown, hi: unknown) => `V/C ${s(now)} now and ${s(end)} in 2 hours (likely ${s(lo)} to ${s(hi)})`,
	fld_fc_speed: (kmh: unknown) => `${s(kmh)} km/h now`,
	fld_tag_simulated: 'Simulated traffic',
	fld_fc_note: 'Forecast on simulated traffic until Mumbai traffic is recorded.',
	fld_fc_proposal: 'A proposal waits for an officer',
	fld_fc_none: 'This road has no forecast.',
	fld_fc_down: 'The forecast service is not reachable right now.',
	fld_fc_model: (m: unknown) => `Model ${s(m)}`,
	fld_fc_min: (m: unknown) => `${s(m)} min`,
	fld_fc_chart: (road: unknown) => `V/C forecast for ${s(road)} over the next 2 hours`,

	// ── waterlogging (segment page) ──
	fld_wl_title: 'Waterlogging · next 2 hours',
	fld_tag_modelled: 'Modelled',
	fld_risk_0: 'Dry',
	fld_risk_1: 'Shallow water',
	fld_risk_2: 'Deep water',
	fld_risk_3: 'Impassable',
	fld_risk_0_sub: 'No water expected on the road.',
	fld_risk_1_sub: 'Puddles of 2 to 10 cm. Traffic slows.',
	fld_risk_2_sub: 'Water of 10 to 30 cm. Small cars and two-wheelers may stall.',
	fld_risk_3_sub: 'Over 30 cm. Most vehicles cannot pass.',
	fld_wl_depth: (band: unknown) => `Depth ${s(band)}`,
	fld_wl_peak_in: (m: unknown) => `Peaks in ${s(m)} min`,
	fld_wl_deep_in: (m: unknown) => `Deep water in ${s(m)} min`,
	fld_wl_now: 'As it is now',
	fld_wl_elevated: 'Elevated road: water does not pond here.',
	fld_wl_down: 'The waterlogging nowcast is not reachable right now.',
	fld_wl_none: 'This road is not in the nowcast network.',
	fld_wl_replay: 'Replay a recorded storm',
	fld_wl_replaying: 'Replaying the storm',
	fld_wl_replay_h: 'This road in the recorded storm',
	fld_wl_replay_label: 'Hindsight: observed rain, modelled depth',
	fld_wl_replay_deep: (at: unknown) => `deep water from ${s(at)}`,
	fld_wl_replay_peak: (at: unknown) => `peak at ${s(at)} IST`,
	fld_wl_replay_dry: 'This road stayed dry in the replay.',
	fld_wl_replay_rain: (mm: unknown) => `${s(mm)} mm of rain fell here in the window.`,
	fld_wl_replay_news: (a: unknown, b: unknown) => `The model flagged ${s(a)} of the ${s(b)} network places the news reported under water.`,
	fld_wl_drivers: 'What drives it',
	fld_drv_rain: 'Rain',
	fld_drv_tide: 'Tide',
	fld_drv_ground: 'Ground and drains',
	fld_drv_pumps: 'Pumps',
	fld_drv_rain_v: (past: unknown, next: unknown) => `${s(past)} mm in the past hour, ${s(next)} mm in the next 2 hours`,
	fld_drv_tide_v: (lvl: unknown) => `${s(lvl)} m at Apollo Bunder`,
	fld_drv_gates_open: 'Outfall gates open',
	fld_drv_gates_shut: 'Outfall gates shut',
	fld_drv_tide_next: (clock: unknown, lvl: unknown) => `High water at ${s(clock)}, ${s(lvl)} m`,
	fld_drv_ground_v: (score: unknown, km: unknown) => `Susceptibility ${s(score)}, ${s(km)} km to a drain`,
	fld_drv_hotspot: (km: unknown) => `Reported hotspot ${s(km)} km away`,
	fld_drv_pumps_v: (a: unknown, b: unknown) => `${s(a)} of ${s(b)} pumps available`,
	fld_lbl_live: 'Live',
	fld_lbl_modelled: 'Modelled',
	fld_lbl_emulated: 'Emulated',
	fld_lbl_simulated: 'Simulated',

	// ── the public pages ──
	fld_pub_title: 'Waterlogging on your road',
	fld_pub_lead: 'Next 2 hours, from rain, the sea tide, ground level and drains.',
	fld_pub_pick: 'Your road',
	fld_pub_all: 'All roads in the city',
	fld_pub_city_dry: 'No road is expected to waterlog in the next 2 hours.',
	fld_pub_city_some: (n: unknown) => `${s(n)} roads may waterlog in the next 2 hours.`,
	fld_pub_city_one: 'One road may waterlog in the next 2 hours.',
	fld_pub_when_now: 'now',
	fld_pub_when_in: (m: unknown) => `in about ${s(m)} minutes`,
	fld_pub_road_0: 'No water is expected on this road in the next 2 hours.',
	fld_pub_road_1: (when: unknown) => `Shallow water (2 to 10 cm) is likely ${s(when)}. Please drive slowly.`,
	fld_pub_road_2: (when: unknown) => `Deep water (10 to 30 cm) is likely ${s(when)}. Please take another road if you can.`,
	fld_pub_road_3: (when: unknown) => `This road may be impassable ${s(when)}. Please avoid it.`,
	fld_pub_elevated: 'This is an elevated road, so water does not collect on it.',
	fld_pub_tide_h: 'Tide at Apollo Bunder',
	fld_pub_tide_rising: (lvl: unknown) => `The tide is rising, now ${s(lvl)} m.`,
	fld_pub_tide_falling: (lvl: unknown) => `The tide is falling, now ${s(lvl)} m.`,
	fld_pub_gates_open: 'The sea outfall gates are open, so rainwater can drain to the sea.',
	fld_pub_gates_shut: 'The sea outfall gates are shut for the high tide, so rainwater drains slowly.',
	fld_pub_next_high: (clock: unknown) => `Next high tide at ${s(clock)}.`,
	fld_pub_now: 'Now',
	fld_pub_gate_line: 'Dashed: gates shut above this level',
	fld_pub_12h: '+12 h',
	fld_pub_next_high_say: (when: unknown) => `The next high tide is ${s(when)}.`,
	fld_say_decimal: (a: unknown, b: unknown) => `${s(a)} point ${s(b)}`,
	fld_say_clock: (part: unknown, h: unknown, m: unknown) => `at ${s(h)}:${String(m ?? '').padStart(2, '0')} ${s(part)}`,
	fld_say_clock_hour: (part: unknown, h: unknown) => `at ${s(h)} o’clock ${s(part)}`,
	fld_say_tomorrow: 'tomorrow',
	fld_say_night: 'at night',
	fld_say_dawn: 'at dawn',
	fld_say_morning: 'in the morning',
	fld_say_noon: 'in the afternoon',
	fld_say_afternoon: 'in the late afternoon',
	fld_say_evening: 'in the evening',
	fld_pub_rain_h: 'Rain',
	fld_pub_rain_none: 'No rain now, and little is expected in the next 2 hours.',
	fld_pub_rain_light: (mm: unknown) => `Light rain: about ${s(mm)} mm in the next 2 hours.`,
	fld_pub_rain_heavy: (mm: unknown) => `Heavy rain: about ${s(mm)} mm in the next 2 hours.`,
	fld_pub_rain_now: (mmh: unknown) => `It is raining now, about ${s(mmh)} mm an hour.`,
	fld_pub_src: 'Modelled from a rain nowcast (Open-Meteo, not a rain gauge), an approximate tide model and ground data. Pump status is emulated.',
	fld_pub_down: 'Waterlogging information is not available right now.',
	fld_pub_loading: 'Checking the roads',
	fld_pub_roads_at_risk: 'Roads to watch',
	fld_listen: 'Listen',
	fld_listen_loading: 'Preparing the voice',
	fld_listen_stop: 'Stop',
	fld_listen_voice: 'Synthetic voice',
	fld_listen_failed: 'The voice is not available right now.',
	fld_listen_busy: 'Too many requests. Please try again in a minute.',
};

export type FieldKey = keyof typeof en;

registerPack('en', en);

/** For tests: the key list and the packs. */
export const FIELD_PACK_KEYS: readonly FieldKey[] = Object.keys(en) as FieldKey[];
export const FIELD_PACKS: Record<string, FieldPack> = { en };

/** Register one language chunk (lib/i18n/load.ts's landing site; additive, first registration wins). */
export function adopt(code: 'hi' | 'mr', pack: FieldPack): void {
	FIELD_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (the deck's FIX-E-PERF2 pattern, as packs.object): HI and MR live only in their own modules. The
 * server render and every non-production run register both before this module finishes evaluating; the production
 * browser awaits the document's language and loads the other on the first switch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.field.hi')).hi);
	adopt('mr', (await import('./packs.field.mr')).mr);
} else {
	await langChunks('packs.field', (code) =>
		code === 'hi' ? import('./packs.field.hi').then((c) => adopt('hi', c.hi)) : import('./packs.field.mr').then((c) => adopt('mr', c.mr)),
	);
}
