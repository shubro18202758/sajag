#!/usr/bin/env python3
"""Sajag illustration set — hand-authored SVG, generated from this one file so the palette stays frozen.

Style rules (V3-SPEC §4.6):
  * flat planes in the night palette, one light "object" ink, at most one accent (Sajag blue or route teal);
  * never orange or red (those colours mean "a decision waits" and "stolen / watchlisted");
  * no people, no faces, no camera frames, no real logos — places, roads, vehicles and abstract symbols only;
  * readable at 56 px (event art) — big shapes, 6-unit minimum strokes on the 160 grid.

Run:  python3 build_illustrations.py [outdir]   → writes services/command-deck/static/illustrations/{events,empty,onboarding,vehicles,agencies}/*.svg
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'services', 'command-deck', 'static', 'illustrations')

BG = '#1F1F1F'      # tile
P1 = '#292929'      # ground plane
P2 = '#333333'      # road / mid plane
P3 = '#474747'      # raised plane
INK = '#E2E2E2'     # the object
INK2 = '#AFAFAF'    # secondary object ink
BLUE = '#276EF1'
TEAL = '#2DD4BF'
GREEN = '#3CCB7F'


def tile(body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" width="160" height="160" role="img" aria-label="{label}">'
            f'<defs><clipPath id="t"><rect width="160" height="160" rx="36"/></clipPath></defs>'
            f'<g clip-path="url(#t)"><rect width="160" height="160" fill="{BG}"/>{body}</g></svg>\n')


def car_side(x, y, s=1.0, fill=INK, w=None):
    """A generic hatchback in side view, origin at the rear-bottom; ~64 x 26 at s=1."""
    return (f'<g transform="translate({x} {y}) scale({s})" fill="{fill}">'
            f'<path d="M2 -8 Q2 -14 8 -15 L16 -16 L24 -25 Q26 -27 30 -27 L46 -27 Q50 -27 53 -24 L60 -16 Q66 -15 66 -9 L66 -5 L2 -5 Z"/>'
            f'<circle cx="16" cy="-4" r="6" fill="{BG}"/><circle cx="16" cy="-4" r="4"/>'
            f'<circle cx="52" cy="-4" r="6" fill="{BG}"/><circle cx="52" cy="-4" r="4"/>'
            f'<path d="M27 -23 L33 -23 L33 -16 L21 -16 Z M37 -23 L46 -23 Q48 -23 50 -21 L55 -16 L37 -16 Z" fill="{BG}" opacity=".85"/></g>')


EVENTS = {
    'protected_movement': ('Protected movement',
        f'<path d="M-6 132 C40 120 60 70 100 56 C124 47 146 44 170 30" stroke="{P2}" stroke-width="34" fill="none"/>'
        f'<path d="M-6 132 C40 120 60 70 100 56 C124 47 146 44 170 30" stroke="{TEAL}" stroke-width="4" stroke-dasharray="2 12" stroke-linecap="round" fill="none"/>'
        f'<g fill="{INK}"><rect x="22" y="104" width="26" height="15" rx="5" transform="rotate(-24 35 111)"/>'
        f'<rect x="64" y="72" width="28" height="16" rx="5" transform="rotate(-40 78 80)" fill="{TEAL}"/>'
        f'<rect x="108" y="44" width="26" height="15" rx="5" transform="rotate(-20 121 51)"/></g>'),
    'procession': ('Procession',
        f'<path d="M-4 118 C30 96 52 128 82 106 C108 88 128 112 164 92" stroke="{P2}" stroke-width="26" fill="none" stroke-linecap="round"/>'
        f'<path d="M14 40 C50 58 100 58 146 40" stroke="{INK2}" stroke-width="3" fill="none"/>'
        + ''.join(f'<path d="M{x} {y} l12 0 l-6 16 z" fill="{BLUE if i % 2 else INK}"/>' for i, (x, y) in enumerate([(20, 44), (42, 51), (64, 55), (86, 55), (108, 51), (130, 44)]))),
    'mass_gathering': ('Mass gathering',
        f'<circle cx="80" cy="84" r="56" fill="none" stroke="{INK}" stroke-opacity=".18" stroke-width="10"/>'
        f'<circle cx="80" cy="84" r="38" fill="none" stroke="{INK}" stroke-opacity=".38" stroke-width="10"/>'
        f'<circle cx="80" cy="84" r="20" fill="{INK}"/><rect x="72" y="76" width="16" height="16" rx="3" fill="{BG}"/>'),
    'race': ('Race',
        f'<path d="M80 168 L80 70" stroke="{P2}" stroke-width="48"/>'
        f'<path d="M80 160 L80 76" stroke="{INK2}" stroke-width="4" stroke-dasharray="10 10"/>'
        f'<rect x="34" y="36" width="8" height="70" rx="3" fill="{INK}"/><rect x="118" y="36" width="8" height="70" rx="3" fill="{INK}"/>'
        f'<rect x="34" y="34" width="92" height="22" rx="4" fill="{INK}"/>'
        + ''.join(f'<rect x="{38 + i * 10}" y="{37 + (i % 2) * 8}" width="10" height="8" fill="{BG}"/>' for i in range(9))),
    'ceremonial': ('Ceremonial',
        f'<rect x="20" y="118" width="120" height="14" rx="4" fill="{P3}"/>'
        f'<path d="M34 72 Q80 18 126 72 Z" fill="{INK}"/><rect x="74" y="28" width="12" height="10" rx="3" fill="{INK}"/>'
        f'<rect x="30" y="70" width="100" height="10" rx="3" fill="{INK}"/>'
        f'<g fill="{INK2}"><rect x="40" y="80" width="9" height="38"/><rect x="65" y="80" width="9" height="38"/><rect x="86" y="80" width="9" height="38"/><rect x="111" y="80" width="9" height="38"/></g>'),
    'egress_surge': ('Stadium egress',
        f'<ellipse cx="80" cy="82" rx="40" ry="28" fill="{INK}"/><ellipse cx="80" cy="82" rx="24" ry="14" fill="{P2}"/>'
        + ''.join(f'<path d="M{80 + 52 * c} {82 + 40 * s} l{10 * c} {10 * s}" stroke="{TEAL}" stroke-width="7" stroke-linecap="round"/>'
                  f'<path d="M{80 + 64 * c - 8 * s - 4 * c} {82 + 52 * s + 8 * c - 4 * s} L{80 + 66 * c} {82 + 54 * s} L{80 + 64 * c + 8 * s - 4 * c} {82 + 52 * s - 8 * c - 4 * s}" stroke="{TEAL}" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                  for c, s in [(1, 0), (-1, 0), (0.6, 0.8), (-0.6, 0.8), (0.6, -0.8), (-0.6, -0.8)])),
    'emergency_evacuation': ('Emergency evacuation',
        f'<path d="M22 120 V78 L52 56 L82 78 V120 Z" fill="{INK}"/><rect x="44" y="94" width="16" height="26" rx="2" fill="{BG}"/>'
        f'<path d="M66 128 C92 128 104 112 118 100" stroke="{TEAL}" stroke-width="7" fill="none" stroke-linecap="round" stroke-dasharray="1 13"/>'
        f'<path d="M122 108 V52" stroke="{INK}" stroke-width="6" stroke-linecap="round"/><path d="M124 52 H146 L140 62 L146 72 H124 Z" fill="{TEAL}"/>'),
    'work_zone': ('Work zone',
        f'<rect x="-4" y="118" width="168" height="26" fill="{P2}"/>'
        f'<g><rect x="26" y="68" width="108" height="22" rx="4" fill="{INK}"/>'
        + ''.join(f'<path d="M{36 + i * 22} 90 l14 -22 h10 l-14 22 z" fill="{BG}"/>' for i in range(4))
        + f'<rect x="38" y="90" width="7" height="30" fill="{INK2}"/><rect x="115" y="90" width="7" height="30" fill="{INK2}"/></g>'
        f'<path d="M80 30 L92 66 H68 Z" fill="{INK}" opacity=".0"/>'),
    'crime_incident': ('Watchlisted vehicle (ANPR)',
        f'<rect x="26" y="54" width="108" height="56" rx="14" fill="{INK}"/>'
        f'<rect x="42" y="74" width="76" height="20" rx="4" fill="{BG}"/>'
        f'<g fill="{INK}"><circle cx="58" cy="84" r="3"/><circle cx="70" cy="84" r="3"/><circle cx="82" cy="84" r="3"/><rect x="94" y="80" width="14" height="8" rx="2"/></g>'
        f'<path d="M14 40 V28 H28 M132 28 H146 V40 M146 120 V132 H132 M28 132 H14 V120" stroke="{BLUE}" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'),
    'vehicle_pursuit': ('Vehicle pursuit',
        f'<rect x="-4" y="98" width="168" height="34" fill="{P2}"/>'
        f'<path d="M-4 115 H164" stroke="{INK2}" stroke-width="3" stroke-dasharray="12 10" opacity=".6"/>'
        + car_side(70, 112, 1.0)
        + f'<g fill="{BLUE}"><circle cx="20" cy="58" r="7"/><circle cx="48" cy="48" r="7"/></g>'
        f'<path d="M20 58 L48 48 L78 44" stroke="{BLUE}" stroke-width="3" stroke-dasharray="3 6" fill="none"/>'
        f'<path d="M22 80 H54 M30 90 H58" stroke="{INK2}" stroke-width="5" stroke-linecap="round"/>'),
    'reported_crime': ('Reported incident',
        f'<rect x="22" y="40" width="74" height="92" rx="8" fill="{INK}"/>'
        f'<g fill="{BG}"><rect x="32" y="52" width="54" height="10" rx="3"/><rect x="32" y="70" width="40" height="6" rx="3"/><rect x="32" y="82" width="48" height="6" rx="3"/><rect x="32" y="94" width="34" height="6" rx="3"/><rect x="32" y="106" width="44" height="6" rx="3"/></g>'
        f'<path d="M116 118 s-24 -22 -24 -40 a24 24 0 0 1 48 0 c0 18 -24 40 -24 40z" fill="{BLUE}"/><circle cx="116" cy="78" r="9" fill="{BG}"/>'),
    'public_disorder': ('Public disorder (reported)',
        f'<path d="M80 124 s-26 -24 -26 -44 a26 26 0 0 1 52 0 c0 20 -26 44 -26 44z" fill="{INK}"/><circle cx="80" cy="80" r="10" fill="{BG}"/>'
        f'<path d="M36 52 a54 54 0 0 1 22 -22 M124 52 a54 54 0 0 0 -22 -22 M24 86 a60 60 0 0 1 0 -18 M136 86 a60 60 0 0 0 0 -18" stroke="{BLUE}" stroke-width="6" fill="none" stroke-linecap="round"/>'),
    'road_accident': ('Road accident',
        f'<rect x="-4" y="104" width="168" height="34" fill="{P2}"/>'
        f'<g transform="rotate(-14 46 110)">{car_side(10, 118, 0.9)}</g>'
        f'<g transform="rotate(16 112 110) translate(176 0) scale(-1 1)">{car_side(10, 118, 0.9, INK2)}</g>'
        f'<path d="M80 40 l5 14 14 -6 -7 13 14 6 -14 5 6 14 -13 -7 -5 14 -5 -14 -13 7 6 -14 -14 -5 14 -6 -7 -13 14 6z" fill="{BLUE}"/>'),
    'hazard': ('Hazard',
        f'<path d="M80 26 L140 128 H20 Z" fill="{INK}" stroke="{INK}" stroke-width="10" stroke-linejoin="round"/>'
        f'<path d="M80 62 c4 12 18 20 18 36 a18 18 0 0 1 -36 0 c0 -9 5 -13 9 -18 1 5 4 9 7 11 0 -11 2 -20 2 -29z" fill="{BG}"/>'),
    'flooding': ('Flooding',
        f'<rect x="-4" y="60" width="168" height="30" fill="{P2}"/>'
        f'<path d="M-4 96 c14 0 14 -10 28 -10 s14 10 28 10 14 -10 28 -10 14 10 28 10 14 -10 28 -10 14 10 28 10 V170 H-4z" fill="{BLUE}" opacity=".9"/>'
        f'<path d="M-4 120 c14 0 14 -10 28 -10 s14 10 28 10 14 -10 28 -10 14 10 28 10 14 -10 28 -10 14 10 28 10" stroke="{INK}" stroke-width="5" fill="none" opacity=".7"/>'
        f'<rect x="104" y="34" width="8" height="64" rx="3" fill="{INK}"/><g fill="{INK}"><rect x="112" y="46" width="12" height="4"/><rect x="112" y="60" width="8" height="4"/><rect x="112" y="74" width="12" height="4"/></g>'),
    'infra_failure': ('Infrastructure failure',
        f'<path d="M-4 112 H164" stroke="{P3}" stroke-width="10"/>'
        f'<path d="M14 82 H70 L64 92 L72 100 H14 Z M146 82 H88 L94 92 L86 100 H146 Z" fill="{INK}"/>'
        f'<g fill="{INK2}"><rect x="24" y="100" width="10" height="40"/><rect x="126" y="100" width="10" height="40"/></g>'
        f'<path d="M14 82 Q40 50 70 70 M146 82 Q120 50 90 70" stroke="{INK}" stroke-width="5" fill="none"/>'
        f'<path d="M78 70 l-6 10 8 6 -6 10" stroke="{BLUE}" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'),
    'weather': ('Weather warning',
        f'<path d="M44 96 a22 22 0 0 1 4 -43.6 a30 30 0 0 1 56 6 a20 20 0 0 1 12 37.6 z" fill="{INK}"/>'
        f'<path d="M82 92 L70 118 H86 L76 142 L104 108 H88 L98 92 Z" fill="{BLUE}"/>'),
    'advisory': ('Advisory',
        f'<path d="M34 70 v20 a6 6 0 0 0 6 6 h8 l40 24 V40 L48 64 h-8 a6 6 0 0 0 -6 6z" fill="{INK}"/>'
        f'<path d="M104 64 a22 22 0 0 1 0 32 M118 50 a40 40 0 0 1 0 60" stroke="{BLUE}" stroke-width="7" fill="none" stroke-linecap="round"/>'),
    'green_corridor': ('Green corridor (108)',
        f'<path d="M-4 120 C50 120 90 70 164 70" stroke="{P2}" stroke-width="30" fill="none"/>'
        f'<path d="M-4 120 C50 120 90 70 164 70" stroke="{GREEN}" stroke-width="4" stroke-dasharray="14 10" fill="none"/>'
        f'<g transform="translate(28 34)"><path d="M0 44 V12 h40 v32 z M40 22 h16 l12 13 v9 H40z" fill="{INK}"/>'
        f'<circle cx="14" cy="46" r="7" fill="{BG}"/><circle cx="14" cy="46" r="4.5" fill="{INK}"/><circle cx="54" cy="46" r="7" fill="{BG}"/><circle cx="54" cy="46" r="4.5" fill="{INK}"/>'
        f'<path d="M20 20 v16 M12 28 h16" stroke="{BG}" stroke-width="5"/></g>'),
}

VEHICLES = {  # 120 x 56 side views, currentColor so the UI can tint them; origin bottom-left, wheels on y=50
    'car': 'M8 40 Q8 32 16 31 L30 30 L42 18 Q45 15 50 15 L76 15 Q81 15 85 19 L96 30 Q108 31 110 39 L110 45 L8 45 Z',
    'suv': 'M8 42 Q8 30 14 28 L24 27 L32 12 Q34 9 39 9 L88 9 Q93 9 96 13 L104 27 Q112 29 112 38 L112 46 L8 46 Z',
    'two_wheeler': 'M28 26 L44 26 L50 34 L70 34 L78 22 L90 22 L86 26 L82 26 L76 38 L54 42 L40 42 L32 34 Z M78 22 L74 14 L82 14',
    'auto_rickshaw': 'M16 44 L16 30 Q16 9 40 8 L84 8 Q90 8 90 13 L90 30 L100 30 L108 40 L108 44 Z M48 13 L84 13 L84 29 L48 29 Z',
    'bus': 'M6 44 L6 12 Q6 7 12 7 L104 7 Q112 7 113 14 L115 30 L115 44 Z',
    'truck': 'M6 44 L6 6 L76 6 L76 44 Z M78 44 L78 18 L98 18 L112 30 L112 44 Z',
    'ambulance': 'M6 44 L6 10 Q6 7 10 7 L78 7 L78 44 Z M80 44 L80 18 L98 18 L112 32 L112 44 Z',
    'patrol': 'M8 40 Q8 32 16 31 L30 30 L42 18 Q45 15 50 15 L76 15 Q81 15 85 19 L96 30 Q108 31 110 39 L110 45 L8 45 Z M52 9 L72 9 L72 14 L52 14 Z',
    'fire_tender': 'M6 44 L6 14 L80 14 L80 44 Z M82 44 L82 12 Q82 8 88 8 L102 8 L114 26 L114 44 Z M10 8 L74 8 L74 11 L10 11 Z',
    'tempo': 'M6 44 L6 14 L70 14 L70 44 Z M72 44 L72 16 L92 16 L106 32 L106 44 Z',
}
WHEELS = {
    'car': [(30, 46, 9), (90, 46, 9)], 'suv': [(30, 47, 10), (92, 47, 10)], 'two_wheeler': [(30, 44, 10), (84, 44, 10)],
    'auto_rickshaw': [(32, 46, 8), (98, 46, 8)], 'bus': [(26, 46, 9), (96, 46, 9)], 'truck': [(22, 46, 9), (54, 46, 9), (98, 46, 9)],
    'ambulance': [(24, 46, 9), (98, 46, 9)], 'patrol': [(30, 46, 9), (90, 46, 9)], 'fire_tender': [(24, 46, 9), (60, 46, 9), (100, 46, 9)],
    'tempo': [(22, 46, 8), (92, 46, 8)],
}
WINDOWS = {
    'car': 'M47 19 L60 19 L60 29 L36 29 Z M64 19 L76 19 Q79 19 82 22 L89 29 L64 29 Z',
    'suv': 'M38 13 L60 13 L60 26 L30 26 Z M64 13 L88 13 Q91 13 93 16 L99 26 L64 26 Z',
    'auto_rickshaw': 'M22 30 Q22 16 40 14 L42 14 L42 30 Z',
    'bus': 'M14 12 H30 V24 H14Z M36 12 H52 V24 H36Z M58 12 H74 V24 H58Z M80 12 H96 V24 H80Z M101 12 H108 L110 26 H101Z',
    'truck': 'M84 22 H96 L104 30 H84 Z', 'ambulance': 'M84 22 H96 L105 31 H84 Z', 'patrol': 'M47 19 L60 19 L60 29 L36 29 Z M64 19 L76 19 Q79 19 82 22 L89 29 L64 29 Z',
    'fire_tender': 'M88 12 H100 L108 24 H88 Z', 'tempo': 'M76 20 H90 L99 30 H76 Z',
}
MARKS = {  # generic markings only — never a real livery
    'ambulance': '<path d="M38 18 v16 M30 26 h16" stroke="var(--sajag-silhouette-bg, #1F1F1F)" stroke-width="5"/>',
    'patrol': '<rect x="10" y="33" width="98" height="4" fill="var(--sajag-silhouette-bg, #1F1F1F)" opacity=".7"/>',
    'fire_tender': '<path d="M14 22 H74 M14 30 H74" stroke="var(--sajag-silhouette-bg, #1F1F1F)" stroke-width="3"/>',
}

AGENCIES = {  # 64 x 64 generic symbols, never an official emblem
    'police': ('Police (generic)', f'<path d="M32 10 L50 17 V31 C50 42 42 50 32 54 C22 50 14 42 14 31 V17 Z" fill="{INK}"/><path d="M32 22 l3.5 7.2 7.9 1.1 -5.7 5.6 1.4 7.8 -7.1 -3.7 -7.1 3.7 1.4 -7.8 -5.7 -5.6 7.9 -1.1z" fill="{BG}"/>'),
    'traffic': ('Traffic management', f'<rect x="22" y="8" width="20" height="48" rx="8" fill="{INK}"/><g fill="{BG}"><circle cx="32" cy="19" r="5"/><circle cx="32" cy="32" r="5"/></g><circle cx="32" cy="45" r="5" fill="{GREEN}"/>'),
    'ems': ('Emergency medical (generic)', f'<rect x="12" y="12" width="40" height="40" rx="12" fill="{INK}"/><path d="M32 20 v24 M20 32 h24" stroke="{BG}" stroke-width="8" stroke-linecap="round"/>'),
    'fire': ('Fire and rescue (generic)', f'<path d="M32 8 c3 10 15 15 15 29 a15 15 0 0 1 -30 0 c0 -8 5 -11 8 -15 1 5 3 8 6 9 0 -9 1 -16 1 -23z" fill="{INK}"/><path d="M32 34 c1 4 6 6 6 11 a6 6 0 0 1 -12 0 c0 -4 3 -6 6 -11z" fill="{BG}"/>'),
    'municipal': ('Municipal services (generic)', f'<path d="M10 24 L32 12 L54 24 Z" fill="{INK}"/><g fill="{INK}"><rect x="14" y="27" width="6" height="20"/><rect x="25" y="27" width="6" height="20"/><rect x="36" y="27" width="6" height="20"/><rect x="47" y="27" width="4" height="20"/><rect x="10" y="49" width="44" height="6" rx="2"/></g>'),
    'disaster': ('Disaster response (generic)', f'<circle cx="32" cy="32" r="20" fill="none" stroke="{INK}" stroke-width="9"/><g stroke="{BG}" stroke-width="5"><path d="M32 12 v8 M32 44 v8 M12 32 h8 M44 32 h8"/></g>'),
    'control_room': ('Control room (generic)', f'<g fill="{INK}"><rect x="8" y="12" width="22" height="16" rx="3"/><rect x="34" y="12" width="22" height="16" rx="3"/><rect x="8" y="32" width="22" height="16" rx="3"/><rect x="34" y="32" width="22" height="16" rx="3"/></g><rect x="22" y="52" width="20" height="4" rx="2" fill="{INK2}"/><circle cx="45" cy="20" r="3" fill="{BLUE}"/>'),
    'volunteers': ('Citizen volunteers (generic)', f'<path d="M32 50 C18 40 10 32 10 23 a10 10 0 0 1 22 -4 a10 10 0 0 1 22 4 c0 9 -8 17 -22 27z" fill="{INK}"/>'),
}

EMPTY = {
    'all-clear': ('Nothing needs you right now',
        f'<rect x="0" y="150" width="320" height="50" fill="{P1}"/>'
        f'<g fill="{P2}"><rect x="30" y="104" width="34" height="46"/><path d="M76 150 V96 a18 18 0 0 1 36 0 V150z"/><rect x="120" y="86" width="20" height="64"/><rect x="128" y="70" width="4" height="16"/>'
        f'<rect x="150" y="112" width="44" height="38"/><path d="M204 150 V100 a14 14 0 0 1 28 0 V150z"/><rect x="242" y="92" width="18" height="58"/><rect x="249" y="76" width="4" height="16"/><rect x="268" y="118" width="30" height="32"/></g>'
        f'<circle cx="230" cy="52" r="26" fill="{GREEN}" opacity=".16"/><path d="M218 52 l8 8 16 -17" stroke="{GREEN}" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'),
    'no-reports': ('No reported events here',
        f'<path d="M40 40 L120 20 L200 40 L280 20 V160 L200 180 L120 160 L40 180 Z" fill="{P1}"/>'
        f'<path d="M120 20 V160 M200 40 V180" stroke="{P2}" stroke-width="3"/>'
        f'<path d="M60 120 C110 110 150 70 260 60" stroke="{P2}" stroke-width="10" fill="none"/>'
        f'<circle cx="160" cy="100" r="54" fill="none" stroke="{BLUE}" stroke-width="3" stroke-dasharray="6 9" opacity=".8"/>'
        f'<circle cx="160" cy="100" r="6" fill="{BLUE}"/>'),
    'assistant': ('Ask about the city',
        f'<rect x="56" y="38" width="150" height="70" rx="22" fill="{P2}"/><path d="M84 108 l-10 22 30 -22z" fill="{P2}"/>'
        f'<g fill="{INK2}"><rect x="78" y="62" width="104" height="8" rx="4"/><rect x="78" y="78" width="70" height="8" rx="4"/></g>'
        f'<rect x="130" y="100" width="140" height="58" rx="20" fill="{INK}"/><path d="M244 158 l12 18 -28 -18z" fill="{INK}"/>'
        f'<path d="M200 112 l3.6 9.2 9.2 3.6 -9.2 3.6 -3.6 9.2 -3.6 -9.2 -9.2 -3.6 9.2 -3.6z" fill="{BLUE}"/>'),
    'offline': ('Feed not answering',
        f'<path d="M20 120 H96 L110 90 L126 150 L140 110" stroke="{INK2}" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M180 110 H300" stroke="{P3}" stroke-width="6" stroke-dasharray="4 12" stroke-linecap="round"/>'
        f'<circle cx="160" cy="110" r="14" fill="none" stroke="{BLUE}" stroke-width="5"/><path d="M151 101 l18 18" stroke="{BLUE}" stroke-width="5" stroke-linecap="round"/>'),
    'select-something': ('Select something on the map',
        f'<path d="M40 40 L120 20 L200 40 L280 20 V160 L200 180 L120 160 L40 180 Z" fill="{P1}"/>'
        f'<circle cx="110" cy="90" r="10" fill="{INK2}"/><circle cx="210" cy="70" r="10" fill="{INK2}"/><circle cx="170" cy="130" r="14" fill="{INK}" stroke="{BLUE}" stroke-width="5"/>'
        f'<path d="M182 140 l0 34 9 -9 7 14 6 -3 -7 -14 13 0z" fill="{INK}" stroke="{BG}" stroke-width="3" stroke-linejoin="round"/>'),
}

ONBOARD = {
    '1-glance': ('See the city at a glance',
        f'<rect x="40" y="60" width="400" height="66" rx="16" fill="{P1}"/>'
        f'<rect x="56" y="76" width="34" height="34" rx="17" fill="{GREEN}" opacity=".25"/><rect x="104" y="82" width="160" height="10" rx="5" fill="{INK}"/><rect x="104" y="100" width="110" height="8" rx="4" fill="{INK2}"/>'
        + ''.join(f'<rect x="{40 + i * 136}" y="146" width="124" height="112" rx="14" fill="{P2}"/><rect x="{40 + i * 136}" y="146" width="124" height="62" rx="14" fill="{P3}"/>'
                  f'<rect x="{52 + i * 136}" y="222" width="80" height="9" rx="4" fill="{INK}"/><rect x="{52 + i * 136}" y="238" width="56" height="7" rx="3" fill="{INK2}"/>' for i in range(3))
        + f'<path d="M80 176 C100 166 120 186 150 168" stroke="{TEAL}" stroke-width="4" fill="none"/><circle cx="352" cy="178" r="8" fill="{BLUE}"/>'),
    '2-decide': ('One decision at a time',
        f'<rect x="120" y="36" width="240" height="232" rx="20" fill="{P2}" transform="rotate(-4 240 150)" opacity=".5"/>'
        f'<rect x="120" y="36" width="240" height="232" rx="20" fill="{P1}" stroke="{P3}" stroke-width="2"/>'
        f'<rect x="140" y="56" width="200" height="70" rx="12" fill="{P3}"/><path d="M150 112 C190 96 230 108 330 70" stroke="{TEAL}" stroke-width="4" fill="none"/>'
        f'<rect x="140" y="140" width="150" height="11" rx="5" fill="{INK}"/><rect x="140" y="160" width="190" height="8" rx="4" fill="{INK2}"/><rect x="140" y="174" width="160" height="8" rx="4" fill="{INK2}"/>'
        f'<rect x="140" y="214" width="84" height="36" rx="18" fill="{P3}"/><rect x="234" y="214" width="106" height="36" rx="18" fill="{INK}"/>'),
    '3-you-decide': ('The assistant proposes. You decide.',
        f'<rect x="60" y="70" width="170" height="150" rx="18" fill="{P1}"/>'
        f'<path d="M100 100 l3.6 9.2 9.2 3.6 -9.2 3.6 -3.6 9.2 -3.6 -9.2 -9.2 -3.6 9.2 -3.6z" fill="#5B91F5"/>'
        f'<rect x="84" y="146" width="120" height="9" rx="4" fill="{INK2}"/><rect x="84" y="164" width="90" height="9" rx="4" fill="{INK2}"/>'
        f'<path d="M244 145 h46 m-12 -12 l12 12 -12 12" stroke="{INK2}" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<rect x="304" y="70" width="140" height="150" rx="18" fill="{P2}"/>'
        f'<rect x="330" y="92" width="88" height="62" rx="10" fill="{INK}"/><circle cx="374" cy="116" r="12" fill="{P2}"/><rect x="352" y="134" width="44" height="7" rx="3" fill="{P2}"/>'
        f'<path d="M330 186 c10 -14 20 8 30 -4 s16 -10 24 2" stroke="{INK}" stroke-width="4" fill="none" stroke-linecap="round"/>'
        f'<circle cx="418" cy="190" r="13" fill="{GREEN}"/><path d="M412 190 l4.5 4.5 8 -8.5" stroke="{BG}" stroke-width="3.5" fill="none" stroke-linecap="round"/>'),
}


def write(sub, name, svg):
    d = os.path.join(OUT, sub)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name + '.svg'), 'w') as f:
        f.write(svg)


def main():
    for k, (label, body) in EVENTS.items():
        write('events', k, tile(body, label))
    for k, path in VEHICLES.items():
        wheels = ''.join(f'<circle cx="{x}" cy="{y}" r="{r + 3}" fill="var(--sajag-silhouette-bg, #1F1F1F)"/><circle cx="{x}" cy="{y}" r="{r}"/><circle cx="{x}" cy="{y}" r="{r * .38:.1f}" fill="var(--sajag-silhouette-bg, #1F1F1F)"/>' for x, y, r in WHEELS[k])
        win = f'<path d="{WINDOWS[k]}" fill="var(--sajag-silhouette-bg, #1F1F1F)" opacity=".8"/>' if k in WINDOWS else ''
        label = k.replace('_', ' ')
        write('vehicles', k, f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 58" width="120" height="58" role="img" aria-label="{label} (vehicle class)" fill="currentColor" style="color:{INK}">'
                             f'<path d="{path}" fill-rule="evenodd"/>{win}{MARKS.get(k, "")}{wheels}</svg>\n')
    for k, (label, body) in AGENCIES.items():
        write('agencies', k, f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" role="img" aria-label="{label}">{body}</svg>\n')
    for k, (label, body) in EMPTY.items():
        write('empty', k, f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200" width="320" height="200" role="img" aria-label="{label}">{body}</svg>\n')
    for k, (label, body) in ONBOARD.items():
        write('onboarding', k, f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 300" width="480" height="300" role="img" aria-label="{label}">'
                                f'<rect width="480" height="300" rx="28" fill="{BG}"/>{body}</svg>\n')
    print('ok', sum(len(x) for x in (EVENTS, VEHICLES, AGENCIES, EMPTY, ONBOARD)), 'files')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        OUT = os.path.abspath(sys.argv[1])
    main()
