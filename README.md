# Plantera

![CI](https://github.com/tmannell/plantera/actions/workflows/ci.yml/badge.svg)

Too busy writing code to remember to water your plants? Try Plantera, a simple CLI tool that lets you track and schedule watering of your little work buddies.

![demo](https://raw.githubusercontent.com/tmannell/plantera/main/assets/demo.gif)

## Installation

Requires Python 3.11+.

```bash
# with pipx (recommended)
pipx install plantera

# with pip
pip install plantera

# with uv
uv tool install plantera
```

## Quick Start

```bash
# Add a plant species to the library
plantera add-species Crassula "Jade Plant" "Soak when soil is completely dry"

# Add a plant
plantera add Bob Crassula 2026-04-01 7

# See what needs watering today
plantera show --due

# Mark a plant as watered
plantera watered Bob
```

---

## Commands

### `add`
Add a plant to your collection.
```
plantera add <nickname> <genus> [last-watered] [interval]
```
- `nickname` — your name for the plant (e.g. Bob)
- `genus` — must exist in the species library
- `last-watered` — date in YYYY-MM-DD format (default: today)
- `interval` — watering interval in days (default: 7)

---

### `add-species`
Add a plant species to the library.
```
plantera add-species <genus> <common-name> [care-info]
```

---

### `show`
Show your plants or the species library.
```
plantera show [--species] [--due]
```
- `--species` — show the species library instead of your plants
- `--due` — show only plants due for watering today
- Options are mutually exclusive.

---

### `watered`
Mark a plant as watered. Recalculates the next watering date automatically.
```
plantera watered <nickname>
```

---

### `update`
Update a plant's details.
```
plantera update <nickname> [--nickname] [--genus] [--last-watered] [--next-watering] [--interval]
```

---

### `update-species`
Update a species in the library.
```
plantera update-species <genus> [--genus] [--common-name] [--care-info]
```

---

### `delete`
Delete a plant from your collection.
```
plantera delete <nickname>
```

---

### `delete-species`
Delete a species from the library.
```
plantera delete-species <genus>
```

---

### `remind`
Send a desktop notification for any plants due or overdue for watering. Designed to be run on a schedule.

```
plantera remind
```

Schedule `plantera remind` to run daily using cron (Linux), launchd (macOS), or Task Scheduler (Windows).

---

## Data

Plantera stores all data locally in a SQLite database at `~/.local/share/plantera/plantera.db`. No accounts, no cloud, no setup required.

---

## Dev Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/tmannell/plantera
cd plantera
uv sync --all-groups
uv run pytest
```

Tests are written with pytest and cover all CLI commands and service functions.
