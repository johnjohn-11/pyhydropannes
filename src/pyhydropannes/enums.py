"""What the Info-pannes site shows for a location, as enumerations, and the API codes behind them."""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class ServiceStatus(StrEnum):
    """The overall status of a location."""

    NO_OUTAGE = "no_outage"
    OUTAGE = "outage"
    MAJOR_OUTAGE = "major_outage"
    GRADUAL_RESTORATION = "gradual_restoration"
    RESTORED = "restored"
    PLANNED_IN_PROGRESS = "planned_in_progress"
    PLANNED_UPCOMING = "planned_upcoming"
    PLANNED_TERMINATED = "planned_terminated"
    PLANNED_CANCELLED = "planned_cancelled"
    PLANNED_POSTPONED = "planned_postponed"


class InterventionStep(StrEnum):
    """The step the work on an interruption has reached."""

    PLANNED_UPCOMING = "planned_upcoming"
    PLANNED_POSTPONED = "planned_postponed"
    PLANNED_CANCELLED = "planned_cancelled"
    ASSESSMENT = "assessment"
    CREW_ASSIGNED = "crew_assigned"
    WORK_IN_PROGRESS = "work_in_progress"
    WORK_BY_PRIORITY = "work_by_priority"
    RESTORATION_UNDER_ASSESSMENT = "restoration_under_assessment"
    RESTORATION_EXPECTED = "restoration_expected"
    END_UNDETERMINED = "end_undetermined"
    GRADUAL_RESTORATION = "gradual_restoration"
    RESTORED = "restored"


class RestorationStep(StrEnum):
    """The restoration step of the site's outage tracker, separate from the intervention step."""

    UNDER_ASSESSMENT = "under_assessment"
    EXPECTED = "expected"
    UNDER_REVISION = "under_revision"


class UrgencyLevel(StrEnum):
    """The urgency level of an interruption."""

    NORMAL = "normal"
    MAJOR = "major"


class EndKind(StrEnum):
    """What the end shown for an interruption is: the actual end, an estimate, or the end of a new window."""

    ACTUAL = "actual"
    ESTIMATED = "estimated"
    POSTPONED = "postponed"


class Cause(StrEnum):
    """The cause of an interruption, as the Info-pannes site groups the cause codes."""

    ACCIDENT_OR_INCIDENT = "accident_or_incident"
    ACCIDENTAL_CONTACT = "accidental_contact"
    ANIMAL_DAMAGE = "animal_damage"
    BIRD_DAMAGE = "bird_damage"
    EQUIPMENT_DAMAGE = "equipment_damage"
    EQUIPMENT_FAILURE = "equipment_failure"
    EXTREME_TEMPERATURE = "extreme_temperature"
    FIRE_OR_GAS_LEAK = "fire_or_gas_leak"
    GRID_MAINTENANCE = "grid_maintenance"
    GRID_OVERLOAD = "grid_overload"
    HIGH_WINDS = "high_winds"
    LIGHTNING = "lightning"
    NATURAL_DISASTER = "natural_disaster"
    POLE_COLLISION = "pole_collision"
    PRECIPITATION = "precipitation"
    PROTECTIVE_MEASURE = "protective_measure"
    PUBLIC_SAFETY = "public_safety"
    TREE_TRIMMING = "tree_trimming"
    UNDETERMINED = "undetermined"
    URGENT_MAINTENANCE = "urgent_maintenance"
    VEGETATION_DAMAGE = "vegetation_damage"
    WORK_SAFETY = "work_safety"
    WORN_EQUIPMENT = "worn_equipment"


