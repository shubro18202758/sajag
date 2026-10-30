#!/usr/bin/env python3
"""Sajag identity: the mark, the wordmark, the lockups, the app icon and the favicon — generated from this one file.

Pure python3 stdlib, deterministic. Text is never set with a font at run time: the wordmark outlines come from
glyphs.json (Inter, SIL OFL 1.1, outlined once by outline_text.py).

THE MARK — the tide line through the S.
  Sajag (सजग) means alert, watchful. Mumbai floods when a heavy burst of rain meets a high tide and the sea outfalls
  close, so the one thing the city must always watch is where the water stands. The mark is a geometric S (two round
  bowls on the 64 grid, a constant stroke with round ends) whose spine is one wave: the tide line, in the accent blue
  (#276EF1), running out past both bowls. The top stroke dips into the water on the left and the bottom stroke rises out
  of it on the right. A clear gap (a mask, never a background colour) keeps the wave and the S apart, so the mark reads
  the same on night, on paper and in one colour (mono). Everything except the wave is
  white on night, black on paper, currentColor in mono. The wave is the ONLY colour in the identity: no warm hue (never
  the decision orange or the alert red, never a taxi yellow), no gradient, no filter, no image.
  At 32 px and below the solid mark (a heavier S, a thicker and flatter tide line) stands in; at 16 px it reads as an S
  with a blue line through it.

Run:  python3 build_brand.py [outdir]     (default: services/command-deck/static/brand)
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'services', 'command-deck', 'static', 'brand')

ACCENT = '#276EF1'       # the one accent: links and the AI in the deck, the tide line in the mark
INK = '#FFFFFF'          # night ink
PAPER_INK = '#000000'    # day ink
TILE = '#000000'
TILE_EDGE = '#FFFFFF'    # the app icon's hairline (at 14 % opacity) keeps the tile's edge on a black home screen

with open(os.path.join(HERE, 'glyphs.json'), encoding='utf-8') as fh:
    GLYPHS = json.load(fh)


def f(v):
    s = f'{v:.2f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


# ── geometry ──────────────────────────────────────────────────────────────────────────────────────────────────
T, B, L, R = 12.0, 52.0, 15.0, 49.0   # top and bottom bar, left and right side of the S (its centreline)
M = (T + B) / 2                       # the spine, where the tide line runs
RAD = (M - T) / 2                     # the bowls' radius
EXT = 3.0                             # the tide line runs this far past both sides of the S


def s_path(dip):
    """The S's centreline in two strokes that meet at the water: the top bar from its open end (right) round the left bowl
    until it dips into the tide line, `dip` degrees below the bowl's level; then, mirrored, out of the tide line round the
    right bowl to the bottom bar's open end (left). The tide line itself is the S's spine."""
    lx, rx = L + RAD, R - RAD
    c, sn = math.cos(math.radians(dip)), math.sin(math.radians(dip))
    e1 = (lx - RAD * c, T + RAD + RAD * sn)          # where the top stroke enters the water
    s2 = (rx + RAD * c, B - RAD - RAD * sn)          # where the bottom stroke leaves it
    return (f'M{f(R)} {f(T)}L{f(lx)} {f(T)}A{f(RAD)} {f(RAD)} 0 0 0 {f(e1[0])} {f(e1[1])}'
            f'M{f(s2[0])} {f(s2[1])}A{f(RAD)} {f(RAD)} 0 0 1 {f(rx)} {f(B)}L{f(L)} {f(B)}')


def wave_path(amp):
    """One period of the tide line across the spine: a crest on the left, a trough on the right (two cubic arcs)."""
    x0, x1 = L - EXT, R + EXT
    h = (x1 - x0) / 2
    k = amp * 4 / 3   # a cubic with both handles at height k peaks at 3/4 k
    return (f'M{f(x0)} {f(M)}C{f(x0 + h / 3)} {f(M - k)} {f(x0 + 2 * h / 3)} {f(M - k)} {f(x0 + h)} {f(M)}'
            f'S{f(x1 - h / 3)} {f(M + k)} {f(x1)} {f(M)}')


FULL = {'road': 8.0, 'wave': 5.0, 'amp': 2.2, 'gap': 1.8, 'dip': 46}     # the mark at 40 px and up
SOLID = {'road': 10.5, 'wave': 7.0, 'amp': 1.2, 'gap': 1.6, 'dip': 40}   # 32 px and below: heavier, so it holds at 16 px


def mark_body(col, accent, g=FULL, mid='sj'):
    """The S in `col`, cut by a clear band round the tide line (a mask: no background colour), and the tide line in `accent`."""
    wave = wave_path(g['amp'])
    cut = g['wave'] + 2 * g['gap']
    return (f'<mask id="{mid}"><rect x="-8" y="-8" width="80" height="80" fill="white"/>'
            f'<path d="{wave}" fill="none" stroke="black" stroke-width="{f(cut)}" stroke-linecap="round"/></mask>'
            f'<path d="{s_path(g['dip'])}" mask="url(#{mid})" fill="none" stroke="{col}" stroke-width="{f(g["road"])}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="{wave}" fill="none" stroke="{accent}" stroke-width="{f(g["wave"])}" stroke-linecap="round"/>')


def mark_full(col, accent, mid='sj'):
    return mark_body(col, accent, FULL, mid)


def mark_solid(col, accent, mid='sj'):
    """The small-size mark (≤ 32 px): the same S and tide line, a heavier S and a thicker, flatter line."""
    return mark_body(col, accent, SOLID, mid)


# ── text ──────────────────────────────────────────────────────────────────────────────────────────────────────
def text(key, x, baseline, scale, col):
    g = GLYPHS[key]
    return f'<path transform="translate({f(x)} {f(baseline)}) scale({f(scale)})" d="{g["d"]}" fill="{col}"/>', g['advance'] * scale


def svg(w, h, body, label=None, extra=''):
    lab = f' role="img" aria-label="{label}"' if label else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {f(w)} {f(h)}" width="{f(w)}" height="{f(h)}"{lab}{extra}>'
            f'{body}</svg>\n')


LABEL = 'Sajag'


def word(x, cap_top, cap, ink):
    """'Sajag' set with cap height `cap` from `cap_top`; returns (svg, width)."""
    la = GLYPHS['latin']
    k = cap / la['cap']
    p, w = text('latin', x - la['bbox'][0] * k, cap_top + cap, k, ink)
    return p, (la['bbox'][2] - la['bbox'][0]) * k


def mark_g(inner, x, y, size):
    return f'<g transform="translate({f(x)} {f(y)}) scale({f(size / 64)})">{inner}</g>'


def lockup(ink, mark_col, accent, mono=False):
    """The horizontal lockup: the mark, then 'Sajag' with its cap height at 36 % of the mark."""
    h = 64
    body = mark_g(mark_full(mark_col, accent), 0, 0, 64)
    cap = 23.0
    words, w = word(74, (h - cap) / 2, cap, ink)
    W = 74 + w + 2
    extra = ' fill="currentColor"' if mono else ''
    return svg(W, h, body + words, LABEL, extra)


def stacked(ink, mark_col, accent):
    cap = 26.0
    la = GLYPHS['latin']
    wl = (la['bbox'][2] - la['bbox'][0]) * cap / la['cap']
    W = max(wl, 104) + 24
    msize = 104
    body = mark_g(mark_full(mark_col, accent), (W - msize) / 2, 0, msize)
    words, _ = word((W - wl) / 2, msize + 14, cap, ink)
    desc = la['bbox'][3] * cap / la['cap']   # the j and the g descend below the baseline
    return svg(W, msize + 14 + cap + desc + 3, body + words, LABEL)


def wordmark(ink):
    cap = 26.0
    words, w = word(2, 12, cap, ink)
    return svg(w + 4, 50, words, LABEL)


def app_icon():
    # black tile, the white S and the blue tide line; a hairline keeps the tile's edge on a black home screen
    return svg(64, 64, f'<rect width="64" height="64" rx="15" fill="{TILE}"/>'
               f'<rect x=".75" y=".75" width="62.5" height="62.5" rx="14.25" fill="none" stroke="{TILE_EDGE}" stroke-opacity=".14" stroke-width="1.5"/>'
               + mark_g(mark_full(INK, ACCENT), 8, 8, 48), LABEL)


def favicon():
    # the tab icon: the solid mark (the heavier S and the thicker tide line hold at 16 px), white and blue on a black tile
    return svg(32, 32, f'<rect width="32" height="32" rx="7" fill="{TILE}"/>' + mark_g(mark_solid(INK, ACCENT), 2, 2, 28))


FILES = {
    'sajag-mark': lambda: svg(64, 64, mark_full(INK, ACCENT), LABEL),
    'sajag-mark-day': lambda: svg(64, 64, mark_full(PAPER_INK, ACCENT), LABEL),
    'sajag-mark-mono': lambda: svg(64, 64, mark_full('currentColor', 'currentColor'), LABEL),
    'sajag-mark-solid': lambda: svg(64, 64, mark_solid(INK, ACCENT), LABEL),
    'sajag-wordmark': lambda: wordmark(INK),
    'sajag-wordmark-day': lambda: wordmark(PAPER_INK),
    'sajag-lockup': lambda: lockup(INK, INK, ACCENT),
    'sajag-lockup-day': lambda: lockup(PAPER_INK, PAPER_INK, ACCENT),
    'sajag-lockup-mono': lambda: lockup('currentColor', 'currentColor', 'currentColor', True),
    'sajag-lockup-stacked': lambda: stacked(INK, INK, ACCENT),
    'sajag-lockup-stacked-day': lambda: stacked(PAPER_INK, PAPER_INK, ACCENT),
    'sajag-app-icon': app_icon,
    'favicon': favicon,
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in FILES.items():
        with open(os.path.join(OUT, f'{name}.svg'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(fn())
    print('ok', len(FILES), 'brand files →', OUT)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        OUT = os.path.abspath(sys.argv[1])
    main()
