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
plantera add Bob Crassula 2026-04-01 7 "North-facing windowsill"

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
plantera add <nickname> <genus> [last-watered] [interval] [environment]
```
- `nickname` — your name for the plant (e.g. Bob)
- `genus` — must exist in the species library
- `last-watered` — date in YYYY-MM-DD format (default: today)
- `interval` — watering interval in days (default: 7)
- `environment` — optional description of the plant's location (e.g. "South-facing windowsill")

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
plantera show [--name] [--species] [--due]
```
- `--name` — show a single plant by nickname, including environment and care info
- `--species` — show the species library instead of your plants
- `--due` — show only plants due for watering today
- `--name` cannot be combined with `--species` or `--due`

---

### `watered`
Mark a plant as watered. Recalculates the next watering date automatically.
```
plantera watered <nickname>
```

---

### `snooze`
Delay a plant's next watering date by a number of days.
```
plantera snooze <nickname> [days]
```
- `days` — number of days to delay (default: 1, max: 365)

---

### `update`
Update a plant's details.
```
plantera update <nickname> [--nickname] [--genus] [--last-watered] [--next-watering] [--interval] [--environment]
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

### `config`
View or update Plantera settings.
```
plantera config [setting] [--value] [--delete]
```
- Run without arguments to display all current settings
- `auto_interval` — once set, enables automatic watering interval adjustment. Each time you mark a plant as watered, Plantera blends the real gap since last watering into the current interval using an exponential moving average: `new_interval = alpha × actual_days + (1 − alpha) × current_interval`. A higher alpha (e.g. 0.7) reacts faster to recent waterings; a lower alpha (e.g. 0.2) keeps it more stable. Default: 0.4.
- `claude_api_key` — once set, unlocks the `diagnose` and `update-care-info` commands.

```bash
plantera config claude_api_key --value sk-ant-...
plantera config auto_interval --value 0.3
plantera config auto_interval --delete
```

---

### `update-care-info`
Use Claude AI to review and update the care info for a species in your library.
```
plantera update-care-info <genus>
```
Requires `claude_api_key` to be set via `plantera config`.

---

### `diagnose`
Diagnose a plant's condition using Claude AI. Accepts a text description, an image, or both. Plantera automatically includes the plant's species, care info, environment, and watering history as context so Claude can give a more informed response.
```
plantera diagnose <nickname> [--condition] [--picture]
```
- `--condition` — text description of what you're observing (e.g. "yellowing leaves")
- `--picture` — path to an image of the plant

```bash
plantera diagnose Bob --condition "brown leaf tips, soil feels dry"
plantera diagnose Bob --picture /path/to/photo.jpg
plantera diagnose Bob --condition "looks droopy" --picture /path/to/photo.jpg
```
Requires `claude_api_key` to be set via `plantera config`.

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
