"""No social output carries a poster: no author name, handle or profile URI value reaches any signal, and the
Reddit parser has no code path that touches the entry's poster block (AST scan of ``connectors/reddit.py``)."""

from __future__ import annotations

import ast
import html
import json
import re
from pathlib import Path

import defusedxml.ElementTree as DET
from conftest import CAPTURE, POC_RAW, URL_HANDLE_PROBES, h12, needs_poc

import osint_ingress.connectors.reddit as reddit_module
from osint_ingress.cache import Cache
from osint_ingress.connectors.reddit import ENTRY_FIELDS, Reddit, post_text

ATOM = "{http://www.w3.org/2005/Atom}"


def _poster_values(feed: bytes) -> set[str]:
    """Every poster value of a feed (read HERE, by the test, to prove the parser never emits one)."""
    root = DET.fromstring(feed)
    values: set[str] = set()
    for entry in root.findall(ATOM + "entry"):
        block = entry.find(ATOM + "aut" + "hor")
        if block is None:
            continue
        for child in block:
            v = (child.text or "").strip()
            if v:
                values.add(v)
                # the bare handle too: "/u/name" -> "name", ".../user/name" -> "name"
                values.add(re.split(r"/u/|/user/", v)[-1].strip("/"))
    return {v for v in values if len(v) >= 3}


def _emitted(feed: bytes, tmp_path: Path, protect, *, synthetic: bool = False, community: str = "mumbai") -> str:
    entry = Cache(tmp_path).put("reddit_rss", feed, "xml", synthetic=synthetic)
    sigs = Reddit(community=community).parse(entry, protect)
    return json.dumps([s.model_dump(mode="json") for s in sigs], ensure_ascii=False)


def test_synthetic_posters_never_reach_a_signal(tmp_path, protect):
    feed = (CAPTURE / "reddit_live.rss").read_bytes()
    posters = _poster_values(feed)
    assert {"synthetic_user_01", "synthetic_user_04"} <= posters
    blob = _emitted(feed, tmp_path, protect, synthetic=True)  # the capture's fictional community
    assert blob.count('"t3_syn') == 4  # every post was read (none dropped as another community)
    assert not [p for p in posters if p in blob]
    assert "/u/" not in blob and "u/synthetic" not in blob and "/user/" not in blob
    assert "synthetic_friend_02" not in blob  # a handle mentioned in a body is redacted too
    assert "synthetic.player@example.com" not in blob and "[CONTACT]" in blob


def test_footer_and_mentions_are_cut():
    html = ('<div class="md"><p>Hello u/someone_else and /u/another_one</p></div> submitted by '
            '<a href="https://www.reddit.com/user/poster_x"> /u/poster_x </a> <span><a href="#">[link]</a></span> '
            '<span><a href="#">[comments]</a></span>')
    text = post_text(html)
    assert "poster_x" not in text and "submitted by" not in text and "[link]" not in text
    # mentions inside the body stay until redaction (which turns them into [PERSON])
    from osint_ingress.connectors._redact import redact_persons

    out, n = redact_persons(text, "social_unverified", frozenset())
    assert "someone_else" not in out and "another_one" not in out and n == 2


def test_at_mentions_in_a_post_are_redacted(tmp_path, protect):
    html = ('<div class="md"><p>Lost wallet near the gate, DM @synthetic_finder or @fictus.handle on insta</p></div>'
            ' submitted by <a href="https://www.reddit.com/user/poster_y"> /u/poster_y </a>')
    from osint_ingress.connectors._redact import redact_persons
    from osint_ingress.runner import signal_checks

    out, n = redact_persons(post_text(html), "social_unverified", frozenset())
    assert "synthetic_finder" not in out and "fictus.handle" not in out and "poster_y" not in out and n == 2
    assert "@" not in out
    # the parity checks count an @mention left in a social post as a poster handle
    entry = Cache(tmp_path).put("reddit_rss", (CAPTURE / "reddit_live.rss").read_bytes(), "xml", synthetic=True)
    sigs = Reddit().parse(entry, protect)
    assert sigs and signal_checks(sigs)["with_poster_handle"] == 0
    leaked = [sigs[0].model_copy(update={"text": sigs[0].text + " DM @synthetic_finder"})]
    assert signal_checks(leaked)["with_poster_handle"] == 1


