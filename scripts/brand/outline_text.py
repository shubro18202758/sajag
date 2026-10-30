#!/usr/bin/env python3
"""Outline the Sajag wordmark text into SVG path data (scripts/brand/glyphs.json).

The wordmark is set in two OFL faces and stored as outlines, so no font file ships with the logo:
  * Latin "Sajag" in Inter (SIL OFL 1.1; the deck's own UI face, static/fonts/inter-latin.woff2);
  * Devanagari "सजग" (Marathi and Hindi) in Noto Sans Devanagari (SIL OFL 1.1; the deck's own face,
    static/fonts/noto-sans-devanagari.woff2).
OFL allows artwork (a logo) made with the fonts; the outlines are not a font and carry no Reserved Font Name.

This is the ONE step that needs third-party tools (fontTools + uharfbuzz, in a private venv). It runs once; the
result (glyphs.json) is committed and build_brand.py, which draws every brand file, stays pure stdlib.

  python outline_text.py <inter-latin.woff2> <noto-sans-devanagari.woff2>

Coordinates: font size 100 (1 unit = 1/100 em), baseline at y = 0, y grows downwards (SVG), x starts at 0.
"""
import io
import json
import os
import sys

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
import uharfbuzz as hb

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 100.0


def fmt(v):
    s = f'{v:.1f}'
    return s[:-2] if s.endswith('.0') else ('0' if s in ('-0', '-0.0') else s)


class RoundPen(SVGPathPen):
    """SVGPathPen with one-decimal coordinates (small files, sub-pixel exact at any logo size)."""

    def __init__(self, glyphset):
        super().__init__(glyphset, ntos=fmt)


def static_instance(path, axes):
    f = TTFont(path)
    if 'fvar' in f:
        f = instantiateVariableFont(f, axes, inplace=False)
    buf = io.BytesIO()
    f.flavor = None
    f.save(buf)
    data = buf.getvalue()
    return TTFont(io.BytesIO(data)), data


def outline(path, axes, text, tracking=0.0, lang=None, script=None):
    """Shape `text` with HarfBuzz, draw each glyph; returns (d, advance, ascent-ish box)."""
    font, data = static_instance(path, axes)
    upem = font['head'].unitsPerEm
    k = SIZE / upem
    face = hb.Face(data)
    hfont = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    if script:
        buf.script = script
    if lang:
        buf.language = lang
    hb.shape(hfont, buf, {'kern': True, 'liga': True})
    order = font.getGlyphOrder()
    gs = font.getGlyphSet()
    pen = RoundPen(gs)
    bp = BoundsPen(gs)
    x = 0.0
    n = len(buf.glyph_infos)
    for i, (info, pos) in enumerate(zip(buf.glyph_infos, buf.glyph_positions)):
        name = order[info.codepoint]
        dx, dy = pos.x_offset * k, pos.y_offset * k
        # font units (y up) -> SVG (y down), at font size 100
        tp = TransformPen(pen, (k, 0, 0, -k, x + dx, -dy))
        gs[name].draw(tp)
        gs[name].draw(TransformPen(bp, (k, 0, 0, -k, x + dx, -dy)))
        x += pos.x_advance * k
        if i < n - 1 and pos.x_advance:
            x += tracking
    os2 = font['OS/2']
    return {
        'd': pen.getCommands(),
        'bbox': [round(v, 2) for v in bp.bounds],
        'advance': round(x, 2),
        'cap': round(getattr(os2, 'sCapHeight', 0) * k, 2),
        'xh': round(getattr(os2, 'sxHeight', 0) * k, 2),
        'asc': round(os2.sTypoAscender * k, 2),
        'desc': round(os2.sTypoDescender * k, 2),
    }


def bbox_of(d):
    import re
    nums = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', d)]
    xs, ys = nums[0::2], nums[1::2]
    return [min(xs), min(ys), max(xs), max(ys)]


def main(inter, devanagari):
    out = {
        'source': {
            'latin': 'Inter (SIL OFL 1.1), wght 700, tracking -2.4 per glyph at size 100',
            'devanagari': 'Noto Sans Devanagari (SIL OFL 1.1), wght 700',
        },
        'latin': outline(inter, {'wght': 700}, 'Sajag', tracking=-2.4),
        'latin_semibold': outline(inter, {'wght': 600}, 'Sajag', tracking=-1.6),
        'devanagari': outline(devanagari, {'wght': 700}, 'सजग', lang='mr', script='Deva'),
        'devanagari_semibold': outline(devanagari, {'wght': 600}, 'सजग', lang='mr', script='Deva'),
    }
    with open(os.path.join(HERE, 'glyphs.json'), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write('\n')
    for k_, v in out.items():
        if isinstance(v, dict) and 'd' in v:
            print(k_, 'advance', v['advance'], 'bbox', v['bbox'], len(v['d']), 'chars')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
