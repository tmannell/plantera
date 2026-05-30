import base64
import json
import mimetypes
import sqlite3
import os
from datetime import datetime, timedelta, date
from typing import Optional, Union, Iterator

import plantera.db as db

ALLOWED_LOOKUPS = {
    'my_plants': 'nickname',
    'plant_species': 'genus'
}

def add_plant(nickname: str, genus: str, last_watered: str, interval: int, environment: str) -> Union[
    bool, Exception, str]:
    """
    Adds a plant to the database.

    Parameters
    ----------
    nickname : str
        The user's name for the plant (e.g. "Bob")
    genus : str
        The genus of the plant species (must exist in plant_species table)
    last_watered : str
        Date the plant was last watered in YYYY-MM-DD format
    interval : int
        Watering interval in days
    environment : str
        Optional description of the plant's environment (e.g. "North facing window")

    Returns
    -------
    bool or Exception or str
        True on success, error message string on failure
    """

    validated = _validate_inputs(nickname=nickname, genus=genus, last_watered=last_watered, interval=interval)
    if validated is not True:
        return validated

    species = _get_plant('plant_species', genus)

    if species is None:
        return f"Error: Species '{genus}' not found. Run 'plantera show --species' to see available species."

    else:

        try:
            plant_species_id = species["id"]

            last_watered = datetime.strptime(last_watered, "%Y-%m-%d")
            next_watering = last_watered + timedelta(days=interval)

            with db.get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO my_plants (nickname, plant_species_id, last_watered, next_watering, interval, environment) VALUES (?, ?, ?, ?, ?, ?)",
                    (nickname, plant_species_id, last_watered.strftime('%Y-%m-%d'), next_watering.strftime('%Y-%m-%d'), interval, environment)
                )

                _log_watering(conn, cursor.lastrowid, last_watered.strftime('%Y-%m-%d'))

                return True
        except sqlite3.IntegrityError:
            return f"Error: Plant '{nickname}' already exists. Run 'plantera show' to see your plants."
        except Exception as e:
            return e

def add_plant_species(genus: str, common_name: str, care_info: str) -> Union[bool, Exception]:
    """
    Adds a plant species to the database.

    Parameters
    ----------
    genus : str
        The scientific genus name (e.g. "Crassula")
    common_name : str
        The common name of the plant (e.g. "Jade Plant")
    care_info : str
        Care instructions for the species

    Returns
    -------
    bool or Exception
        True on success, Exception on failure
    """

    validated = _validate_inputs(genus=genus, common_name=common_name)
    if validated is not True:
        return validated

    try:
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO plant_species (genus, common_name, care_info) VALUES (?, ?, ?)", (genus, common_name, care_info)
            )

            return True
    except sqlite3.IntegrityError:
        return f"Error: Species '{genus}' already exists. Run 'plantera show --species' to see available species."
    except Exception as e:
        return e

def show_plants(name: str, species: bool, due: bool) -> Union[list, Exception]:
    """
    Show plants in database. Options allow user to filter by name, species, or plants due for watering.

    Parameters
    ----------
    name : str
        If provided, show a single plant matching the nickname
    species : bool
        If True, show plant species from plant_species table instead of my_plants
    due : bool
        If True, show only plants with next_watering <= today

    Returns
    -------
    list or Exception
        List of rows on success, Exception on failure
    """

    try:
        with db.get_connection() as conn:

            if not name and species is False and due is False:
                # Show all plants from my_plants
                cursor = conn.execute(
                    "SELECT * \
                     FROM my_plants \
                     LEFT JOIN plant_species on my_plants.plant_species_id = plant_species.id \
                    ")
            elif name:
                # Show plant matching the provided nickname
                cursor = conn.execute("SELECT * FROM my_plants \
                                           LEFT JOIN plant_species on my_plants.plant_species_id = plant_species.id \
                                           WHERE nickname = ? COLLATE NOCASE", [name])

            elif species:
                # Show all plants from plant_species
                cursor = conn.execute("SELECT * FROM plant_species")
            else:
                # Show all plants due for watering
                cursor = conn.execute("SELECT * FROM my_plants \
                                      LEFT JOIN plant_species on my_plants.plant_species_id = plant_species.id \
                                      WHERE next_watering <= date('now', 'localtime')")

            return cursor.fetchall()

    except Exception as e:
        return e


