"""The city fusion text mask for registration marks (C-C; ethics rule 5: ANPR is vehicles-only, marks are masked
on every surface) — ``traffic_oracle.city.common.mask_plates_in_text``.

The rule is the deck's ``src/lib/workspace/mask.ts`` (``maskMarks``), so the oracle and the deck mask the same
text the same way:

* a mark starts with a REAL Indian state / union-territory code (39, incl. TG), in ANY case, with up to three
  separators between its parts: space, ``.``, ``-``, ``/``, ``_`` (``wb06em9001``, ``WB.06.EM.9001``,
  ``WB/06/EM/9001``, ``Wb 06 Em 9001``); the 4-digit number is masked but its last digit;
* a spaced candidate whose series spells a month is a DATE (left alone) only when the state code and the series
  are not both upper case ("As of 24 Oct 2026", "on 12 oct 2026"); "WB 01 MAY 1234" is a mark;
* uuids are held out (a URN's hex group is never a mark); times, years, FIR numbers stay;
* then the pre-change upper-case rule runs as a SUPERSET pass (fail closed): an UPPER-case mark shape masks
  exactly as it always did, a real state code or not (``XY12AB1234`` — the watchlist's ``normalize_plate`` accepts
  any two letters); text without a mark comes back unchanged (the same string).

Lockstep: the state codes equal ``mask.ts``'s, and — when node and the deck's esbuild are
installed — the oracle's output on the whole case table IS the deck's own ``maskMarks`` output
(the deck runs the same upper-case pass, FIX-C): the two differ on nothing —
:data:`SUPERSET_ONLY` is empty — (bundled into a temporary directory, never the worktree).

Both passes have ASCII semantics, as the deck's JavaScript regexes do (FIX-AUDIT-A: the upper-case
pass lacked ``re.ASCII``, so ``\\d`` took Arabic-Indic digits and ``\\b`` saw them as word characters
— ``WS 21019١٢`` stayed raw in the oracle while the deck masked it).  A SEEDED differential fuzz
(ASCII and Unicode-adjacent text: Unicode digits and spaces, accented and case-folding-trap letters)
runs the generated corpus through both masks and requires identical output, case for case.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from traffic_oracle.city import common

DECK = Path(__file__).resolve().parents[2] / "command-deck"
MASK_TS = DECK / "src" / "lib" / "workspace" / "mask.ts"
ESBUILD = DECK / "node_modules" / ".bin" / "esbuild"

#: The pre-change rule (upper-case marks only; any two letters) — the reference for "unchanged".
_OLD_RE = re.compile(r"\b([A-Z]{2}[ -]?\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?)(\d{4})\b")


def _old(text: str) -> str:
    return _OLD_RE.sub(lambda m: m.group(1) + "•••" + m.group(2)[-1], text)


#: (text, masked) — the rule, case by case.
CASES: list[tuple[str, str]] = [
    # upper case: exactly as before
    ("WB06EM9001", "WB06EM•••1"),
    ("WB 06 EM 9001", "WB 06 EM •••1"),
    ("WB-01-AB-1234", "WB-01-AB-•••4"),
    ("Car WB01AB1234 seen at J11", "Car WB01AB•••4 seen at J11"),
    ("WB 1 1234", "WB 1 •••4"),
    ("TG09AB1234", "TG09AB•••4"),
    # any case
    ("wb06em9001", "wb06em•••1"),
    ("Wb 06 Em 9001", "Wb 06 Em •••1"),
    ("e-challan for mh12ab3456 proposed", "e-challan for mh12ab•••6 proposed"),
    # dotted, slashed, underscored, spaced twice, glued
    ("WB.06.EM.9001", "WB.06.EM.•••1"),
    ("wb.06.em.9001", "wb.06.em.•••1"),
    ("WB/06/EM/9001", "WB/06/EM/•••1"),
    ("WB_06_EM_9001", "WB_06_EM_•••1"),
    ("WB - 06 - EM - 9001", "WB - 06 - EM - •••1"),
    ("WB 06 EM 9001", "WB 06 EM •••1"),
    ("dl8sep1234", "dl8sep•••4"),  # a series glued to its number is never a date
    ("DL8SEP1234", "DL8SEP•••4"),
    # month series: upper case is a mark, mixed / lower case a date
    ("WB 01 MAY 1234", "WB 01 MAY •••4"),
    ("WB-01-OCT-1234", "WB-01-OCT-•••4"),
    ("AS 24 OCT 2026", "AS 24 OCT •••6"),  # all caps after a state-code word: the rail prefers masking
    ("As of 24 Oct 2026", "As of 24 Oct 2026"),
    ("AS 24 Oct 2026", "AS 24 Oct 2026"),
    ("on 12 oct 2026", "on 12 oct 2026"),
    ("dl 8 sep 1234", "dl 8 sep 1234"),
    ("updated 24 Oct 2026 at 10:30", "updated 24 Oct 2026 at 10:30"),
    # an upper-case shape without a real state code: the pre-change rule still masks it (superset, fail closed)
    ("XY12AB1234", "XY12AB•••4"),
    ("XY 12 AB 1234 on the watchlist", "XY 12 AB •••4 on the watchlist"),
    ("AS OF 24 OCT 2026", "AS OF 24 OCT •••6"),  # all caps: masked as it always was
    # never a mark
    ("xy12ab1234", "xy12ab1234"),  # any case needs a real state code
    ("FIR 12/2026 registered", "FIR 12/2026 registered"),
    ("at 10 am 2026", "at 10 am 2026"),
    ("UP 2026 budget", "UP 2026 budget"),
    ("event:3f2a1b12-3456-4abc-8def-0123456789ab", "event:3f2a1b12-3456-4abc-8def-0123456789ab"),
    ("ab12-3456 and 0b7e3c2a-1111-4d1e-9a8b-5c6d7e8f9a0b", "ab12-3456 and 0b7e3c2a-1111-4d1e-9a8b-5c6d7e8f9a0b"),
    # a uuid whose hex groups read like a Daman & Diu mark ('dd12-3456') stays an id
    ("dispatch:0b7e3c2a-dd12-3456-9a8b-5c6d7e8f9a0b", "dispatch:0b7e3c2a-dd12-3456-9a8b-5c6d7e8f9a0b"),
    ("DD 12 AB 3456 near dispatch:0b7e3c2a-dd12-3456-9a8b-5c6d7e8f9a0b",
     "DD 12 AB •••6 near dispatch:0b7e3c2a-dd12-3456-9a8b-5c6d7e8f9a0b"),
    ("osint_event:0b7e3c2a-1111-4d1e-9a8b-5c6d7e8f9a0b near WB01AB1234",
     "osint_event:0b7e3c2a-1111-4d1e-9a8b-5c6d7e8f9a0b near WB01AB•••4"),
    ("", ""),
    ("plain text, no mark", "plain text, no mark"),
    # ASCII semantics around Unicode digits (audit A's fuzz divergences): an Arabic-Indic digit is
    # never a digit of a mark, and is a word boundary like any non-ASCII character
    ("FIR 1234/2026 UC  49\tWS 21019١٢", "FIR 1234/2026 UC  49\tWS 2•••9١٢"),
    ("dispatch:TB--69./DF 5941١٢", "dispatch:TB--69./DF 5941١٢"),
    ("24 Oct 2026 JH_758-SA-0240١٢", "24 Oct 2026 JH_758-SA-0240١٢"),
    ("XY12AB1234١", "XY12AB•••4١"),
    ("WB 06 EM ١٢٣٤", "WB 06 EM ١٢٣٤"),
    ("WB06EM９００１", "WB06EM９００１"),  # fullwidth digits are not ASCII digits either
]

#: The cases where the oracle masks MORE than the deck's ``maskMarks``: none — the deck runs the
#: same upper-case pass (FIX-C), so the two agree on every case.
SUPERSET_ONLY: frozenset[str] = frozenset()


@pytest.mark.parametrize(("text", "masked"), CASES)
def test_the_mask_case_by_case(text, masked):
    assert common.mask_plates_in_text(text) == masked


def test_lower_case_dotted_and_slashed_marks_never_leave_raw():
    for text in ("wb06em9001", "WB.06.EM.9001", "wb/06/em/9001", "Wb_06_Em_9001"):
        out = common.mask_plates_in_text(text)
        assert "9001" not in out and out.endswith("•••1"), text


def test_upper_case_marks_mask_exactly_as_before():
    marks = ["WB06EM9001", "WB 06 EM 9001", "WB-01-AB-1234", "MH12AB3456", "DL 8 C 1234", "KA01MX0001",
             "WB 1 1234", "near WB01AB1234 and WB 05 CD 5678 at J11", "TN 07 BZ 9876"]
    for text in marks:
        assert common.mask_plates_in_text(text) == _old(text), text


def test_every_upper_case_mark_shape_masks_as_before_state_code_or_not():
    """Seeded sweep over the pre-change rule's own domain (two upper-case letters, a space, a dash or nothing
    between the parts, an optional 1-3 letter series): the output is exactly the pre-change output."""
    import random

    rng = random.Random(20261025)
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for _ in range(5000):
        sep = [rng.choice(["", " ", "-"]) for _ in range(3)]
        series = "".join(rng.choice(letters) for _ in range(rng.randint(0, 3)))
        mark = (rng.choice(letters) + rng.choice(letters) + sep[0] + str(rng.randint(1, 99)) + sep[1]
                + (series + sep[2] if series else "") + f"{rng.randint(0, 9999):04d}")
        text = rng.choice(["{}", "Car {} seen at J11", "reason: watch {} near Esplanade"]).format(mark)
        assert common.mask_plates_in_text(text) == _old(text), text


def test_text_without_a_mark_is_returned_as_it_was():
    text = "Officer note: road clear by 24 Oct 2026, ref 0b7e3c2a-1111-4d1e-9a8b-5c6d7e8f9a0b"
    assert common.mask_plates_in_text(text) is text
    assert common.mask_plates_in_text(None) == ""


def test_mask_plate_and_the_feed_text_use_the_rule():
    assert common.mask_plate("wb06em9001") == "wb06em•••1"
    assert common.mask_plate("XY12AB1234") == "XY12AB•••4"  # a raw plate field is always masked
    item = common.feed_item("x", datetime.now(UTC), "anpr", [], actor=None, actor_kind="machine",
                            text="Read wb.06.em.9001 at camera C1")
    assert item["text"] == "Read wb.06.em.•••1 at camera C1"


def test_the_state_codes_are_the_decks():
    if not MASK_TS.exists():
        pytest.skip("command-deck workspace/mask.ts not in this tree")
    src = MASK_TS.read_text(encoding="utf-8")
    block = re.search(r"STATE_CODES[^=]*=\s*Object\.freeze\(\[(.*?)\]\)", src, re.S)
    assert block, "STATE_CODES not found in mask.ts"
    deck = re.findall(r"'([A-Z]{2})'", block.group(1))
    assert tuple(deck) == common.STATE_CODES and len(deck) == 39


def test_both_passes_have_ascii_semantics():
    """Every mark regex is ASCII (``\\d``, ``\\b``, case folding), like the deck's JavaScript."""
    for rx in (common._PLATE_IN_TEXT_RE, common._PLATE_UPPER_RE, common._UUID_IN_TEXT_RE):
        assert rx.flags & re.ASCII, rx.pattern[:40]
    for digits in ("١٢٣٤", "१२३४", "১২৩৪", "１２３４"):  # Arabic-Indic, Devanagari, Marathi, fullwidth
        for text in (f"XY12AB{digits}", f"WB 06 EM {digits}", f"wb06em{digits}"):
            assert common.mask_plates_in_text(text) == text


