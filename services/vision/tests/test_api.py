"""API contract tests (in-process, fake model; no llama-server)."""

from __future__ import annotations

import importlib.util

import pytest
from fastapi.testclient import TestClient

from fakes import FakeModel
from vision_service.api import VERIFICATION_STATE, create_app, normalize
from vision_service.config import Settings
from vision_service.ethics import mentions_person
from vision_service.model import STATES, ModelUnavailable

HAS_PIL = importlib.util.find_spec("PIL") is not None
HAS_MULTIPART = importlib.util.find_spec("multipart") is not None or \
    importlib.util.find_spec("python_multipart") is not None


def _client(model: FakeModel | None = None, **kw) -> tuple[TestClient, FakeModel]:
    m = model or FakeModel()
    s = Settings(llm_manage=False, **kw)
    return TestClient(create_app(s, model=m)), m


def _post(c: TestClient, data: bytes, ctype: str = "image/jpeg", **params):
    return c.post("/vision/road-state", content=data, headers={"Content-Type": ctype}, params=params)


def test_health_states_policy() -> None:
    c, _ = _client()
    with c:
        body = c.get("/health").json()
    assert body["status"] == "ok" and body["service"] == "vision"
    assert body["states"] == list(STATES)
    assert "no plate reading" in body["policy"]


def test_road_state_contract(jpeg_bytes: bytes) -> None:
    c, m = _client()
    with c:
        r = _post(c, jpeg_bytes)
    assert r.status_code == 200
    b = r.json()
    assert b["state"] == "congested"
    assert b["confidence"] == 0.9
    assert b["vehicles_estimate"] == {"cars": 12, "buses": 3, "two_wheelers": 4, "autos": 1}
    assert b["verification_state"] == VERIFICATION_STATE == "UNVERIFIED-CAMERA"
    assert b["requires_confirmation"] is True
    assert b["model"] == "fake-vl"
    assert "water_depth_band" not in b  # not waterlogged, band "none"
    assert len(b["rationale"].split()) <= 25
    assert len(m.calls) == 1


def test_road_with_pedestrians_gives_road_state_without_person_description(jpeg_bytes: bytes) -> None:
    """The model (here: a fake that ignores its prompt) talks about people; the
    response still carries the road state and no person description."""
    raw = {
        "state": "waterlogged", "confidence": 0.93,
        "vehicles_estimate": {"cars": 2, "buses": 1, "two_wheelers": 0, "autos": 0},
        "water_depth_band": "up_to_wheel_hub",
        "rationale": "Two men in yellow vests and a woman in a saree wade through the water. "
                     "Water covers the carriageway to the wheel hubs.",
    }
    c, _ = _client(FakeModel(raw))
    with c:
        b = _post(c, jpeg_bytes).json()
    assert b["state"] == "waterlogged"
    assert b["water_depth_band"] == "up_to_wheel_hub"
    assert b["rationale"] == "Water covers the carriageway to the wheel hubs."
    assert not mentions_person(b["rationale"])
    assert b["filtered"] is True
    assert b["filter"]["policy"] == "vehicles-and-roads-only"
    for word in ("men", "woman", "saree", "vest"):
        assert word not in b["rationale"].lower()


def test_who_is_in_this_image_is_refused_without_calling_the_model(jpeg_bytes: bytes) -> None:
    c, m = _client()
    with c:
        r = _post(c, jpeg_bytes, question="who is in this image")
    assert r.status_code == 403
    b = r.json()
    assert b["refused"] is True and b["policy"] == "vehicles-and-roads-only"
    assert m.calls == []  # the image never reached the model


def test_plate_question_is_refused(jpeg_bytes: bytes) -> None:
    c, m = _client()
    with c:
        r = _post(c, jpeg_bytes, question="read the number plate of the taxi")
    assert r.status_code == 403 and r.json()["policy"] == "no-plate-reading"
    assert m.calls == []


def test_road_question_is_passed_to_the_model(jpeg_bytes: bytes) -> None:
    c, m = _client()
    with c:
        r = _post(c, jpeg_bytes, question="Is the road passable for buses?")
    assert r.status_code == 200
    assert m.calls[0][1] == "Is the road passable for buses?"


def test_rejects_wrong_content_type_and_non_images(jpeg_bytes: bytes) -> None:
    c, m = _client()
    with c:
        assert _post(c, b"hello", "text/plain").status_code == 415
        assert _post(c, b"GIF89a....", "image/jpeg").status_code == 422
        assert _post(c, b"", "image/jpeg").status_code == 422
    assert m.calls == []


