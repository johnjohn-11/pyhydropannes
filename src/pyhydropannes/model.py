"""Typed reading of a Hydro-Québec Info-pannes payload.

LocationState.from_payload() reads one payload into the interruptions to display. The rules follow the Info-pannes site. Interruption methods do not depend on the root status, the LocationState methods do.

Datetimes are timezone-aware. A date the API sends without an offset is read in Hydro-Québec's time zone. Every rule comparing with the current time takes ``now``, so a caller can read a payload at any instant.
"""

from __future__ import annotations

import html
import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .const import (
    CANCELLATION_REASON_DEFAULT,
    CANCELLATION_REASONS,
    EXPECTED_ROOT_FIELDS,
    KNOWN_INTERRUPTION_FIELDS,
    KNOWN_ROOT_FIELDS,
    MAJOR_URGENCY_CODES,
    OUTAGE_ONGOING,
    OUTAGE_TERMINATED,
    PLANNED_CANCELLED,
    PLANNED_POSTPONED,
    PLANNED_SHIFTED,
    ROOT_OFF,
    ROOT_ON,
)

HYDRO_QUEBEC_TZ = ZoneInfo("America/Toronto")

_FAR_FUTURE = datetime.max.replace(tzinfo=UTC)
_EPOCH = datetime.fromtimestamp(0, UTC)

# ==========================================================================
# Values
# ==========================================================================


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO datetime string to an aware datetime, or return None."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=HYDRO_QUEBEC_TZ)


def round_up_quarter(value: datetime) -> datetime:
    """Round a time up to the next quarter hour, as the Info-pannes site does before comparing it to now.

    Only the minutes are rounded, seconds are kept, like the site's dateArrondie pipe.
    """
    quarters = math.ceil(value.minute / 15)
    if quarters == 4:
        return value.replace(minute=0) + timedelta(hours=1)
    return value.replace(minute=quarters * 15)


def _code(value: Any) -> str | None:
    """Return a code as a string, None when absent. The API sends some codes as integers."""
    if value is None or value == "":
        return None
    return str(value)


