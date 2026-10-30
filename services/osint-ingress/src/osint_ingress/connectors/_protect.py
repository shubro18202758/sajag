"""The gazetteer protect-set: place phrases the redactor never mistakes for a person's name.

Built from the X19 gazetteer ``scripts/data/osint_gazetteer.json`` (``canonical_name`` with its parenthesised
parts, and every ``surface_forms`` entry), plus the city pack (``cities/<city>/landmarks.json`` and
``gazetteer.json``: ``en`` names, their parenthesised parts and ``aka`` aliases; ``<city>`` from ``SAJAG_CITY``,
default ``mumbai``) and :data:`MUMBAI_EPONYMOUS_PLACES` (Mumbai's places named after people, which the surname and
honorific rules would otherwise read as a person: "Senapati Bapat Marg", "Bhulabhai Desai Road", "Shivaji Park").
Normalised exactly as ``osint_common.ethics`` normalises phrases (NFKC, lower case, every run of non ``[a-z0-9]``
→ one space), so the same set can be handed to ``ethics.pii_spans(protect=...)``. The city pack's Marathi and
Hindi spellings are offered separately (:func:`city_indic_places`): the redactor's Indic cue rules never read one
as a name word (the ``[WITHHELD]`` rule itself follows ``osint_common.ethics`` and its gazetteer alone).

Path: the argument, else ``$OSINT_GAZETTEER_PATH``, else the repo-rooted file (walking up from this module), else
the image path ``/repo/VVIP/scripts/data/osint_gazetteer.json``. A missing or malformed gazetteer gives the empty
set: protection then rests on the generic place words alone, which can only redact MORE, never less.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

__all__ = [
    "CITY_ENV",
    "GAZETTEER_ENV",
    "MUMBAI_EPONYMOUS_PLACES",
    "city_indic_places",
    "city_pack_phrases",
    "default_protect",
    "gazetteer_path",
    "load_protect",
    "norm_phrase",
]

GAZETTEER_ENV = "OSINT_GAZETTEER_PATH"
CITY_ENV = "SAJAG_CITY"
DEFAULT_CITY = "mumbai"
_CITY_ID = re.compile(r"^[a-z][a-z0-9_-]{1,40}$")
_ALIAS_KEYS = ("aka", "aka_mr", "aka_hi", "aka_bn")

#: Mumbai's public places named after people, with the spellings the city's copy uses (English; normalised on
#: load). Each would otherwise read as "<Given> <Surname>", an honorific and a name, or a name before a place noun.
MUMBAI_EPONYMOUS_PLACES: tuple[str, ...] = (
    "Chhatrapati Shivaji Maharaj Terminus", "Chhatrapati Shivaji Terminus",
    "Chhatrapati Shivaji Maharaj International Airport",
    "Chhatrapati Shivaji Maharaj Vastu Sangrahalaya", "Shivaji Park", "Shivaji Nagar", "Lokmanya Tilak Terminus",
    "Lokmanya Tilak Marg", "Lokmanya Tilak Municipal General Hospital", "Tilak Nagar", "Tilak Bridge",
    "Dr Ambedkar Road", "Dr. Ambedkar Road", "Dr Babasaheb Ambedkar Road", "Babasaheb Ambedkar Road", "Ambedkar Road",
    "Senapati Bapat Marg", "Annie Besant Road", "Dr Annie Besant Road", "Netaji Subhash Chandra Bose Road",
    "Swatantryaveer Savarkar Marg", "Savarkar Marg", "Acharya Atre Chowk", "Sant Gadge Maharaj Chowk",
    "Gokhale Bridge", "Gopal Krishna Gokhale Bridge", "Gokhale Road", "Jijamata Udyan",
    "Veermata Jijabai Bhosale Udyan", "Nana Chowk", "Nana Shankarshet Marg", "Haji Ali", "Haji Ali Dargah",
    "Haji Ali Juice Centre", "Mahalaxmi", "Mahalaxmi Temple", "Mahalaxmi Racecourse", "Mahalaxmi station",
    "Bhulabhai Desai Road", "Pherozeshah Mehta Road", "Dadabhai Naoroji Road", "D N Road", "Mohammed Ali Road",
    "Sardar Vallabhbhai Patel Road", "Swami Vivekanand Road", "S V Road", "Lal Bahadur Shastri Marg", "L B S Marg",
    "LBS Marg", "Ganpatrao Kadam Marg", "N M Joshi Marg", "Keshavrao Khadye Marg", "Pandurang Budhkar Marg",
    "Bhausaheb Hire Marg", "Rafi Ahmed Kidwai Road", "R A Kidwai Road", "Dr E Moses Road", "Jamshedji Tata Road",
    "Jagannath Shankarseth Road", "Sir Pochkhanwala Road", "P D'Mello Road", "P D Mello Road", "Nariman Point",
    "Nehru Planetarium", "Nehru Centre", "Rajiv Gandhi Sea Link", "Atal Setu",
    "Atal Bihari Vajpayee Sewri Nhava Sheva Atal Setu",
    "Sanjay Gandhi National Park", "Indira Dock", "Mahatma Phule Market", "Mahatma Phule Mandai", "Phule Market",
    "Mahatma Gandhi Road", "M G Road", "Grant Road", "Charni Road", "Elphinstone Road", "Elphinstone Bridge",
    "Prabhadevi", "Bhau Daji Lad Museum", "Bhau Daji Road", "Dr Dadasaheb Bhadkamkar Marg",
    "Dadasaheb Phalke Chitranagari",
    "Mount Mary", "Mount Mary Church", "Mount Mary Steps", "Wankhede Stadium", "Brabourne Stadium",
    "Rajawadi Hospital", "Nair Hospital", "B Y L Nair Hospital", "Cooper Hospital", "Hinduja Hospital",
    "Lilavati Hospital", "Bhabha Hospital", "Wadia Hospital", "K B Bhabha Hospital", "Shatabdi Hospital",
    "Sion Hospital", "KEM Hospital", "J J Hospital", "Sir J J Hospital", "Jaslok Hospital", "Breach Candy",
    "Kemps Corner", "Peddar Road", "Warden Road", "Napean Sea Road", "Hughes Road", "Marine Drive", "Girgaon Chowpatty",
    "Dadar Chowpatty", "Juhu Chowpatty", "Lalbaug", "Lalbaugcha Raja", "Hindmata", "King's Circle", "Kings Circle",
    "Andheri Subway", "Milan Subway", "Gandhi Market", "Siddhivinayak Temple", "Shanmukhananda Hall",
    "Bandra Worli Sea Link", "Bandra-Worli Sea Link", "Mahim Causeway", "Kala Ghoda", "Gateway of India",
    "Dharavi", "Kranti Nagar", "Ramabai Nagar", "Ramabai Ambedkar Nagar", "Annabhau Sathe Nagar", "Sathe Nagar",
    "Shastri Nagar", "Nehru Nagar", "Indira Nagar", "Rajiv Nagar", "Sanjay Nagar", "Gandhi Nagar", "Tilak Road",
    "Ranade Road", "Gokhale Road", "Kher Nagar", "Pant Nagar", "Vidyavihar", "Ghatkopar", "Vikhroli", "Kanjurmarg",
    "Bhandup", "Mulund", "Nahur", "Matunga", "Wadala", "Chembur", "Kurla", "Sion", "Byculla", "Parel", "Lower Parel",
    "Worli", "Worli Naka", "Dadar TT", "Dadar", "Bandra", "Kalanagar", "Santacruz", "Vile Parle", "Andheri",
    "Jogeshwari", "Goregaon", "Malad", "Kandivali", "Borivali", "Dahisar", "Colaba", "Churchgate", "Marine Lines",
    "Tardeo", "Mazgaon", "Sewri", "Mankhurd", "Govandi", "Deonar", "Trombay", "Powai", "Saki Naka", "Sakinaka",
    "Marol", "Versova", "Juhu", "Khar", "Mahim", "Girgaon", "Thakurdwar", "Kandivali Thakur Village", "Thakur Village",
)
_REPO_PARTS = ("scripts", "data", "osint_gazetteer.json")
_IMAGE_PATH = Path("/repo/VVIP/scripts/data/osint_gazetteer.json")
_MAX_BYTES = 8 * 1024 * 1024


def norm_phrase(s: str) -> str:
    """``"Science City (EM Bypass)"`` → ``"science city em bypass"`` (the ``osint_common.ethics`` rule)."""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def gazetteer_path(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    env = os.environ.get(GAZETTEER_ENV)
    if env:
        p = Path(env)
        return p if p.is_file() else None
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent.joinpath(*_REPO_PARTS)
        if cand.is_file():
            return cand
    return _IMAGE_PATH if _IMAGE_PATH.is_file() else None


def load_protect(path: str | os.PathLike[str] | None = None) -> frozenset[str]:
    """The normalised place phrases of the gazetteer at ``path`` (see :func:`gazetteer_path`); never raises."""
    p = gazetteer_path(path)
    if p is None:
        return frozenset()
    try:
        if p.stat().st_size > _MAX_BYTES:
            return frozenset()
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    entries = doc.get("entries", []) if isinstance(doc, Mapping) else []
    out: set[str] = set()
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, Mapping):
            continue
        names: list[str] = []
        canon = entry.get("canonical_name")
        if isinstance(canon, str):
            names.append(canon)
            names.extend(part for part in re.split(r"[()]", canon) if part.strip())
        forms = entry.get("surface_forms")
        if isinstance(forms, list):
            names.extend(f for f in forms if isinstance(f, str))
        for name in names:
            phrase = norm_phrase(name[:200])
            if phrase:
                out.add(phrase)
    return frozenset(out)


def _city() -> str:
    c = os.environ.get(CITY_ENV, "").strip().lower() or DEFAULT_CITY
    return c if _CITY_ID.match(c) else DEFAULT_CITY


def _pack_file(name: str, city: str | None = None) -> Path | None:
    """``cities/<city>/<name>`` found by walking up from this module, or ``None``."""
    c = city or _city()
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "cities" / c / name
        if cand.is_file():
            return cand
    return None


def _pack_items(name: str, key: str, city: str | None = None) -> list[Mapping[str, object]]:
    p = _pack_file(name, city)
    if p is None:
        return []
    try:
        if p.stat().st_size > _MAX_BYTES:
            return []
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = doc.get(key, []) if isinstance(doc, Mapping) else []
    return [i for i in items if isinstance(i, Mapping)] if isinstance(items, list) else []


def _pack_names(item: Mapping[str, object], keys: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for k in keys:
        v = item.get(k)
        if isinstance(v, str):
            out.append(v)
            out.extend(part for part in re.split(r"[()]", v) if part.strip())
        elif isinstance(v, list):
            out.extend(x for x in v if isinstance(x, str))
    return out


@lru_cache(maxsize=4)
def city_pack_phrases(city: str | None = None) -> frozenset[str]:
    """The city pack's place names (``landmarks.json`` and ``gazetteer.json``: ``en`` and ``aka``), normalised, plus
    :data:`MUMBAI_EPONYMOUS_PLACES` for Mumbai. Never raises (a missing pack gives the curated list alone)."""
    c = city or _city()
    names: list[str] = list(MUMBAI_EPONYMOUS_PLACES) if c == "mumbai" else []
    for file, key in (("landmarks.json", "landmarks"), ("gazetteer.json", "places")):
        for item in _pack_items(file, key, c):
            names.extend(_pack_names(item, ("en", "aka")))
    return frozenset(p for p in (norm_phrase(n[:200]) for n in names) if p)


@lru_cache(maxsize=4)
def city_indic_places(city: str | None = None) -> frozenset[str]:
    """The city pack's Marathi and Hindi place spellings, word by word (NFKC, format characters dropped): words the
    redactor's Indic cue rules never read as a name ("दादर", "लालबाग", "हिंदमाता")."""
    out: set[str] = set()
    for file, key in (("landmarks.json", "landmarks"), ("gazetteer.json", "places")):
        for item in _pack_items(file, key, city):
            for name in _pack_names(item, ("mr", "hi", "aka_mr", "aka_hi")):
                for word in re.findall(r"[\u0900-\u0963\u0971-\u097f\u200c\u200d]+", name[:200]):
                    key_ = "".join(ch for ch in unicodedata.normalize("NFKC", word) if unicodedata.category(ch) != "Cf")
                    if len(key_) > 1:
                        out.add(key_)
    return frozenset(out)


@lru_cache(maxsize=4)
def default_protect(path: str | None = None) -> frozenset[str]:
    """:func:`load_protect` (cached per path: the gazetteer is read once per process) and the city pack's place
    phrases (:func:`city_pack_phrases`)."""
    return load_protect(path) | city_pack_phrases()
