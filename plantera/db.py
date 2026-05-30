import sqlite3
from pathlib import Path

DB_DIR = Path.home() / ".local" / "share" / "plantera"
DB_PATH = DB_DIR / "plantera.db"

# Each entry is a SQL statement applied once in order and tracked in schema_version.
_migrations = [
    "ALTER TABLE my_plants ADD COLUMN environment TEXT",
]

def _run_migrations(conn):
    """
    Apply any pending schema migrations in order.

    Reads the current schema version from schema_version, then runs each
    migration in _migrations that hasn't been applied yet. Each applied
    migration is recorded so it only runs once.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection (called within db_init's transaction)
    """
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
    current = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] or 0
    for i, sql in enumerate(_migrations[current:], start=current + 1):
        conn.execute(sql)
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", [i])

def db_init():
    """
    Initialize the database by creating all required tables and running pending migrations.

    Creates plant_species, my_plants, watered_log, and settings tables if they
    don't exist, then delegates to _run_migrations to apply any schema changes.

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

            conn.execute("CREATE TABLE IF NOT EXISTS watered_log ( \
                         id INTEGER PRIMARY KEY AUTOINCREMENT, \
                         plant_id INTEGER NOT NULL, \
                         watered_date TEXT NOT NULL)")

            conn.execute("CREATE TABLE IF NOT EXISTS settings ( \
                         id INTEGER PRIMARY KEY AUTOINCREMENT, \
                         key TEXT UNIQUE COLLATE NOCASE, \
                         value TEXT)")

            _run_migrations(conn)

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