"""Transcript → structured field report awaiting an officer's confirmation.

A field report is a *claim*, never an action: it always leaves here with
``verification_state = "UNVERIFIED-FIELD"`` and ``requires_confirmation =
true``. Nothing in this service dispatches, diverts or publishes anything.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .kinds import classify
from .places import Gazetteer

__all__ = ["VERIFICATION_STATE", "build_report"]

VERIFICATION_STATE = "UNVERIFIED-FIELD"
NOTE_EN = "Field report awaiting an officer's confirmation. It is not an action."
NOTE_MR = "क्षेत्रातून आलेला अहवाल, अधिकाऱ्याच्या पुष्टीच्या प्रतीक्षेत. ही कारवाई नाही."
NOTE_HI = "फ़ील्ड से आई रिपोर्ट, अधिकारी की पुष्टि की प्रतीक्षा में। यह कोई कार्रवाई नहीं है।"


def build_report(
    transcript: str,
    gazetteer: Gazetteer,
    *,
    source: str,
    language: str,
    asr: dict[str, Any] | None = None,
) -> dict[str, Any]:
    match, candidates = gazetteer.match(transcript)
    cls = classify(transcript)
    return {
        "report_id": str(uuid.uuid4()),
        "received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "place": match.as_dict() if match else None,
        "place_candidates": [c.as_dict() for c in candidates],
        "kind": cls.kind,
        "kind_cues": list(cls.kind_cues),
        "severity": cls.severity,
        "severity_cues": list(cls.severity_cues),
        "transcript": transcript,
        "language": language,
        "source": source,
        "asr": asr,
        "verification_state": VERIFICATION_STATE,
        "requires_confirmation": True,
        "note": {"en": NOTE_EN, "mr": NOTE_MR, "hi": NOTE_HI},
    }