def _deck_mask(tmp_path, texts: list[str]) -> list[str]:
    """The deck's own ``maskMarks`` over ``texts`` (esbuild bundle + node, in ``tmp_path``)."""
    node = shutil.which("node")
    if node is None or not ESBUILD.exists() or not MASK_TS.exists():
        pytest.skip("node or the deck's esbuild not installed")
    bundle = tmp_path / "mask.mjs"
    subprocess.run(
        [str(ESBUILD), str(MASK_TS), "--format=esm", "--platform=node", "--tsconfig-raw={}",
         f"--outfile={bundle}", "--log-level=error"],
        check=True, capture_output=True, timeout=60,
    )
    runner = tmp_path / "run.mjs"
    runner.write_text(
        "import { maskMarks } from './mask.mjs';\n"
        "import { readFileSync } from 'node:fs';\n"
        "const cases = JSON.parse(readFileSync(process.argv[2], 'utf8'));\n"
        "process.stdout.write(JSON.stringify(cases.map((c) => maskMarks(c))));\n",
        encoding="utf-8",
    )
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps(texts), encoding="utf-8")
    out = subprocess.run([node, str(runner), str(cases)], check=True, capture_output=True, timeout=120)
    deck = json.loads(out.stdout.decode("utf-8"))
    assert len(deck) == len(texts)
    return deck


