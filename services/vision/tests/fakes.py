"""Test doubles for the vision service (no model, no network)."""

from __future__ import annotations

from typing import Any


class FakeModel:
    name = "fake-vl"

    def __init__(self, raw: dict[str, Any] | None = None, exc: Exception | None = None) -> None:
        self.raw = raw or {
            "state": "congested", "confidence": 0.9,
            "vehicles_estimate": {"cars": 12, "buses": 3, "two_wheelers": 4, "autos": 1},
            "water_depth_band": "none", "rationale": "Dense queued traffic on all lanes.",
        }
        self.exc = exc
        self.calls: list[tuple[int, str | None]] = []
        self.closed = False

    async def classify(self, image_jpeg: bytes, question: str | None = None) -> dict[str, Any]:
        self.calls.append((len(image_jpeg), question))
        if self.exc:
            raise self.exc
        return dict(self.raw)

    def status(self) -> dict[str, Any]:
        return {"model": self.name, "managed": False, "running": True}

    async def maybe_stop_idle(self) -> bool:
        return False

    async def aclose(self) -> None:
        self.closed = True
