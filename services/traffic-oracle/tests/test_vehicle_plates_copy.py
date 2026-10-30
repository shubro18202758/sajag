"""The 422 refusal copy of plate normalisation (FIX-E-LOOKUP, audit A).

``normalize_plate``'s :class:`InvalidPlate` messages used to ECHO the raw
input and name a FULL mark (``expected e.g. WB06EM9001`` — the demo's
stolen plate).  The lookup route's 422 already went through
``LOOKUP_INVALID_PLATE_DETAIL`` (no echo, no full mark) because a
near-mark is a mark in all but one character: an error that quotes the
input or an example lets a caller search the space (the audit's
hash-reversal demo recovered the plate in 0.47 ms after 901 tries).

This file pins, for BOTH raises (the too-long/empty guard and the
pattern guard — the earmark route shows them verbatim via ``str(exc)``):

* the message names the FORMAT in words (state code, district number,
  optional series, 4-digit number, BH series) — a caller can fix the
  input without seeing any plate;
* the message never echoes the input and never carries a full mark —
  nothing that ``normalize_plate`` itself would accept, in any
  spelling;
* the message is input-INDEPENDENT: the same sentence for junk, for a
  near-mark and for a date phrase (no per-input detail to mine);
* normalisation itself is unchanged (the accepted/refused sets).

Fails on the pre-change code: the old messages quoted ``{raw!r}`` and
the example marks.  Pure, hermetic, no DB.
"""

from __future__ import annotations

import re

import pytest

from traffic_oracle.vehicles.plates import InvalidPlate, PLATE_PATTERNS, normalize_plate

#: A full registration mark, in the deck's mirrored shape (search.ts's
#: FULL_MARK_RE): the standard series and the Bharat series.  The refusal
#: copy may carry NEITHER.
FULL_MARK = re.compile(r"^(?:[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}|\d{2}BH\d{4}[A-Z]{1,2})$")

#: The format words the copy must carry (a caller can fix the input).
#: "1-4 digit" — what ``PLATE_PATTERNS`` accepts (audit E round 2).
FORMAT_WORDS = ("state code", "district number", "1-4 digit number", "BH-series")

#: Inputs across every refusal path — junk, a near-mark, an over-long
#: input, an empty one.  None may appear in the message.  (A date phrase
#: like "on 12 oct 2026" never reaches the 422: plates.py's own
#: normalisation accepts ON12OCT2026 — the deck's offer gate is what
#: refuses it there; test_normalisation_is_unchanged pins that.)
ECHOES = ["wb!!", "WB06EM9001!", "x" * 40, "", "   ", "WB 06 EM 9001!!"]


def _message(raw: str) -> str:
    with pytest.raises(InvalidPlate) as exc:
        normalize_plate(raw)
    return str(exc.value)


def test_both_raises_describe_the_format_without_any_plate() -> None:
    for raw in ("wb!!", "WB06EM9001!"):
        msg = _message(raw)
        for word in FORMAT_WORDS:
            assert word in msg, f"{raw!r} → {msg!r} lacks {word!r}"


@pytest.mark.parametrize("raw", ECHOES)
def test_the_input_is_never_echoed(raw: str) -> None:
    msg = _message(raw)
    probe = raw.strip()
    if probe:
        assert probe not in msg, f"the message echoes the input: {probe!r} in {msg!r}"
        assert probe.upper() not in msg, f"the message echoes the input: {probe.upper()!r} in {msg!r}"


@pytest.mark.parametrize("raw", ECHOES)
def test_no_full_mark_in_the_message(raw: str) -> None:
    msg = _message(raw)
    # Strip the SEPARATORS the oracle itself strips (space, hyphen, dot) BEFORE
    # the full-mark check (audit E round 2, OR-3): a spaced example mark like
    # 'MH 01 AB 1234' tokenises as WB/01/AB/1234 without the strip and slips
    # past the anchored pattern.  Quotes and other punctuation stay as
    # boundaries, so a quoted example PREFIX ("'MH 01 AB' then 1-4 digits")
    # still tokenises as WB01AB / THEN14DIGITS — neither a full mark.
    flattened = re.sub(r"[\s\-.]+", "", msg.upper())
    for token in re.findall(r"[A-Z0-9]+", flattened):
        assert not FULL_MARK.match(token), f"the message names a full mark: {token!r} in {msg!r}"


