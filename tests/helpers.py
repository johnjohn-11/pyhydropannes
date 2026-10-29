"""Payload builders shared by the tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def hours_from_now(hours: float) -> str:
    """Return an ISO datetime string offset from now by ``hours``."""
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def make_interruption(**overrides: Any) -> dict[str, Any]:
    """Build an interruption dict with sensible defaults.

    ``None`` values are dropped so tests can express "field absent" by passing ``field=None``.
    """
    interruption: dict[str, Any] = {
        "dateDebut": hours_from_now(-2),
        "etat": "N",
        "interruptionPlanifiee": False,
    }
    interruption.update(overrides)
    if not interruption["interruptionPlanifiee"] and "etat" not in overrides:
        # Like real payloads: an unplanned interruption is "C" while under way and "T" once its dateFin is past.
        date_fin = interruption.get("dateFin")
        ended = date_fin is not None and datetime.fromisoformat(date_fin) <= datetime.now(UTC)
        interruption["etat"] = "T" if ended else "C"
    return {k: v for k, v in interruption.items() if v is not None}


def make_payload(
    etat: str = "N", interruptions: list[dict[str, Any]] | None = None, **root: Any
) -> dict[str, Any]:
    """Build a top-level API payload with the given root etat and interruptions."""
    payload: dict[str, Any] = {
        "etat": etat,
        "idLieuConso": "0000001234",
        "interruptions": interruptions if interruptions is not None else [],
    }
    payload.update(root)
    return payload
