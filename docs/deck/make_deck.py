#!/usr/bin/env python3
"""Render the Sajag deck for Mumbai (docs/deck/Sajag_Deck.pptx, and a PDF with --pdf).

Run:   <python with python-pptx and Pillow> docs/deck/make_deck.py [--out PATH.pptx] [--pdf]
       (--pdf converts with LibreOffice: soffice --headless --convert-to pdf, next to the .pptx)
Inputs:
  docs/evidence/facts.json            every number that exists only after the merge ("values"); the evidence
                                      PDF reads the same file, so the numbers are filled in one place
  docs/screenshots/*.jpg              product screenshots (a missing one renders as a labelled empty frame)
  docs/deck/assets/lockup-*.png       brand lockups, rendered from services/command-deck/static/brand/*.svg
                                      by docs/deck/render_brand.mjs
  docs/deck/assets/photos.json        reference photos and their credits (also in assets/CREDITS.md)
A value in facts.json that is still its own placeholder ("{{KEY}}") is drawn as-is, in the accent colour,
and listed on stderr, so nothing unfilled can pass unnoticed.
Every figure on a slide says what it is (LIVE, EMULATED, SIMULATED, MODELLED) and every real-world number
carries its source in small print.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
SHOTS = ROOT / "docs" / "screenshots"
FACTS = json.loads((ROOT / "docs" / "evidence" / "facts.json").read_text(encoding="utf-8"))
VALUES: dict[str, str] = FACTS["values"]
PHOTOS = {p["slug"]: p for p in json.loads((ASSETS / "photos.json").read_text(encoding="utf-8"))}
REPO = FACTS.get("repo", "github.com/shubro18202758/sajag")

BLACK = RGBColor(0x00, 0x00, 0x00)
S1 = RGBColor(0x11, 0x11, 0x11)
S2 = RGBColor(0x1A, 0x1A, 0x1A)
S3 = RGBColor(0x2E, 0x2E, 0x2E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
T2 = RGBColor(0xCB, 0xCB, 0xCB)
T3 = RGBColor(0xA6, 0xA6, 0xA6)
T4 = RGBColor(0x80, 0x80, 0x80)
ACCENT = RGBColor(0x7F, 0xA8, 0xF7)  # unfilled placeholders only
LATIN = "Inter"
DEVANAGARI = "Noto Sans Devanagari"

W, H = Inches(13.333), Inches(7.5)
PH = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
UNFILLED: set[str] = set()


# ---------------------------------------------------------------- placeholders
def is_unfilled(key: str) -> bool:
    v = VALUES.get(key)
    return v is None or PH.fullmatch(str(v).strip()) is not None


def fill(s: str) -> str:
    """Replace {{KEY}} with facts.json values; an unfilled key stays visible as {{KEY}}."""
    def sub(m: re.Match) -> str:
        key = m.group(1)
        if is_unfilled(key):
            UNFILLED.add(key)
            return m.group(0)
        return str(VALUES[key])
    return PH.sub(sub, s)


# ---------------------------------------------------------------- drawing helpers
def has_devanagari(s: str) -> bool:
    return any("ऀ" <= c <= "ॿ" for c in s)


def font(run, size, color=WHITE, bold=False, text=""):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    f.name = DEVANAGARI if has_devanagari(text) else LATIN
    rpr = run._r.get_or_add_rPr()
    for tag, face in (("a:latin", LATIN), ("a:cs", DEVANAGARI)):
        el = rpr.find(qn(tag))
        if el is None:
            el = rpr.makeelement(qn(tag), {})
            rpr.append(el)
        el.set("typeface", face)


def bg(slide, color=BLACK):
    fill_ = slide.background.fill
    fill_.solid()
    fill_.fore_color.rgb = color


def box(slide, x, y, w, h, color, line=None, alpha=None):
    shp = slide.shapes.add_shape(1, x, y, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(0.75)
    shp.shadow.inherit = False
    if alpha is not None:  # 0-100 000, opacity
        clr = shp.fill._xPr.find(qn("a:solidFill"))[0]
        clr.append(clr.makeelement(qn("a:alpha"), {"val": str(alpha)}))
    return shp


def text(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP):
    """paras: list of (text, size, color, bold[, align]) or (runs, size, color, bold[, align]),
    runs being a list of (text, color, bold). Placeholders are filled; unfilled ones show in the accent colour."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, (content, size, color, bold, *rest) in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = rest[0] if rest else PP_ALIGN.LEFT
        p.space_after = Pt(size * 0.45)
        runs = content if isinstance(content, list) else [(content, color, bold)]
        for t, c, b in runs:
            for piece in re.split(r"(\{\{[A-Z0-9_]+\}\})", fill(t)):
                if not piece:
                    continue
                r = p.add_run()
                r.text = piece
                font(r, size, ACCENT if PH.fullmatch(piece) else c, b, text=piece)
    return tb


