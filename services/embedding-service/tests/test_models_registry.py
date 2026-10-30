"""Model registry, dense geometry, lazy loading, fallback recall, fused ranking, model markers,
re-embedding and the read-only /embed and /pii/spans routes. All offline: models are faked; the two
real-model tests are ``slow`` and skip unless torch imports and the weights are cached."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

from embedding_service import config
from embedding_service.encoders import (
    BgeM3DenseEncoder,
    DenseEncoder,
    EncodingError,
    FakeDenseEncoder,
    FakeLateInteractionEncoder,
    ModelUnavailable,
    PplxLateInteractionEncoder,
    _LazyModel,
    build_dense_encoder,
    encoder_model,
    fit_dense,
)
from embedding_service.pii import FakePiiDetector
from embedding_service.retrieval import HybridRetriever, embedding_marker
from embedding_service.service import build_api, create_app
from embedding_service.writer import embed_and_upsert

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reembed import reembed  # noqa: E402


class NamedFakeDense(FakeDenseEncoder):
    """A fake dense encoder that claims a registry name (so markers and recall filters apply)."""

    def __init__(self, name: str = "pplx-embed-context-v1-4b"):
        super().__init__(salt=name)
        self.name = name


class BrokenDense(FakeDenseEncoder):
    def encode(self, texts):
        raise ModelUnavailable("CUDA out of memory (test)")


# ─── registry ────────────────────────────────────────────────────────────────


class TestRegistry:
    def test_every_dense_model_fits_the_store_column(self):
        for name in config.DENSE_MODELS:
            spec = config.dense_spec(name)
            assert spec["store_dim"] == config.DENSE_DIM == 1024
            assert spec["store_dim"] <= spec["dim"]
            assert spec["licence"] == "MIT"

    def test_unknown_dense_model_refused(self):
        with pytest.raises(ValueError, match="unknown dense model"):
            config.dense_spec("text-embedding-unknown")

    def test_width_the_store_cannot_hold_is_refused(self, monkeypatch):
        monkeypatch.setitem(config.DENSE_MODELS, "wide", {**config.DENSE_MODELS["bge-m3"], "store_dim": 2560,
                                                          "dim": 2560})
        with pytest.raises(ValueError, match="migration"):
            config.dense_spec("wide")

    def test_late_models_and_pins(self):
        for name, spec in config.LATE_MODELS.items():
            assert config.late_spec(name)["source"].startswith("perplexity-ai/")
            assert len(spec["revision"]) == 40
        with pytest.raises(ValueError):
            config.late_spec("nope")

    def test_pplx_models_are_pinned(self):
        for name, spec in config.DENSE_MODELS.items():
            if spec["source"].startswith("perplexity-ai/"):
                assert spec["revision"] and len(spec["revision"]) == 40, name

    def test_default_models_are_registered(self):
        assert config.DEFAULT_DENSE_MODEL in config.DENSE_MODELS
        assert config.LATE_MODEL in config.LATE_MODELS
        assert config.RANK_MODE in config.RANK_MODES


# ─── encoders (no torch import) ──────────────────────────────────────────────


class TestEncoders:
    def test_late_encoder_accepts_repo_id_backward_compatible(self):
        enc = PplxLateInteractionEncoder("perplexity-ai/pplx-embed-v2-late-0.6b")
        assert enc.model == "pplx-embed-v2-late-0.6b"
        assert enc.name == "pplx-embed-v2-late"
        assert enc._revision == config.LATE_MODELS["pplx-embed-v2-late-0.6b"]["revision"]
        assert not enc.loaded

    def test_9b_late_is_bf16(self):
        assert PplxLateInteractionEncoder("pplx-embed-v2-late-9b")._dtype == "bfloat16"

    def test_dense_encoders_construct_lazily(self):
        for name in config.DENSE_MODELS:
            enc = build_dense_encoder(name)
            assert enc.name == name and enc.dim == 1024 and not enc.loaded
        assert isinstance(build_dense_encoder("bge-m3"), BgeM3DenseEncoder)
        ctx = DenseEncoder("pplx-embed-context-v1-4b")
        assert ctx.native_dim == 2560 and ctx.family == "contextual"

    def test_encoder_model_names_only_registry_models(self):
        assert encoder_model(BgeM3DenseEncoder(), "dense") == "bge-m3"
        assert encoder_model(PplxLateInteractionEncoder(), "late") == config.LATE_MODEL
        assert encoder_model(FakeDenseEncoder(), "dense") is None
        assert encoder_model(FakeLateInteractionEncoder(), "late") is None


class TestFitDense:
    def test_matryoshka_prefix_and_unit_norm(self):
        row = [3.0, 4.0] + [0.0] * 1022 + [100.0] * 1536  # 2560 wide; the tail must be dropped
        out = fit_dense(row, 1024)
        assert len(out) == 1024
        assert out[0] == pytest.approx(0.6) and out[1] == pytest.approx(0.8)
        assert math.isclose(sum(v * v for v in out), 1.0, rel_tol=1e-9)

    def test_int8_scale_vectors_are_normalised(self):
        out = fit_dense([127.0] * 1024, 1024)
        assert out[0] == pytest.approx(1 / 32)

    def test_zero_vector_rejected(self):
        with pytest.raises(EncodingError):
            fit_dense([0.0] * 1024, 1024)

    def test_short_vector_rejected(self):
        with pytest.raises(EncodingError):
            fit_dense([1.0] * 512, 1024)


class TestDenseEncodePath:
    """The encode path with a stub model: blanks never reach the model; tensor rows (bf16) become floats."""

    class _Row:
        def __init__(self, vals):
            self.vals = vals

        def float(self):
            return self

        def cpu(self):
            return self

        def tolist(self):
            return list(self.vals)

    def _encoder(self, family):
        seen = []
        row = self._Row([3.0, 4.0] + [0.0] * 2558)

        class Stub:
            def encode(self_inner, items, **kw):
                seen.append((items, kw))
                if family == "contextual":
                    assert kw.get("convert_to_numpy") is False
                    return [[row] for _ in items]
                assert kw.get("convert_to_tensor") is True
                return [row for _ in items]

        name = "pplx-embed-context-v1-4b" if family == "contextual" else "pplx-embed-v1-4b"
        enc = DenseEncoder(name)
        enc._build = lambda: Stub()
        return enc, seen

    @pytest.mark.parametrize("family", ["contextual", "sentence_transformers"])
    def test_blank_texts_become_a_placeholder_and_rows_are_cut(self, family):
        from embedding_service.encoders import BLANK_TEXT

        enc, seen = self._encoder(family)
        out = enc.encode(["Sea Link", "", "   "])
        items = seen[0][0]
        flat = [i[0] for i in items] if family == "contextual" else items
        assert flat == ["Sea Link", BLANK_TEXT, BLANK_TEXT]
        assert all(len(v) == 1024 and v[0] == pytest.approx(0.6) for v in out)


class TestLazyLoad:
    def test_failed_load_backs_off_and_reports(self):
        class Boom(_LazyModel):
            builds = 0

            def _build(self):
                Boom.builds += 1
                raise RuntimeError("no weights")

        m = Boom()
        with pytest.raises(ModelUnavailable, match="no weights"):
            m._load_model()
        with pytest.raises(ModelUnavailable):
            m._load_model()
        assert Boom.builds == 1  # the second call did not retry inside the back-off window
        assert m.status()["load_error"].startswith("RuntimeError")
        m._failed_at -= m.retry_after_sec + 1
        with pytest.raises(ModelUnavailable):
            m._load_model()
        assert Boom.builds == 2

    def test_successful_load_is_cached(self):
        class Ok(_LazyModel):
            builds = 0

            def _build(self):
                Ok.builds += 1
                return object()

        m = Ok()
        a, b = m._load_model(), m._load_model()
        assert a is b and Ok.builds == 1 and m.status()["loaded"]


# ─── write path: markers ─────────────────────────────────────────────────────


class TestMarkers:
    def test_marker_names_registry_models_and_legacy_for_fakes(self):
        assert embedding_marker(FakeLateInteractionEncoder(), FakeDenseEncoder()) == {
            "dense": "bge-m3", "late": "pplx-embed-v2-late-0.6b"}
        assert embedding_marker(PplxLateInteractionEncoder(), NamedFakeDense()) == {
            "dense": "pplx-embed-context-v1-4b", "late": config.LATE_MODEL}
        assert embedding_marker(FakeLateInteractionEncoder(), NamedFakeDense(), dense_ok=False)["dense"] is None

    async def test_writer_marks_and_survives_a_dense_outage(self, fake_store):
        late = FakeLateInteractionEncoder()
        doc_id = await embed_and_upsert(fake_store, late, NamedFakeDense(), kind="decision", ref_id="d:1",
                                        title="t", body="waterlogging at Hindmata", metadata={"trigger": "x"})
        row = fake_store.docs[doc_id]
        assert row.metadata["embedding"]["dense"] == "pplx-embed-context-v1-4b"
        assert row.metadata["trigger"] == "x" and row.dense is not None
        doc2 = await embed_and_upsert(fake_store, late, BrokenDense(), kind="decision", ref_id="d:2",
                                      title="t", body="tree fall on Marine Drive", metadata=None)
        row2 = fake_store.docs[doc2]
        assert row2.dense is None and row2.metadata["embedding"]["dense"] is None
        assert fake_store.token_map[doc2]  # MaxSim vectors kept


# ─── retrieval ───────────────────────────────────────────────────────────────


def _docs():
    return [
        ("incident", "i:1", "Waterlogging", "waterlogging at Hindmata high tide gates closed"),
        ("incident", "i:2", "Tree fall", "tree fall on Marine Drive after the cyclone"),
        ("decision", "d:1", "Bridge", "bus breakdown on Sea Link evening peak"),
    ]


async def _seed(store, late, dense):
    for kind, ref, title, body in _docs():
        await embed_and_upsert(store, late, dense, kind=kind, ref_id=ref, title=title, body=body, metadata={})


class TestRetrieval:
    async def test_recall_is_scoped_to_the_dense_model(self, fake_store):
        late = FakeLateInteractionEncoder()
        await _seed(fake_store, late, FakeDenseEncoder())  # legacy (bge-m3-marked) vectors
        retr = HybridRetriever(fake_store, late, NamedFakeDense())
        res = await retr.search("waterlogging Hindmata", kinds=["incident", "decision"])
        assert fake_store.last_dense_model == "pplx-embed-context-v1-4b"
        assert res.recalled == 0 and res.recall == "dense"
        # after re-embedding with the new model the docs are visible again
        out = await reembed(fake_store, late, NamedFakeDense())
        assert out["reembedded"] == 3 and out["dense_model"] == "pplx-embed-context-v1-4b"
        res = await retr.search("waterlogging Hindmata", kinds=["incident", "decision"])
        assert res.recalled == 3 and res.results[0].ref_id == "i:1"
        assert res.to_dict()["models"] == {"dense": "pplx-embed-context-v1-4b", "late": "pplx-embed-v2-late-0.6b"}

    async def test_dense_outage_falls_back_to_recent_recall(self, fake_store):
        late = FakeLateInteractionEncoder()
        await _seed(fake_store, late, FakeDenseEncoder())
        retr = HybridRetriever(fake_store, late, BrokenDense())
        res = await retr.search("tree fall Marine Drive", kinds=["incident", "decision"])
        d = res.to_dict()
        assert d["recall"] == "recent" and d["models"]["dense"] is None
        assert d["results"][0]["ref_id"] == "i:2"
        assert all(r["strategy"] == "maxsim" and r["maxsim_score"] is not None for r in d["results"])
        assert retr.dense_error and "out of memory" in retr.dense_error

    async def test_fused_rank_keeps_maxsim_semantics(self, fake_store):
        late, dense = FakeLateInteractionEncoder(), FakeDenseEncoder()
        await _seed(fake_store, late, dense)
        retr = HybridRetriever(fake_store, late, dense, rank_mode="fused")
        d = (await retr.search("bus breakdown Sea Link", kinds=["incident", "decision"])).to_dict()
        assert d["rank_mode"] == "fused"
        fused = [r["fused_score"] for r in d["results"]]
        assert fused == sorted(fused, reverse=True)
        assert all(r["score"] == r["maxsim_score"] for r in d["results"])
        assert d["results"][0]["ref_id"] == "d:1"

    async def test_rank_is_a_per_request_opt_in(self, fake_store):
        from embedding_service.api import ApiError

        late, dense = FakeLateInteractionEncoder(), FakeDenseEncoder()
        await _seed(fake_store, late, dense)
        api = build_api(fake_store, late, dense)  # config default: maxsim
        plain = await api.search({"query": "tree fall Marine Drive", "kinds": ["incident"]})
        assert plain["rank_mode"] == "maxsim" and "fused_score" not in plain["results"][0]
        fused = await api.search({"query": "tree fall Marine Drive", "kinds": ["incident"], "rank": "fused"})
        assert fused["rank_mode"] == "fused" and "fused_score" in fused["results"][0]
        with pytest.raises(ApiError) as err:
            await api.search({"query": "x", "rank": "random"})
        assert err.value.status == 400

    def test_bad_rank_mode_refused(self, fake_store):
        with pytest.raises(ValueError, match="rank_mode"):
            HybridRetriever(fake_store, FakeLateInteractionEncoder(), FakeDenseEncoder(), rank_mode="random")

    async def test_reembed_dry_run_changes_nothing(self, fake_store):
        late = FakeLateInteractionEncoder()
        await _seed(fake_store, late, FakeDenseEncoder())
        out = await reembed(fake_store, late, NamedFakeDense(), dry_run=True)
        assert out == {"stale_first_page": 3, "dense_model": "pplx-embed-context-v1-4b",
                       "late_model": "pplx-embed-v2-late-0.6b", "dry_run": True}
        assert all(d.metadata["embedding"]["dense"] == "bge-m3" for d in fake_store.docs.values())


# ─── read-only routes ────────────────────────────────────────────────────────


@pytest.fixture
def routed_api(fake_store):
    return build_api(fake_store, FakeLateInteractionEncoder(), NamedFakeDense(),
                     pii=FakePiiDetector({"Rohan Kulkarni": "private_person", "Senapati Bapat": "private_person"}))


class TestEmbedRoute:
    async def test_vectors_are_unit_and_named(self, routed_api):
        out = await routed_api.embed({"texts": ["Sea Link bus breakdown", "वांद्रे–वरळी सागरी सेतूवर बस बंद पडली"]})
        assert out["model"] == "pplx-embed-context-v1-4b" and out["dim"] == 1024 and out["normalized"]
        assert len(out["vectors"]) == 2
        for v in out["vectors"]:
            assert len(v) == 1024 and math.isclose(sum(x * x for x in v), 1.0, rel_tol=1e-6)

    @pytest.mark.parametrize("payload", [{}, {"texts": []}, {"texts": "one"}, {"texts": [1]},
                                         {"texts": ["x"] * 65}, {"texts": ["x" * 2001]}])
    async def test_bad_bodies_are_400(self, routed_api, payload):
        from embedding_service.api import ApiError

        with pytest.raises(ApiError) as err:
            await routed_api.embed(payload)
        assert err.value.status == 400

    async def test_dense_outage_is_503(self, fake_store):
        from embedding_service.api import ApiError

        api = build_api(fake_store, FakeLateInteractionEncoder(), BrokenDense())
        with pytest.raises(ApiError) as err:
            await api.embed({"texts": ["x"]})
        assert err.value.status == 503

    async def test_embed_stores_nothing(self, routed_api, fake_store):
        await routed_api.embed({"texts": ["Hindmata waterlogging"]})
        assert fake_store.docs == {}


class TestPiiRoute:
    async def test_spans_and_toponym_guard(self, routed_api):
        text = "Rohan Kulkarni was stuck on Senapati Bapat Marg near Annie Besant Road."
        out = await routed_api.pii_spans({"texts": [text]})
        assert out["model"] == "fake-pii" and "private_person" in out["labels"]
        spans = out["spans"][0]
        assert [text[s["start"]:s["end"]] for s in spans] == ["Rohan Kulkarni"]  # the road keeps its name

    async def test_disabled_and_failing_detector_are_503(self, fake_store):
        from embedding_service.api import ApiError

        api = build_api(fake_store, FakeLateInteractionEncoder(), FakeDenseEncoder(), pii=None)
        with pytest.raises(ApiError) as err:
            await api.pii_spans({"texts": ["x"]})
        assert err.value.status == 503

        class Down(FakePiiDetector):
            def detect(self, texts):
                raise ModelUnavailable("weights missing")

        api = build_api(fake_store, FakeLateInteractionEncoder(), FakeDenseEncoder(), pii=Down())
        with pytest.raises(ApiError) as err:
            await api.pii_spans({"texts": ["x"]})
        assert err.value.status == 503


class TestHealthAndWiring:
    async def test_health_reports_models(self, routed_api):
        h = await routed_api.health()
        assert h["status"] == "ok" and h["late_encoder"] == "fake-late"
        assert h["models"]["dense"]["model"] == "pplx-embed-context-v1-4b"
        assert h["models"]["dense"]["dim"] == 1024
        assert h["models"]["rank_mode"] == config.RANK_MODE
        assert h["models"]["pii"]["model"] == "fake-pii"
        assert h["models"]["recall_fallback_active"] is False

    def test_http_roundtrip_for_new_routes(self, routed_api):
        from fastapi.testclient import TestClient

        client = TestClient(create_app(routed_api))
        assert {"/embed", "/pii/spans"} <= {r.path for r in client.app.routes}
        r = client.post("/embed", json={"texts": ["Sion Circle signal failure"]})
        assert r.status_code == 200 and len(r.json()["vectors"][0]) == 1024
        assert client.post("/embed", json={"texts": []}).status_code == 400
        r = client.post("/pii/spans", json={"texts": ["Rohan Kulkarni at Dadar"]})
        assert r.status_code == 200 and r.json()["spans"][0][0]["label"] == "private_person"
        s = client.post("/search", json={"query": "signal failure", "top_k": 3})
        assert s.status_code == 200 and s.json()["recall"] == "dense" and "models" in s.json()


# ─── real models (slow; skipped without torch or cached weights) ─────────────


def _cached(repo: str) -> bool:
    return (Path.home() / ".cache/huggingface/hub" / f"models--{repo.replace('/', '--')}" / "refs/main").exists()


needs_torch = pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="torch not installed")


@pytest.mark.slow
@needs_torch
@pytest.mark.parametrize("name", ["pplx-embed-context-v1-4b", "bge-m3"])
def test_real_dense_encoder(name, monkeypatch):
    spec = config.DENSE_MODELS[name]
    if spec["source"].startswith("perplexity-ai/") and not _cached(spec["source"]):
        pytest.skip("weights not cached")
    if not spec["source"].startswith("perplexity-ai/") and not Path(spec["source"]).exists():
        pytest.skip("weights not present")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    enc = build_dense_encoder(name)
    a, b, c, blank = enc.encode(["Waterlogging at Hindmata junction", "हिंदमाता चौकात पाणी साचले",
                                 "Ganeshotsav crowd at Lalbaug", ""])
    assert len(blank) == 1024  # a blank text embeds (placeholder), never fails the batch
    dot = lambda x, y: sum(p * q for p, q in zip(x, y))  # noqa: E731
    assert len(a) == 1024 and math.isclose(dot(a, a), 1.0, rel_tol=1e-4)
    assert dot(a, b) > dot(a, c)  # cross-script: the same event beats a different one


@pytest.mark.slow
@needs_torch
def test_real_late_encoder(monkeypatch):
    if not _cached("perplexity-ai/pplx-embed-v2-late-0.6b"):
        pytest.skip("weights not cached")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    enc = PplxLateInteractionEncoder("pplx-embed-v2-late-0.6b")
    q = enc.encode_query("waterlogging at high tide")
    docs = enc.encode_documents(["Water rising at Hindmata at high tide.", "Tree fall on Marine Drive."])
    assert all(len(t) == 128 for t in q) and len(docs) == 2
