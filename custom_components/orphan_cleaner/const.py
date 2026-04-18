"""Costanti per Orphan Entity Cleaner."""

DOMAIN = "orphan_cleaner"

# Panel
PANEL_URL  = "orphan-cleaner"
PANEL_NAME = "Orphan Cleaner"
PANEL_ICON = "mdi:broom"

# Config / Options keys
CONF_MIN_AGE_HOURS = "min_orphan_age_hours"
CONF_AGGRESSIVE    = "aggressive_heuristic"

# Defaults
DEFAULT_MIN_AGE_HOURS = 24
DEFAULT_AGGRESSIVE    = False

# Servizi
SERVICE_SCAN          = "scan"
SERVICE_DELETE_ORPHANS = "delete_orphans"

# Campi servizio
FIELD_ENTITY_IDS = "entity_ids"
FIELD_DRY_RUN    = "dry_run"

# Evento
EVENT_ORPHANS_FOUND = "orphan_cleaner_orphans_found"

# Piattaforme "manuali" escluse dall'euristica
MANUAL_PLATFORMS = {
    "template", "input_boolean", "input_number", "input_text",
    "input_select", "input_datetime", "input_button", "counter",
    "timer", "schedule", "group", "persistent_notification",
    "script", "automation", "scene", "zone", "person", "tag",
}