def test_parity_with_the_decks_mask_marks(tmp_path):
    texts = [t for t, _ in CASES]
    deck = _deck_mask(tmp_path, texts)
    oracle = [common.mask_plates_in_text(t) for t in texts]
    # the oracle and the deck run the same two passes: identical output on every case
    assert oracle == deck
    assert {t for t, o, d in zip(texts, oracle, deck, strict=True) if o != d} == SUPERSET_ONLY


# ── seeded differential fuzz: oracle vs the deck's maskMarks ─────────────────

#: Separators between a mark's parts: the ones a mark is written with, and Unicode-adjacent ones
#: (JavaScript's ``\s`` includes NBSP and the other Unicode spaces; the any-case rule honours them).
_FUZZ_SEPS_ASCII = ["", " ", "-", ".", "/", "_", "  ", " - ", "\t", "--", "./"]
_FUZZ_SEPS_UNICODE = ["\u00a0", "\u2009", "\u3000", "\ufeff", "\u2028", "\u00a0-"]

#: Text around the marks: ASCII noise, then Unicode-adjacent noise — Unicode digits (Arabic-Indic,
#: Devanagari, Marathi, fullwidth), accented and dotless letters, the case-folding traps (ı, ſ,
#: K Kelvin sign, İ — which fold to ASCII letters under Unicode rules but not under ASCII ones).
_FUZZ_NOISE_ASCII = ["", " ", "x", "1", "_", "-", ":", "ref ", " at 10:30", "Officer note: ", " near ",
                     "dispatch:", "0b7e3c2a-dd12-3456-9a8b-5c6d7e8f9a0b ", "24 Oct 2026 ", "FIR 1234/2026 "]
