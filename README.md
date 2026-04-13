## Plantera (brief)

CLI tool to track plants and show what needs watering.

---

## Core Commands

* `add` → add a plant
* `add-type` → add plant type
* `show` → (default "myplants", --types BOLEAN, --due BOOLEAN)
* `watered` → mark plant as watered
* `update` -> update anything from my plants
* `update-type` -> update anything from plant types
* `delete` -> delete plant or plant type
* `delete-type` -> delete plant type

---

## Core Behavior

* each plant has a watering interval
* `next_due = last_watered + interval`
* `due` shows due + overdue plants
* user must mark plants as watered

---

## Data Model
**SQLite Tables**

**Plant Library**
* id
* type
* care_info (json)

**My Plants (SQLite)**
* id
* plant_type_id
* name
* last watered
* next watering
* watering interval

---

## Tech Stack

* Python
* Typer (CLI)
* SQLite
* (optional) Rich for output
