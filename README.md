# Orphan Entity Cleaner — Custom Integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)

A custom integration (not an add-on) that finds and deletes **orphan entities** — entities left in the registry after the integration that created them has been removed — via a web panel in the sidebar and services callable from scripts and automations.

---

## Installation

### Via HACS (recommended)

1. In HACS → **Integrations → ⋮ → Custom repositories**
2. Add the URL of this repository, category **Integration**
3. Search for "Orphan Entity Cleaner" and install
4. Restart Home Assistant
5. **Settings → Devices & Services → Add Integration → Orphan Entity Cleaner**

### Manual installation

1. Copy the `custom_components/orphan_cleaner/` folder to `<config>/custom_components/`
2. Restart Home Assistant
3. **Settings → Devices & Services → Add Integration → Orphan Entity Cleaner**

---

## Configuration

| Parameter | Type | Default | Description |
|---|---|---|---|
| `min_orphan_age_hours` | int (1–720) | `24` | Minimum hours since `orphaned_timestamp` was set on the entity |
| `aggressive_heuristic` | bool | `false` | Also include entities with no `config_entry_id` and a non-manual platform |

Options can be changed at any time from **Settings → Devices & Services → Orphan Cleaner → Configure**.

---

## Web Panel

After installation, the **Orphan Cleaner** icon (🧹) appears in the HA sidebar.

The panel allows you to:
- **Scan** the registry with one click
- **Filter** results by entity_id or platform
- **Select** entities individually or all at once
- **Delete** with a confirmation dialog
- View the **operation log** in real time

---

## Services

### `orphan_cleaner.scan`

Runs the scan and fires the `orphan_cleaner_orphans_found` event on the HA event bus.

```yaml
action: orphan_cleaner.scan
```

The event payload contains:
```yaml
count: 5
orphans:
  - entity_id: sensor.old_shelly
    platform: shelly
    method: timestamp
    age_hours: 72.3
    disabled_by: null
  - ...
```

Example automation for notification:
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
      message: "Found {{ trigger.event.data.count }} orphan entities in Home Assistant."
```

---

### `orphan_cleaner.delete_orphans`

Deletes the specified entities, or all detected orphans if none are specified.

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_ids` | list | No | Entity IDs to delete. If omitted → all orphans |
| `dry_run` | bool | No (default `false`) | Log only, without making any changes |

```yaml
# Delete all orphans
action: orphan_cleaner.delete_orphans

# Dry run: log only
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

## How Detection Works

### Method 1 — `orphaned_timestamp` (reliable)

HA sets this field in the registry when, after a full restart, an entity is not claimed by any integration. This is the official signal and is always used.

The `min_orphan_age_hours` parameter filters out entities that are too recent (e.g. an integration that is temporarily offline).

### Method 2 — Dead config entry

If an entity's `config_entry_id` points to a config entry that no longer exists, the entity is considered an orphan.

### Method 3 — Unavailable state

Entities in `unavailable` state for longer than `min_orphan_age_hours` are flagged. This catches entities like those from `ble_monitor` that HA marks with the yellow warning "no longer provided by the integration".

### Method 4 — Heuristic (optional)

Enabled by `aggressive_heuristic: true`. Also considers as orphans entities with no `config_entry_id` and a platform not in this exclusion list:

`template`, `input_boolean`, `input_number`, `input_text`, `input_select`, `input_datetime`, `input_button`, `counter`, `timer`, `schedule`, `group`, `persistent_notification`, `script`, `automation`, `scene`, `zone`, `person`, `tag`

---

## File Structure

```
custom_components/orphan_cleaner/
├── __init__.py           ← setup, panel registration, teardown
├── config_flow.py        ← configuration and options UI
├── const.py              ← constants
├── manifest.json         ← integration metadata
├── orphan_detector.py    ← detection and deletion logic
├── panel_api.py          ← HTTP views (panel + internal REST API)
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

- **Always make a backup** before deleting entities in bulk.
- Deleted entities are removed from the **registry**: historical data in the **recorder** remains but is no longer associated with an active entity. To clean the database as well, use `recorder.purge_entities`.
- An entity with `orphaned_timestamp` may belong to an integration that is temporarily offline: increase `min_orphan_age_hours` if you have unstable integrations.

---

## License

MIT