def _int(value: Any) -> int | None:
    """Return an integer field, None when absent or not a number."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    """Return an address field as plain text, None when missing."""
    # The API embeds HTML entities such as &nbsp; in its formatted addresses.
    text = html.unescape(str(value or "")).replace("\xa0", " ").strip()
    return text or None


def _now(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(UTC)


# ==========================================================================
# A single interruption
# ==========================================================================


@dataclass(frozen=True, kw_only=True)
class Interruption:
    """One interruption listed in a payload.

    ``start`` and ``end`` are the original window. A postponed or shifted planned interruption carries its new window in ``postponed_*`` or ``shifted_*``: use ``effective_start`` and ``effective_end``. ``raw`` is the interruption as the API sent it.
    """

    raw: Mapping[str, Any] = field(repr=False, compare=False)
    id: str | None
    status: str | None
    planned: bool
    start: datetime | None
    end: datetime | None
    postponed_start: datetime | None
    postponed_end: datetime | None
    shifted_start: datetime | None
    shifted_end: datetime | None
    estimated_end_min: datetime | None
    estimated_end_max: datetime | None
    published: datetime | None
    cause_code: str | None
    intervention_code: str | None
    urgency_code: str | None
    end_type_code: str | None
    remark_code: str | None
    municipality_code: str | None
    customers: int | None
    customers_in_other_outage: int | None
    planned_duration_minutes: int | None
    gradual_restoration_possible: bool

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Interruption:
        """Read one interruption of the payload."""
        return cls(
            raw=data,
            id=_code(data.get("idInterruption")),
            status=_code(data.get("etat")),
            planned=bool(data.get("interruptionPlanifiee", False)),
            start=parse_datetime(data.get("dateDebut")),
            end=parse_datetime(data.get("dateFin")),
            postponed_start=parse_datetime(data.get("dateDebutReport")),
            postponed_end=parse_datetime(data.get("dateFinReport")),
            shifted_start=parse_datetime(data.get("dateDebutDecalage")),
            shifted_end=parse_datetime(data.get("dateFinDecalage")),
            estimated_end_min=parse_datetime(data.get("dateFinEstimeeMin")),
            estimated_end_max=parse_datetime(data.get("dateFinEstimeeMax")),
            published=parse_datetime(data.get("datePublication")),
            cause_code=_code(data.get("codeCause")),
            intervention_code=_code(data.get("codeIntervention")),
            urgency_code=_code(data.get("niveauUrgence")),
            end_type_code=_code(data.get("typeFinPrevue")),
            remark_code=_code(data.get("codeRemarque")),
            municipality_code=_code(data.get("codeMunicipal")),
            customers=_int(data.get("nbClient")),
            customers_in_other_outage=_int(data.get("nbClientsInclusDansAutrePanne")),
            planned_duration_minutes=_int(data.get("dureePrevu")),
            gradual_restoration_possible=bool(data.get("repriseGraduellePossible")),
        )

    @property
    def is_postponed(self) -> bool:
        """Return True if the planned interruption was postponed (status "R")."""
        return self.status == PLANNED_POSTPONED

    @property
    def is_cancelled(self) -> bool:
        """Return True if the planned interruption was cancelled (status "A").

        The Info-pannes site shows status "A" as cancelled whatever the remark code, even when report dates are present.
        """
        return self.status == PLANNED_CANCELLED

    @property
    def is_major(self) -> bool:
        """Return True when the interruption carries a major-outage urgency level."""
        return self.urgency_code in MAJOR_URGENCY_CODES

    @property
    def cancellation_reason(self) -> str | None:
        """Return the cancellation or postponement reason, None without a remark code."""
        if self.remark_code is None:
            return None
        return CANCELLATION_REASONS.get(self.remark_code, CANCELLATION_REASON_DEFAULT)

    @property
    def _new_window(self) -> tuple[datetime | None, datetime | None] | None:
        """Return the new window of a postponed or shifted interruption, None for any other status.

        The API keeps the original dateDebut and dateFin as the abandoned slot.
        """
        if self.status == PLANNED_POSTPONED:
            return self.postponed_start, self.postponed_end
        if self.status == PLANNED_SHIFTED:
            return self.shifted_start, self.shifted_end
        return None

    @property
    def effective_start(self) -> datetime | None:
        """Return the start of the window in force: the new one once postponed or shifted, if it has a start."""
        window = self._new_window
        if window and window[0]:
            return window[0]
        return self.start

    @property
    def effective_end(self) -> datetime | None:
        """Return the end of the window in force, paired with ``effective_start``."""
        window = self._new_window
        if window and window[0]:
            return window[1]
        return self.end

    def is_terminated(self, now: datetime | None = None) -> bool:
        """Return True if the interruption is terminated (power restored).

        A postponed or shifted planned interruption is terminated only once its new end is past, and never without one. Any other interruption is terminated once its end is past.
        """
        window = self._new_window
        end = window[1] if window else self.end
        return end is not None and end <= _now(now)

    def is_future_planned(self, now: datetime | None = None) -> bool:
        """Return True if the interruption is a planned one with a future effective start."""
        start = self.effective_start
        return self.planned and start is not None and start > _now(now)

    def supersedes_terminated(self, now: datetime | None = None) -> bool:
        """Return True when this planned interruption outranks a past outage: neither cancelled nor terminated."""
        return not self.is_cancelled and not self.is_terminated(now)

    @property
    def _outage_end_for_sort(self) -> datetime:
        """Return the end used to rank simultaneous outages, far in the future when there is none."""
        return self.estimated_end_max or self.end or _FAR_FUTURE

    @property
    def _planned_sort_key(self) -> tuple[bool, datetime]:
        """Rank planned interruptions like the Info-pannes site: cancelled last, then by original start."""
        return self.is_cancelled, self.start or _FAR_FUTURE


# ==========================================================================
# A whole payload
# ==========================================================================


@dataclass(frozen=True, kw_only=True)
class LocationState:
    """What one payload says about a location, read at ``now``.

    ``active_outage`` is the unplanned outage to display, ``terminated_outage`` the most recently terminated one, ``planned`` the most relevant planned interruption, ``pending_planned`` the planned ones neither cancelled nor terminated (nearest first) and ``current`` the interruption to describe. ``out_of_sync`` mirrors the site's nonSynchronise flag.
    """

    raw: Mapping[str, Any] = field(repr=False, compare=False)
    now: datetime
    location_id: str | None
    status: str | None
    date: datetime | None
    gradual_restoration_possible: bool
    interruptions: tuple[Interruption, ...]
    active_outage: Interruption | None = None
    terminated_outage: Interruption | None = None
    planned: Interruption | None = None
    pending_planned: tuple[Interruption, ...] = ()
    out_of_sync: bool = False
    current: Interruption | None = None

    @classmethod
    def from_payload(cls, data: Mapping[str, Any], now: datetime | None = None) -> LocationState:
        """Read a payload as ``async_get_payload()`` returns it.

        The selections are computed in order: each may rely on the ones before it.
        """
        interruptions = data.get("interruptions") or []
        state = cls(
            raw=data,
            now=_now(now),
            location_id=_code(data.get("idLieuConso")),
            status=_code(data.get("etat")),
            date=parse_datetime(data.get("date")),
            gradual_restoration_possible=bool(data.get("repriseGraduellePossible")),
            interruptions=tuple(
                Interruption.from_dict(i) for i in interruptions if isinstance(i, Mapping)
            ),
        )
        state = replace(state, active_outage=state._select_active_outage())
        state = replace(state, terminated_outage=state._select_terminated_outage())
        state = replace(state, planned=state._select_planned())
        state = replace(state, pending_planned=state._select_pending_planned())
        state = replace(state, out_of_sync=state._compute_out_of_sync())
        return replace(state, current=None if state.out_of_sync else state._select_current())

    # ----------------------------------------------------------------------
    # Rules that depend on the root status
    # ----------------------------------------------------------------------

    def is_active(self, intr: Interruption) -> bool:
        """Return True if the interruption is under way.

        An unplanned interruption is active from its own status, as on the site: C, I or N is under way, T is terminated. A planned one, or an unplanned one with another status, is active when the root status is "N" and its end (the new window's end once postponed or shifted) is absent or in the future.
        """
        if not intr.planned:
            # The site goes by the interruption's own status: a C with root status "A" is still shown as an outage under way.
            if intr.status in OUTAGE_ONGOING:
                return True
            if intr.status == OUTAGE_TERMINATED:
                return False

        if self.status != ROOT_OFF:
            return False

        # A postponed or shifted planned interruption is active only inside its new window: the root status can be "N" because of another outage before the new window starts.
        window = intr._new_window
        if window and intr.planned:
            start, end = window
            return start is not None and start <= self.now and (end is None or end > self.now)
        return intr.end is None or intr.end > self.now

    def is_planned_in_progress(self, intr: Interruption) -> bool:
        """Return True for a planned interruption under way: root status "N", neither cancelled nor terminated."""
        return (
            intr.planned
            and self.status == ROOT_OFF
            and not intr.is_cancelled
            and not intr.is_terminated(self.now)
        )

    def is_gradual_restoration(self, intr: Interruption | None = None) -> bool:
        """Return True when Hydro-Québec signals a gradual service restoration.

        The flag is read from the payload root and from the interruption, so it is not missed if Hydro-Québec reports it per interruption.
        """
        if intr is not None and intr.gradual_restoration_possible:
            return True
        return self.gradual_restoration_possible

    # ----------------------------------------------------------------------
    # Selection, run once by from_payload()
    # ----------------------------------------------------------------------

    def _select_active_outage(self) -> Interruption | None:
        """Return the active unplanned outage to display, or None.

        Like the Info-pannes site, the unplanned interruptions are ranked major first, then by latest end. The first active one is kept, and any interruption ranked after it that overlaps it moves its start back. The returned interruption is then a copy carrying that earlier start.
        """
        unplanned = [i for i in self.interruptions if not i.planned]
        # Sort ascending then reverse, like the site, so that ties also come out in reverse payload order.
        ranked = sorted(unplanned, key=lambda i: (i.is_major, i._outage_end_for_sort))[::-1]
        chosen: Interruption | None = None
        for intr in ranked:
            if chosen is None:
                if self.is_active(intr):
                    chosen = intr
                continue
            if (
                chosen.start
                and intr.start
                and intr.start < chosen.start
                and intr._outage_end_for_sort > chosen.start
            ):
                chosen = replace(chosen, start=intr.start)
        return chosen

    def _select_terminated_outage(self) -> Interruption | None:
        """Return the most recently terminated unplanned outage, the one with the latest end when Hydro-Québec splits an outage into sections."""
        candidates = [i for i in self.interruptions if not i.planned and i.is_terminated(self.now)]
        if not candidates:
            return None
        return max(candidates, key=lambda i: i.end or _EPOCH)

    def _select_pending_planned(self) -> tuple[Interruption, ...]:
        """Return the planned interruptions that are neither cancelled nor terminated, nearest first."""
        pending = (
            i
            for i in self.interruptions
            if i.planned and not i.is_cancelled and not i.is_terminated(self.now)
        )
        return tuple(sorted(pending, key=lambda i: i._planned_sort_key))

    def _select_planned(self) -> Interruption | None:
        """Return the most relevant planned interruption, or None.

        Priority: the active one, then the nearest future one not cancelled, then the nearest future one, then the first listed. "Nearest" follows the Info-pannes ranking, by original start.
        """
        planned = [i for i in self.interruptions if i.planned]
        if not planned:
            return None
        for p in planned:
            if self.is_active(p):
                return p
        ranked = sorted(planned, key=lambda i: i._planned_sort_key)
        for p in ranked:
            if p.is_future_planned(self.now) and not p.is_cancelled:
                return p
        for p in ranked:
            if p.is_future_planned(self.now):
                return p
        return planned[0]

    def _compute_out_of_sync(self) -> bool:
        """Return True when the root status and the listed interruptions disagree, as the site's nonSynchronise flag.

        Either the root status is "A" while an unplanned interruption is under way, or it is "N" while no unplanned outage is under way and no planned interruption is in progress. The site then shows an outage under way without any detail.
        """
        if self.status == ROOT_ON:
            return self.active_outage is not None
        if self.status != ROOT_OFF or self.active_outage:
            return False
        return not (self.planned and self.is_planned_in_progress(self.planned))

    def _select_current(self) -> Interruption | None:
        """Return the interruption to describe.

        Priority: the active unplanned outage, then the latest terminated one unless a planned interruption still pending outranks it, then the planned interruption, then the first listed.
        """
        if self.active_outage:
            return self.active_outage
        if self.terminated_outage and not (
            self.planned and self.planned.supersedes_terminated(self.now)
        ):
            return self.terminated_outage
        if self.planned:
            return self.planned
        return self.interruptions[0] if self.interruptions else None


# ==========================================================================
# Address lookup
# ==========================================================================


@dataclass(frozen=True, kw_only=True)
class Location:
    """A consumption location found by the address lookup."""

    raw: Mapping[str, Any] = field(repr=False, compare=False)
    id: str
    full_address: str | None
    street_address: str | None
    apartment_address: str | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Location:
        """Read one lookup result whose ``lieuConsommation`` was already checked."""
        return cls(
            raw=data,
            id=str(data["lieuConsommation"]),
            full_address=_text(data.get("adresseCompleteFr")),
            street_address=_text(data.get("adresseFormateePourChoixRue")),
            apartment_address=_text(data.get("adresseFormateePourChoixAppartementFr")),
        )


# ==========================================================================
# Schema checks
# ==========================================================================


def missing_root_fields(data: Mapping[str, Any]) -> frozenset[str]:
    """Return the expected root fields the payload lacks, a sign the API changed."""
    return EXPECTED_ROOT_FIELDS - data.keys()


def unknown_root_fields(data: Mapping[str, Any]) -> frozenset[str]:
    """Return the root fields no recorded payload had."""
    return frozenset(data.keys() - KNOWN_ROOT_FIELDS)


def unknown_interruption_fields(data: Mapping[str, Any]) -> frozenset[str]:
    """Return the interruption fields no recorded payload had, across every listed interruption."""
    fields: set[str] = set()
    for intr in data.get("interruptions") or []:
        if isinstance(intr, Mapping):
            fields |= intr.keys() - KNOWN_INTERRUPTION_FIELDS
    return frozenset(fields)