def watered(nickname: str) -> tuple[bool, Union[str, date, Exception]]:
    """
    Mark a plant as watered and recalculate next watering date.

    Parameters
    ----------
    nickname : str
        The plant's nickname

    Returns
    -------
    tuple[bool, str or date or Exception]
        (True, next_watering date) on success, (False, error message or Exception) on failure.
    """

    my_plant = _get_plant('my_plants', nickname)

    if my_plant is None:
        return False, f"Error: Plant '{nickname}' not found. Run 'plantera show' to see your plants."

    else:
        try:
            with db.get_connection() as conn:
                # Update the next watering date, auto-calculate the next watering date based on the interval
                new_interval = _calculate_interval(my_plant['interval'], my_plant['last_watered'])
                next_watering = date.today() + timedelta(days=new_interval)
                conn.execute(
                    "UPDATE my_plants \
                         SET last_watered = date('now', 'localtime'), \
                         next_watering = ?, \
                         interval = ? \
                         WHERE nickname = ? COLLATE NOCASE", [str(next_watering), new_interval, nickname])

                _log_watering(conn, my_plant['id'], str(date.today()))

                return True, next_watering

        except Exception as e:
            return False, e


def snooze(nickname_to_update: str, days: int) -> Union[tuple, Exception, str]:
    """
    Delay a plant's next watering date by a given number of days.

    If the plant is overdue (next_watering <= today), the new date is calculated
    from today. If it's not yet due, the days are added to the existing next_watering date.

    Parameters
    ----------
    nickname_to_update : str
        Nickname of the plant to snooze
    days : int
        Number of days to delay the next watering

    Returns
    -------
    tuple[bool, date or str]
        (True, new next_watering date) on success, (False, error message) on failure
    """

    plant = _get_plant('my_plants', nickname_to_update)
    if plant is None:
        return False, f"Error: Plant '{nickname_to_update}' not found. Run 'plantera show' to see your plants."

    try:
        with db.get_connection() as conn:
            next_watering = date.fromisoformat(plant['next_watering'])
            if next_watering <= date.today():
                new_watering = date.today() + timedelta(days=days)
            elif next_watering > date.today():
                new_watering = next_watering + timedelta(days=days)

            conn.execute("UPDATE my_plants SET next_watering = ? WHERE id = ?", [str(new_watering), plant['id']])
            return True, new_watering

    except Exception as e:

        return False, e