def _feed(bodies: list[str]) -> bytes:
    """A minimal r/mumbai Atom feed whose posts show ``bodies`` the way Reddit renders a bare URL: as a link whose
    visible text is the URL itself (fictional handles only)."""
    def link(m: re.Match[str]) -> str:
        url = m.group(1)
        return f'<a href="{url if url.startswith("http") else "https://" + url}">{url}</a>'

    entries = []
    for i, body in enumerate(bodies):
        linked = re.sub(r"(\S+\.(?:com|it)/[^\s]+?)(?=[.,]?(?:\s|$))", link, body)
        content = html.escape(f'<div class="md"><p>{linked}</p></div> submitted by '
                              f'<a href="https://www.reddit.com/user/poster_{i}"> /u/poster_{i} </a>', quote=True)
        entries.append(
            f'<entry><category term="mumbai" label="r/mumbai"/><content type="html">{content}</content>'
            f"<id>t3_url{i:04d}</id><link href=\"https://www.reddit.com/r/mumbai/comments/url{i:04d}/x/\" />"
            f"<updated>2026-10-20T14:30:00+00:00</updated><published>2026-10-20T14:30:00+00:00</published>"
            f"<title>Traffic jam near Sion flyover, post {i}</title></entry>"
        )
    return ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">'
            + "".join(entries) + "</feed>").encode("utf-8")


def test_handles_inside_urls_in_a_post_never_reach_a_signal(tmp_path, protect):
    """Review-r2 must-fix: a profile link or a Reddit user page in the post body (reddit.com/u/<h>,
    reddit.com/user/<h>, instagram.com/<h>, x.com/<h>, www.facebook.com/<h>) is redacted, and the parity checks
    find no handle and no URL left."""
    from osint_ingress.runner import signal_checks

    feed = _feed([text for text, _h, _e in URL_HANDLE_PROBES])
    entry = Cache(tmp_path).put("reddit_rss", feed, "xml")
    sigs = Reddit().parse(entry, protect)
    assert len(sigs) == len(URL_HANDLE_PROBES)
    blob = json.dumps([s.model_dump(mode="json") for s in sigs], ensure_ascii=False)
    for _text, handle, _expected in URL_HANDLE_PROBES:
        assert handle not in blob, h12(handle)
    assert "instagram.com" not in blob and "x.com/" not in blob and "facebook.com" not in blob
    assert "/u/" not in blob and "/user/" not in blob
    checks = signal_checks(sigs)
    assert checks["with_poster_handle"] == 0 and checks["social_text_with_url"] == 0
    assert checks["find_pii_clean"] == len(sigs) and checks["news_social_with_url"] == 0
    assert sum(s.pii_redactions for s in sigs) == len(URL_HANDLE_PROBES)  # one [URL] or [PERSON] per post
    # the checks are not vacuous: a URL left in a post is counted, and a profile link as a poster handle too
    leaked = [sigs[0].model_copy(update={"text": sigs[0].text + " https://instagram.com/fictus_dummyvala"})]
    assert signal_checks(leaked)["social_text_with_url"] == 1 and signal_checks(leaked)["with_poster_handle"] == 1


@needs_poc
def test_real_capture_posters_never_reach_a_signal(tmp_path, protect):
    """A real Reddit community capture (the PoC's, of the platform's previous city), read in place for its shape:
    report only sha256 prefixes of any leaked poster value. The parser is pointed at that capture's community, so
    every post is read (the test is not vacuous); the live connector reads r/mumbai only."""
    feed = (POC_RAW / "reddit_live.rss").read_bytes()
    posters = _poster_values(feed)
    assert posters
    community = DET.fromstring(feed).find(ATOM + "category").get("term")
    blob = _emitted(feed, tmp_path, protect, community=community)
    assert blob.count('"t3_') >= 10  # the real posts were read
    leaked = sorted(h12(p) for p in posters if p in blob)
    assert not leaked, f"poster values leaked (sha256 prefixes): {leaked}"
    assert "/u/" not in blob and "/user/" not in blob and "submitted by" not in blob


def _docstring_nodes(tree: ast.Module) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def test_reddit_parser_has_no_access_to_the_poster_block():
    path = Path(reddit_module.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = _docstring_nodes(tree)
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            if re.search(r"author|\buri\b|}uri|/user/|thumbnail", node.value, re.IGNORECASE):
                hits.append(f"string constant at line {node.lineno}")
        elif isinstance(node, ast.Name) and "author" in node.id.lower():
            hits.append(f"name {node.id} at line {node.lineno}")
        elif isinstance(node, ast.Attribute) and "author" in node.attr.lower():
            hits.append(f"attribute {node.attr} at line {node.lineno}")
        elif isinstance(node, ast.arg) and "author" in node.arg.lower():
            hits.append(f"argument {node.arg} at line {node.lineno}")
    assert not hits, hits
    assert "author" not in ENTRY_FIELDS and not any("uri" in f for f in ENTRY_FIELDS)
    # every child access goes through the ENTRY_FIELDS gate (no generic iteration over an entry)
    src = path.read_text(encoding="utf-8")
    assert "for child in" not in src and ".iter(" not in src and "getchildren" not in src
