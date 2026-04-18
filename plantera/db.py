import sqlite3
from pathlib import Path

DB_DIR = Path.home() / ".local" / "share" / "plantera"
DB_PATH = DB_DIR / "plantera.db"

def db_init():
    """
    Initialize the database by creating the plant_species and my_plants tables if they don't exist.

    Returns
    -------
    Exception or None
        None on success, Exception on failure
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS plant_species ( \
                         id INTEGER PRIMARY KEY AUTOINCREMENT, \
                         genus TEXT UNIQUE COLLATE NOCASE, \
                         common_name TEXT, \
                         care_info TEXT)")

            conn.execute("CREATE TABLE IF NOT EXISTS my_plants ( \
                         id INTEGER PRIMARY KEY AUTOINCREMENT, \
                         plant_species_id INTEGER, \
                         nickname TEXT UNIQUE COLLATE NOCASE, \
                         last_watered TEXT, \
                         next_watering TEXT, \
                         interval INTEGER)")

        except Exception as e:
            return e

def get_connection():
    """
    Create and return a new SQLite database connection.

    Returns
    -------
    sqlite3.Connection
        A connection to the database with row_factory set to sqlite3.Row
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