def update_plant(nickname_to_update: str, nickname: str = None, genus: str = None, last_watered: str = None,
                 next_watering: str = None, interval: int = None, environment: str = None) -> Union[bool, Exception, str]:
    """
    Update a plant from the my_plants table.

    Parameters
    ----------
    nickname_to_update : str
        Nickname of the plant to update
    nickname : str, optional
        New nickname for the plant
    genus : str, optional
        New genus (must exist in plant_species table)
    last_watered : str, optional
        New last watered date in YYYY-MM-DD format
    next_watering : str, optional
        Override next watering date in YYYY-MM-DD format
    interval : int, optional
        New watering interval in days
    environment : str, optional
        Updated description of the plant's environment

    Returns
    -------
    bool or Exception or str
        True on success, error message string on failure
    """
    my_plant = _get_plant('my_plants', nickname_to_update)
    if my_plant is None:
        return f"Error: Plant '{nickname_to_update}' not found. Run 'plantera show' to see your plants."

    else:

        validated = _validate_inputs(nickname=nickname, genus=genus, last_watered=last_watered, next_watering=next_watering, interval=interval)
        if validated is not True:
            return validated

        fields = []
        values = []

        if nickname:
            fields.append('nickname = ?')
            values.append(nickname)

        if genus:
            species = _get_plant('plant_species', genus)
            if species is not None:
                fields.append('plant_species_id = ?')
                values.append(species['id'])
            else:
                return f"Error: Species '{genus}' not found. Run 'plantera show --species' to see available species."

        if last_watered:
            fields.append('last_watered = ?')
            values.append(last_watered)
            if not next_watering:
                fields.append('next_watering = ?')
                effective_interval = interval if interval else my_plant['interval']
                calculated_date = date.fromisoformat(last_watered) + timedelta(days=effective_interval)
                values.append(str(calculated_date))

        if next_watering:
            fields.append('next_watering = ?')
            values.append(next_watering)

        if interval:
            fields.append('interval = ?')
            values.append(interval)

        if environment:
            fields.append('environment = ?')
            values.append(environment)

        values.append(nickname_to_update)

        if len(fields) == 0:
            return "Error: No fields to update. Run 'plantera update --help' for usage."

        try:
            with db.get_connection() as conn:
                conn.execute(
                    f"UPDATE my_plants SET {', '.join(fields)} WHERE nickname = ? COLLATE NOCASE", values
                )

                if last_watered:
                    _log_watering(conn, my_plant['id'], last_watered, update=True)

                return True

        except Exception as e:
            return e

def update_species(genus_to_update: str, genus: str = None, common_name: str = None, care_info: str = None) -> Union[
    bool, Exception, str]:
    """
    Update a species from the plant_species table.

    Parameters
    ----------
    genus_to_update : str
        Genus of the species to update
    genus : str, optional
        New genus name
    common_name : str, optional
        New common name
    care_info : str, optional
        Updated care instructions

    Returns
    -------
    bool or Exception or str
        True on success, error message string on failure
    """

    species = _get_plant('plant_species', genus_to_update)
    if species is None:
        return f"Error: Species '{genus_to_update}' not found. Run 'plantera show --species' to see available species."

    else:

        validated = _validate_inputs(genus=genus, common_name=common_name)
        if validated is not True:
            return validated

        fields = []
        values = []

        if genus:
            fields.append('genus = ?')
            values.append(genus)

        if common_name:
            fields.append('common_name = ?')
            values.append(common_name)

        if care_info:
            fields.append('care_info = ?')
            values.append(care_info.strip())

        values.append(species['id'])

        if len(fields) == 0:
            return "Error: No fields to update. Run 'plantera update-species --help' for usage."

        try:
            with db.get_connection() as conn:
                conn.execute(
                    f"UPDATE plant_species SET {', '.join(fields)} where id = ?", values
                )

                return True

        except Exception as e:
            return e

def delete_plant(nickname: str) -> Union[bool, Exception, str]:
    """
    Delete a plant from the my_plants table.

    Parameters
    ----------
    nickname : str
        Nickname of the plant to delete

    Returns
    -------
    bool or Exception or str
        True on success, error message string on failure
    """
    if _get_plant('my_plants', nickname):

        try:
            with db.get_connection() as conn:
                conn.execute("DELETE FROM my_plants WHERE nickname = ? COLLATE NOCASE", [nickname])

                return True

        except Exception as e:
            return e

    else:
        return f"Error: Plant '{nickname}' not found. Run 'plantera show' to see your plants."


def delete_species(genus: str) -> Union[bool, Exception, str]:
    """
    Delete a plant species from the plant_species table.

    Parameters
    ----------
    genus : str
        Genus of the species to delete

    Returns
    -------
    bool or Exception or str
        True on success, error message string on failure
    """

    species = _get_plant('plant_species', genus)
    if species is None:
        return f"Error: Species '{genus}' not found. Run 'plantera show --species' to see available species."

    else:
        try:
            with db.get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM my_plants WHERE plant_species_id = ?", [species['id']])
                if cursor.fetchone()[0] > 0:
                    return f"Error: Species '{genus}' has plants associated with it. Delete the plants first."

                conn.execute("DELETE FROM plant_species WHERE id = ?", [species['id']])

                return True

        except Exception as e:
            return e

