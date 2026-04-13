import pytest
import plantera.db as db
from plantera.service import add_plant_species


@pytest.fixture
def test_db(monkeypatch, tmp_path):
    """Set up a temporary database for each test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_file))
    db.db_init()


@pytest.fixture
def create_species():
    """
    Factory fixture to insert a test species into the database.

    Returns
    -------
    callable
        A function that accepts plant_id (1 or 2) and inserts the corresponding species.
    """
    def _inner(plant_id: int = 1) -> bool:
        """
        Parameters
        ----------
        plant_id : int, optional
            1 for Crassula (default), 2 for Rosa.

        Returns
        -------
        bool
            True on success, False if plant_id is invalid.
        """
        if plant_id == 1:
            return add_plant_species("Crassula", "Jade Plant", "Soak when soil is completely dry for a day or two")
        elif plant_id == 2:
            return add_plant_species("Rosa", "Rose", "Water deeply at the base 2-3 times per week in warm weather, once a week in cooler weather.")
        else:
            return False
    return _inner
