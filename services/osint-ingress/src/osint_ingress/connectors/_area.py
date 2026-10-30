"""Which part of Maharashtra an official alert names: a Mumbai district, the state, or neither.

Greater Mumbai is two revenue districts (``cities/mumbai/city.json``: the island city and the suburbs, BMC's 24
wards): **Mumbai City** and **Mumbai Suburban**. The official feeds Sajag reads cover more than the city: NDMA
SACHET publishes a Maharashtra CAP RSS (every district's nowcasts, issued by IMD Mumbai and Maharashtra SDMA), and
IMD's CAP feed covers every state. :func:`match_area` reads an alert's own text (title, description, CAP headline
and ``areaDesc``) and its CAP LGD district codes, and answers:

* the **Mumbai districts** it names (:data:`CITY_CODE`, :data:`SUBURBAN_CODE`): "Mumbai" or "Mumbai City" (मुंबई,
  मुंबई शहर) is the city district, "Mumbai Suburban" (मुंबई उपनगर) the suburban one, "Greater Mumbai" /
  "Brihanmumbai" (बृहन्मुंबई) both; LGD district code 482 is Mumbai City and 483 Mumbai Suburban (the codes
  SACHET's CAP 1.2 detail carries: "Mumbai,Mumbai Suburban districts of Maharashtra" → 482, 483, seen 2026-10-30).
  "Navi Mumbai" (नवी मुंबई) is never Mumbai: it is a separate city in Thane and Raigad districts;
* whether it is a **Maharashtra** alert at all: a Mumbai district, the state's name or region ("Konkan",
  "Vidarbha", "Marathwada", "Madhya Maharashtra"), or any other district of the state
  (:data:`MH_OTHER_DISTRICTS`, English and Marathi spellings, Marathi oblique stems such as "ठाण्या-" for ठाणे).
  Such an alert that names no Mumbai district is state-level (:data:`STATE_CODE`): a nowcast for Thane or Kolhapur
  is not a Mumbai location, and the analysis holds it as outside the city;
* whether it names **another state** (:data:`OTHER_STATES`: Goa, Karnataka, Telangana ...), so a caller that reads
  the Maharashtra file can tell "names nothing" (the state, by the feed it came from) from "another state's".

**The issuer's sign-off is not an area.** Maharashtra SDMA ends every Marathi nowcast with "मंत्रालय, मुंबई"
(Mantralaya, Mumbai: where the state's control room sits), whatever district the alert is for. It is cut before
matching (:func:`normal_form`), so a Kolhapur nowcast signed in Mumbai stays a state-level alert.

Matching runs on a normal form: NFKC, lower case, Marathi (Devanagari) digits as ASCII digits, hyphens as spaces,
Unicode format characters (ZWJ, ZWNJ) dropped, whitespace collapsed. A Latin-script name matches as a whole word;
an Indic-script name matches at the start of a word, so a Marathi case ending stays attached ("मुंबईत", in Mumbai;
"नाशिकमधील", in Nashik).

**Codes** come from the shared contract (``osint_common.kinds``): ``CITY_DISTRICTS`` (``LGD:MUMBAI``,
``LGD:MUMBAI_SUBURBAN``), ``AREA_STATE_CODE_MAHARASHTRA`` (``LGD:MAHARASHTRA``) and ``GDELT_ADM1_MAHARASHTRA``
(``IN16``, FIPS 10-4 Maharashtra), with the same values written here as the fallback for an older contract.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache

from osint_common import kinds as _kinds

__all__ = [
    "CITY_CODE",
    "DISTRICT_NAMES",
    "GDELT_ADM1",
    "LGD_DISTRICT_CODES",
    "MH_OTHER_DISTRICTS",
    "MH_STATE_NAMES",
    "OTHER_STATES",
    "STATE_CODE",
    "STATE_NAME",
    "SUBURBAN_CODE",
    "AreaMatch",
    "area_hint",
    "match_area",
    "normal_form",
    "state_level",
]


_CITY_DISTRICTS: tuple[str, ...] = tuple(getattr(_kinds, "CITY_DISTRICTS", ("LGD:MUMBAI", "LGD:MUMBAI_SUBURBAN")))
#: Mumbai City district (``cities/mumbai/city.json``: Colaba to Mahim and Sion).
CITY_CODE = _CITY_DISTRICTS[0]
#: Mumbai Suburban district (Bandra to Dahisar, Kurla to Mulund).
SUBURBAN_CODE = _CITY_DISTRICTS[1]
#: The state-level admin code (an alert naming Maharashtra but no Mumbai district). Never a point.
STATE_CODE = str(getattr(_kinds, "AREA_STATE_CODE_MAHARASHTRA", "LGD:MAHARASHTRA"))
#: GDELT ``ActionGeo_ADM1Code`` for Maharashtra (FIPS 10-4 ``IN16``).
GDELT_ADM1 = str(getattr(_kinds, "GDELT_ADM1_MAHARASHTRA", "IN16"))
STATE_NAME = "Maharashtra"

#: The English name a district code is shown with (``RawGeoHint.place_names``).
DISTRICT_NAMES: dict[str, str] = {CITY_CODE: "Mumbai City", SUBURBAN_CODE: "Mumbai Suburban"}
#: LGD district codes (CAP ``geocode`` "LGD District Code") of the two Mumbai districts.
LGD_DISTRICT_CODES: dict[str, str] = {"482": CITY_CODE, "483": SUBURBAN_CODE}

#: The state's own names and its regions (IMD's English bulletins: "North Konkan", "Madhya Maharashtra").
MH_STATE_NAMES: tuple[str, ...] = (
    "maharashtra", "konkan", "north konkan", "south konkan", "madhya maharashtra", "marathwada", "vidarbha",
    "महाराष्ट्र", "कोकण", "कोंकण", "मध्य महाराष्ट्र", "मराठवाडा", "मराठवाड़ा", "विदर्भ",
)

#: The other districts of Maharashtra (everything outside the two Mumbai districts), English spellings in use (IMD,
#: NDMA and news, old and new names) and Marathi ones, with the oblique stems Marathi case endings attach to
#: ("ठाण्यातील", in Thane; "पुण्यात", in Pune). Used only to tell a Maharashtra alert from another state's, never
#: as a location. "Navi Mumbai" is listed here: it lies in Thane and Raigad districts, not in Mumbai.
MH_OTHER_DISTRICTS: tuple[str, ...] = (
    "navi mumbai", "thane", "palghar", "raigad", "raigarh", "ratnagiri", "sindhudurg", "pune", "satara", "sangli",
    "kolhapur", "solapur", "nashik", "nasik", "ahmednagar", "ahilyanagar", "dhule", "nandurbar", "jalgaon",
    "aurangabad", "chhatrapati sambhajinagar", "sambhajinagar", "jalna", "beed", "latur", "osmanabad",
    "dharashiv", "nanded", "parbhani", "hingoli", "akola", "amravati", "buldhana", "buldana", "washim", "yavatmal",
    "nagpur", "wardha", "bhandara", "gondia", "gondiya", "chandrapur", "gadchiroli",
    "नवी मुंबई", "ठाणे", "ठाण्या", "पालघर", "रायगड", "रत्नागिरी", "सिंधुदुर्ग", "पुणे", "पुण्या", "सातारा", "साताऱ्या",
    "सांगली", "कोल्हापूर", "कोल्हापुर", "सोलापूर", "सोलापुर", "नाशिक", "नासिक", "अहमदनगर", "अहिल्यानगर", "धुळे",
    "धुळ्या", "नंदुरबार", "जळगाव", "जलगांव", "औरंगाबाद", "छत्रपती संभाजीनगर", "संभाजीनगर", "जालना", "जालन्या",
    "बीड", "लातूर", "लातुर", "उस्मानाबाद", "धाराशिव", "नांदेड", "परभणी", "हिंगोली", "अकोला", "अकोल्या", "अमरावती",
    "बुलढाणा", "बुलडाणा", "वाशिम", "यवतमाळ", "नागपूर", "नागपुर", "वर्धा", "वर्ध्या", "भंडारा", "भंडाऱ्या", "गोंदिया",
    "चंद्रपूर", "चंद्रपुर", "गडचिरोली",
)

#: Other states and union territories that reach the all-India CAP feeds (English, Marathi and Hindi spellings).
#: "Arabian Sea" and "Bay of Bengal" name seas, not states, and are not listed.
OTHER_STATES: tuple[str, ...] = (
    "saurashtra", "kutch", "valsad", "surat", "goa", "karnataka", "madhya pradesh", "telangana", "chhattisgarh",
    "andhra pradesh", "odisha",
    "orissa", "kerala", "tamil nadu", "puducherry", "rajasthan", "uttar pradesh", "bihar", "jharkhand",
    "west bengal", "assam", "meghalaya", "arunachal pradesh", "nagaland", "manipur", "mizoram", "tripura", "sikkim",
    "himachal pradesh", "uttarakhand", "punjab", "haryana", "delhi", "jammu and kashmir", "ladakh",
    "andaman and nicobar", "lakshadweep", "dadra and nagar haveli", "daman and diu", "srikakulam", "ganjam", "puri",
    "सौराष्ट्र", "कच्छ", "गोवा", "कर्नाटक", "मध्य प्रदेश", "तेलंगणा", "तेलंगाना", "छत्तीसगड", "छत्तीसगढ़",
    "आंध्र प्रदेश", "ओडिशा",
    "केरळ", "केरल", "तमिळनाडू", "तमिलनाडु", "राजस्थान", "उत्तर प्रदेश", "बिहार", "झारखंड", "पश्चिम बंगाल", "आसाम",
    "असम", "दिल्ली", "पंजाब", "हरियाणा", "अंदमान",
)

_CITY_SPELLINGS: tuple[str, ...] = ("mumbai city", "mumbai", "bombay", "मुंबई शहर", "मुंबई", "बम्बई", "बंबई")
_SUBURBAN_SPELLINGS: tuple[str, ...] = (
    "mumbai suburban", "mumbai suburbs", "mumbai suburb", "mumbai upnagar", "मुंबई उपनगर",
)
_BOTH_SPELLINGS: tuple[str, ...] = ("greater mumbai", "brihanmumbai", "brihan mumbai", "बृहन्मुंबई")

_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_WS = re.compile(r"\s+")
#: The issuer's sign-off at the end of a Maharashtra SDMA nowcast: "मंत्रालय, मुंबई" / "Mantralaya, Mumbai" (with
#: any punctuation between), never an area.
_SIGN_OFF = re.compile(r"(?:मंत्रालय|mantralaya)[\s,.।:;]*(?:मुंबई|mumbai)", re.IGNORECASE)
#: A bare "Mumbai" is the city district unless "Suburban" / "उपनगर" follows it ("Mumbai, Mumbai Suburban").
_NOT_SUBURBAN = r"(?!\s*(?:suburban|suburbs?|upnagar|उपनगर))"
#: ... and never when "Navi" / "नवी" precedes it.
_NOT_NAVI = r"(?<!navi )(?<!नवी )"


def normal_form(text: str) -> str:
    """The matching form of ``text`` (module docstring): NFKC, lower case, ASCII digits, the sign-off cut."""
    s = unicodedata.normalize("NFKC", text or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Cf").lower().translate(_DIGITS)
    s = _WS.sub(" ", s.replace("-", " ")).strip()
    return _WS.sub(" ", _SIGN_OFF.sub(" ", s)).strip()


def _pattern(names: Iterable[str], *, guard: str = "") -> re.Pattern[str]:
    parts: list[str] = []
    for name in sorted({normal_form(n) for n in names if n}, key=len, reverse=True):
        body = r"\s+".join(re.escape(w) for w in name.split())
        if name.isascii():
            parts.append(rf"{_NOT_NAVI}(?<![a-z0-9]){body}(?![a-z0-9]){guard}")
        else:
            # an Indic name starts a word; a Marathi case ending may follow it ("मुंबईत", "ठाण्यातील")
            parts.append(rf"{_NOT_NAVI}(?<![ऀ-ൿ]){body}{guard}")
    return re.compile("|".join(parts))


@lru_cache(maxsize=1)
def _patterns() -> tuple[re.Pattern[str], ...]:
    shared = getattr(_kinds, "AREA_DISTRICTS", {})
    city = (*_CITY_SPELLINGS, *shared.get(CITY_CODE, ()))
    suburban = (*_SUBURBAN_SPELLINGS, *shared.get(SUBURBAN_CODE, ()))
    return (
        _pattern(city, guard=_NOT_SUBURBAN),
        _pattern(suburban),
        _pattern(_BOTH_SPELLINGS),
        _pattern((*MH_STATE_NAMES, *MH_OTHER_DISTRICTS)),
        _pattern(OTHER_STATES),
    )


@dataclass(frozen=True)
class AreaMatch:
    """What :func:`match_area` found. ``districts`` keep city-then-suburban order."""

    districts: tuple[str, ...] = ()
    maharashtra: bool = False
    #: the text names another state or union territory (and no Maharashtra place)
    other_state: bool = False
    #: the English names of the districts (``RawGeoHint.place_names``), or ``("Maharashtra",)`` at state level
    place_names: tuple[str, ...] = field(default=())

    @property
    def in_area(self) -> bool:
        """A Maharashtra alert (a Mumbai district or the state): emitted. Otherwise outside the area."""
        return self.maharashtra

    @property
    def admin_codes(self) -> list[str]:
        """The Mumbai district codes it names, else the state code."""
        return list(self.districts) if self.districts else [STATE_CODE]


def state_level() -> AreaMatch:
    """A Maharashtra alert that names no place at all (an item of the Maharashtra feed saying "in your district"):
    the state, by the feed it came from."""
    return AreaMatch(maharashtra=True, place_names=(STATE_NAME,))


def match_area(*texts: str | None, lgd_codes: Iterable[str] = ()) -> AreaMatch:
    """Read the alert's texts and CAP LGD district codes (module docstring). Never raises."""
    hay = normal_form(" \n ".join(t for t in texts if t))
    by_code = {LGD_DISTRICT_CODES[c] for c in lgd_codes if c in LGD_DISTRICT_CODES}
    if not hay and not by_code:
        return AreaMatch()
    city_rx, suburban_rx, both_rx, state_rx, other_rx = _patterns()
    both = both_rx.search(hay) is not None
    found = set(by_code)
    if both or city_rx.search(hay):
        found.add(CITY_CODE)
    if both or suburban_rx.search(hay):
        found.add(SUBURBAN_CODE)
    districts = tuple(c for c in (CITY_CODE, SUBURBAN_CODE) if c in found)
    maharashtra = bool(districts) or state_rx.search(hay) is not None
    other = not maharashtra and other_rx.search(hay) is not None
    names = tuple(DISTRICT_NAMES[c] for c in districts) if districts else ((STATE_NAME,) if maharashtra else ())
    return AreaMatch(districts=districts, maharashtra=maharashtra, other_state=other, place_names=names)


def area_hint(match: AreaMatch) -> list[str]:
    """``area:<district>`` for each Mumbai district (``area:mumbai``, ``area:mumbai_suburban``), else
    ``area:maharashtra``; nothing outside the area."""
    if match.districts:
        return [f"area:{c.removeprefix('LGD:').lower()}" for c in match.districts]
    return ["area:maharashtra"] if match.maharashtra else []
