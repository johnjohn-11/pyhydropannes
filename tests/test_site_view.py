"""Tests of what the Info-pannes site shows for a location: statuses, steps, causes and windows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from pyhydropannes import (
    Cause,
    EndKind,
    Interruption,
    InterventionStep,
    LocationState,
    RestorationStep,
    ServiceStatus,
    UrgencyLevel,
)

from .helpers import hours_from_now, make_interruption, make_payload


def state(**payload_kwargs: Any) -> LocationState:
    return LocationState.from_payload(make_payload(**payload_kwargs))


def read(**fields: Any) -> Interruption:
    return Interruption.from_dict(make_interruption(**fields))


def planned(**fields: Any) -> dict[str, Any]:
    return make_interruption(interruptionPlanifiee=True, **fields)


# ---------------------------------------------------------------------------
# service_status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param({"etat": "A"}, ServiceStatus.NO_OUTAGE, id="fed_without_interruption"),
        pytest.param({"etat": "N"}, ServiceStatus.OUTAGE, id="not_fed_without_interruption"),
        pytest.param({"etat": "Z"}, None, id="unknown_root_status"),
        pytest.param(
            {"etat": "A", "interruptions": [make_interruption()]},
            ServiceStatus.OUTAGE,
            id="out_of_sync",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [make_interruption()]},
            ServiceStatus.OUTAGE,
            id="outage",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [make_interruption(niveauUrgence="P")]},
            ServiceStatus.MAJOR_OUTAGE,
            id="major_outage",
        ),
        pytest.param(
            {
                "etat": "N",
                "interruptions": [make_interruption()],
                "repriseGraduellePossible": True,
            },
            ServiceStatus.GRADUAL_RESTORATION,
            id="gradual_restoration",
        ),
        pytest.param(
            {"etat": "A", "interruptions": [make_interruption(dateFin=hours_from_now(-1))]},
            ServiceStatus.RESTORED,
            id="restored",
        ),
        pytest.param(
            {
                "etat": "A",
                "interruptions": [
                    planned(
                        etat="R",
                        dateDebutReport=hours_from_now(24),
                        dateFinReport=hours_from_now(26),
                    )
                ],
            },
            ServiceStatus.PLANNED_POSTPONED,
            id="planned_postponed",
        ),
        pytest.param(
            {"etat": "A", "interruptions": [planned(etat="A", dateDebut=hours_from_now(2))]},
            ServiceStatus.PLANNED_CANCELLED,
            id="planned_cancelled",
        ),
        pytest.param(
            {"etat": "A", "interruptions": [planned(dateFin=hours_from_now(-1))]},
            ServiceStatus.PLANNED_TERMINATED,
            id="planned_terminated",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [planned(dateFin=hours_from_now(2))]},
            ServiceStatus.PLANNED_IN_PROGRESS,
            id="planned_in_progress",
        ),
        pytest.param(
            {
                "etat": "A",
                "interruptions": [planned(dateDebut=hours_from_now(2), dateFin=hours_from_now(4))],
            },
            ServiceStatus.PLANNED_UPCOMING,
            id="planned_upcoming",
        ),
        pytest.param(
            {"etat": "A", "interruptions": [make_interruption(etat="Z")]},
            ServiceStatus.NO_OUTAGE,
            id="unplanned_with_unknown_status",
        ),
    ],
)
def test_service_status(payload: dict[str, Any], expected: ServiceStatus | None) -> None:
    assert state(**payload).service_status is expected


# ---------------------------------------------------------------------------
# intervention_step
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param({"etat": "A"}, None, id="no_interruption"),
        pytest.param(
            {"etat": "A", "interruptions": [planned(etat="A", dateFin=hours_from_now(-1))]},
            InterventionStep.PLANNED_CANCELLED,
            id="cancelled_even_once_past",
        ),
        pytest.param(
            {"etat": "A", "interruptions": [make_interruption(dateFin=hours_from_now(-1))]},
            InterventionStep.RESTORED,
            id="restored",
        ),
        pytest.param(
            {
                "etat": "A",
                "interruptions": [
                    planned(
                        etat="R",
                        dateDebutReport=hours_from_now(24),
                        dateFinReport=hours_from_now(26),
                    )
                ],
            },
            InterventionStep.PLANNED_POSTPONED,
            id="postponed",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [make_interruption(repriseGraduellePossible=True)]},
            InterventionStep.GRADUAL_RESTORATION,
            id="gradual_restoration",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [planned(dateFin=hours_from_now(2))]},
            InterventionStep.RESTORATION_EXPECTED,
            id="planned_in_progress_with_end",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [planned()]},
            InterventionStep.WORK_IN_PROGRESS,
            id="planned_in_progress_without_end",
        ),
        pytest.param(
            {"etat": "A", "interruptions": [planned(dateDebut=hours_from_now(2))]},
            InterventionStep.PLANNED_UPCOMING,
            id="planned_upcoming",
        ),
        pytest.param(
            {
                "etat": "N",
                "interruptions": [make_interruption(codeIntervention="L", niveauUrgence="P")],
            },
            InterventionStep.WORK_BY_PRIORITY,
            id="crew_on_site_during_major_outage",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [make_interruption(codeIntervention="L")]},
            InterventionStep.WORK_IN_PROGRESS,
            id="crew_on_site",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [make_interruption(codeIntervention="R")]},
            InterventionStep.CREW_ASSIGNED,
            id="crew_on_the_way",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [make_interruption(codeIntervention="N")]},
            InterventionStep.ASSESSMENT,
            id="no_crew",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [make_interruption(typeFinPrevue="U")]},
            InterventionStep.RESTORATION_UNDER_ASSESSMENT,
            id="end_type_without_intervention_code",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [make_interruption(typeFinPrevue="F")]},
            InterventionStep.END_UNDETERMINED,
            id="end_undetermined",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [make_interruption()]},
            None,
            id="no_code_at_all",
        ),
    ],
)
def test_intervention_step(payload: dict[str, Any], expected: InterventionStep | None) -> None:
    assert state(**payload).intervention_step is expected


# ---------------------------------------------------------------------------
# restoration_step
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param({"etat": "A"}, None, id="no_interruption"),
        pytest.param(
            {"etat": "A", "interruptions": [make_interruption()]},
            None,
            id="out_of_sync",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [planned(dateFin=hours_from_now(2))]},
            RestorationStep.EXPECTED,
            id="planned_in_progress_with_end",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [planned()]},
            None,
            id="planned_in_progress_without_end",
        ),
        pytest.param(
            {
                "etat": "N",
                "interruptions": [make_interruption(dateFinEstimeeMax=hours_from_now(3))],
            },
            RestorationStep.EXPECTED,
            id="estimate_ahead",
        ),
        pytest.param(
            {
                "etat": "N",
                "interruptions": [make_interruption(dateFinEstimeeMax=hours_from_now(-1))],
            },
            RestorationStep.UNDER_REVISION,
            id="estimate_past",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [make_interruption(codeIntervention="L")]},
            RestorationStep.UNDER_REVISION,
            id="crew_on_site_without_estimate",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [make_interruption(codeIntervention="A")]},
            RestorationStep.UNDER_ASSESSMENT,
            id="no_estimate",
        ),
    ],
)
def test_restoration_step(payload: dict[str, Any], expected: RestorationStep | None) -> None:
    assert state(**payload).restoration_step is expected


def test_restoration_estimate_is_rounded_up_to_the_quarter_hour() -> None:
    """An estimate at 10:05 is shown as 10:15, so it is still expected at 10:10."""
    now = datetime(2026, 1, 15, 15, 10, tzinfo=UTC)  # 10:10 in Hydro-Québec's time zone
    payload = make_payload(
        etat="N",
        interruptions=[
            make_interruption(
                etat="C",
                dateDebut="2026-01-15T08:00:00-05:00",
                dateFinEstimeeMax="2026-01-15T10:05:00-05:00",
            )
        ],
    )
    assert LocationState.from_payload(payload, now=now).restoration_step is RestorationStep.EXPECTED
    later = now + timedelta(minutes=5)
    assert (
        LocationState.from_payload(payload, now=later).restoration_step
        is RestorationStep.UNDER_REVISION
    )


# ---------------------------------------------------------------------------
# time_to_restoration
# ---------------------------------------------------------------------------


def test_time_to_restoration_counts_down_to_the_estimate() -> None:
    now = datetime(2026, 1, 15, 15, 0, tzinfo=UTC)
    payload = make_payload(
        etat="N",
        interruptions=[
            make_interruption(
                etat="C",
                dateDebut="2026-01-15T08:00:00-05:00",
                dateFinEstimeeMax="2026-01-15T12:30:00-05:00",
            )
        ],
    )
    remaining = LocationState.from_payload(payload, now=now).time_to_restoration
    assert remaining == timedelta(hours=2, minutes=30)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"etat": "A"}, id="no_interruption"),
        pytest.param(
            {"etat": "A", "interruptions": [make_interruption(dateFin=hours_from_now(-1))]},
            id="terminated",
        ),
        pytest.param(
            {
                "etat": "A",
                "interruptions": [
                    planned(dateDebut=hours_from_now(2), dateFinEstimeeMax=hours_from_now(4))
                ],
            },
            id="not_under_way",
        ),
        pytest.param({"etat": "N", "interruptions": [make_interruption()]}, id="no_estimate"),
        pytest.param(
            {
                "etat": "N",
                "interruptions": [make_interruption(dateFinEstimeeMax=hours_from_now(-1))],
            },
            id="estimate_past",
        ),
    ],
)
def test_time_to_restoration_is_none(payload: dict[str, Any]) -> None:
    assert state(**payload).time_to_restoration is None


# ---------------------------------------------------------------------------
# Root status
# ---------------------------------------------------------------------------


def test_power_off_follows_the_root_status() -> None:
    assert state(etat="N").power_off is True
    assert state(etat="A").power_off is False


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param({"etat": "N"}, True, id="not_fed"),
        pytest.param({"etat": "A"}, False, id="fed"),
        pytest.param(
            {"etat": "A", "interruptions": [make_interruption()]},
            True,
            id="fed_with_outage_under_way",
        ),
    ],
)
def test_service_problem(payload: dict[str, Any], expected: bool) -> None:
    assert state(**payload).service_problem is expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param(
            {"etat": "A", "interruptions": [make_interruption()]},
            True,
            id="unplanned_under_way_whatever_the_root",
        ),
        pytest.param(
            {"etat": "A", "interruptions": [planned()]},
            False,
            id="fed",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [planned()]},
            True,
            id="not_fed_without_end",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [planned(dateFin=hours_from_now(1))]},
            True,
            id="not_fed_with_end_ahead",
        ),
        pytest.param(
            {"etat": "N", "interruptions": [planned(dateFin=hours_from_now(-1))]},
            False,
            id="not_fed_with_end_past",
        ),
        pytest.param({"etat": "N"}, False, id="not_fed_without_interruption"),
    ],
)
def test_has_ongoing_interruption(payload: dict[str, Any], expected: bool) -> None:
    assert state(**payload).has_ongoing_interruption is expected


# ---------------------------------------------------------------------------
# Interruption
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param("N", UrgencyLevel.NORMAL, id="normal"),
        pytest.param("M", UrgencyLevel.MAJOR, id="major"),
        pytest.param("P", UrgencyLevel.MAJOR, id="purs"),
        pytest.param("Z", None, id="unknown"),
        pytest.param(None, None, id="absent"),
    ],
)
def test_urgency(code: str | None, expected: UrgencyLevel | None) -> None:
    assert read(niveauUrgence=code).urgency is expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param("21", Cause.LIGHTNING, id="string"),
        pytest.param(54, Cause.POLE_COLLISION, id="integer"),
        pytest.param("58", Cause.UNDETERMINED, id="unmapped"),
        pytest.param(None, Cause.UNDETERMINED, id="absent"),
    ],
)
def test_cause(code: Any, expected: Cause) -> None:
    assert read(codeCause=code).cause is expected


def test_end_shown_is_the_new_end_once_postponed() -> None:
    intr = read(
        interruptionPlanifiee=True,
        etat="R",
        dateFin="2026-01-15T12:00:00-05:00",
        dateDebutReport="2026-01-20T08:00:00-05:00",
        dateFinReport="2026-01-20T12:00:00-05:00",
    )
    assert intr.has_new_window is True
    assert intr.end_kind is EndKind.POSTPONED
    assert intr.display_end == intr.postponed_end
    assert intr.estimated_end_earliest is None


def test_end_shown_is_the_actual_end() -> None:
    intr = read(dateFin=hours_from_now(-1), dateFinEstimeeMax=hours_from_now(1))
    assert intr.has_new_window is False
    assert intr.end_kind is EndKind.ACTUAL
    assert intr.display_end == intr.end


def test_end_shown_is_the_latest_estimate() -> None:
    intr = read(dateFinEstimeeMin=hours_from_now(1), dateFinEstimeeMax=hours_from_now(3))
    assert intr.end_kind is EndKind.ESTIMATED
    assert intr.display_end == intr.estimated_end_max
    assert intr.estimated_end_earliest == intr.estimated_end_min


def test_estimate_given_as_a_single_time_has_no_range() -> None:
    estimate = hours_from_now(2)
    intr = read(dateFinEstimeeMin=estimate, dateFinEstimeeMax=estimate)
    assert intr.estimated_end_earliest is None


def test_no_end_to_show() -> None:
    intr = read()
    assert intr.end_kind is None
    assert intr.display_end is None


def test_elapsed_runs_to_now_while_under_way() -> None:
    now = datetime(2026, 1, 15, 15, 0, tzinfo=UTC)
    intr = read(dateDebut="2026-01-15T08:00:00-05:00")
    assert intr.elapsed(now) == timedelta(hours=2)


def test_elapsed_stops_at_the_end() -> None:
    intr = read(dateDebut="2026-01-15T08:00:00-05:00", dateFin="2026-01-15T09:30:00-05:00")
    assert intr.elapsed() == timedelta(hours=1, minutes=30)


def test_elapsed_is_never_negative() -> None:
    intr = read(dateDebut="2026-01-15T08:00:00-05:00", dateFin="2026-01-15T07:00:00-05:00")
    assert intr.elapsed() == timedelta(0)


@pytest.mark.parametrize(
    "start",
    [pytest.param(None, id="no_start"), pytest.param(hours_from_now(2), id="start_ahead")],
)
def test_elapsed_is_none_before_the_start(start: str | None) -> None:
    assert read(dateDebut=start).elapsed() is None


def test_long_planned_interruption_may_restore_gradually() -> None:
    intr = read(interruptionPlanifiee=True, dureePrevu=480, dateFin="2026-01-15T16:00:00-05:00")
    assert intr.may_restore_gradually is True
    assert intr.latest_end == datetime(2026, 1, 16, 2, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"dureePrevu": 479, "dateFin": hours_from_now(4)}, id="short"),
        pytest.param({"dateFin": hours_from_now(4)}, id="no_duration"),
        pytest.param({"dureePrevu": 480}, id="no_end"),
    ],
)
def test_no_latest_end(fields: dict[str, Any]) -> None:
    assert read(interruptionPlanifiee=True, **fields).latest_end is None


def test_fallback_window_of_a_confirmed_interruption() -> None:
    intr = read(
        interruptionPlanifiee=True,
        dateDebutReport="2026-01-20T08:00:00-05:00",
        dateFinReport="2026-01-20T12:00:00-05:00",
    )
    assert intr.fallback_window == (intr.postponed_start, intr.postponed_end)


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({}, id="no_report_dates"),
        pytest.param({"etat": "R", "dateDebutReport": hours_from_now(24)}, id="postponed"),
    ],
)
def test_no_fallback_window(fields: dict[str, Any]) -> None:
    assert read(interruptionPlanifiee=True, **fields).fallback_window is None
