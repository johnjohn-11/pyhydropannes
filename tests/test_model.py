"""Tests of the payload reading rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from pyhydropannes import (
    Interruption,
    Location,
    LocationState,
    missing_root_fields,
    parse_datetime,
    round_up_quarter,
    unknown_interruption_fields,
    unknown_root_fields,
)

from .helpers import hours_from_now, make_interruption, make_payload


def harness(**payload_kwargs: Any) -> LocationState:
    """Read a freshly constructed payload."""
    return LocationState.from_payload(make_payload(**payload_kwargs))


def read(data: dict[str, Any]) -> Interruption:
    return Interruption.from_dict(data)


def find(state: LocationState, data: dict[str, Any]) -> Interruption:
    """Return the interruption of the state read from ``data``."""
    return next(i for i in state.interruptions if i.raw is data)


# ---------------------------------------------------------------------------
# is_active
# ---------------------------------------------------------------------------


def test_outage_active_when_root_off_and_no_end() -> None:
    intr = make_interruption(dateFin=None)
    h = harness(etat="N", interruptions=[intr])
    assert h.is_active(find(h, intr)) is True


def test_outage_active_when_end_in_future() -> None:
    intr = make_interruption(dateFin=hours_from_now(3))
    h = harness(etat="N", interruptions=[intr])
    assert h.is_active(find(h, intr)) is True


def test_planned_not_active_when_root_on() -> None:
    intr = make_interruption(interruptionPlanifiee=True, dateFin=None)
    h = harness(etat="A", interruptions=[intr])
    assert h.is_active(find(h, intr)) is False


def test_outage_not_active_when_end_in_past() -> None:
    intr = make_interruption(dateFin=hours_from_now(-1))
    h = harness(etat="N", interruptions=[intr])
    assert h.is_active(find(h, intr)) is False


def test_unplanned_without_known_status_follows_root() -> None:
    intr = make_interruption(etat="X", dateFin=None)
    assert harness(etat="N", interruptions=[intr]).active_outage is not None
    assert harness(etat="A", interruptions=[intr]).active_outage is None


@pytest.mark.parametrize(("etat", "suffix"), [("R", "Report"), ("E", "Decalage")])
def test_postponed_planned_active_follows_new_end(etat: str, suffix: str) -> None:
    """The abandoned end of a postponed planned interruption does not keep it active."""
    intr = make_interruption(
        interruptionPlanifiee=True,
        etat=etat,
        dateFin=hours_from_now(3),
        **{f"dateDebut{suffix}": hours_from_now(-5), f"dateFin{suffix}": hours_from_now(-1)},
    )
    h = harness(etat="N", interruptions=[intr])
    assert h.is_active(find(h, intr)) is False


@pytest.mark.parametrize(("etat", "suffix"), [("R", "Report"), ("E", "Decalage")])
def test_postponed_planned_not_active_before_new_window(etat: str, suffix: str) -> None:
    """Root status "N" from another outage does not make a postponed interruption active before its new window.

    Replays a real payload: an unplanned outage under way while the postponed planned interruption starts later the same day.
    """
    planned = make_interruption(
        interruptionPlanifiee=True,
        etat=etat,
        dateDebut=hours_from_now(-120),
        dateFin=hours_from_now(-116),
        **{f"dateDebut{suffix}": hours_from_now(2), f"dateFin{suffix}": hours_from_now(5)},
    )
    outage = make_interruption(etat="C", dateFin=None)
    h = harness(etat="N", interruptions=[planned, outage])
    assert h.is_active(find(h, planned)) is False
    assert h.current is not None
    assert h.current.raw is outage


@pytest.mark.parametrize(("etat", "suffix"), [("R", "Report"), ("E", "Decalage")])
def test_postponed_planned_active_inside_new_window(etat: str, suffix: str) -> None:
    intr = make_interruption(
        interruptionPlanifiee=True,
        etat=etat,
        dateFin=hours_from_now(-100),
        **{f"dateDebut{suffix}": hours_from_now(-1), f"dateFin{suffix}": hours_from_now(2)},
    )
    h = harness(etat="N", interruptions=[intr])
    assert h.is_active(find(h, intr)) is True


def test_postponed_planned_without_new_start_is_not_active() -> None:
    intr = make_interruption(interruptionPlanifiee=True, etat="R", dateFin=None)
    h = harness(etat="N", interruptions=[intr])
    assert h.is_active(find(h, intr)) is False


# ---------------------------------------------------------------------------
# is_terminated
# ---------------------------------------------------------------------------


def test_outage_terminated_when_end_in_past() -> None:
    assert read(make_interruption(dateFin=hours_from_now(-1))).is_terminated() is True


def test_outage_not_terminated_when_postponed_without_new_end() -> None:
    # Status "R" (postponed): the original dateFin is the abandoned slot.
    assert read(make_interruption(etat="R", dateFin=hours_from_now(-1))).is_terminated() is False


@pytest.mark.parametrize(("etat", "suffix"), [("R", "Report"), ("E", "Decalage")])
def test_postponed_or_shifted_terminated_follows_new_end(etat: str, suffix: str) -> None:
    def planned(new_end: str) -> Interruption:
        return read(
            make_interruption(
                etat=etat,
                interruptionPlanifiee=True,
                dateFin=hours_from_now(-48),
                **{f"dateFin{suffix}": new_end},
            )
        )

    assert planned(hours_from_now(-1)).is_terminated() is True
    assert planned(hours_from_now(24)).is_terminated() is False


def test_terminated_uses_given_now() -> None:
    intr = read(make_interruption(dateFin="2026-01-15T10:00:00+00:00"))
    assert intr.is_terminated(datetime(2026, 1, 15, 9, tzinfo=UTC)) is False
    assert intr.is_terminated(datetime(2026, 1, 15, 10, tzinfo=UTC)) is True


# ---------------------------------------------------------------------------
# is_cancelled / is_postponed / cancellation_reason
# ---------------------------------------------------------------------------


def test_planned_cancelled_via_status_a() -> None:
    assert read(make_interruption(interruptionPlanifiee=True, etat="A")).is_cancelled is True


def test_remark_code_alone_is_not_a_state() -> None:
    # codeRemarque is only the reason: a confirmed interruption carrying 92 stays confirmed.
    intr = read(make_interruption(interruptionPlanifiee=True, etat="P", codeRemarque="92"))
    assert intr.is_cancelled is False
    assert intr.is_postponed is False


def test_cancellation_with_report_dates_stays_cancelled() -> None:
    # Recorded payload: status "A" with code 91 and report dates, followed by no new interruption.
    intr = read(
        make_interruption(
            interruptionPlanifiee=True,
            etat="A",
            codeRemarque="91",
            dateDebutReport=hours_from_now(24),
            dateFinReport=hours_from_now(26),
        )
    )
    assert intr.is_cancelled is True
    assert intr.is_postponed is False


def test_planned_postponed_via_status_r() -> None:
    intr = read(make_interruption(interruptionPlanifiee=True, etat="R", codeRemarque="93"))
    assert intr.is_postponed is True
    assert intr.is_cancelled is False


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("45", "work_already_done"),
        ("91", "third_party_request"),
        (91, "third_party_request"),  # HQ sometimes returns an integer
        ("92", "weather_conditions"),
        ("93", "other_urgent_work"),
        ("40", "schedule_changed"),  # any other code
        ("", None),
        (None, None),
    ],
)
def test_cancellation_reason(code: Any, expected: str | None) -> None:
    intr = read(make_interruption(interruptionPlanifiee=True, etat="A", codeRemarque=code))
    assert intr.cancellation_reason == expected


# ---------------------------------------------------------------------------
# effective window
# ---------------------------------------------------------------------------


def test_effective_window_defaults_to_start_end() -> None:
    start, end = hours_from_now(-2), hours_from_now(2)
    intr = read(make_interruption(dateDebut=start, dateFin=end))
    assert intr.effective_start == parse_datetime(start)
    assert intr.effective_end == parse_datetime(end)


@pytest.mark.parametrize(("etat", "suffix"), [("R", "Report"), ("E", "Decalage")])
def test_effective_window_uses_new_window(etat: str, suffix: str) -> None:
    data = make_interruption(
        etat=etat,
        interruptionPlanifiee=True,
        dateDebut=hours_from_now(-48),
        dateFin=hours_from_now(-46),
        **{f"dateDebut{suffix}": hours_from_now(24), f"dateFin{suffix}": hours_from_now(26)},
    )
    intr = read(data)
    assert intr.effective_start == parse_datetime(data[f"dateDebut{suffix}"])
    assert intr.effective_end == parse_datetime(data[f"dateFin{suffix}"])


@pytest.mark.parametrize("etat", ["P", "A"])
def test_effective_window_ignores_report_dates_unless_postponed(etat: str) -> None:
    # Recorded payloads carry dateDebutReport on confirmed and cancelled interruptions too.
    data = make_interruption(
        etat=etat,
        interruptionPlanifiee=True,
        dateDebut=hours_from_now(24),
        dateFin=hours_from_now(26),
        dateDebutReport=hours_from_now(48),
        dateFinReport=hours_from_now(50),
    )
    intr = read(data)
    assert (intr.effective_start, intr.effective_end) == (
        parse_datetime(data["dateDebut"]),
        parse_datetime(data["dateFin"]),
    )


# ---------------------------------------------------------------------------
# selection priority
# ---------------------------------------------------------------------------


def test_active_outage_selected_over_planned() -> None:
    outage = make_interruption(dateFin=None)
    planned = make_interruption(
        interruptionPlanifiee=True, dateDebut=hours_from_now(48), dateFin=None
    )
    h = harness(etat="N", interruptions=[planned, outage])
    assert h.current is not None and h.current.raw is outage


def test_terminated_outage_yields_to_future_planned() -> None:
    terminated = make_interruption(dateFin=hours_from_now(-1))
    future_planned = make_interruption(
        interruptionPlanifiee=True, dateDebut=hours_from_now(24), dateFin=hours_from_now(26)
    )
    h = harness(etat="A", interruptions=[terminated, future_planned])
    assert h.current is not None and h.current.raw is future_planned
    assert [i.raw for i in h.pending_planned] == [future_planned]


def test_terminated_outage_kept_when_only_cancelled_planned() -> None:
    terminated = make_interruption(dateFin=hours_from_now(-1))
    cancelled_planned = make_interruption(
        interruptionPlanifiee=True, etat="A", codeRemarque="92", dateDebut=hours_from_now(24)
    )
    h = harness(etat="A", interruptions=[terminated, cancelled_planned])
    assert h.current is not None and h.current.raw is terminated


def test_most_recent_terminated_outage_is_chosen() -> None:
    older = make_interruption(dateFin=hours_from_now(-5))
    newer = make_interruption(dateFin=hours_from_now(-1))
    h = harness(etat="A", interruptions=[older, newer])
    assert h.terminated_outage is not None and h.terminated_outage.raw is newer


def test_planned_priority() -> None:
    cancelled = make_interruption(
        interruptionPlanifiee=True,
        etat="A",
        dateDebut=hours_from_now(10),
        dateFin=hours_from_now(12),
    )
    later = make_interruption(
        interruptionPlanifiee=True, dateDebut=hours_from_now(48), dateFin=hours_from_now(50)
    )
    sooner = make_interruption(
        interruptionPlanifiee=True, dateDebut=hours_from_now(24), dateFin=hours_from_now(26)
    )
    h = harness(etat="A", interruptions=[cancelled, later, sooner])
    assert h.planned is not None and h.planned.raw is sooner
    # Only a cancelled future one left: it is still the planned interruption.
    h = harness(etat="A", interruptions=[cancelled])
    assert h.planned is not None and h.planned.raw is cancelled
    # Nothing in the future: the first listed.
    past = make_interruption(
        interruptionPlanifiee=True, dateDebut=hours_from_now(-5), dateFin=hours_from_now(-4)
    )
    h = harness(etat="A", interruptions=[past])
    assert h.planned is not None and h.planned.raw is past
    assert h.current is h.planned


def test_planned_in_progress_is_the_planned_one() -> None:
    planned = make_interruption(
        interruptionPlanifiee=True, dateDebut=hours_from_now(-1), dateFin=hours_from_now(2)
    )
    h = harness(etat="N", interruptions=[planned])
    assert h.planned is not None and h.planned.raw is planned
    assert h.is_planned_in_progress(h.planned) is True
    assert h.out_of_sync is False


def test_no_interruptions_returns_none() -> None:
    h = harness(etat="A", interruptions=[])
    assert h.current is None


def test_first_listed_when_nothing_else_applies() -> None:
    odd = make_interruption(etat="X", dateFin=hours_from_now(2))
    h = harness(etat="A", interruptions=[odd])
    assert h.current is not None and h.current.raw is odd


# ---------------------------------------------------------------------------
# out_of_sync
# ---------------------------------------------------------------------------


def test_out_of_sync_root_on_with_outage_under_way() -> None:
    h = harness(etat="A", interruptions=[make_interruption(dateFin=None)])
    assert h.out_of_sync is True
    assert h.current is None


def test_out_of_sync_root_off_without_outage() -> None:
    h = harness(etat="N", interruptions=[])
    assert h.out_of_sync is True


def test_not_out_of_sync_with_unknown_root() -> None:
    assert harness(etat="?", interruptions=[]).out_of_sync is False


# ---------------------------------------------------------------------------
# supersedes_terminated
# ---------------------------------------------------------------------------


def test_supersedes_terminated() -> None:
    future = read(
        make_interruption(
            interruptionPlanifiee=True, dateDebut=hours_from_now(24), dateFin=hours_from_now(26)
        )
    )
    cancelled = read(make_interruption(interruptionPlanifiee=True, etat="A", codeRemarque="92"))
    terminated = read(make_interruption(interruptionPlanifiee=True, dateFin=hours_from_now(-1)))
    assert future.supersedes_terminated() is True
    assert cancelled.supersedes_terminated() is False
    assert terminated.supersedes_terminated() is False


# ---------------------------------------------------------------------------
# gradual restoration
# ---------------------------------------------------------------------------


def test_gradual_restoration_read_from_payload_root() -> None:
    intr = make_interruption(dateFin=None)
    h = harness(etat="N", interruptions=[intr], repriseGraduellePossible=True)
    assert h.is_gradual_restoration(find(h, intr)) is True
    assert h.is_gradual_restoration() is True


def test_gradual_restoration_read_from_interruption() -> None:
    # The flag is listed as an interruption-level field, so it must be honoured there too and not only at the payload root.
    intr = make_interruption(dateFin=None, repriseGraduellePossible=True)
    h = harness(etat="N", interruptions=[intr])
    assert h.is_gradual_restoration(find(h, intr)) is True


def test_gradual_restoration_absent_is_false() -> None:
    intr = make_interruption(dateFin=None)
    h = harness(etat="N", interruptions=[intr])
    assert h.is_gradual_restoration(find(h, intr)) is False


# ---------------------------------------------------------------------------
# Field reading
# ---------------------------------------------------------------------------


def test_interruption_fields_are_typed() -> None:
    intr = read(
        {
            "idInterruption": 42,
            "etat": "C",
            "interruptionPlanifiee": False,
            "dateDebut": "2026-01-15T08:00:00.000+00:00",
            "dateFinEstimeeMax": "2026-01-15T12:00:00.000+00:00",
            "codeCause": 21,
            "niveauUrgence": "P",
            "nbClient": "120",
            "nbClientsInclusDansAutrePanne": True,
            "dureePrevu": "abc",
        }
    )
    assert intr.id == "42"
    assert intr.start == datetime(2026, 1, 15, 8, tzinfo=UTC)
    assert intr.estimated_end_max == datetime(2026, 1, 15, 12, tzinfo=UTC)
    assert intr.cause_code == "21"
    assert intr.is_major is True
    assert intr.customers == 120
    assert intr.customers_in_other_outage is None
    assert intr.planned_duration_minutes is None


def test_payload_root_fields() -> None:
    h = LocationState.from_payload(
        {
            "etat": "A",
            "idLieuConso": "0000001234",
            "date": "2026-10-02T00:00:00.000+00:00",
            "interruptions": ["x"],
        },
        now=datetime(2026, 10, 2, tzinfo=UTC),
    )
    assert h.location_id == "0000001234"
    assert h.date == datetime(2026, 10, 2, tzinfo=UTC)
    assert h.now == datetime(2026, 10, 2, tzinfo=UTC)
    assert h.interruptions == ()


def test_location_unescapes_addresses() -> None:
    location = Location.from_dict(
        {"lieuConsommation": "0000000001", "adresseCompleteFr": "1, rue Exemple, Qc A1A&nbsp;1A1"}
    )
    assert location.id == "0000000001"
    assert location.full_address == "1, rue Exemple, Qc A1A 1A1"
    assert location.street_address is None


# ---------------------------------------------------------------------------
# Dates and schema checks
# ---------------------------------------------------------------------------


def test_parse_datetime_reads_naive_in_hydro_quebec_time() -> None:
    parsed = parse_datetime("2026-01-15T08:00:00")
    assert parsed is not None
    assert parsed.utcoffset() == timedelta(hours=-5)


@pytest.mark.parametrize("value", [None, "", "pas une date", 12])
def test_parse_datetime_invalid(value: Any) -> None:
    assert parse_datetime(value) is None


@pytest.mark.parametrize(
    ("minute", "expected"), [(0, (14, 0)), (1, (14, 15)), (31, (14, 45)), (46, (15, 0))]
)
def test_round_up_quarter(minute: int, expected: tuple[int, int]) -> None:
    value = round_up_quarter(datetime(2026, 9, 25, 14, minute, 30, tzinfo=UTC))
    assert (value.hour, value.minute, value.second) == (*expected, 30)


def test_schema_checks() -> None:
    payload = {"etat": "N", "nouveau": 1, "interruptions": [{"dateDebut": "x", "autre": 2}, "x"]}
    assert missing_root_fields(payload) == {"idLieuConso"}
    assert unknown_root_fields(payload) == {"nouveau"}
    assert unknown_interruption_fields(payload) == {"autre"}
    assert unknown_interruption_fields({}) == frozenset()


def test_overlapping_outage_moves_start_back() -> None:
    chosen = make_interruption(dateDebut=hours_from_now(-1), dateFin=hours_from_now(3))
    earlier = make_interruption(dateDebut=hours_from_now(-4), dateFin=hours_from_now(1))
    apart = make_interruption(dateDebut=hours_from_now(-9), dateFin=hours_from_now(-8))
    h = harness(etat="N", interruptions=[earlier, chosen, apart])
    assert h.active_outage is not None
    assert h.active_outage.raw is chosen
    assert h.active_outage.start == parse_datetime(earlier["dateDebut"])
    assert h.active_outage.end == parse_datetime(chosen["dateFin"])
    assert find(h, chosen).start == parse_datetime(chosen["dateDebut"])
