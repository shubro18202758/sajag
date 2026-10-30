"""The Mumbai replicas through the whole analysis (fake resolver, ``cities/mumbai/landmarks.json`` coordinates,
synthetic segment and junction ids): classified, fused, correlated, scored, attached and counted.

* the Western Express Highway case near Andheri: four collision reports and one mob report, one
  ``affray+collision`` situation on segment 4101, two news publishers, ``NEWS-REPORTED`` 0.65;
* the Dadar robbery: ``reported_crime`` at junction 4023 (never ``crime_incident``);
* the Mumbai SACHET thunderstorm alert: a district-level ``weather_hazard``, ``OFFICIAL-VERIFIED`` 0.95;
* the Maharashtra state-wide nowcast naming other districts: held as outside the city;
* a single social post about metro work near Ghatkopar: held, aggregate-only;
* nothing corroborates the live vehicle pursuit near Dadar (a pursuit is never corroborated).
"""

from __future__ import annotations

from analysis_fixtures import mumbai_resolver, mumbai_signals
from osint_common import ethics, testing
from osint_analysis.fusion import area_key_for
from osint_analysis.pipeline import HELD_SINGLE_SOCIAL, HELD_STATE_LEVEL, fused_event_id, run_pipeline


def run():
    return run_pipeline(mumbai_signals(), resolver=mumbai_resolver(), live=testing.live_state_dadar_pursuit(),
                        now=testing.live_state_dadar_pursuit().as_of)


def test_the_mumbai_situations():
    result = run()
    rows = [(r.is_event, r.event_class, r.subtype, r.toponym, r.segment_id, r.junction_id, r.area_level,
             r.held_reason, r.verification_state, r.credibility, r.source_count) for r in result.resolved]
    assert rows == [
        (True, "road_accident", "affray+collision", "Western Express Highway", testing.WEH_SEGMENT, None, False, None,
         "NEWS-REPORTED", 0.65, 5),
        (True, "reported_crime", "daylight_robbery", "Dadar TT Circle", None, 4023, False, None, "NEWS-REPORTED",
         0.6, 1),
        (True, "weather_hazard", "thunderstorm", "Mumbai (district)", None, None, True, None, "OFFICIAL-VERIFIED",
         0.95, 1),
        (False, "weather_hazard", "thunderstorm", "Maharashtra (state)", None, None, True, HELD_STATE_LEVEL,
         "OFFICIAL-VERIFIED", 0.95, 1),
        (False, "road_closure", "closure", "Ghatkopar (LBS Marg)", None, 4027, False, HELD_SINGLE_SOCIAL,
         "UNVERIFIED-OSINT", 0.25, 1),
    ]
    weh = result.resolved[0]
    assert weh.correlated_classes == ["road_accident", "public_conflict"] and weh.sajag_event_kind == "road_accident"
    assert weh.label == "Road accident · Western Express Highway"
    assert weh.fused_event_id == fused_event_id(testing.weh_signals())
    assert weh.independent_publishers == 2
    assert result.counts.surfaced == 3 and result.counts.outside_city_held == 1 and result.counts.social_held == 1
    assert result.counts.attached_to_live == 0


def test_the_area_keys_and_labels_are_mumbai_and_maharashtra():
    result = run()
    district = next(r for r in result.resolved if r.toponym == "Mumbai (district)")
    assert district.label == "Weather hazard · Mumbai district"
    state = next(r for r in result.resolved if r.toponym == "Maharashtra (state)")
    assert state.label == "Weather hazard · Maharashtra state"
    # an area geocode without a toponym is keyed by the connector's admin code
    geo = mumbai_resolver().by_id[testing.sachet_mumbai_signal().signal_id].model_copy(update={"toponym": None})
    assert area_key_for(geo, testing.sachet_mumbai_signal()) == "mumbai"
    geo = mumbai_resolver().by_id[testing.sachet_maharashtra_signal().signal_id].model_copy(update={"toponym": None})
    gdelt = testing.sachet_maharashtra_signal().model_copy(
        update={"raw_geo_hint": testing.sachet_maharashtra_signal().raw_geo_hint.model_copy(
            update={"admin_codes": ["GDELT_ADM1:IN16"]})})
    assert area_key_for(geo, gdelt) == "maharashtra"


def test_the_mumbai_output_carries_no_person_and_never_crime_incident():
    result = run()
    dumped = result.model_dump(mode="json")
    ethics.assert_no_person_keys(dumped)
    for r in result.resolved:
        assert r.sajag_event_kind not in ("crime_incident", "vehicle_pursuit")
        assert ethics.find_pii(r.label) == [] and ethics.find_pii(r.summary) == []