def picture(slide, path: Path, x, y, w, h, label=None):
    """Fit inside the box at the picture's own aspect ratio, centred (never stretched)."""
    if path.exists():
        iw, ih = Image.open(path).size
        scale = min(w / iw, h / ih)
        pw, ph = int(iw * scale), int(ih * scale)
        return slide.shapes.add_picture(str(path), x + (w - pw) // 2, y + (h - ph) // 2, pw, ph)
    frame = box(slide, x, y, w, h, S2, line=S3)
    text(slide, x + Inches(0.2), y + Inches(0.2), w - Inches(0.4), Inches(0.6),
         [(f"[ screenshot: {label or path.name} ]", 12, T3, False)])
    return frame


def cover_picture(slide, path: Path, x, y, w, h, fx=0.5, fy=0.5):
    """Fill the frame, cropping the photo to the frame's aspect; fx/fy place the crop (0 = left/top)."""
    pic = slide.shapes.add_picture(str(path), x, y, w, h)
    iw, ih = Image.open(path).size
    fr, ir = w / h, iw / ih
    if ir > fr:
        cut = 1 - fr / ir
        pic.crop_left, pic.crop_right = cut * fx, cut * (1 - fx)
    else:
        cut = 1 - ir / fr
        pic.crop_top, pic.crop_bottom = cut * fy, cut * (1 - fy)
    return pic


def credit(slug: str) -> str:
    p = PHOTOS[slug]
    return (f"Reference photo · not live · {p['caption']} · {p['author']} · {p['license_short']} · "
            "Wikimedia Commons")


def photo(slide, slug, x, y, w, h, fx=0.5, fy=0.5, credit_below=True):
    cover_picture(slide, ASSETS / PHOTOS[slug]["file"], x, y, w, h, fx, fy)
    if credit_below:
        text(slide, x, y + h + Inches(0.06), w, Inches(0.3), [(credit(slug), 8, T4, False)])


def footer(slide, n: int, source: str | None = None):
    if source:
        text(slide, Inches(0.6), Inches(6.68), Inches(12.1), Inches(0.36), [("Sources: " + source, 8.5, T4, False)])
    text(slide, Inches(0.6), Inches(7.08), Inches(8), Inches(0.3),
         [([("Sajag", WHITE, True), ("  ·  Mumbai  ·  Not by stopping. By steering.", T3, False)], 10, T3, False)])
    text(slide, Inches(12.2), Inches(7.08), Inches(0.6), Inches(0.3), [(str(n), 10, T3, False, PP_ALIGN.RIGHT)])


def kicker_title(slide, kicker: str, title: str, y=Inches(0.5)):
    text(slide, Inches(0.6), y, Inches(12), Inches(0.35), [(kicker, 13, T3, True)])
    text(slide, Inches(0.6), y + Inches(0.4), Inches(12.1), Inches(1.0), [(title, 29, WHITE, True)])


# ---------------------------------------------------------------- the deck
def build(out: Path) -> int:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    blank = prs.slide_layouts[6]
    n = 0

    def slide():
        nonlocal n
        n += 1
        s = prs.slides.add_slide(blank)
        bg(s)
        return s

    # 1 · title (poster)
    s = slide()
    photo(s, "sea-link-night", Inches(5.6), 0, Inches(7.733), H, fx=0.62, credit_below=False)
    box(s, Inches(5.6), Inches(6.98), Inches(7.733), Inches(0.52), BLACK, alpha=60000)
    s.shapes.add_picture(str(ASSETS / "lockup-night.png"), Inches(0.6), Inches(0.85), height=Inches(0.62))
    text(s, Inches(0.6), Inches(1.95), Inches(5.0), Inches(2.4), [
        ("Not by stopping.", 42, WHITE, True),
        ("By steering.", 42, T3, True),
    ])
    text(s, Inches(0.6), Inches(4.05), Inches(4.8), Inches(2.4), [
        ("For the city that never stops.", 22, WHITE, True),
        ("One live picture of Mumbai's roads, rain, tide and crowds for Mumbai Traffic Police, the BMC and its "
         "1916 disaster control, ambulance (108) crews and BEST. The AI proposes; a named officer decides.", 14, T2, False),
    ])
    text(s, Inches(0.6), Inches(6.35), Inches(4.9), Inches(0.7), [
        ("Sajag (सजग): Hindi and Marathi for “alert, watchful”.", 11, T3, False),
        (f"Open source (MIT) · one on-premises AI computer · {REPO}", 11, T3, False),
    ])
    text(s, Inches(5.8), Inches(7.1), Inches(7.35), Inches(0.3), [(credit("sea-link-night"), 8.5, T2, False, PP_ALIGN.RIGHT)])

    # 2 · the problem
    s = slide()
    kicker_title(s, "THE PROBLEM", "Rain at high tide, and Mumbai stops")
    photo(s, "tulsi-pipe-road-rain", Inches(0.6), Inches(1.95), Inches(3.7), Inches(4.1), fx=0.45)
    cards = [
        ("≈ 4.5 m tide", "A heavy burst at a high tide of about 4.5 m closes the sea outfalls. The water has nowhere to go.¹"),
        ("386–498 spots", "Hundreds of known flooding spots, by year: Hindmata, King's Circle, Sion, Kurla, Parel, Andheri and Milan subways.²"),
        ("26 May · 18–19 Aug 2025", "The earliest onset in decades flooded a new Metro station; in August Santacruz logged ~207–238 mm in 24 h, the Mithi reached ~3.9 m against a 4 m danger mark and Andheri Subway shut.³"),
        ("~68 lakh riders a day", "ride the suburban locals. When tracks flood at Sion and Kurla, they pour onto roads and station forecourts.⁴"),
        ("~126 hours", "lost to peak-hour traffic in 2025; rush hour runs at ~17–21 km/h; 18th most congested city in the world.⁵"),
        ("53 roads", "under restrictions on a visarjan night, Lalbaug to Girgaon Chowpatty, while emergencies still need a way through.⁶"),
    ]
    for i, (big, body) in enumerate(cards):
        cx = Inches(4.55) + (i % 2) * Inches(4.12)
        cy = Inches(1.95) + (i // 2) * Inches(1.5)
        box(s, cx, cy, Inches(3.97), Inches(1.38), S1)
        text(s, cx + Inches(0.2), cy + Inches(0.13), Inches(3.6), Inches(1.2), [(big, 16, WHITE, True), (body, 10, T2, False)])
    footer(s, n, "¹ BMC chief engineer via Free Press Journal (2025); India TV explainer (27 May 2025). ² BMC counts via Free Press Journal "
                 "(386 chronic spots; 453 → 498 waterlogging spots in a later report). ³ IMD; Free Press Journal; The Statesman; HT (May and Aug 2025). "
                 "⁴ Central and Western Railway data via Free Press Journal (2025-26 average). ⁵ TomTom Traffic Index 2025. ⁶ The Statesman (2024).")

    # 3 · who sees what today
    s = slide()
    kicker_title(s, "TODAY", "Every agency sees one piece")
    cols = [
        ("Mumbai Traffic Police", "Roads, signals, junctions and cameras.", "Diversions, holds, closures."),
        ("BMC · 1916", "Drains, storm-water pumps, waterlogging and tree-fall calls.", "Pumps, crews, civic alerts."),
        ("Central and Western Railway", "Tracks and trains.", "Suspensions and platform announcements."),
        ("Ambulance (108)", "Its own vehicles and calls.", "Needs a clear road to KEM, Sion, JJ or Nair."),
        ("IMD Mumbai", "Rain at Santacruz and Colaba, radar, warnings.", "Nowcasts and colour-coded alerts."),
    ]
    for i, (who, sees, does) in enumerate(cols):
        cx = Inches(0.6) + i * Inches(2.45)
        box(s, cx, Inches(1.9), Inches(2.3), Inches(1.95), S1)
        text(s, cx + Inches(0.2), Inches(2.05), Inches(1.95), Inches(1.8), [
            (who, 14, WHITE, True),
            ([("Sees  ", T3, True), (sees, T2, False)], 10.5, T2, False),
            ([("Acts  ", T3, True), (does, T2, False)], 10.5, T2, False),
        ])
    box(s, Inches(0.6), Inches(3.98), Inches(12.1), Inches(1.12), S2)
    text(s, Inches(0.85), Inches(4.1), Inches(11.6), Inches(0.95), [
        ("Nobody holds one live picture that joins rain × tide × pumps × traffic × crowds and says what to do in the next 30–90 minutes.", 15.5, WHITE, True),
        ("The same gap shows on visarjan nights, at Wankhede egress, during protected movements and when a bridge or highway breaks down. "
         "Coordination runs on phone and radio.", 10.5, T2, False),
    ])
    for i, (slug, fy) in enumerate((("apollo-bunder-rain", 0.62), ("dadar-local", 0.6), ("best-double-decker", 0.56))):
        cx = Inches(0.6) + i * Inches(4.1)
        photo(s, slug, cx, Inches(5.25), Inches(3.9), Inches(1.12), fy=fy)
    footer(s, n)

    # 4 · the answer
    s = slide()
    kicker_title(s, "SAJAG", "One live picture. One decision loop.")
    steps = [
        ("See", "Roads and live traffic, rain, the Apollo Bunder tide, BMC pumps, IMD and NDMA alerts, Mumbai news (aggregate), field reports and camera road state, on one map."),
        ("Look ahead", "Each corridor 15–120 min ahead with uncertainty bands; a waterlogging nowcast ranks every road and subway by risk and lead time."),
        ("Decide", "One proposal at a time, with what changes if approved: a diversion, a signal plan tested in a traffic twin, a rolling hold, a green corridor, a request to BMC."),
        ("Act", "A named officer approves or rejects; nothing acts on its own. No answer: the current plan holds. Advisories go out in English, Marathi and Hindi, read aloud."),
    ]
    picture(s, SHOTS / "home.jpg", Inches(0.6), Inches(1.9), Inches(6.0), Inches(3.75), label="home.jpg")
    for i, (h, b) in enumerate(steps):
        cx = Inches(6.85) + (i % 2) * Inches(2.98)
        cy = Inches(1.9) + (i // 2) * Inches(1.93)
        box(s, cx, cy, Inches(2.86), Inches(1.82), S1)
        text(s, cx + Inches(0.18), cy + Inches(0.13), Inches(2.52), Inches(1.65), [(f"{i + 1}  {h}", 15, WHITE, True), (b, 10, T2, False)])
    text(s, Inches(0.6), Inches(5.9), Inches(12.1), Inches(0.9), [
        ("The AI proposes. A named officer decides.", 17, WHITE, True),
        ("Every approval and rejection is recorded with the officer's name, the evidence and the time. "
         "If no one answers, nothing changes on the street.", 11.5, T2, False),
    ])
    footer(s, n)

    # 5 · monsoon x tide nowcast
    s = slide()
    kicker_title(s, "1 · RAIN × TIDE NOWCAST", "Which road goes under next, 30–90 minutes ahead")
    picture(s, SHOTS / "map-waterlogging.jpg", Inches(0.6), Inches(1.9), Inches(7.4), Inches(4.63), label="map-waterlogging.jpg")
    text(s, Inches(8.3), Inches(1.95), Inches(4.45), Inches(4.7), [
        ("Watched first", 15, WHITE, True),
        ("Hindmata, King's Circle, Sion, Kurla by the Mithi, Andheri Subway, Milan Subway, Parel.", 11.5, T2, False),
        ("The drivers, each labelled", 15, WHITE, True),
        ("Rain: Open-Meteo, LIVE (IMD where reachable). Tide: Apollo Bunder harmonic model, MODELLED. "
         "Terrain: Copernicus 30 m DEM and OSM drains. Pumps: BMC storm-water stations at Haji Ali, Irla, Love Grove, "
         "Cleveland Bunder, Britannia and Gazdarbandh, EMULATED until access.", 11.5, T2, False),
        ("Replayed on a real storm", 15, WHITE, True),
        ("{{REPLAY_DATE}}: {{REPLAY_RESULT}}", 11.5, T2, False),
    ])
    footer(s, n, "risk, depth and lead time are MODELLED from the drivers above; the replay uses observed rain for that date (IMD / Open-Meteo archive).")

    # 6 · decide
    s = slide()
    kicker_title(s, "2 · DECIDE", "One proposal at a time. A named officer decides.")
    picture(s, SHOTS / "decide-waterlogging.jpg", Inches(0.6), Inches(1.9), Inches(7.4), Inches(4.63), label="decide-waterlogging.jpg")
    props = [
        ("Divert WEH traffic", "before Andheri Subway closes, onto routes the nowcast keeps dry."),
        ("Hold BEST routes", "that run through a flooding subway, with the diversion attached."),
        ("Green corridor", "for an ambulance (108) to KEM or Sion Hospital, junction by junction."),
        ("Ask BMC · 1916", "for pumps at King's Circle when the station there is short."),
    ]
    y = Inches(1.95)
    for h_, b in props:
        box(s, Inches(8.3), y, Inches(4.45), Inches(0.9), S1)
        text(s, Inches(8.48), y + Inches(0.12), Inches(4.1), Inches(0.75), [([(h_ + "  ", WHITE, True), (b, T2, False)], 11.5, T2, False)])
        y += Inches(0.99)
    text(s, Inches(8.3), Inches(5.95), Inches(4.45), Inches(0.7), [
        ("Each card shows its evidence, what changes, confidence and assumptions. Approve or reject is logged with the officer's name.", 10.5, T3, False)])
    footer(s, n)

    # 7 · traffic two hours ahead + protected movements
    s = slide()
    kicker_title(s, "3 · TRAFFIC AHEAD · PROTECTED MOVEMENTS", "The next two hours, and movements without a freeze")
    picture(s, SHOTS / "map-forecast.jpg", Inches(0.6), Inches(1.9), Inches(5.0), Inches(3.13), label="map-forecast.jpg")
    picture(s, SHOTS / "map-escort.jpg", Inches(5.8), Inches(1.9), Inches(5.0), Inches(3.13), label="map-escort.jpg")
    photo(s, "evening-traffic", Inches(11.0), Inches(1.9), Inches(1.73), Inches(3.13), fx=0.7, credit_below=False)
    text(s, Inches(0.6), Inches(5.25), Inches(5.0), Inches(1.4), [
        ("Two hours ahead, with bands", 15, WHITE, True),
        ("Chronos-2 forecasts every corridor 15–120 min ahead with p10–p90 bands. A signal change is tested in a "
         "traffic twin of Mumbai's roads first, and offered only if it helps without moving the jam. SIMULATED traffic until MTP detectors are connected.", 11, T2, False),
    ])
    text(s, Inches(5.8), Inches(5.25), Inches(6.9), Inches(1.4), [
        ("Mantralaya → Mumbai Airport T2: rolling holds", 15, WHITE, True),
        ("Each junction is held for a couple of minutes just ahead of the convoy and released behind it, never a blanket freeze. "
         "On Sajag's network the route runs {{IMPACT_VIP_KM}} km over {{IMPACT_VIP_JUNCTIONS}} junctions.", 11, T2, False),
    ])
    footer(s, n, "route length and junction count from Sajag's OpenStreetMap network of Mumbai. "
                 f"Photo, right: {credit('evening-traffic')}.")

    # 8 · crowds: visarjan night and station surge
    s = slide()
    kicker_title(s, "4 · CROWDS", "Visarjan night and the station surge")
    photo(s, "visarjan-girgaon-chowpatty", Inches(0.6), Inches(1.9), Inches(5.95), Inches(2.45), fy=0.55)
    photo(s, "csmt-dusk", Inches(6.75), Inches(1.9), Inches(5.95), Inches(2.45), fy=0.6)
    text(s, Inches(0.6), Inches(4.95), Inches(5.95), Inches(1.7), [
        ("Lalbaug → Girgaon Chowpatty", 15, WHITE, True),
        ("Closures and one-ways on the procession roads, the crowd load at Girgaon Chowpatty, Juhu and Dadar Chowpatty, "
         "and an emergency corridor kept open through the night. Restrictions on 53 roads in 2024.¹ Crowd load is a SIMULATED scenario.", 11, T2, False),
    ])
    text(s, Inches(6.75), Inches(4.95), Inches(5.95), Inches(1.7), [
        ("When the locals stop", 15, WHITE, True),
        ("Flooded tracks at Sion and Kurla push riders out at CSMT, Dadar, Kurla and Andheri. Sajag shows the forecourt load and "
         "proposes holds on turning traffic and extra BEST buses on the right roads. Rail running status is EMULATED.", 11, T2, False),
    ])
    footer(s, n, "¹ The Statesman (2024 visarjan advisory).")

    # 9 · vehicles, voice, advisories
    s = slide()
    kicker_title(s, "5 · VEHICLES · VOICE · ADVISORIES", "A stolen car, a spoken report, an advisory in three languages")
    cols = [
        ("decide-stolen.jpg", "Stolen-vehicle chain",
         "ANPR sightings (EMULATED) of a sample plate, MH 01 AB 1234, are linked into one chain for an officer. The plate stays masked until a named "
         "officer is on duty. No e-challan can be approved against a theft victim."),
        ("voice-report.jpg", "Voice field report",
         "An officer speaks in Marathi, Hindi or English; the on-premises speech model returns place · kind · severity with the "
         "transcript, as an unverified report. Audio is not stored. Camera road state reads roads and vehicles only."),
        ("advisories.jpg", "Advisories, read aloud",
         "Plain words for citizens, in three languages, with a Listen button (synthetic voice):"),
    ]
    for i, (shot, h_, b) in enumerate(cols):
        cx = Inches(0.6) + i * Inches(4.1)
        picture(s, SHOTS / shot, cx, Inches(1.9), Inches(3.9), Inches(2.44), label=shot)
        text(s, cx, Inches(4.5), Inches(3.9), Inches(2.1), [(h_, 15, WHITE, True), (b, 11, T2, False)])
    text(s, Inches(8.8), Inches(5.55), Inches(3.9), Inches(1.1), [
        ("Hindmata waterlogged; please use another route.", 10, T3, False),
        ("हिंदमाता येथे पाणी साचले आहे; कृपया पर्यायी मार्ग वापरा.", 10, T3, False),
        ("हिंदमाता में जलभराव है; कृपया वैकल्पिक मार्ग लें।", 10, T3, False),
    ])
    footer(s, n)

    # 10 · technology
    s = slide()
    kicker_title(s, "TECHNOLOGY", "Open models on one on-premises computer")
    rows = [
        ("Forecast", "Chronos-2 (Apache-2.0)", "Corridors 15–120 min ahead; error 55% below the seasonal baseline in backtest (SIMULATED history)"),
        ("Waterlogging", "Rain × tide × terrain × pumps", "{{REPLAY_DATE}} replay: {{REPLAY_RESULT}}"),
        ("Signal twin", "Cell-transmission model + Webster / max-pressure", "Shockwave speed within 0.2% of theory; every signal proposal tested against doing nothing"),
        ("Speech", "IndicConformer 600M (Marathi, Hindi) · Whisper large-v3-turbo (English) · Indic Parler-TTS", "{{SPEECH_RESULT}}"),
        ("Vision", "Qwen3-VL-8B (Apache-2.0)", "{{VISION_RESULT}}"),
        ("Decision", "pplx-decider-v1.2 (27B) + Gemma 4", "Typed answers in 1.0 s at p95; 22 of 26 labelled decisions on the Kolkata reference pack"),
    ]
    y = Inches(1.9)
    for a, b, c in rows:
        box(s, Inches(0.6), y, Inches(12.1), Inches(0.66), S1)
        text(s, Inches(0.8), y + Inches(0.16), Inches(1.8), Inches(0.45), [(a, 13, WHITE, True)])
        text(s, Inches(2.6), y + Inches(0.12), Inches(4.4), Inches(0.5), [(b, 10.5, T2, False)])
        text(s, Inches(7.1), y + Inches(0.12), Inches(5.45), Inches(0.5), [(c, 10.5, T2, False)])
        y += Inches(0.72)
    text(s, Inches(0.6), Inches(6.3), Inches(12.1), Inches(0.75), [
        ("No data leaves the control room; it keeps working when the internet fails in a cyclone. No licence fees.", 12, T2, False),
        ("It runs today: {{GATES}} gates green · {{TESTS_PY}} Python and {{TESTS_RUST}} Rust tests · {{SUITES}} console unit suites.", 12, WHITE, True),
    ])
    footer(s, n)

    # 11 · honest labels and guardrails
    s = slide()
    kicker_title(s, "HONEST BY DESIGN", "Every number says what it is")
    labels = [
        ("LIVE", "a real public feed: Open-Meteo rain, WAQI and OpenAQ air, NASA FIRMS, NDMA Sachet alerts for Maharashtra, IMD where reachable, Mumbai news (aggregate), OpenStreetMap."),
        ("EMULATED", "a stand-in for an agency feed until access: BMC pumps and sensors, MTP signal controllers and detectors, ANPR, CCTV, 108 and fleet GPS, BEST and rail running status."),
        ("SIMULATED", "a scenario: traffic and crowds for an exercise or a demo."),
        ("MODELLED", "a computed estimate under stated assumptions: the tide, flood risk, impact."),
        ("Reference photo · not live", "a credited photo that shows a place, never the present."),
    ]
    y = Inches(1.9)
    for lab, body in labels:
        box(s, Inches(0.6), y, Inches(2.1), Inches(0.36), S3)
        text(s, Inches(0.6), y + Inches(0.08), Inches(2.1), Inches(0.3), [(lab, 9.5, WHITE, True, PP_ALIGN.CENTER)])
        text(s, Inches(2.9), y, Inches(4.15), Inches(0.85), [(body, 10.5, T2, False)])
        y += Inches(0.92)
    rules = [
        ("Vehicles only", "No faces, no persons, no tracking of individuals. Plates masked until a named officer is on duty."),
        ("Human in charge", "The AI proposes; a named officer approves every action; no answer, the plan holds; all audited."),
        ("Events, not people", "News and social signals are aggregate and about places; posters are never stored or scored."),
        ("Fair enforcement", "No fine for a theft victim; penalties are recommendations a human reviews."),
        ("Data stays home", "On premises, with retention limits, in the spirit of the DPDP Act 2023."),
    ]
    y = Inches(1.9)
    for h_, b in rules:
        box(s, Inches(7.3), y, Inches(5.4), Inches(0.84), S1)
        text(s, Inches(7.5), y + Inches(0.1), Inches(5.05), Inches(0.72), [(h_, 12.5, WHITE, True), (b, 10, T2, False)])
        y += Inches(0.92)
    footer(s, n)

    # 12 · impact (modelled)
    s = slide()
    kicker_title(s, "EXPECTED IMPACT · MODELLED", "Delay grows with the square of a freeze")
    figs = [
        ("{{IMPACT_FACTOR_CENTRAL}}× less", "junction-freeze delay in the central case (range {{IMPACT_FACTOR_LOW}}×–{{IMPACT_FACTOR_HIGH}}×)"),
        ("{{IMPACT_VIP_BASELINE}} → {{IMPACT_VIP_PLATFORM}}", "commuter-minutes per protected movement, Mantralaya → Mumbai Airport T2 ({{IMPACT_VIP_JUNCTIONS}} junctions, {{IMPACT_VIP_KM}} km)"),
        ("≈ {{IMPACT_AMB_MINUTES_YEAR}} min a year", "returned to ambulance (108) trips that cross a held corridor. Today: ~18.75 min to the patient in older Mumbai figures; 20–45 min at peak in Andheri, Kurla and South Mumbai.¹"),
        ("{{REPLAY_LEAD}}", "warning before a road goes under, in the {{REPLAY_DATE}} replay"),
    ]
    for i, (big, lab) in enumerate(figs):
        cx = Inches(0.6) + (i % 2) * Inches(6.1)
        cy = Inches(1.95) + (i // 2) * Inches(2.2)
        box(s, cx, cy, Inches(5.9), Inches(2.0), S1)
        size = 28 if len(fill(big)) <= 24 else 15  # unfilled placeholders are long; real numbers are short
        text(s, cx + Inches(0.3), cy + Inches(0.22), Inches(5.3), Inches(1.7), [(big, size, WHITE, True), (lab, 11.5, T2, False)])
    footer(s, n, "Model outputs on Sajag's Mumbai OpenStreetMap network ({{NET_JUNCTIONS}} junctions, {{NET_SEGMENTS}} segments, {{NET_KM}} km) "
                 "under stated assumptions (IMPACT_REPORT.md): not field measurements, never a claim about lives saved. "
                 "¹ Context only: BW Healthcare World; The Bridge Chronicle (ranges as reported).")

    # 13 · pilot and cost
    s = slide()
    kicker_title(s, "PILOT", "Twelve months, through one monsoon and one Ganeshotsav")
    plan = [
        ("Month 0–1", "Read-only data MoU with Mumbai Traffic Police, the BMC (1916 disaster control, storm-water drains), Maharashtra SDMA and the ambulance (108) operator; nodal officers named."),
        ("Month 1–2", "Install the on-premises unit in one control room; finish the Mumbai City Pack for the pilot zone; switch adapters from EMULATED to LIVE as access arrives."),
        ("Month 2–4", "Shadow mode before the monsoon: Sajag proposes, officers work as usual; weekly comparison."),
        ("Month 5–12", "Live pilot, e.g. Dr Ambedkar Road (Dadar TT – Hindmata – King's Circle – Sion) and the WEH at Andheri, through the monsoon and visarjan; officers approve every action."),
        ("Month 12", "Independent review; a city-wide plan across the 24 wards."),
    ]
    y = Inches(1.9)
    for a, b in plan:
        text(s, Inches(0.6), y, Inches(1.5), Inches(0.6), [(a, 12.5, WHITE, True)])
        text(s, Inches(2.1), y, Inches(5.4), Inches(0.9), [(b, 11, T2, False)])
        y += Inches(0.92)
    box(s, Inches(7.85), Inches(1.9), Inches(4.85), Inches(4.55), S1)
    text(s, Inches(8.1), Inches(2.1), Inches(4.4), Inches(4.3), [
        ("Cost (planning estimates, not quotes)", 16, WHITE, True),
        ("Pilot, 12 months: ≈ ₹45–55 lakh", 14.5, WHITE, True),
        ("Two on-premises AI units ₹8–10 lakh · engineering ₹29 lakh · water-level sensors at subways and low spots without "
         "BMC gauges (optional, Mumbai estimate) ₹4 lakh · training ₹2 lakh · backup link ₹0.5 lakh · 15% contingency.", 11.5, T2, False),
        ("City-wide, two years: ≈ ₹2–2.5 crore", 14.5, WHITE, True),
        ("Mumbai estimate for 24 wards; running ≈ ₹40–60 lakh a year (estimate).", 11.5, T2, False),
        ("Software licences: ₹0", 14.5, WHITE, True),
        ("Open models, OpenStreetMap, Sajag under MIT; existing CCTV, control rooms and BMC sensors are reused.", 11.5, T2, False),
    ])
    footer(s, n)

    # 14 · scale
    s = slide()
    kicker_title(s, "SCALE", "A city is a folder")
    text(s, Inches(0.6), Inches(1.95), Inches(6.2), Inches(4.6), [
        ("The engine (live picture, forecasting, nowcast, voice, vision, decision loop, console) is the same everywhere. "
         "A City Pack holds what differs: the OpenStreetMap extract and corridors, the gazetteer, agencies and emergency numbers, "
         "plate format, UI languages, local scenarios and impact parameters.", 13, T2, False),
        ("The prototype proves it: the same engine runs the Mumbai pack and the Kolkata reference pack.", 13, T2, False),
        ("Per city: about 1–2 weeks of local data work, local adapters (CCTV, signals, flood sensors) and local SOPs. "
         "The software, models and hardware stay the same.", 13, T2, False),
    ])
    nxt = [
        ("Thane · Navi Mumbai", "the same region, monsoon, tide and commuters"),
        ("Pune", "Mula–Mutha river floods and a Ganeshotsav of its own"),
        ("Nagpur", "the state's second capital; monsoon flash floods"),
        ("Nashik", "pilgrim crowds on the Godavari"),
    ]
    for i, (a, b) in enumerate(nxt):
        cy = Inches(1.95) + i * Inches(1.15)
        box(s, Inches(7.4), cy, Inches(5.3), Inches(1.0), S1)
        text(s, Inches(7.65), cy + Inches(0.15), Inches(4.9), Inches(0.8), [(a, 15, WHITE, True), (b, 11, T2, False)])
    text(s, Inches(7.4), Inches(6.6), Inches(5.3), Inches(0.4), [("Marathi and Hindi are already first-class in the console.", 10.5, T3, False)])
    footer(s, n)

    # 15 · close
    s = slide()
    cover_picture(s, ASSETS / PHOTOS["marine-drive-night"]["file"], 0, 0, W, H, fy=0.55)
    box(s, 0, 0, W, H, BLACK, alpha=55000)
    s.shapes.add_picture(str(ASSETS / "lockup-stacked-night.png"), Inches(5.42), Inches(1.2), height=Inches(1.6))
    text(s, Inches(1.5), Inches(3.3), Inches(10.33), Inches(2.6), [
        ("Not by stopping. By steering.", 44, WHITE, True, PP_ALIGN.CENTER),
        ("For the city that never stops.", 20, T2, False, PP_ALIGN.CENTER),
        (REPO, 14, T2, False, PP_ALIGN.CENTER),
    ])
    text(s, Inches(1.5), Inches(7.08), Inches(10.33), Inches(0.3), [(credit("marine-drive-night"), 8.5, T2, False, PP_ALIGN.CENTER)])

    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    print("wrote", out, n, "slides")
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=HERE / "Sajag_Deck.pptx", help="where to write the .pptx")
    ap.add_argument("--pdf", action="store_true", help="also convert to PDF with LibreOffice, next to the .pptx")
    a = ap.parse_args()
    out = a.out.resolve()
    build(out)
    if a.pdf:
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(out.parent), str(out)], check=True)
    if UNFILLED:
        print("unfilled placeholders (fill docs/evidence/facts.json \"values\"): " + ", ".join(sorted(UNFILLED)), file=sys.stderr)


if __name__ == "__main__":
    main()