def config_setting(setting: str, value: Optional[str], delete_setting: bool) -> Union[bool, Exception]:
    """
    Upsert or delete a setting in the settings table.

    Parameters
    ----------
    setting : str
        The setting key to update or delete.
    value : str or None
        The value to set. Ignored when delete_setting is True.
    delete_setting : bool
        If True, delete the setting row instead of upserting.

    Returns
    -------
    bool or Exception
        True on success, Exception on failure.
    """

    # Delete or save the config setting.
    with db.get_connection() as conn:

        try:
            if delete_setting:
                conn.execute("DELETE FROM settings WHERE key = ?", [setting])
                return True

            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) \
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value", [setting, value])
            return True

        except Exception as e:
            return e

def get_settings() -> Union[list, Exception]:
    """
    Retrieve all rows from the settings table.

    Returns
    -------
    list or Exception
        List of settings rows on success, Exception on failure.
    """
    try:
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM settings")

            return cursor.fetchall()

    except Exception as e:
        return e

def update_care_info(genus: str) -> tuple[bool, str]:
    """
    Fetch updated care info for a species from the Claude API and persist it if changed.

    Parameters
    ----------
    genus : str
        The genus of the species to update (must exist in plant_species table)

    Returns
    -------
    tuple[bool, str]
        (True, result message) on success, (False, error message) on failure
    """

    with db.get_connection() as conn:
        cursor = conn.execute("SELECT value FROM settings WHERE key = 'claude_api_key'")
        row = cursor.fetchone()
        if row is None:
            return False, "Error: API key not found. Please set it using 'plantera config claude_api_key <your_api_key>'"

        api_key = row[0]

    species = _get_plant('plant_species', genus)

    if species is None:
        return False, f"Error: Species '{genus}' not found. Run 'plantera show --species' to see available species."

    prompt = [
        {
            "type": "text",
            "text": (
                f"Review the following care info for {species['common_name']} ({species['genus']}):\n\n"
                f"{species['care_info']}\n\n"
                "If the care info is accurate and complete, return exactly:\n"
                "{\"care_info\": \"<original text>\", \"changed\": false}\n\n"
                "If it needs updating, keep response concise, format for terminal\n"
                "return exactly:\n"
                "{\"care_info\": \"<updated text>\", \"changed\": true}\n\n"
                "Return only valid JSON, no markdown formatting, no preamble or explanation."
            )
        }
    ]

    response = json.loads(_ask_claude(prompt, api_key))

    if response['changed']:
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE plant_species SET care_info = ? WHERE id = ?",
                [response['care_info'], species['id']]
            )
        return True, f"Care info updated\n\n{response['care_info']}"
    else:
        return True, "Care info is already up to date."


