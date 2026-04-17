# Orphan Entity Cleaner — Custom Integration per Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)

Integrazione custom (non add-on) che trova e cancella le **entità orfane** — rimaste nel registro dopo la rimozione dell'integrazione che le aveva create — tramite panel web nella sidebar e servizi richiamabili da script e automazioni.

---

## Installazione

### Via HACS (consigliato)

1. In HACS → **Integrazioni → ⋮ → Repository personalizzati**
2. Aggiungi l'URL di questo repository, categoria **Integration**
3. Cerca "Orphan Entity Cleaner" e installa
4. Riavvia Home Assistant
5. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Orphan Entity Cleaner**

### Installazione manuale

1. Copia la cartella `custom_components/orphan_cleaner/` in `<config>/custom_components/`
2. Riavvia Home Assistant
3. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Orphan Entity Cleaner**

---

## Configurazione

| Parametro | Tipo | Default | Descrizione |
|---|---|---|---|
| `min_orphan_age_hours` | int (1–720) | `24` | Ore minime da cui l'entità deve avere `orphaned_timestamp` impostato |
| `aggressive_heuristic` | bool | `false` | Includi anche entità senza `config_entry_id` e piattaforma non manuale |

Le opzioni sono modificabili in qualsiasi momento da **Impostazioni → Dispositivi e servizi → Orphan Cleaner → Configura**.

---

## Panel web

Dopo l'installazione compare l'icona **Orphan Cleaner** (🧹) nella barra laterale di HA.

Il panel permette di:
- **Scansionare** il registro con un click
- **Filtrare** i risultati per entity_id o piattaforma
- **Selezionare** singolarmente o in blocco
- **Eliminare** con modale di conferma
- Visualizzare il **log** delle operazioni in tempo reale

---

## Servizi

### `orphan_cleaner.scan`

Esegue la scansione e spara l'evento `orphan_cleaner_orphans_found` sul bus di HA.

```yaml
action: orphan_cleaner.scan
```

Il payload dell'evento contiene:
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

Esempio automazione per notifica:
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
      title: "Entità orfane rilevate"
      message: "Trovate {{ trigger.event.data.count }} entità orfane in Home Assistant."
```

---

### `orphan_cleaner.delete_orphans`

Elimina le entità specificate, oppure tutte le orfane rilevate.

| Campo | Tipo | Obbligatorio | Descrizione |
|---|---|---|---|
| `entity_ids` | list | No | Entity ID da eliminare. Se omesso → tutte le orfane |
| `dry_run` | bool | No (default `false`) | Log senza modificare nulla |

```yaml
# Elimina tutte le orfane
action: orphan_cleaner.delete_orphans

# Dry run: vedi solo i log
action: orphan_cleaner.delete_orphans
data:
  dry_run: true

# Elimina entità specifiche
action: orphan_cleaner.delete_orphans
data:
  entity_ids:
    - sensor.old_device
    - binary_sensor.ghost_sensor
```

---

## Come funziona il rilevamento

### Metodo 1 — `orphaned_timestamp` (affidabile)

HA imposta questo campo nel registry quando, dopo un riavvio completo, un'entità non viene reclamata da nessuna integrazione. È il segnale ufficiale e viene usato sempre.

Il parametro `min_orphan_age_hours` filtra le entità troppo recenti (es. integrazione temporaneamente offline).

### Metodo 2 — Euristica (opzionale)

Attivato da `aggressive_heuristic: true`. Considera orfane anche le entità senza `config_entry_id` e con piattaforma non in questa lista di esclusioni:

`template`, `input_boolean`, `input_number`, `input_text`, `input_select`, `input_datetime`, `input_button`, `counter`, `timer`, `schedule`, `group`, `persistent_notification`, `script`, `automation`, `scene`, `zone`, `person`, `tag`

---

## Struttura

```
custom_components/orphan_cleaner/
├── __init__.py           ← setup, panel, teardown
├── config_flow.py        ← UI configurazione e opzioni
├── const.py              ← costanti
├── manifest.json         ← metadati integrazione
├── orphan_detector.py    ← logica rilevamento e cancellazione
├── panel_api.py          ← view HTTP (panel + API REST interna)
├── services.py           ← servizi HA (scan, delete_orphans)
├── services.yaml         ← documentazione servizi per Developer Tools
├── strings.json          ← etichette UI
├── translations/
│   └── en.json
└── frontend/
    └── panel.html        ← interfaccia web completa
```

---

## Avvertenze

- **Fai sempre un backup** prima di eliminare entità in blocco.
- Le entità cancellate vengono rimosse dal **registry**: i dati storici nel **recorder** rimangono ma non sono più associati a un'entità attiva. Per pulire anche il DB usa `recorder.purge_entities`.
- Un'entità con `orphaned_timestamp` potrebbe appartenere a un'integrazione temporaneamente offline: aumenta `min_orphan_age_hours` se hai integrazioni instabili.

---

## Licenza

MIT
