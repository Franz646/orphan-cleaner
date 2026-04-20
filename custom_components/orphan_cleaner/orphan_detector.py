"""
Logica di rilevamento entità orfane.
Opera direttamente sul registry e sugli stati di Home Assistant.

Quattro metodi di rilevamento:
  1. orphaned_timestamp  — campo ufficiale HA
  2. dead_config_entry   — config_entry_id punta a integrazione rimossa
  3. unavailable_state   — stato unavailable da più di N ore (es. ble_monitor)
  4. heuristic           — nessun config_entry_id, piattaforma non manuale
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

# Piattaforme che per natura hanno spesso stato unavailable (non sono orfane)
ALWAYS_UNAVAILABLE_PLATFORMS = {
    "template", "group", "universal", "input_boolean",
}


@dataclass
class OrphanInfo:
    """Metadati di un'entità orfana."""
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
    include_dead_entry: bool = True,
    include_unavailable: bool = False,
) -> list[OrphanInfo]:
    """
    Scansiona registry e stati, restituisce le entità orfane.

    Metodo 1 — orphaned_timestamp (ufficiale):
      Campo impostato da HA dopo riavvio se l'entità non viene reclamata.

    Metodo 2 — dead_config_entry:
      config_entry_id punta a una config entry non più esistente.

    Metodo 3 — unavailable_state:
      Stato `unavailable` da più di min_age_hours ore. Intercetta entità
      come quelle di ble_monitor che HA segnala con il warning giallo
      "non più fornita dall'integrazione".

    Metodo 4 — heuristic (solo se aggressive=True):
      Nessun config_entry_id e piattaforma non manuale.
    """
    entity_registry = er.async_get(hass)
    now             = time.time()
    orphans: list[OrphanInfo] = []

    # Indice config entry attive per lookup O(1)
    active_entry_ids: set[str] = {
        e.entry_id for e in hass.config_entries.async_entries()
    }

    for entry in entity_registry.entities.values():
        platform     = entry.platform or ""
        cfg_entry_id = entry.config_entry_id

        # ── Metodo 1: orphaned_timestamp ──────────────────────────────
        ts = getattr(entry, "orphaned_timestamp", None)
        if ts is not None:
            age_h = (now - ts) / 3600
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

        # ── Metodo 2: config entry rimossa ────────────────────────────
        if include_dead_entry and cfg_entry_id and cfg_entry_id not in active_entry_ids:
            orphans.append(OrphanInfo(
                entity_id   = entry.entity_id,
                platform    = platform or "—",
                method      = "dead_entry",
                age_hours   = None,
                disabled_by = entry.disabled_by,
            ))
            continue

        # ── Metodo 3: stato unavailable + registry non aggiornato ────
        # Salta piattaforme che sono spesso unavailable per natura
        # e entità disabilitate
        if not include_unavailable:
            pass
        elif platform in ALWAYS_UNAVAILABLE_PLATFORMS:
            pass
        elif entry.disabled_by is not None:
            pass
        else:
            state_obj = hass.states.get(entry.entity_id)
            if state_obj and state_obj.state == "unavailable":
                # Usa modified_at dal registry: non si azzera al riavvio
                # a differenza di last_changed nello state machine.
                modified_at = getattr(entry, "modified_at", None)
                if modified_at:
                    age_h = (
                        datetime.now(timezone.utc) - modified_at
                    ).total_seconds() / 3600
                else:
                    # Fallback: created_at
                    created_at = getattr(entry, "created_at", None)
                    age_h = (
                        (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                        if created_at else 0
                    )
                if age_h >= min_age_hours:
                    orphans.append(OrphanInfo(
                        entity_id   = entry.entity_id,
                        platform    = platform or "—",
                        method      = "unavailable",
                        age_hours   = round(age_h, 1),
                        disabled_by = entry.disabled_by,
                        state       = "unavailable",
                    ))
                    continue

        # ── Metodo 4: euristica ───────────────────────────────────────
        if aggressive:
            if not cfg_entry_id and platform and platform not in MANUAL_PLATFORMS:
                orphans.append(OrphanInfo(
                    entity_id   = entry.entity_id,
                    platform    = platform,
                    method      = "heuristic",
                    age_hours   = None,
                    disabled_by = entry.disabled_by,
                ))

    ts_n  = sum(1 for o in orphans if o.method == "timestamp")
    de_n  = sum(1 for o in orphans if o.method == "dead_entry")
    un_n  = sum(1 for o in orphans if o.method == "unavailable")
    he_n  = sum(1 for o in orphans if o.method == "heuristic")

    _LOGGER.info(
        "Scansione: %d totali, %d orfane "
        "(timestamp:%d dead_entry:%d unavailable:%d heuristic:%d)",
        len(entity_registry.entities), len(orphans),
        ts_n, de_n, un_n, he_n,
    )
    return orphans


async def async_delete_entities(
    hass: HomeAssistant,
    entity_ids: list[str],
) -> tuple[list[str], list[str]]:
    """Elimina le entità dal registry."""
    registry = er.async_get(hass)
    deleted: list[str] = []
    failed:  list[str] = []

    for eid in entity_ids:
        entry = registry.async_get(eid)
        if entry is None:
            _LOGGER.warning("Entità non trovata nel registry: %s", eid)
            failed.append(eid)
            continue
        try:
            registry.async_remove(eid)
            _LOGGER.info("Cancellata: %s", eid)
            deleted.append(eid)
        except Exception as exc:
            _LOGGER.error("Errore cancellazione %s: %s", eid, exc)
            failed.append(eid)

    return deleted, failed
