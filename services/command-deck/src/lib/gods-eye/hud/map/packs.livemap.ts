/**
 * The live map's canvas words (the landmarks, live-values and flow layers' labels), in English, Marathi and Hindi.
 * Values stay in Latin digits in all three languages. Honest words in sentence case: emulated (a feed stand-in),
 * modelled (a computed estimate), live (a real feed), simulated (a scenario feed). Every key starts with `lm_`.
 */
import { registerPack } from '$lib/i18n/strings';

type Fn = (...args: unknown[]) => string;
const s = (v: unknown) => String(v ?? '');

export const en: Record<string, string | Fn> = {
	lm_src_emulated: 'emulated',
	lm_road_line2: (kmh: unknown, vc: unknown, sim: unknown) => `${s(kmh)} km/h${vc != null ? ` · V/C ${s(vc)}` : ''}${sim ? ' (simulated)' : ''}`,
	lm_pumps: (name: unknown, up: unknown, total: unknown) => `${s(name)} · pumps ${s(up)}/${s(total)} (emulated)`,
	lm_tide: (name: unknown, m: unknown, dir: unknown) => `${s(name)} · ${s(m)} m ${s(dir)} (modelled)`,
	lm_rising: 'rising',
	lm_falling: 'falling',
	lm_gates_shut: 'outfall gates shut',
	lm_heat: (name: unknown, c: unknown) => `${s(name)} · ${s(c)} °C (modelled)`,
	lm_river: (name: unknown, m: unknown) => `${s(name)} · ${s(m)} m (live gauge)`,
	lm_fire: (ago: unknown) => `Satellite heat spot · ${s(ago)} ago (live)`,
	lm_quake: (mag: unknown, ago: unknown) => `Earthquake M${s(mag)} · ${s(ago)} ago (live)`,
	lm_air: (name: unknown, aqi: unknown) => `${s(name)} · AQI ${s(aqi)} (modelled)`,
	lm_road: (name: unknown, kmh: unknown) => `${s(name)} · ${s(kmh)} km/h`,
	lm_road_vc: (name: unknown, vc: unknown) => `${s(name)} · V/C ${s(vc)}`,
	lm_fresh: (title: unknown, ago: unknown) => `${s(title)} · ${s(ago)}`,
	lm_now: 'just now',
	lm_unit: (id: unknown, what: unknown) => `${s(id)} · ${s(what)}`,
	lm_patrol: 'patrol',
	lm_standby: 'standby',
	lm_enroute: 'en route',
	lm_onscene: 'on scene',
};

export const mr: Record<string, string | Fn> = {
	lm_src_emulated: 'एम्युलेटेड',
	lm_road_line2: (kmh: unknown, vc: unknown, sim: unknown) => `${s(kmh)} km/h${vc != null ? ` · V/C ${s(vc)}` : ''}${sim ? ' (सिम्युलेटेड)' : ''}`,
	lm_pumps: (name: unknown, up: unknown, total: unknown) => `${s(name)} · पंप ${s(up)}/${s(total)} (एम्युलेटेड)`,
	lm_tide: (name: unknown, m: unknown, dir: unknown) => `${s(name)} · ${s(m)} m ${s(dir)} (मॉडेल-आधारित)`,
	lm_rising: 'वाढत आहे',
	lm_falling: 'उतरत आहे',
	lm_gates_shut: 'आउटफॉल गेट बंद',
	lm_heat: (name: unknown, c: unknown) => `${s(name)} · ${s(c)} °C (मॉडेल-आधारित)`,
	lm_river: (name: unknown, m: unknown) => `${s(name)} · ${s(m)} m (लाइव्ह मापक)`,
	lm_fire: (ago: unknown) => `उपग्रहाने टिपलेले उष्ण ठिकाण · ${s(ago)} पूर्वी (लाइव्ह)`,
	lm_quake: (mag: unknown, ago: unknown) => `भूकंप M${s(mag)} · ${s(ago)} पूर्वी (लाइव्ह)`,
	lm_air: (name: unknown, aqi: unknown) => `${s(name)} · AQI ${s(aqi)} (मॉडेल-आधारित)`,
	lm_road: (name: unknown, kmh: unknown) => `${s(name)} · ${s(kmh)} km/h`,
	lm_road_vc: (name: unknown, vc: unknown) => `${s(name)} · V/C ${s(vc)}`,
	lm_fresh: (title: unknown, ago: unknown) => `${s(title)} · ${s(ago)}`,
	lm_now: 'आत्ताच',
	lm_unit: (id: unknown, what: unknown) => `${s(id)} · ${s(what)}`,
	lm_patrol: 'गस्त',
	lm_standby: 'सज्ज',
	lm_enroute: 'मार्गावर',
	lm_onscene: 'घटनास्थळी',
};

export const hi: Record<string, string | Fn> = {
	lm_src_emulated: 'अनुकृत',
	lm_road_line2: (kmh: unknown, vc: unknown, sim: unknown) => `${s(kmh)} किमी/घं${vc != null ? ` · V/C ${s(vc)}` : ''}${sim ? ' (सिम्युलेटेड)' : ''}`,
	lm_pumps: (name: unknown, up: unknown, total: unknown) => `${s(name)} · पंप ${s(up)}/${s(total)} (अनुकृत)`,
	lm_tide: (name: unknown, m: unknown, dir: unknown) => `${s(name)} · ${s(m)} मी ${s(dir)} (मॉडल आधारित)`,
	lm_rising: 'बढ़ रहा',
	lm_falling: 'घट रहा',
	lm_gates_shut: 'आउटफ़ॉल गेट बंद',
	lm_heat: (name: unknown, c: unknown) => `${s(name)} · ${s(c)} °C (मॉडल आधारित)`,
	lm_river: (name: unknown, m: unknown) => `${s(name)} · ${s(m)} मी (लाइव गेज)`,
	lm_fire: (ago: unknown) => `उपग्रह ताप बिंदु · ${s(ago)} पहले (लाइव)`,
	lm_quake: (mag: unknown, ago: unknown) => `भूकंप M${s(mag)} · ${s(ago)} पहले (लाइव)`,
	lm_air: (name: unknown, aqi: unknown) => `${s(name)} · AQI ${s(aqi)} (मॉडल आधारित)`,
	lm_road: (name: unknown, kmh: unknown) => `${s(name)} · ${s(kmh)} किमी/घं`,
	lm_road_vc: (name: unknown, vc: unknown) => `${s(name)} · V/C ${s(vc)}`,
	lm_fresh: (title: unknown, ago: unknown) => `${s(title)} · ${s(ago)}`,
	lm_now: 'अभी',
	lm_unit: (id: unknown, what: unknown) => `${s(id)} · ${s(what)}`,
	lm_patrol: 'गश्त',
	lm_standby: 'तैयार',
	lm_enroute: 'रास्ते में',
	lm_onscene: 'मौके पर',
};

registerPack('en', en);
registerPack('mr', mr);
registerPack('hi', hi);
