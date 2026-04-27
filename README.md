# Orphan Entity Cleaner — Custom Integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)

A custom integration that finds and deletes **orphan entities** — entities left in the registry after the integration that created them has been removed or failed — via a web panel in the sidebar and services callable from scripts and automations.

---

## Installation

### Via HACS (recommended)

1. In HACS → **Integrations → ⋮ → Custom repositories**
2. Add the URL of this repository, category **Integration**
3. Search for **Orphan Entity Cleaner** and install
4. Restart Home Assistant
5. **Settings → Devices & Services → Add Integration → Orphan Entity Cleaner**

### Manual installation

1. Copy the `custom_components/orphan_cleaner/` folder to `<config>/custom_components/`
2. Restart Home Assistant
3. **Settings → Devices & Services → Add Integration → Orphan Entity Cleaner**

---

## Web Panel

After installation, the **Orphan Cleaner** icon appears in the HA sidebar. All settings are controlled directly from the panel — no configuration flow needed after the initial setup.

### Controls

| Control | Description |
|---|---|
| **Scan** | Scans the registry and populates the table |
| **Heuristic** | Enables detection method 4 (see below) |
| **Min age (h)** | Minimum age in hours for an entity to be flagged |
| **Ignore platforms** | Add platform names to exclude from results (e.g. `tuya`, `shelly`) |
| **Filter** | Filter visible results by entity_id or platform |
| **Select all / Deselect** | Bulk checkbox controls |
| **Delete selected** | Delete selected entities with a confirmation dialog |
| **Save & Delete** | Save a JSON backup of selected entities to `/config/` before deleting |

### Ignore Platforms

Type a platform name in the **Ignore platforms** field and press **Enter** or **+ Add**. The platform appears as a removable pill tag. Ignored entities remain visible in the table but are greyed out and non-interactive. The orphan counter reflects the exclusion. The ignore list is applied immediately and persists across rescans during the same session.

### Save & Delete

**Save & Delete** exports a timestamped JSON backup of the selected entities to `/config/orphan_cleaner_backup_<timestamp>.json` before proceeding with deletion. If the backup fails, deletion is aborted. The backup contains entity metadata (entity_id, platform, detection method, age, disabled state) and can be used as a reference in case of accidental deletion.

---

## Detection Methods

### Method 1 — `orphaned_timestamp` (reliable)

Home Assistant sets this field in the registry when, after a full restart, an entity is not claimed by any integration. This is the official signal and is always active.

**Min age (h)** filters out recently orphaned entities, useful if an integration is temporarily offline.

### Method 2 — Dead config entry

If an entity's `config_entry_id` points to a config entry that no longer exists or is in a `FAILED` / `NOT_LOADED` state, the entity is considered an orphan.

### Method 3 — Unavailable state

Entities in `unavailable` state for longer than **Min age (h)** are flagged. Catches entities that HA marks with the yellow warning "no longer provided by the integration".

### Method 4 — Heuristic (optional)

Enabled by the **Heuristic** checkbox. Also flags entities with no `config_entry_id` and a platform not in the following exclusion list:

`automation`, `counter`, `group`, `input_boolean`, `input_button`, `input_datetime`, `input_number`, `input_select`, `input_text`, `person`, `persistent_notification`, `scene`, `schedule`, `script`, `tag`, `template`, `timer`, `zone`

---

## Services

### `orphan_cleaner.scan`

Runs the scan and fires the `orphan_cleaner_orphans_found` event on the HA event bus.

```yaml
action: orphan_cleaner.scan
```

Event payload:
```yaml
count: 5
orphans:
  - entity_id: sensor.old_shelly
    platform: shelly
    method: timestamp
    age_hours: 72.3
    disabled_by: null
```

Example automation:
```yaml
automation:
  trigger:
    platform: event
    event_type: orphan_cleaner_orphans_found
  condition:
    condition: template
    value_template: "{{ trigger.event.data.count > 0 }}"
  action:
    service: notify.mobile_app
    data:
      title: "Orphan entities detected"
      message: "Found {{ trigger.event.data.count }} orphan entities."
```

### `orphan_cleaner.delete_orphans`

Deletes the specified entities, or all detected orphans if none are specified.

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_ids` | list | No | Entities to delete. If omitted → all orphans |
| `dry_run` | bool | No | Log only, without making changes (default: `false`) |

```yaml
# Delete all orphans
action: orphan_cleaner.delete_orphans

# Dry run
action: orphan_cleaner.delete_orphans
data:
  dry_run: true

# Delete specific entities
action: orphan_cleaner.delete_orphans
data:
  entity_ids:
    - sensor.old_device
    - binary_sensor.ghost_sensor
```

---

## File Structure

```
custom_components/orphan_cleaner/
├── __init__.py           ← setup, panel registration, teardown
├── config_flow.py        ← initial config flow
├── const.py              ← constants
├── manifest.json         ← integration metadata
├── orphan_detector.py    ← detection and deletion logic
├── panel_api.py          ← HTTP views (panel, scan, delete, export)
├── services.py           ← HA services (scan, delete_orphans)
├── services.yaml         ← service documentation for Developer Tools
├── strings.json          ← UI labels
├── translations/
│   └── en.json
└── frontend/
    ├── panel.html        ← full web interface
    └── orphan-cleaner-panel.js
```

---

## Warnings

- **Always make a backup** before deleting entities in bulk. Use **Save & Delete** to automatically export a JSON record before each deletion.
- Deleted entities are removed from the **registry**: historical data in the **recorder** remains but is no longer associated with an active entity. To clean the recorder as well, use the `recorder.purge_entities` service.
- An entity with `orphaned_timestamp` may belong to an integration that is temporarily offline. Increase **Min age (h)** if you have unstable integrations.
- Deletion is **irreversible**. Entities cannot be restored from the backup — the backup is a reference record only.

---

## License

MIT