def test_rejects_oversize_image(jpeg_bytes: bytes) -> None:
    c, m = _client(max_image_bytes=1000)
    with c:
        assert _post(c, jpeg_bytes).status_code == 413
    assert m.calls == []


@pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
def test_png_is_reencoded_and_downscaled() -> None:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2400, 1200), (90, 90, 90)).save(buf, "PNG")
    c, m = _client()
    with c:
        b = _post(c, buf.getvalue(), "image/png").json()
    assert b["image"] == {"width": 1024, "height": 512, "format": "png", "resized": True,
                          "metadata": "stripped"}
    assert m.calls[0][0] > 0


@pytest.mark.skipif(HAS_PIL, reason="only without Pillow")
def test_png_without_pillow_is_rejected_cleanly() -> None:
    c, _ = _client()
    with c:
        r = _post(c, b"\x89PNG\r\n\x1a\n" + b"\0" * 64, "image/png")
    assert r.status_code == 422


@pytest.mark.skipif(not HAS_MULTIPART, reason="python-multipart not installed")
def test_multipart_upload_with_question(jpeg_bytes: bytes) -> None:
    c, m = _client()
    with c:
        r = c.post("/vision/road-state", files={"image": ("x.jpg", jpeg_bytes, "image/jpeg")},
                   data={"question": "who is this"})
    assert r.status_code == 403
    assert m.calls == []


def test_model_unavailable_is_503(jpeg_bytes: bytes) -> None:
    c, _ = _client(FakeModel(exc=ModelUnavailable("refused to start: 4 GiB available")))
    with c:
        r = _post(c, jpeg_bytes)
    assert r.status_code == 503
    assert "refused" in r.json()["detail"]


def test_model_is_closed_on_shutdown() -> None:
    c, m = _client()
    with c:
        pass
    assert m.closed


# --- normalisation of whatever the model returns -------------------------------


def test_normalize_unknown_state_and_clamps() -> None:
    out = normalize({"state": "on fire", "confidence": 87,
                     "vehicles_estimate": {"cars": -3, "buses": "2", "two_wheelers": 9999},
                     "water_depth_band": "knee", "rationale": ""}, "m")
    assert out["state"] == "unknown"
    assert out["confidence"] == 0.5  # 87 → 0.87, capped at 0.5 for unknown
    assert out["vehicles_estimate"] == {"cars": 0, "buses": 2, "two_wheelers": 500, "autos": 0}
    assert "water_depth_band" not in out
    assert out["rationale"]  # neutral text, never empty


def test_normalize_waterlogged_always_reports_a_band() -> None:
    out = normalize({"state": "waterlogged", "confidence": 0.8, "vehicles_estimate": {},
                     "water_depth_band": "none", "rationale": "Water on the road."}, "m")
    assert out["water_depth_band"] == "unknown"


@pytest.mark.parametrize("state", STATES)
def test_every_state_round_trips(state: str) -> None:
    out = normalize({"state": state, "confidence": 0.7, "vehicles_estimate": {},
                     "water_depth_band": "below_kerb", "rationale": "Road surface visible."}, "m")
    assert out["state"] == state
    assert out["verification_state"] == "UNVERIFIED-CAMERA"


class _NotReadyModel:
    name = "fake-vl"

    def status(self):
        return {"model": self.name, "managed": True, "running": False,
                "readiness": {"ready": False, "reason": "a start would be refused now: 15.5 GiB "
                              "available, needs ~16 GiB", "start_needs_gib": 16.0,
                              "mem_available_gib": 15.5}}

    async def maybe_stop_idle(self):
        return False

    async def aclose(self):
        return None


def test_health_says_degraded_when_a_request_would_get_a_503() -> None:
    """Audit 29 Oct: /health said "ok" while every road-state call answered 503."""
    from vision_service.api import create_app

    with TestClient(create_app(model=_NotReadyModel())) as c:
        body = c.get("/health").json()
    assert body["status"] == "degraded" and body["ready"] is False
    assert "15.5 GiB available" in body["degraded_reason"]
    assert body["service"] == "vision" and "no plate reading" in body["policy"]


def test_health_ok_carries_ready_true() -> None:
    c, _ = _client()
    with c:
        body = c.get("/health").json()
    assert body["status"] == "ok" and body["ready"] is True and body["degraded_reason"] is None
