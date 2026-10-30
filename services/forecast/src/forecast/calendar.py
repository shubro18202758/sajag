"""Mumbai calendar facts the synthetic history and the event covariate use.

Ganeshotsav (Ganesh Chaturthi → Anant Chaturdashi), the dates:

* **Ganesh Chaturthi** is a state public holiday, so its date is the Maharashtra General Administration
  Department's annual notification (Negotiable Instruments Act s. 25): 27 Aug 2025; 14 Sep 2026
  ("14th September, 2026 / 23 Bhadrapad 1948, Monday"; reported by Lokshahi, LatestLY and others,
  Nov 2025).
* **Anant Chaturdashi** (the tenth day, the city's big visarjan): 6 Sep 2025 (as reported for the 2025
  visarjan, MUMBAI.md §5); 25 Sep 2026 (panchang listings: shubhpanchang.com, drikpanchang.com — the
  Chaturdashi tithi runs 24 Sep 23:18 → 25 Sep 23:06 IST). Not a gazetted state date: **approximate**.
* The intermediate immersions (1½-day, 5th-day and 7th-day/Gauri visarjan) are counted from Chaturthi
  by custom; their exact day varies by household and mandal: **approximate**.

Other dates:

* **Mumbai Marathon** (Tata Mumbai Marathon, Procam): Sunday 18 Jan 2026 (21st edition) and Sunday
  17 Jan 2027 (22nd edition, the race site and Raj Bhavan Maharashtra, Jul 2026). Route closures in South
  Mumbai, Marine Drive, the Sea Link and Bandra from early morning to late morning.
* **New Year's Eve** on Marine Drive, Girgaon Chowpatty, the Gateway and Juhu: the night of 31 Dec.
* **Mount Mary fair** (Bandra fair): the eight days from the Sunday after 8 September (the feast of the
  Nativity of Mary), by custom: **approximate** (13–20 Sep 2026; 14–21 Sep 2025).

The traffic rhythm itself (office peaks, festival nights) is a MODELLED pattern for the SIMULATED history,
not a measurement.
"""

from __future__ import annotations

from datetime import date, timedelta

__all__ = [
    "GANESHOTSAV",
    "MARATHON_DAYS",
    "ganeshotsav_day",
    "visarjan_day",
    "marathon_day",
    "new_year_eve",
    "mount_mary_fair",
]

#: year → (Ganesh Chaturthi, Anant Chaturdashi), per the module doc
GANESHOTSAV: dict[int, tuple[date, date]] = {
    2025: (date(2025, 8, 27), date(2025, 9, 6)),
    2026: (date(2026, 9, 14), date(2026, 9, 25)),
}

#: the Mumbai Marathon's race day (a Sunday in January), per the module doc
MARATHON_DAYS: frozenset[date] = frozenset({date(2026, 1, 18), date(2027, 1, 17)})


def visarjan_day(d: date) -> int:
    """0 no immersion; 1 an intermediate immersion (1½-day, 5th, 7th day; approximate);
    2 Anant Chaturdashi (the processions from Lalbaug to Girgaon Chowpatty run through the night)."""
    w = GANESHOTSAV.get(d.year)
    if not w:
        return 0
    start, end = w
    if d == end:
        return 2
    if d in (start + timedelta(days=1), start + timedelta(days=4), start + timedelta(days=6)):
        return 1
    return 0


def ganeshotsav_day(d: date) -> int:
    """0 outside Ganeshotsav; 1 a festival day (pandal evenings, the Lalbaugcha Raja queues);
    2 an intermediate immersion day; 3 Anant Chaturdashi."""
    w = GANESHOTSAV.get(d.year)
    if not w or not (w[0] <= d <= w[1]):
        return 0
    v = visarjan_day(d)
    return 3 if v == 2 else 2 if v == 1 else 1


def marathon_day(d: date) -> bool:
    return d in MARATHON_DAYS


def new_year_eve(d: date) -> bool:
    return d.month == 12 and d.day == 31


def mount_mary_fair(d: date) -> bool:
    """The eight days from the Sunday after 8 September (approximate, by custom)."""
    sept8 = date(d.year, 9, 8)
    first_sunday = sept8 + timedelta(days=(6 - sept8.weekday()) or 7)
    return first_sunday <= d <= first_sunday + timedelta(days=7)