def diagnose(nickname: str, condition: str, picture_path: str) -> tuple[bool, Union[str, any]]:
    """
    Diagnose a plant's condition using the Claude API, optionally with an image.

    Builds a prompt from the plant's stored data including watering history and environment,
    then streams the response back to the caller.

    Parameters
    ----------
    nickname : str
        The plant's nickname (must exist in my_plants)
    condition : str
        A text description of the observed condition (e.g. "Brown leaves")
    picture_path : str or None
        Path to an image file to include in the diagnosis, or None for text-only

    Returns
    -------
    tuple[bool, str or iterator]
        (True, text stream iterator) on success, (False, error message) on failure
    """

    with db.get_connection() as conn:
        cursor = conn.execute("SELECT value FROM settings WHERE key = 'claude_api_key'")
        row = cursor.fetchone()

        if row is None:
            return False, "Error: API key not found. Please set it using 'plantera config claude_api_key <your_api_key>'"

        api_key = row[0]

    plant = _get_plant('my_plants', nickname)
    if plant is None:
        return False, f"Error: Plant '{nickname}' not found. Run 'plantera show' to see your plants."

    data = dict()
    data['nickname'] = nickname
    data['genus'] = plant['genus']
    data['common_name'] = plant['common_name']
    data['last_watered'] = plant['last_watered']
    data['next_watering'] = plant['next_watering']
    data['interval'] = plant['interval']

    if plant['environment']:
        data['environment'] = plant['environment']

    data['condition'] = condition

    with db.get_connection() as conn:
        cursor = conn.execute("SELECT watered_date FROM watered_log WHERE plant_id = ? ORDER BY id DESC LIMIT 10", [plant['id']])
        watering_dates = cursor.fetchall()

    plant_info = "Plant Information:\n"
    plant_info += "\n".join(f"{k}: {v}" for k, v in data.items())
    plant_info += "\nThe last 10 watering dates were:\n"
    plant_info += ", ".join(f"{row['watered_date']}" for row in watering_dates) + "\n"

    prompt = []
    if picture_path:
        if not os.path.exists(picture_path):
            return False, "Error: Picture file not found."

        if mimetypes.guess_type(picture_path) not in ['image/jpeg', 'image/png', 'image/gif', 'image/webp']:
            return False, "Error: Invalid picture file type. Must be jpeg, png, gif, or webp."


        with open(picture_path, "rb") as file:
            image_data = base64.standard_b64encode(file.read()).decode("utf-8")
            prompt.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mimetypes.guess_type(picture_path)[0],
                "data": image_data
            }
        })

    prompt.append({
        "type": "text",
        "text": (
            f"Please diagnose my plant with the following information:\n{plant_info}\n\n"
            "Provide a complete diagnosis and all recommendations in one response. "
            "Comment specifically on watered dates and environmental factors if they exist in data. "
            "Do not ask follow-up questions. "
            "Format your response for terminal output using plain text only, "
            "no markdown headers, no emoji, use simple dashes for bullet points."
        )
    })

    return True, _ask_claude_stream(prompt, api_key)

def _get_plant(table: str, value: str) -> Optional[dict]:
    """
    Internal helper to retrieve a single row from my_plants or plant_species.

    Parameters
    ----------
    table : str
        Table to query — must be 'my_plants' or 'plant_species'
    value : str
        Value to match against the table's unique lookup column

    Returns
    -------
    sqlite3.Row or None
        The matching row, or None if not found
    """
    if table not in ALLOWED_LOOKUPS:
        raise ValueError(
            f"Invalid table name: {table}. Allowed tables are 'my_plants' and 'plant_species'."
        )

    try:
        with db.get_connection() as conn:
            column = ALLOWED_LOOKUPS[table]
            if table == 'my_plants':
                cursor = conn.execute(
                    f"SELECT my_plants.*, plant_species.genus, plant_species.common_name, plant_species.care_info \
                    FROM my_plants \
                    LEFT JOIN plant_species ON my_plants.plant_species_id = plant_species.id \
                    WHERE my_plants.{column} = ? COLLATE NOCASE", [value]
                )
            else:
                cursor = conn.execute(f"SELECT * FROM {table} WHERE {column} = ? COLLATE NOCASE", [value])
            return cursor.fetchone()

    except Exception:
        return None

