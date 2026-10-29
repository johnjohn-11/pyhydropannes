"""Constants of the Hydro-Québec Info-pannes API."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

API_URL: Final = "https://services-bs.solutions.hydroquebec.com/pan/web/api/v1/lieux-conso/etats/{}"

# Address lookup used by the Info-pannes site. Hydro-Québec does not document it.
SEARCH_URL: Final = "https://services-bs.solutions.hydroquebec.com/pan/web/api/v1/lieux-conso"

# error.code of the HTTP 400 the lookup returns when several locations match the address.
SEARCH_DUPLICATES_CODE: Final = "BSSP0001"

# Root etat values: "A" (alimenté) when the location has power, "N" (non alimenté) when it does not.
ROOT_ON: Final = "A"
ROOT_OFF: Final = "N"

# Planned interruption etat values, as the Info-pannes site names them. The etat alone says whether a planned interruption is confirmed, postponed, shifted or cancelled.
PLANNED_POSTPONED: Final = "R"  # new window in dateDebutReport/dateFinReport
PLANNED_SHIFTED: Final = "E"  # new window in dateDebutDecalage/dateFinDecalage
PLANNED_CANCELLED: Final = "A"

# Unplanned interruption etat values. The site takes C (courante), I (non confirmée isolée) and N (non confirmée) as an outage under way whatever the root etat, and T as terminated.
OUTAGE_ONGOING: Final = frozenset({"C", "I", "N"})
OUTAGE_TERMINATED: Final = "T"

# The Info-pannes site names niveauUrgence "M" panne majeure and "P" PURS, and handles both the same way.
MAJOR_URGENCY_CODES: Final = frozenset({"M", "P"})

# codeRemarque → cancellation reason, as the Info-pannes site maps them. It is only the reason shown next to a cancelled or postponed interruption, never its state: dateDebutReport is present even on confirmed ones. Any other code is "Modification de la planification des travaux" on the site.
CANCELLATION_REASONS: Final = {
    "45": "work_already_done",
    "50": "third_party_request",
    "60": "third_party_request",
    "91": "third_party_request",
    "92": "weather_conditions",
    "93": "other_urgent_work",
    "94": "other_urgent_work",
}
CANCELLATION_REASON_DEFAULT: Final = "schedule_changed"

# dureePrevu (minutes) from which the Info-pannes site warns that a planned interruption may end with a gradual restoration.
GRADUAL_RESTORATION_PLANNED_MINUTES: Final = 480

# For such an interruption the site shows the end as a window from dateFin to this much later.
GRADUAL_RESTORATION_END_MARGIN: Final = timedelta(hours=5)

# Root fields the API always returns. Their absence indicates a breaking schema change.
EXPECTED_ROOT_FIELDS: Final = frozenset({"etat", "interruptions", "idLieuConso"})

# Root fields seen in recorded payloads. The Info-pannes site also reads etatReprise, dureePrevueDelestage, dureeResiduelleDelestage, remiseEnServicePrevue and remiseEnServiceConfirmee, none of which appeared in recorded payloads.
KNOWN_ROOT_FIELDS: Final = frozenset(
    {
        "etat",
        "idLieuConso",
        "interruptions",
        "date",
        "repriseGraduellePossible",
        "declencheurReprise",
    }
)

# Interruption fields seen in recorded payloads.
KNOWN_INTERRUPTION_FIELDS: Final = frozenset(
    {
        "dateDebut",
        "dateFin",
        "etat",
        "dateFinEstimeeMin",
        "dateFinEstimeeMax",
        "dateDebutReport",
        "dateFinReport",
        "dateDebutDecalage",
        "dateFinDecalage",
        "codeIntervention",
        "niveauUrgence",
        "nbClient",
        "codeCause",
        "codeMunicipal",
        "datePublication",
        "codeRemarque",
        "dureePrevu",
        "probabilite",
        "interruptionPlanifiee",
        "typeFinPrevue",
        "idInterruption",
        "nbClientsInclusDansAutrePanne",
        "repriseGraduellePossible",
    }
)
