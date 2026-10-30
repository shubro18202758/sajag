/**
 * The V3 glyph set (V3-SPEC §4.4): 24-unit grid, 1.8 stroke, round caps and joins, drawn for Sajag.
 * **Type is the icon; state is the colour.** One glyph per noun everywhere (flask = emulated, shuffle =
 * simulated, lock = masked, eye-off = withheld, shield = rule, badge = officer, cube = 3D). Never a person.
 *
 * Rendered by Glyph.svelte (stroke = currentColor). The path data is the approved prototype's
 * (redesign/v3/prototype/sajag.js) plus `volume` (the alert chime).
 */
export const GLYPHS = {
	home: 'M3.5 11 12 4l8.5 7v8.5a1 1 0 0 1-1 1H15v-6H9v6H4.5a1 1 0 0 1-1-1z',
	map: 'M9 4 3.5 6.3v13.5L9 17.5l6 2.5 5.5-2.3V4.2L15 6.5zM9 4v13.5M15 6.5V20',
	decide: 'M4 13.5h4.2l1.6 3h4.4l1.6-3H20M4 13.5 6.4 5.6a1 1 0 0 1 1-.6h9.2a1 1 0 0 1 1 .6L20 13.5V19a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z',
	spark: 'M12 3.5l1.9 4.9 4.9 1.9-4.9 1.9L12 17.1l-1.9-4.9-4.9-1.9 4.9-1.9zM18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z',
	megaphone: 'M4 10v4a1 1 0 0 0 1 1h2l6.5 4V5L7 9H5a1 1 0 0 0-1 1zM17 9.2a4 4 0 0 1 0 5.6M19.4 6.8a7.5 7.5 0 0 1 0 10.4',
	analyst: 'M3.5 4.5h7v7h-7zM13.5 4.5h7v4h-7zM13.5 11.5h7v8h-7zM3.5 14.5h7v5h-7z',
	search: 'M11 4.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM20 20l-4.4-4.4',
	bell: 'M6 16.5V11a6 6 0 1 1 12 0v5.5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0',
	chevR: 'M9.5 5.5 16 12l-6.5 6.5',
	chevL: 'M14.5 5.5 8 12l6.5 6.5',
	chevD: 'M5.5 9.5 12 16l6.5-6.5',
	chevU: 'M5.5 14.5 12 8l6.5 6.5',
	close: 'M6.5 6.5l11 11M17.5 6.5l-11 11',
	plus: 'M12 5v14M5 12h14',
	layers: 'M12 3.5 2.8 8.4 12 13.3l9.2-4.9zM2.8 12.7 12 17.6l9.2-4.9M2.8 16.6 12 21.5l9.2-4.9',
	filter: 'M4 5.5h16l-6.2 7.6v5.4l-3.6 1.8v-7.2z',
	clock: 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 7.5V12l3 2',
	route: 'M6 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM18 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM6 16V9.5A3.5 3.5 0 0 1 9.5 6H12M18 8v6.5a3.5 3.5 0 0 1-3.5 3.5H12',
	car: 'M4 16.5h16V13l-1.9-5.2A1.6 1.6 0 0 0 16.6 6.8H7.4a1.6 1.6 0 0 0-1.5 1L4 13zM4 13h16M6.2 16.5v2.2M17.8 16.5v2.2M7.5 10h9',
	anpr: 'M4 8.5V5h3.5M16.5 5H20v3.5M20 15.5V19h-3.5M7.5 19H4v-3.5M7.5 10.2h9v3.6h-9z',
	shield: 'M12 3.2 19.5 6v5.6c0 4.3-3.1 7.9-7.5 9.2-4.4-1.3-7.5-4.9-7.5-9.2V6z',
	lock: 'M6.5 11h11v9h-11zM8.8 11V8.2a3.2 3.2 0 0 1 6.4 0V11',
	eyeoff: 'M3.5 3.5l17 17M10.4 6.2A9.6 9.6 0 0 1 12 6c4.8 0 8.2 4.2 9.3 6-.5.8-1.5 2.1-2.9 3.3M6.7 7.6C4.8 8.9 3.4 10.8 2.7 12c1.1 1.8 4.5 6 9.3 6 1.5 0 2.9-.4 4.1-1M9.9 9.9a3 3 0 0 0 4.2 4.2',
	eye: 'M2.7 12C3.8 10.2 7.2 6 12 6s8.2 4.2 9.3 6c-1.1 1.8-4.5 6-9.3 6s-8.2-4.2-9.3-6zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
	badge: 'M5.5 3.5h13v17h-13zM9 9.2a3 3 0 1 0 6 0 3 3 0 0 0-6 0M8.5 16.5h7',
	check: 'M5 12.5l4.5 4.5L19 7.5',
	checkc: 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM8.3 12.2l2.5 2.5 5-5.2',
	info: 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 11v5M12 7.8h.01',
	alert: 'M12 4.2 2.9 19.5h18.2zM12 10v4.3M12 16.9h.01',
	news: 'M5 5h11v14H6.5A2.5 2.5 0 0 1 4 16.5V8M16 9h3.5v7.5A2.5 2.5 0 0 1 17 19M8 9h5M8 12.5h5M8 16h3',
	verified: 'M12 3l2.3 1.7 2.9-.1.9 2.8 2.3 1.7-.9 2.8.9 2.8-2.3 1.7-.9 2.8-2.9-.1L12 21l-2.3-1.7-2.9.1-.9-2.8-2.3-1.7.9-2.8-.9-2.8 2.3-1.7.9-2.8 2.9.1zM8.6 12l2.3 2.3 4.5-4.6',
	unverified: 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 8v4.6M12 15.6h.01',
	flask: 'M9.5 3.5h5M10.2 3.5v5.8L5 18.1A1.9 1.9 0 0 0 6.6 21h10.8a1.9 1.9 0 0 0 1.6-2.9l-5.2-8.8V3.5M7.6 15h8.8',
	shuffle: 'M3 7h3.5c4 0 5.5 10 9.5 10H21M3 17h3.5c1.4 0 2.4-1.2 3.3-2.8M14.2 9.8C15 8.2 16 7 17.5 7H21M18.5 4.5 21 7l-2.5 2.5M18.5 14.5 21 17l-2.5 2.5',
	send: 'M4.5 11.8 20 4.5l-6.6 15.4-2.4-6.6zM11 13.3 20 4.5',
	share: 'M12 15V3.5M8 7.5l4-4 4 4M5 12v7.5h14V12',
	more: 'M5 12h.01M12 12h.01M19 12h.01',
	arrowR: 'M5 12h14M13 6l6 6-6 6',
	arrowL: 'M19 12H5M11 6l-6 6 6 6',
	arrowUR: 'M7 17 17 7M8.5 7H17v8.5',
	timeline: 'M4 6h10M4 12h16M4 18h7',
	ambulance: 'M3 16V7.5h10.5V16M13.5 10h3.8l3.2 3.6V16M3 16h17.5M7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM16.5 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM8.2 9.5v4M6.2 11.5h4',
	signal: 'M9 3h6v18H9zM12 7h.01M12 12h.01M12 17h.01',
	cone: 'M10 4h4l4 15H6zM8.5 10.5h7M7.3 15h9.4M4 19.5h16',
	wave: 'M3 9c2 0 2-2 4.5-2S10 9 12 9s2-2 4.5-2S19 9 21 9M3 15c2 0 2-2 4.5-2S10 15 12 15s2-2 4.5-2 2.5 2 4.5 2',
	flame: 'M12 3c1 3.5 5 5.5 5 10a5 5 0 0 1-10 0c0-2.5 1.5-3.5 2.5-5 .3 1.5 1 2.5 2 3 0-3 .5-5.5.5-8z',
	pin: 'M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
	target: 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 11.9h.01',
	globe: 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM3.5 12h17M12 3.5c2.4 2.4 3.4 5.3 3.4 8.5s-1 6.1-3.4 8.5c-2.4-2.4-3.4-5.3-3.4-8.5s1-6.1 3.4-8.5z',
	history: 'M4 12a8 8 0 1 0 2.3-5.7L4 8.6M4 4v4.6h4.6M12 8v4l3 2',
	cube: 'M12 3 20 7.5v9L12 21l-8-4.5v-9zM4 7.5 12 12l8-4.5M12 12v9',
	thermal: 'M12 4a2 2 0 0 0-2 2v8.3a4 4 0 1 0 4 0V6a2 2 0 0 0-2-2zM12 17.5h.01',
	ruler: 'M4 16 16 4l4 4L8 20zM8 12l2 2M11 9l2 2M14 6l2 2',
	calendar: 'M4 6h16v14H4zM4 10h16M8 3.5v4M16 3.5v4',
	stadium: 'M3 12c0-3 4-5 9-5s9 2 9 5-4 5-9 5-9-2-9-5zM7.5 12c0-1.4 2-2.5 4.5-2.5s4.5 1.1 4.5 2.5-2 2.5-4.5 2.5-4.5-1.1-4.5-2.5z',
	flag: 'M5.5 21V4M5.5 4H17l-2 4 2 4H5.5',
	convoy: 'M2.5 14.5h5.5V11H2.5zM9.5 14.5H15V11H9.5zM16.5 14.5h5V11h-5zM2 17.5h20',
	pursuit: 'M9 16h10.5v-3l-1.6-3.9a1.3 1.3 0 0 0-1.2-.8H11.8a1.3 1.3 0 0 0-1.2.8L9 13zM9 13h10.5M2.5 10h4.5M3.5 13H7M2.5 16H7',
	compass: 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM15.5 8.5l-2 5-5 2 2-5z',
	copy: 'M8 8h11v12H8zM5 16V4h11',
	sliders: 'M4 7h10M18 7h2M4 17h4M12 17h8M16 5v4M10 15v4',
	up: 'M12 19V5M6 11l6-6 6 6',
	down: 'M12 5v14M6 13l6 6 6-6',
	list: 'M8.5 6.5h11M8.5 12h11M8.5 17.5h11M4.5 6.5h.01M4.5 12h.01M4.5 17.5h.01',
	graph: 'M6 6.5a2 2 0 1 0 0-.01M18 6.5a2 2 0 1 0 0-.01M12 18a2 2 0 1 0 0-.01M7.5 7.8l3.4 8.4M16.5 7.8l-3.4 8.4M8 6.5h8',
	phone: 'M7.5 3h9v18h-9zM11 18h2',
	building: 'M4 20.5h16M6 20.5V8l6-4 6 4v12.5M9.5 20.5v-5h5v5M9 10.5h.01M15 10.5h.01',
	volume: 'M4 9.5v5a1 1 0 0 0 1 1h3l5 4V4.5l-5 4H5a1 1 0 0 0-1 1zM16.5 9a4 4 0 0 1 0 6M19 6.5a7.5 7.5 0 0 1 0 11',
} as const;

export type GlyphName = keyof typeof GLYPHS;

/** The glyph count (V3-SPEC §4.4: 68). */
export const GLYPH_COUNT = Object.keys(GLYPHS).length;

/** Path data for a glyph; an unknown name draws the info glyph (never nothing). */
export function glyphPath(name: string): string {
	return (GLYPHS as Record<string, string>)[name] ?? GLYPHS.info;
}
