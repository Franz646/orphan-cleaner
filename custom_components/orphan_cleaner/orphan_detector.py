"""
Orphan entity detection logic.
Operates directly on the HA entity registry and states.

Detection methods:
  1. orphaned_timestamp  — official HA field
  2. dead_config_entry   — config_entry_id points to a removed integration
  3. unavailable_state   — unavailable state for more than N hours
  4. heuristic           — no config_entry_id and non-manual platform
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MANUAL_PLATFORMS

_LOGGER = logging.getLogger(__name__)

ALWAYS_UNAVAILABLE_PLATFORMS = {
    "template", "group", "universal", "input_boolean",
}


@dataclass
class OrphanInfo:
    entity_id:   str
    platform:    str
    method:      str
    age_hours:   float | None
    disabled_by: str | None
    state:       str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def detect_orphans(
    hass: HomeAssistant,
    min_age_hours: int = 24,
    aggressive: bool = False,
) -> list[OrphanInfo]:
    entity_registry  = er.async_get(hass)
    now              = time.time()
    orphans: list[OrphanInfo] = []

    active_entry_ids: set[str] = {
        e.entry_id for e in hass.config_entries.async_entries()
    }

    # Debug: log first entry fields to detect HA version changes
    sample = next(iter(entity_registry.entities.values()), None)
    if sample:
        ts_val = getattr(sample, "orphaned_timestamp", "FIELD_MISSING")
        _LOGGER.debug(
            "Sample entity %s — orphaned_timestamp field: %s, platform: %s, config_entry_id: %s",
            sample.entity_id, ts_val, sample.platform, sample.config_entry_id,
        )

    for entry in entity_registry.entities.values():
        platform     = entry.platform or ""
        cfg_entry_id = entry.config_entry_id

        # ── Method 1: orphaned_timestamp ──────────────────────────────
        ts = getattr(entry, "orphaned_timestamp", None)
        if ts is not None:
            age_h = (now - ts) / 3600
            _LOGGER.debug(
                "orphaned_timestamp: %s age=%.1fh min=%d → %s",
                entry.entity_id, age_h, min_age_hours,
                "INCLUDE" if age_h >= min_age_hours else "TOO RECENT"
            )
            if age_h >= min_age_hours:
                orphans.append(OrphanInfo(
                    entity_id   = entry.entity_id,
                    platform    = platform or "—",
                    method      = "timestamp",
                    age_hours   = round(age_h, 1),
                    disabled_by = entry.disabled_by,
                    state       = "orphaned",
                ))
            continue

        # ── Method 2: dead config entry ───────────────────────────────
        if cfg_entry_id and cfg_entry_id not in active_entry_ids:
            _LOGGER.debug("dead_entry: %s cfg=%s", entry.entity_id, cfg_entry_id)
            orphans.append(OrphanInfo(
                entity_id   = entry.entity_id,
                platform    = platform or "—",
                method      = "dead_entry",
                age_hours   = None,
                disabled_by = entry.disabled_by,
            ))
            continue

        # ── Method 3: unavailable state ───────────────────────────────
        if platform not in ALWAYS_UNAVAILABLE_PLATFORMS and entry.disabled_by is None:
            state_obj = hass.states.get(entry.entity_id)
            if state_obj and state_obj.state == "unavailable":
                modified_at = getattr(entry, "modified_at", None)
                if modified_at:
                    age_h = (datetime.now(timezone.utc) - modified_at).total_seconds() / 3600
                else:
                    created_at = getattr(entry, "created_at", None)
                    age_h = (
                        (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                        if created_at else 0
                    )
                if age_h >= min_age_hours:
                    _LOGGER.debug("unavailable: %s age=%.1fh", entry.entity_id, age_h)
                    orphans.append(OrphanInfo(
                        entity_id   = entry.entity_id,
                        platform    = platform or "—",
                        method      = "unavailable",
                        age_hours   = round(age_h, 1),
                        disabled_by = entry.disabled_by,
                        state       = "unavailable",
                    ))
                    continue

        # ── Method 4: heuristic ───────────────────────────────────────
        if aggressive and not cfg_entry_id and platform and platform not in MANUAL_PLATFORMS:
            _LOGGER.debug("heuristic: %s platform=%s", entry.entity_id, platform)
            orphans.append(OrphanInfo(
                entity_id   = entry.entity_id,
                platform    = platform,
                method      = "heuristic",
                age_hours   = None,
                disabled_by = entry.disabled_by,
            ))

    _LOGGER.info(
        "Scan: %d total entities, %d orphans "
        "(timestamp:%d dead_entry:%d unavailable:%d heuristic:%d)",
        len(entity_registry.entities), len(orphans),
        sum(1 for o in orphans if o.method == "timestamp"),
        sum(1 for o in orphans if o.method == "dead_entry"),
        sum(1 for o in orphans if o.method == "unavailable"),
        sum(1 for o in orphans if o.method == "heuristic"),
    )
    return orphans


async def async_delete_entities(
    hass: HomeAssistant,
    entity_ids: list[str],
) -> tuple[list[str], list[str]]:
    """Delete entities from the registry."""
    registry = er.async_get(hass)
    deleted: list[str] = []
    failed:  list[str] = []

    for eid in entity_ids:
        entry = registry.async_get(eid)
        if entry is None:
            _LOGGER.warning("Entity not found in registry: %s", eid)
            failed.append(eid)
            continue
        try:
            registry.async_remove(eid)
            _LOGGER.info("Deleted: %s", eid)
            deleted.append(eid)
        except Exception as exc:
            _LOGGER.error("Error deleting %s: %s", eid, exc)
            failed.append(eid)

    return deleted, failed