_FUZZ_NOISE_UNICODE = ["é", "١٢", "٣", "१२", "১২", "１２", "ı", "ſ", "K", "İ", "Ä", "\u00a0", "ß",
                       "\u200b", "\u0301", "ⅰ", "²"]
_FUZZ_LETTER_TRAPS = {"I": ["ı", "İ"], "S": ["ſ"], "K": ["K"]}


def _fuzz_corpus(seed: int, n: int, *, unicode: bool) -> list[str]:
    """``n`` seeded texts of marks (state code or not, any case, 1-3 RTO digits, an optional series
    — month spellings included — and a 3-5 digit number) between noise."""
    rng = random.Random(seed)
    seps = _FUZZ_SEPS_ASCII + (_FUZZ_SEPS_UNICODE if unicode else [])
    noise = _FUZZ_NOISE_ASCII + (_FUZZ_NOISE_UNICODE if unicode else [])
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def rc(text: str) -> str:
        return "".join(c.upper() if rng.random() < 0.5 else c.lower() for c in text)

    def trap(text: str) -> str:  # a letter swapped for its Unicode case-folding twin
        if not unicode or rng.random() > 0.15:
            return text
        i = rng.randrange(len(text)) if text else 0
        twins = _FUZZ_LETTER_TRAPS.get(text[i:i + 1].upper())
        return text[:i] + rng.choice(twins) + text[i + 1:] if twins else text

    def digits(k: int) -> str:
        return "".join(rng.choice("0123456789") for _ in range(k))

    def mark() -> str:
        upper = rng.random() < 0.6
        state = rng.choice(common.STATE_CODES) if rng.random() < 0.6 else (
            rng.choice(letters) + rng.choice(letters))
        series = rng.choice(["", "".join(rng.choice(letters) for _ in range(rng.randint(1, 4))),
                             rng.choice(["OCT", "Oct", "may", "MAY", "Sep"])])
        if not upper:
            state, series = rc(state), rc(series)
        return (trap(state) + rng.choice(seps) + digits(rng.randint(1, 3)) + rng.choice(seps)
                + trap(series) + rng.choice(seps) + digits(rng.choice([3, 4, 4, 4, 5])))

    out = []
    for _ in range(n):
        parts = [rng.choice(noise)]
        for _ in range(rng.randint(1, 3)):
            parts.append(mark() if rng.random() < 0.8 else rng.choice(noise))
            parts.append(rng.choice(noise))
        out.append("".join(parts))
    return out


#: (seed, cases, unicode-adjacent) — fixed, so a divergence is reproducible by its seed.
_FUZZ_RUNS = ((7, 4000, False), (20261025, 4000, False), (7, 6000, True), (20261025, 6000, True),
              (424242, 6000, True))


def test_seeded_differential_fuzz_against_the_decks_mask_marks(tmp_path):
    """The oracle and the deck mask every generated text identically (audit A: 14-22 divergences
    per 20 000 Unicode-adjacent cases before ``re.ASCII``; this corpus holds such cases)."""
    texts: list[str] = []
    for seed, n, unicode in _FUZZ_RUNS:
        texts += _fuzz_corpus(seed, n, unicode=unicode)
    assert len(set(texts)) > 0.9 * len(texts)  # the corpus is varied, not one repeated case
    assert sum(any(d in t for d in ("١", "१", "১", "１")) for t in texts) > 1000  # Unicode digits
    deck = _deck_mask(tmp_path, texts)
    oracle = [common.mask_plates_in_text(t) for t in texts]
    masked = sum(o != t for o, t in zip(oracle, texts, strict=True))
    assert masked > 0.1 * len(texts)  # the corpus exercises the mask, not only its pass-through
    diff = [(t, o, d) for t, o, d in zip(texts, oracle, deck, strict=True) if o != d]
    assert not diff, f"{len(diff)} of {len(texts)} differ; first: {diff[:3]!r}"