# codeCause → cause, as the Info-pannes site maps them. Any other code, 58 included, is undetermined on the site too.
CAUSE_CODES: Final = {
    "11": Cause.EQUIPMENT_FAILURE,
    "12": Cause.GRID_OVERLOAD,
    "13": Cause.EQUIPMENT_DAMAGE,
    "14": Cause.EQUIPMENT_DAMAGE,
    "15": Cause.EQUIPMENT_DAMAGE,
    "72": Cause.EQUIPMENT_DAMAGE,
    "79": Cause.EQUIPMENT_DAMAGE,
    "21": Cause.LIGHTNING,
    "22": Cause.PRECIPITATION,
    "24": Cause.NATURAL_DISASTER,
    "25": Cause.HIGH_WINDS,
    "26": Cause.EXTREME_TEMPERATURE,
    "31": Cause.ACCIDENT_OR_INCIDENT,
    "32": Cause.ACCIDENT_OR_INCIDENT,
    "41": Cause.ACCIDENT_OR_INCIDENT,
    "43": Cause.ACCIDENT_OR_INCIDENT,
    "56": Cause.ACCIDENT_OR_INCIDENT,
    "57": Cause.ACCIDENT_OR_INCIDENT,
    "33": Cause.WORN_EQUIPMENT,
    "34": Cause.FIRE_OR_GAS_LEAK,
    "42": Cause.ACCIDENTAL_CONTACT,
    "55": Cause.ACCIDENTAL_CONTACT,
    "44": Cause.PUBLIC_SAFETY,
    "51": Cause.VEGETATION_DAMAGE,
    "52": Cause.BIRD_DAMAGE,
    "53": Cause.ANIMAL_DAMAGE,
    "54": Cause.POLE_COLLISION,
    "60": Cause.URGENT_MAINTENANCE,
    "70": Cause.URGENT_MAINTENANCE,
    "61": Cause.GRID_MAINTENANCE,
    "62": Cause.GRID_MAINTENANCE,
    "63": Cause.GRID_MAINTENANCE,
    "64": Cause.GRID_MAINTENANCE,
    "65": Cause.GRID_MAINTENANCE,
    "67": Cause.GRID_MAINTENANCE,
    "68": Cause.GRID_MAINTENANCE,
    "69": Cause.GRID_MAINTENANCE,
    "71": Cause.GRID_MAINTENANCE,
    "66": Cause.WORK_SAFETY,
    "73": Cause.PROTECTIVE_MEASURE,
    "74": Cause.PROTECTIVE_MEASURE,
    "77": Cause.TREE_TRIMMING,
    "78": Cause.TREE_TRIMMING,
}

# niveauUrgence → urgency level. Only "N" and "P" were seen in recorded payloads.
URGENCY_CODES: Final = {
    "N": UrgencyLevel.NORMAL,
    "M": UrgencyLevel.MAJOR,
    "P": UrgencyLevel.MAJOR,
}

# codeIntervention → step, following the Info-pannes steps: N (none) and A (assigned) are both shown as the assessment step, R (on the way) as the assigned crew.
INTERVENTION_CODES: Final = {
    "N": InterventionStep.ASSESSMENT,
    "A": InterventionStep.ASSESSMENT,
    "R": InterventionStep.CREW_ASSIGNED,
    "L": InterventionStep.WORK_IN_PROGRESS,
}

# codeIntervention of a crew on site. During a major outage the site words that step as work by priority.
INTERVENTION_ON_SITE: Final = "L"

# codeIntervention values of a crew on the way or on site.
INTERVENTION_CREW_DISPATCHED: Final = frozenset({"R", "L"})

# typeFinPrevue → step, used when the intervention code gives none. U, D and P are documented by Hydro-Québec. F, E and X were only observed, their meaning is provisional.
END_TYPE_CODES: Final = {
    "U": InterventionStep.RESTORATION_UNDER_ASSESSMENT,
    "D": InterventionStep.RESTORATION_EXPECTED,
    "P": InterventionStep.RESTORATION_EXPECTED,
    "F": InterventionStep.END_UNDETERMINED,
    "E": InterventionStep.RESTORATION_EXPECTED,
    "X": InterventionStep.RESTORATION_EXPECTED,
}