def _validate_inputs(nickname: str = None, genus: str = None, common_name: str = None, last_watered: str = None, next_watering: str = None,
                     interval: int = None) -> str | bool:
    """
    Validate plant inputs. All parameters are optional — only provided values are checked.

    Parameters
    ----------
    nickname : str, optional
        Must be non-empty if provided.
    genus : str, optional
        Must be non-empty if provided.
    common_name : str, optional
        Must be non-empty if provided.
    last_watered : str, optional
        Must be a valid date in YYYY-MM-DD format if provided.
    next_watering : str, optional
        Must be a valid date in YYYY-MM-DD format if provided.
    interval : int, optional
        Must be a positive integer if provided.

    Returns
    -------
    str or bool
        True if all inputs are valid, error message string on failure.
    """

    # Validate string inputs
    str_values = [nickname, genus, common_name]
    for value, field_name in zip(str_values, ['Nickname', 'Genus', 'Common Name']):
        if value is not None and value.strip() == '':
            return f"Error: {field_name} cannot be empty."

    # Validate date inputs
    date_values = [last_watered, next_watering]
    for value, field_name in zip(date_values, ['Last Watered', 'Next Watering']):
        if value is not None:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return f"Error: Invalid date format for {field_name}. Use YYYY-MM-DD."

    # Validate interval input
    if interval is not None and interval < 1:
        return "Error: Interval must be a positive number."

    return True


def _calculate_interval(current_interval: int, last_watered: str) -> Union[int, Exception]:
    """
    Calculate a new watering interval using EMA against the actual gap since last watering.

    Reads the ema_alpha from the settings table (key: 'auto_interval'). If the setting is
    absent, EMA is disabled and the current interval is returned unchanged. Same-day
    waterings (gap < 1 day) are also skipped to prevent accidental shrinkage.

    Parameters
    ----------
    current_interval : int
        The plant's existing watering interval in days.
    last_watered : str
        The date the plant was last watered in YYYY-MM-DD format.

    Returns
    -------
    int or Exception
        The updated interval in days, or Exception on failure.
    """

    try:
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = 'auto_interval'")

            row = cursor.fetchone()
            if row is None:
                return current_interval

        ema_value = float(row[0])

    except Exception as e:
        return e

    days_since_watered = (date.today() - date.fromisoformat(last_watered)).days

    # Skip same-day waterings — marking a plant watered twice in one day shouldn't shrink the interval.
    if days_since_watered < 1:
        return current_interval

    return round(ema_value * days_since_watered + (1 - ema_value) * current_interval)


def _log_watering(conn, plant_id: int, watered_date: str, update: bool = False) -> None:
    """
    Insert or update a watered_log entry for a plant.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection (called within an existing transaction)
    plant_id : int
        ID of the plant in my_plants
    watered_date : str
        Date to log in YYYY-MM-DD format
    update : bool
        If True, update the most recent log entry instead of inserting a new one

    Returns
    -------
    None
    """
    if update:
        count = conn.execute(
            "SELECT COUNT(*) FROM watered_log WHERE plant_id = ?", [plant_id]
        )
        if count.fetchone()[0] == 0:
            raise ValueError("Error: Cannot update watering log: this plant has not been watered yet.")

        conn.execute(
            "UPDATE watered_log SET watered_date = ? \
             WHERE id = (SELECT id FROM watered_log WHERE plant_id = ? ORDER BY id DESC LIMIT 1)",
            [watered_date, plant_id]
        )
    else:
        conn.execute(
            "INSERT INTO watered_log (plant_id, watered_date) VALUES (?, ?)",
            [plant_id, watered_date]
        )


def _ask_claude(prompt: list, api_key: str) -> str:
    """
    Send a prompt to Claude and return the full response text.

    Parameters
    ----------
    prompt : list
        List of content blocks to send as the user message.
    api_key : str
        Anthropic API key.

    Returns
    -------
    str
        The full response text from Claude.
    """

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def _ask_claude_stream(prompt: list, api_key: str) -> Iterator[str]:
    """
    Send a prompt to Claude and yield the response text as a stream.

    Parameters
    ----------
    prompt : list
        List of content blocks to send as the user message.
    api_key : str
        Anthropic API key.

    Yields
    ------
    str
        Text chunks from Claude's streaming response.
    """

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text