def test_the_message_is_input_independent() -> None:
    msgs = {_message(raw) for raw in ("wb!!", "WB06EM9001!", "!!!!", "??")}
    assert len(msgs) == 1, f"the copy varies with the input: {sorted(msgs)}"


def test_the_message_matches_the_lookup_route_style() -> None:
    from traffic_oracle.vehicles import LOOKUP_INVALID_PLATE_DETAIL

    msg = _message("wb!!")
    assert msg.startswith("not a registration plate:"), msg  # the house prefix (test_vehicle_lookup.py pins it)
    # the same rule as the lookup route's own 422: no echo, no full mark
    for probe in ("WB06EM9001", "22BH1234AA", "wb!!"):
        assert probe not in msg and probe not in LOOKUP_INVALID_PLATE_DETAIL


def test_normalisation_is_unchanged() -> None:
    assert normalize_plate("WB 06 EM 9001") == "WB06EM9001"
    assert normalize_plate("wb-06-em-9001") == "WB06EM9001"
    assert normalize_plate("22bh1234aa") == "22BH1234AA"
    assert normalize_plate("WB06EM901") == "WB06EM901"  # 1-3-digit numbers accepted
    # a month-series phrase IS a plate here (the oracle's rule) — the deck's
    # offer gate (search.ts lookupOfferActive + mask.ts hasRawMark) is what
    # keeps it from ever being offered as a vehicle lookup
    assert normalize_plate("on 12 oct 2026") == "ON12OCT2026"
    for raw in ("WB06EM", "24 Oct 2026", "WB/06/EM/9001", "WB_06_EM_9001", "ZZ01AB1234A"):
        with pytest.raises(InvalidPlate):
            normalize_plate(raw)
    assert len(PLATE_PATTERNS) == 2


class TestEarmarkRoute422:
    """The earmark ROUTE's 422 (audit E round 2, OR-5): it surfaces
    ``str(InvalidPlate)`` verbatim — pinned never to echo the plate or name a
    full mark.  Route-level, because the message assembly lives at the route,
    not in plates.py.  The 422 precedes every pool access, so no DB here."""

    @pytest.mark.parametrize("plate", ["WB06EM9001!", "wb 06 em 9001!!", "22BH1234AAX", "on 12 oct 2026!"])
    def test_a_near_mark_is_never_echoed(self, plate: str) -> None:
        from urllib.parse import quote

        fastapi = pytest.importorskip("fastapi")
        pytest.importorskip("httpx")
        from fastapi.testclient import TestClient

        from traffic_oracle.vehicles import router as vehicles_router

        app = fastapi.FastAPI()
        app.include_router(vehicles_router)
        # pool stays unset: the 422 must fire before the route touches it
        with TestClient(app, raise_server_exceptions=True) as client:
            r = client.post(
                f"/api/v1/vehicles/{quote(plate)}/earmark",
                json={"state": "watch", "reason": "pytest route-level 422 probe", "lawful_basis": "stolen_vehicle_fir"},
            )
        assert r.status_code == 422, r.text
        body = r.text
        assert plate not in body, f"the earmark 422 echoes the input: {plate!r}"
        assert plate.upper() not in body
        # and, the plates.py rule again: no full mark anywhere in the body
        flattened = re.sub(r"[\s\-.]+", "", body.upper())
        for token in re.findall(r"[A-Z0-9]+", flattened):
            assert not FULL_MARK.match(token), f"the earmark 422 names a full mark: {token!r}"
