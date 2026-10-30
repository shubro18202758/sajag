#!/usr/bin/env python3
"""Build docs/evidence/evidence.html, the prototype-evidence document for Mumbai, from the repository's own outputs.

Run:   python3 docs/evidence/make_evidence.py [--out PATH.html] && node docs/evidence/render_pdf.mjs [PATH.html] [PATH.pdf]
       python3 docs/evidence/make_evidence.py --fill-impact scripts/impact_results.json
           copies the IMPACT_* and NET_* numbers of a Mumbai impact run into facts.json (only those still unfilled), then builds.
Reads: docs/evidence/facts.json   every number that exists only after the merge ("values"), test totals, readiness;
                                  the deck (docs/deck/make_deck.py) reads the same file
       docs/screenshots/*.jpg, docs/diagrams/*.png, docs/deck/assets/lockup-night.png (brand, from render_brand.mjs)
A value still equal to its own placeholder ("{{KEY}}") is printed as-is, highlighted, and listed on stderr.
Every figure carries its label: LIVE, OBSERVED, MODELLED, SIMULATED or EMULATED; every real-world number its source.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FACTS_PATH = HERE / "facts.json"
SHOTS = ROOT / "docs" / "screenshots"
DIAG = ROOT / "docs" / "diagrams"
ASSETS = ROOT / "docs" / "deck" / "assets"
PHOTOS = {p["slug"]: p for p in json.loads((ASSETS / "photos.json").read_text(encoding="utf-8"))}
PH = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
UNFILLED: set[str] = set()
FACTS: dict = {}
OUT_DIR = HERE


def load_facts() -> dict:
    return json.loads(FACTS_PATH.read_text(encoding="utf-8"))


def is_unfilled(values: dict, key: str) -> bool:
    v = values.get(key)
    return v is None or PH.fullmatch(str(v).strip()) is not None


def e(s: str) -> str:
    """Escape for HTML and fill {{KEY}} placeholders from facts.json; unfilled ones are highlighted."""
    values = FACTS["values"]
    out, last = [], 0
    for m in PH.finditer(s):
        out.append(html.escape(s[last:m.start()], quote=True))
        key = m.group(1)
        if is_unfilled(values, key):
            UNFILLED.add(key)
            out.append(f'<mark class="ph">{{{{{key}}}}}</mark>')
        else:
            out.append(html.escape(str(values[key]), quote=True))
        last = m.end()
    out.append(html.escape(s[last:], quote=True))
    return "".join(out)


def src(path: Path) -> str:
    return Path(os.path.relpath(path, OUT_DIR)).as_posix()


def img(path: Path, alt: str, cls: str = "") -> str:
    if not path.exists():
        return f'<div class="missing {cls}">[{html.escape(path.name)}]</div>'
    return f'<img class="{cls}" src="{src(path)}" alt="{html.escape(alt)}">'


def shot(name: str, caption: str) -> str:
    return f'<figure>{img(SHOTS / name, caption)}<figcaption>{e(caption)}</figcaption></figure>'


def photo_credit(p: dict) -> str:
    return f"Reference photo · not live · {p['caption']} · {p['author']} · {p['license_short']} · Wikimedia Commons"


def table(head: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{e(h)}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def build() -> str:
    f = FACTS
    repo = f.get("repo", "github.com/shubro18202758/sajag")
    screens = f.get("screens", {})
    hero = PHOTOS["sea-link-night"]
    parts: list[str] = []
    parts.append(f"""
<section class="cover">
  {img(ROOT / 'docs/deck/assets/lockup-night.png', 'Sajag', 'lockup')}
  <h1>Prototype evidence · Mumbai</h1>
  <p class="tag">Not by stopping. <b>By steering.</b></p>
  <p class="line">For the city that never stops.</p>
  <p class="sub">One live picture of Mumbai's roads, rain, tide and crowds for Mumbai Traffic Police, the BMC and its 1916
  disaster control, ambulance (108) crews and BEST. On-premises open-source AI proposes; a named officer decides.</p>
  <p class="name">Sajag (सजग): Hindi and Marathi for “alert, watchful”.</p>
  <figure class="hero">{img(ASSETS / hero['file'], hero['caption'])}<figcaption>{e(photo_credit(hero))}</figcaption></figure>
  <p class="meta">{e(f['as_of'])} · {e(repo)} · MIT licence</p>
