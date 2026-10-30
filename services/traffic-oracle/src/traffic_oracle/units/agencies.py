"""Agency registry — the closed set of dispatchable agencies.

Civic Volunteers (नागरी स्वयंसेवक) work alongside Mumbai Police and Mumbai
Traffic Police at crossings, chowpatties and crowded places — the
ground-level eyes-and-ears arm beside the police.  Making them a
first-class AGENCY ACTOR means: they are dispatchable through the same
channel as police/traffic, their units are emulated on the same graph, and
every dispatch of a civic-volunteer unit carries the same human-approval and
audit trail as any other agency — Sajag strengthens government capability;
volunteers are coordinated, never automated.  The agency CODE stays
``jan_rakshak`` (the migration 011 CHECK value and the API value); only its
labels say "Civic Volunteers".

The registry is deliberately CLOSED (mirrors the migration 011 CHECK):
every unit surfaced anywhere carries one of these codes and labels, so
the canvas/ops board can badge deterministically.

Ethics (C6): agencies and units — never persons.  No name/face fields.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Agency:
    code: str          # migration 011 CHECK value
    label: str         # UI label (EN)
    label_native: str  # UI label (Marathi)
    role: str


JAN_RAKSHAK = Agency(
    code="jan_rakshak",
    label="Civic Volunteers",
    label_native="नागरी स्वयंसेवक",
    role="citizen volunteer coordination, first responder support",
)

AGENCIES: dict[str, Agency] = {
    a.code: a
    for a in (
        JAN_RAKSHAK,
        Agency("police", "Police Control", "पोलीस नियंत्रण कक्ष", "law & order"),
        Agency("traffic", "Traffic Police", "वाहतूक पोलीस", "traffic management"),
        Agency("ambulance", "Ambulance (108)", "रुग्णवाहिका (१०८)", "emergency medical"),
        Agency("fire", "Fire & Emergency", "अग्निशमन व आपत्कालीन सेवा", "fire & rescue"),
    )
}


def agency_label(code: str) -> str:
    agency = AGENCIES.get(code)
    return agency.label if agency else code


def is_agency(code: str) -> bool:
    return code in AGENCIES


__all__ = ["AGENCIES", "JAN_RAKSHAK", "Agency", "agency_label", "is_agency"]
