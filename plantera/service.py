import sqlite3
from datetime import datetime, timedelta, date
from typing import Optional, Union

import plantera.db as db

ALLOWED_LOOKUPS = {
        'my_plants': 'nickname',
        'plant_species': 'genus'
    }

def add_plant(nickname: str, genus: str, last_watered: str, interval: int) -> Union[
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

    Returns
    -------
    bool or Exception or str
        True on success, error message string on failure
    """

    # Validate key inputs
    validated = _validate_inputs(nickname=nickname, genus=genus, last_watered=last_watered, interval=interval)
    if validated is not True:
        return validated

    # Get the plant species ID from the plant_species table
    species = _get_plant('plant_species', genus)

    if species is None:
        # If species is None / nothing is returned, then the plant species doesn't exist
        return f"Error: Species '{genus}' not found. Run 'plantera show --species' to see available species."

    else:

        try:
            # Store plant_species_id in a variable
            plant_species_id = species["id"]

            # Convert last_watered date to datetime object
            last_watered = datetime.strptime(last_watered, "%Y-%m-%d")
            # Calculate the next watering date based on the last watered date and the interval
            next_watering = last_watered + timedelta(days=interval)
    
            # Open DB connection
            with db.get_connection() as conn:
                # Insert a new user plant into the plants table
                conn.execute(
                    "INSERT INTO my_plants (nickname, plant_species_id, last_watered, next_watering, interval) VALUES (?, ?, ?, ?, ?)",
                    (nickname, plant_species_id, last_watered.strftime('%Y-%m-%d'), next_watering.strftime('%Y-%m-%d'), interval)
                )

                # Return True if the plant was added successfully
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

    # Validate key inputs
    validated = _validate_inputs(genus=genus, common_name=common_name)
    if validated is not True:
        return validated

    try:
        # Open DB connection
        with db.get_connection() as conn:
            # Insert a new plant species into the plant types table
            conn.execute(
                "INSERT INTO plant_species (genus, common_name, care_info) VALUES (?, ?, ?)", (genus, common_name, care_info)
            )

            # Return True if the plant species was added successfully
            return True
    except sqlite3.IntegrityError:
        return f"Error: Species '{genus}' already exists. Run 'plantera show --species' to see available species."
    except Exception as e:
        return e

def show_plants(species: bool, due: bool) -> Union[list, Exception]:
    """
    Show plants in database. Options allow user to filter by species, their plants, or plants due for watering.

    Parameters
    ----------
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

            if species is False and due is False:
                # Show all plants from my_plants
                cursor = conn.execute(
                    "SELECT * \
                     FROM my_plants \
                     LEFT JOIN plant_species on my_plants.plant_species_id = plant_species.id \
                    ")

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
    
    # Check if the plant exists
    my_plant = _get_plant('my_plants', nickname)

    if my_plant is None:
        # If the plant doesn't exist, return an error message'
        return False, f"Error: Plant '{nickname}' not found. Run 'plantera show' to see your plants."

    else:
        try:
            with db.get_connection() as conn:
                # Update the next watering date, auto-calculate the next watering date based on the interval
                next_watering = date.today() + timedelta(days=my_plant['interval'])
                conn.execute(
                    "UPDATE my_plants \
                     SET last_watered = date('now', 'localtime'), \
                     next_watering = ? \
                     WHERE nickname = ?", [str(next_watering), nickname])

                return True, next_watering

        except Exception as e:
            return False, e

def update_plant(nickname_to_update: str, nickname: str = None, genus: str = None, last_watered: str = None,
                 next_watering: str = None, interval: int = None) -> Union[bool, Exception, str]:
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

    Returns
    -------
    bool or Exception or str
        True on success, error message string on failure
    """
    # Retrieve the plant to update
    my_plant = _get_plant('my_plants', nickname_to_update)
    if my_plant is None:
        # if the plant doesn't exist, return an error message'
        return f"Error: Plant '{nickname_to_update}' not found. Run 'plantera show' to see your plants."

    else:

        # Validate key inputs
        validated = _validate_inputs(nickname=nickname, genus=genus, last_watered=last_watered, next_watering=next_watering, interval=interval)
        if validated is not True:
            return validated

        fields = []
        values = []

        if nickname:
            fields.append('nickname = ?')
            values.append(nickname)

        if genus:
            # Get the plant species ID from the plant_species table
            species = _get_plant('plant_species', genus)
            if species is not None:
                fields.append('plant_species_id = ?')
                values.append(species['id'])
            else:
                # Return an error message if the plant species doesn't exist'
                return f"Error: Species '{genus}' not found. Run 'plantera show --species' to see available species."

        if last_watered:
            fields.append('last_watered = ?')
            values.append(last_watered)

        if next_watering:
            fields.append('next_watering = ?')
            values.append(next_watering)

        if interval:
            fields.append('interval = ?')
            values.append(interval)

        values.append(nickname_to_update)

        if len(fields) == 0:
            # No options, no fields return an error message
            return "Error: No fields to update. Run 'plantera update --help' for usage."

        try:
            with db.get_connection() as conn:
                conn.execute(
                    f"UPDATE my_plants SET {', '.join(fields)} where nickname = ?", values
                )

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
    
    # Retrieve the plant species to update
    species = _get_plant('plant_species', genus_to_update)
    if species is None:
        # if the plant species doesn't exist, return an error message'
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
            # No options, no fields to update return an error message
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
    # Check if the plant exists
    if _get_plant('my_plants', nickname):

        try:
            with db.get_connection() as conn:
                conn.execute("DELETE FROM my_plants WHERE nickname = ?", [nickname])

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
    
    # Check if the plant species exists
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
    # Validate table arguments
    if table not in ALLOWED_LOOKUPS:
        raise ValueError(
            f"Invalid table name: {table}. Allowed tables are 'my_plants' and 'plant_species'."
        )

    try:
        with db.get_connection() as conn:
            # Column the matching value in the ALLOWED_LOOKUPS dictionary
            column = ALLOWED_LOOKUPS[table]
            cursor = conn.execute(f"SELECT * FROM {table} WHERE {column} = ?", [value])
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