</section>""")
    parts.append(f"""
<section>
  <h2>1 · What exists today</h2>
  <ul class="facts">
    <li><b>A working system on one on-premises AI computer</b>: {e(f['readiness'])}: road store, live traffic ingest, decision engine,
        operator console (English, Marathi, Hindi), event emulator, OSINT ingest, local language and embedding model hosts.</li>
    <li><b>Five AI services</b> beside it: corridor forecasting (Chronos-2), a waterlogging nowcast (rain × Apollo Bunder tide × terrain × BMC pumps),
        a signal-timing traffic twin, voice in Marathi, Hindi and English (speech-to-text and read-aloud) and camera road state (Qwen3-VL).</li>
    <li><b>Real Mumbai roads</b>: {e(f['network'])}; {e(f['gazetteer'])}.</li>
    <li><b>Open feeds wired in</b>: {e(f['feeds'])}.</li>
    <li><b>Quality</b>: {e('{{GATES}} automated gates green: {{TESTS_PY}} Python tests, {{TESTS_RUST}} Rust tests, {{SUITES}} console unit suites, contract replays and type checks')}.</li>
  </ul>
  <p class="note">Labels used throughout: <b>LIVE</b> (a real open feed), <b>OBSERVED</b> (a measured record), <b>MODELLED</b> (computed
  under stated assumptions), <b>SIMULATED</b> (an exercise scenario), <b>EMULATED</b> (a stand-in for a feed that needs an agency's access),
  <b>Reference photo · not live</b>.</p>
</section>""")
    parts.append(f"""
<section>
  <h2>2 · The problem, in Mumbai</h2>
  {table(['What', 'Fact', 'Source'], [
      ['Rain at high tide', 'Waterlogging is unavoidable when a heavy burst coincides with a high tide of about 4.5 m: the sea outfalls close and the water has nowhere to go', 'BMC chief engineer via Free Press Journal (2025); India TV explainer (27 May 2025)'],
      ['Known flooding spots', "Hundreds, by year: 386 chronic flooding spots in one count; 453 → 498 waterlogging spots in a later one. Hindmata, Dadar TT, King's Circle, Sion, Kurla, Parel, Andheri and Milan subways recur", 'BMC counts via Free Press Journal'],
      ['26 May 2025', 'Earliest monsoon onset in decades; Colaba 135.4 mm in 24 h to 08:30; ~90 mm in 90 minutes flooded the new Acharya Atre Chowk Metro Line 3 station; Hindmata and Dadar TT flooded', 'IMD; Free Press Journal; DT Next; Deccan Herald'],
      ['18–19 Aug 2025', 'Red alert; Vikhroli ~223–230 mm and Santacruz ~207–238 mm in 24 h; the Mithi at ~3.9 m against a 4 m danger mark; 350–500 people evacuated near Kurla; tracks under water at Sion and Kurla; Andheri Subway closed', 'IMD (windows differ); The Statesman; Hindustan Times; Mongabay'],
      ['Pumps', "BMC runs 6 major and 10 mini storm-water pumping stations (Haji Ali, Irla, Love Grove, Cleveland Bunder, Britannia, Gazdarbandh among the major ones); in 2025 only 4 of 6 pumps at King's Circle worked", 'Free Press Journal (2025)'],
      ['Suburban rail', '~68 lakh riders a day on average in 2025-26 (Central ~38.7 lakh, Western ~29.5 lakh); when tracks flood they pour onto roads and station forecourts', 'Railway data via Free Press Journal'],
      ['Traffic', '~126 h lost to peak-hour traffic in 2025; rush-hour speeds ~17–21 km/h; 18th most congested city in the world; worst day 16 Sep 2025', 'TomTom Traffic Index 2025'],
      ['Crowds', 'Anant Chaturdashi visarjan, Lalbaug → Girgaon Chowpatty: restrictions on 53 roads (2024); also Wankhede egress, the Mumbai Marathon, New Year on Marine Drive', 'The Statesman (2024); Lokmat Times (green corridor, 2024)'],
      ['Ambulance (108)', 'Context only: ~18.75 min to the patient in older Mumbai figures; 20–45 min at peak in Andheri, Kurla and South Mumbai', 'BW Healthcare World; The Bridge Chronicle'],
      ['Population', 'Greater Mumbai 1.24 crore; urban agglomeration 1.84 crore', 'Census of India 2011'],
      ['Coordination', 'Mumbai Traffic Police, the BMC and 1916, the railways, ambulance (108) and IMD each hold one piece; nobody holds one live picture of rain × tide × pumps × traffic × crowds', 'observed practice'],
  ])}
</section>""")
    parts.append(f"""
<section>
  <h2>3 · The screens</h2>
  <div class="grid">
    {shot('home.jpg', 'Home: what needs the officer now, rain and tide, the next two hours')}
    {shot('map-waterlogging.jpg', 'Map: waterlogging risk on every road and subway, with its drivers labelled')}
    {shot('decide-waterlogging.jpg', 'Decide: divert, hold BEST, open a green corridor, ask BMC for pumps')}
    {shot('decide-ai.jpg', 'Decide: a signal-timing proposal tested in the traffic twin against doing nothing')}
    {shot('map-escort.jpg', 'A protected movement, Mantralaya → Mumbai Airport T2, with rolling holds')}
    {shot('decide-stolen.jpg', 'A stolen-vehicle chain (MH plates, masked); no fine for a theft victim')}
    {shot('voice-report.jpg', 'A field report spoken in Marathi becomes a structured, unverified report')}
    {shot('road-state.jpg', 'Camera road state: roads and vehicles only; person questions are refused')}
    {shot(screens.get('replay', 'replay-2025-08-19.jpg'), 'Replay of the {{REPLAY_DATE}} storm (observed rain, MODELLED ponding)')}
    {shot('citizen.jpg', 'Citizen page: waterlogging on your road, with Listen')}
    {shot(screens.get('console_marathi', 'home-mr.jpg'), 'The console in Marathi')}
    {shot('advisories.jpg', 'Advisories in English, Marathi and Hindi')}
  </div>
</section>""")
    parts.append(f"""
<section>
  <h2>4 · Architecture</h2>
  <figure class="wide">{img(DIAG / '01-2-system-context.png', 'System context')}<figcaption>System context: everything runs on premises; the console is the only network-facing port.</figcaption></figure>
  <figure class="wide">{img(DIAG / '02-3-1-containers-and-ports.png', 'Containers and ports')}<figcaption>Services and ports.</figcaption></figure>
</section>""")
    parts.append(f"""
<section>
  <h2>5 · The AI, measured</h2>
  {table(['Capability', 'Model (licence)', 'Result', 'Label'], f['ai_rows'])}
  <p class="note">{e(f['ai_note'])}</p>
</section>""")
    parts.append(f"""
<section>
  <h2>6 · Expected impact (MODELLED)</h2>
  {table(['Measure', 'Value', 'Basis'], [
      ['Junction-freeze delay', '{{IMPACT_FACTOR_CENTRAL}}× less (range {{IMPACT_FACTOR_LOW}}×–{{IMPACT_FACTOR_HIGH}}×)', 'rolling holds of a couple of minutes instead of a long freeze (central case); delay scales with the square of the hold'],
      ['Protected movement, Mantralaya → Mumbai Airport T2', '{{IMPACT_VIP_BASELINE}} → {{IMPACT_VIP_PLATFORM}} commuter-minutes', '{{IMPACT_VIP_JUNCTIONS}} junctions, {{IMPACT_VIP_KM}} km on the Mumbai network'],
      ['Ambulance (108)', '≈ {{IMPACT_AMB_MINUTES_YEAR}} minutes a year returned', '{{IMPACT_AMB_TRIPS}} crossing trips per movement-day (assumption)'],
      ['Waterlogging warning', '{{REPLAY_LEAD}} before deep water', 'replay of {{REPLAY_DATE}} on observed rain'],
  ])}
  <p class="note">{e("Model outputs on Sajag's Mumbai OpenStreetMap network ({{NET_JUNCTIONS}} junctions, {{NET_SEGMENTS}} segments, {{NET_KM}} km) under stated assumptions (IMPACT_REPORT.md): not field measurements, and never a claim about lives saved.")}</p>
</section>""")
    parts.append(f"""
<section>
  <h2>7 · Tests and quality</h2>
  {table(['Suite', 'Result'], f['test_rows'])}
</section>""")
    parts.append("""
<section>
  <h2>8 · Implementation and cost</h2>
  <table><thead><tr><th>When</th><th>What</th></tr></thead><tbody>
  <tr><td>Month 0–1</td><td>Read-only data MoU: Mumbai Traffic Police (CCTV stills, signal plans), the BMC (1916 disaster control, storm-water drains and pumps), Maharashtra SDMA (alerts), the ambulance (108) operator; nodal officers named.</td></tr>
  <tr><td>Month 1–2</td><td>Install the on-premises unit in the pilot control room; finish the Mumbai City Pack for the pilot zone; switch adapters from EMULATED to LIVE as access arrives.</td></tr>
  <tr><td>Month 2–4</td><td>Shadow mode before the monsoon: Sajag proposes, officers work as usual, weekly comparison.</td></tr>
  <tr><td>Month 5–12</td><td>Live pilot on one zone, e.g. Dr Ambedkar Road (Dadar TT – Hindmata – King's Circle – Sion) and the WEH at Andheri, through the monsoon and Ganeshotsav; officers approve every action.</td></tr>
  <tr><td>Month 12</td><td>Independent review; a city-wide plan across the 24 wards.</td></tr></tbody></table>
  <table><thead><tr><th>Cost item (planning estimates, not quotes)</th><th>Pilot (12 months)</th></tr></thead><tbody>
  <tr><td>On-premises AI units (2, one as backup)</td><td>₹8–10 lakh</td></tr>
  <tr><td>Engineering (3 × 6 months + 1 × 6 months)</td><td>₹29 lakh</td></tr>
  <tr><td>Water-level sensors at subways and low spots without BMC gauges (optional)</td><td>₹4 lakh (Mumbai estimate)</td></tr>
  <tr><td>Training and SOP workshops</td><td>₹2 lakh</td></tr>
  <tr><td>Backup connectivity</td><td>₹0.5 lakh</td></tr>
  <tr><td>Contingency (15%)</td><td>≈ ₹6–7 lakh</td></tr>
  <tr><td><b>Total pilot</b></td><td><b>≈ ₹45–55 lakh</b></td></tr>
  <tr><td>City-wide, two years (24 wards)</td><td>≈ ₹2–2.5 crore; running ≈ ₹40–60 lakh a year (Mumbai estimates)</td></tr>
  <tr><td>Software licences</td><td>₹0: open models, OpenStreetMap, Sajag (MIT)</td></tr></tbody></table>
</section>
<section>
  <h2>9 · Scalability: a city is a folder</h2>
  <p>Everything city-specific lives in a City Pack (<code>cities/&lt;id&gt;/</code>): the OpenStreetMap extract and corridors, gazetteer, agencies,
  emergency numbers, plate format, languages, scenarios and impact parameters. The same engine runs the Mumbai pack and the Kolkata reference
  pack. Next packs: Thane and Navi Mumbai (the same region, monsoon, tide and commuters), Pune (Mula–Mutha river floods and its own Ganeshotsav),
  Nagpur and Nashik. Marathi and Hindi are already first-class. Per city: about 1–2 weeks of local data work, local adapters and SOPs.</p>
  <h2>10 · Guardrails</h2>
  <ul class="facts">
    <li>Vehicles only: no faces, no persons; number plates masked until a named duty officer is on duty.</li>
    <li>The AI proposes; a named officer approves every action; with no answer the current plan holds; every decision audited.</li>
    <li>Honest labels on every number and every feed not yet connected.</li>
    <li>Events, not people: news and social signals are aggregate and about places; posters are never stored or scored.</li>
    <li>No e-challan can be approved against a theft victim.</li>
    <li>On premises, with retention limits, in the spirit of the DPDP Act 2023.</li>
  </ul>
</section>
<section class="sources">
  <h2>Sources</h2>
  <ol>
    <li>Free Press Journal: BMC chronic-flooding and waterlogging spot counts; pumping stations and pumps (2025); the 26 May and 18–19 Aug 2025 floods; Ganeshotsav advisories; suburban ridership 2025-26 from railway data</li>
    <li>India TV News, explainer on high tide and Mumbai flooding (27 May 2025)</li>
    <li>DT Next, Deccan Herald, The Week, Watchers (26 May 2025 onset and rainfall)</li>
    <li>The Statesman, Mongabay, Watchers, Business Today, Hindustan Times (18–19 Aug 2025 rain, the Mithi, evacuations)</li>
    <li>TomTom Traffic Index 2025 (Mumbai) and coverage (Free Press Journal, NewsBytes)</li>
    <li>The Statesman (2024 visarjan, 53 roads); Lokmat Times (green corridor, 2024)</li>
    <li>BW Healthcare World; The Bridge Chronicle (ambulance response times, as reported)</li>
    <li>Census of India 2011 (Greater Mumbai and urban agglomeration population)</li>
    <li>Model cards: amazon/chronos-2, Qwen/Qwen3-VL-8B-Instruct, ai4bharat/indic-conformer-600m-multilingual, openai/whisper-large-v3-turbo, AI4Bharat Indic Parler-TTS, perplexity-ai/pplx-embed (Hugging Face)</li>
    <li>OpenStreetMap contributors (ODbL 1.0); Copernicus DEM GLO-30; Open-Meteo; WAQI; OpenAQ; NASA FIRMS; NDMA Sachet</li>
  </ol>
</section>""")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Sajag: prototype evidence, Mumbai</title>
<style>
@page {{ size: A4; margin: 14mm 13mm; }} @page :first {{ margin: 0; }}
body {{ margin: 0; font-family: Inter, 'Noto Sans Devanagari', 'Lohit Devanagari', sans-serif; color: #111; font-size: 10.5pt; line-height: 1.45; }}
h1 {{ font-size: 28pt; margin: 14mm 0 4mm; }} h2 {{ font-size: 15pt; margin: 0 0 3mm; border-bottom: 1px solid #ddd; padding-bottom: 2mm; }}
section {{ page-break-inside: avoid; margin-bottom: 8mm; }} section.cover {{ page-break-after: always; background: #000; color: #fff;
  margin: 0; padding: 20mm 18mm 14mm; height: 296mm; box-sizing: border-box; overflow: hidden; }}
.cover .lockup {{ height: 14mm; }} .cover .tag {{ font-size: 30pt; font-weight: 700; margin: 6mm 0 2mm; }}
.cover .tag b {{ color: #a6a6a6; }} .cover .line {{ font-size: 16pt; font-weight: 600; margin: 0 0 8mm; }}
.cover .sub {{ font-size: 13pt; color: #cbcbcb; max-width: 150mm; }} .cover .name {{ color: #a6a6a6; }} .cover .meta {{ color: #a6a6a6; margin-top: 6mm; }}
.cover figure.hero {{ margin: 8mm 0 0; }} .cover figure.hero img {{ width: 100%; height: 104mm; max-height: none; object-fit: cover; object-position: 62% 50%; border: 0; border-radius: 0; background: #000; }}
.cover figure.hero figcaption {{ color: #8a8a8a; font-size: 7.5pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 2mm 0 4mm; font-size: 9.5pt; }} th, td {{ border-bottom: 1px solid #e3e3e3; text-align: left; padding: 1.6mm 2mm; vertical-align: top; }}
th {{ background: #f3f3f3; }} .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; }}
figure {{ margin: 0; }} figure img {{ width: 100%; max-height: 92mm; object-fit: contain; background: #f6f6f6; border: 1px solid #ddd; border-radius: 2mm; }} figcaption {{ font-size: 8.5pt; color: #555; margin-top: 1mm; }}
figure.wide img {{ max-height: 110mm; object-fit: contain; }} .note {{ font-size: 8.8pt; color: #555; }} .facts li {{ margin-bottom: 1.5mm; }}
.missing {{ border: 1px dashed #bbb; padding: 10mm; color: #999; text-align: center; }} .sources {{ font-size: 8.8pt; }}
mark.ph {{ background: #e8eefc; color: #2b4c9a; padding: 0 0.6mm; border-radius: 0.6mm; }}
</style></head><body>{''.join(parts)}</body></html>"""


def fill_impact(path: Path) -> None:
    """Copy IMPACT_* and NET_* numbers from a Mumbai impact run into facts.json (only values still unfilled)."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    sc, vip, amb, net = doc["scenarios"], doc["vip_corridor_central"], doc["ambulance"], doc["network"]
    city = str(doc.get("city", "")).lower()
    if city and city != "mumbai":
        sys.exit(f"{path} is an impact run for {city!r}, not Mumbai; nothing filled")
    if (net.get("junctions"), net.get("segments"), net.get("total_km")) == (49, 65, 125.0):
        sys.exit(f"{path} is the Kolkata reference network (49 junctions, 65 segments, 125 km); "
                 "run scripts/impact_run.py on the Mumbai pack first; nothing filled")
    print(f"impact run on {net.get('junctions')} junctions, {net.get('segments')} segments, {net.get('total_km')} km "
          "(make sure this is the Mumbai run)")
    new = {
        "IMPACT_FACTOR_CENTRAL": f"{sc['central']['reduction_factor']:,.0f}",
        "IMPACT_FACTOR_LOW": f"{sc['conservative']['reduction_factor']:,.0f}",
        "IMPACT_FACTOR_HIGH": f"{sc['optimistic']['reduction_factor']:,.0f}",
        "IMPACT_VIP_BASELINE": f"{vip['commuter_minutes_baseline']:,.0f}",
        "IMPACT_VIP_PLATFORM": f"{vip['commuter_minutes_platform']:,.0f}",
        "IMPACT_VIP_JUNCTIONS": f"{vip['junctions']}",
        "IMPACT_VIP_KM": f"{vip['km']:.0f}",
        "IMPACT_AMB_MINUTES_YEAR": f"{amb['minutes_returned_per_year']:,.0f}",
        "IMPACT_AMB_TRIPS": f"{amb['trips_crossing_per_movement_day']:.0f}",
        "NET_JUNCTIONS": f"{net['junctions']}",
        "NET_SEGMENTS": f"{net['segments']}",
        "NET_KM": f"{net['total_km']:.0f}",
    }
    facts = load_facts()
    for k, v in new.items():
        if is_unfilled(facts["values"], k):
            facts["values"][k] = v
            print(f"filled {k} = {v}")
        else:
            print(f"kept   {k} = {facts['values'][k]} (already filled; run value {v})")
    FACTS_PATH.write_text(json.dumps(facts, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    global FACTS, OUT_DIR
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=HERE / "evidence.html", help="where to write the HTML")
    ap.add_argument("--fill-impact", type=Path, metavar="IMPACT_JSON",
                    help="first fill IMPACT_*/NET_* in facts.json from a Mumbai impact run")
    a = ap.parse_args()
    if a.fill_impact:
        fill_impact(a.fill_impact)
    FACTS = load_facts()
    out = a.out.resolve()
    OUT_DIR = out.parent
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(build(), encoding="utf-8")
    print("wrote", out)
    if UNFILLED:
        print("unfilled placeholders (fill docs/evidence/facts.json \"values\"): " + ", ".join(sorted(UNFILLED)), file=sys.stderr)


if __name__ == "__main__":
    main()
