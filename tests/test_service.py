import plantera.db as db

from datetime import date, timedelta
from plantera.service import add_plant_species
from plantera.service import add_plant
from plantera.service import show_plants
from plantera.service import watered
from plantera.service import update_plant
from plantera.service import update_species
from plantera.service import delete_species
from plantera.service import delete_plant
from plantera.service import _validate_inputs


def test_db_init(test_db) -> None:
    """
    Test that the database is initialized with the correct tables.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        # Query sqlite_master for all user-created tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        assert len(tables) >= 2

        # Extract table names from rows for readable assertions
        table_names = [t[0] for t in tables]
        assert 'plant_species' in table_names
        assert 'my_plants' in table_names


def test_add_species(test_db, create_species) -> None:
    """
    Test adding a plant species to the database.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Add a species and verify the return value
    result = create_species(1)
    assert result is True

    # Query the database to confirm the species was saved
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM plant_species where genus = 'Crassula'")
        species = cursor.fetchone()

    # Verify all field values are correct
    assert species is not None
    assert species['genus'] == 'Crassula'
    assert species['common_name'] == 'Jade Plant'
    assert species['care_info'] == 'Soak when soil is completely dry for a day or two'

    # Verify correct error message shows for duplicate genus
    result = create_species(1)
    assert result == "Error: Species 'Crassula' already exists. Run 'plantera show --species' to see available species."


def test_add_plant(test_db, create_species) -> None:
    """
    Test adding a plant to the database.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up required species first
    species = create_species()
    assert species is True

    # Add a plant and verify the return value
    result = add_plant('Joe', 'Crassula', '2026-04-08', 14)
    assert result is True

    # Query the database to confirm the plant was saved
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM my_plants where nickname = 'Joe'")
        plant = cursor.fetchone()

    # Verify all field values including calculated next_watering
    assert plant is not None
    assert plant['nickname'] == 'Joe'
    assert plant['plant_species_id'] == 1
    assert plant['next_watering'] == '2026-04-22'
    assert plant['last_watered'] == '2026-04-08'
    assert plant['interval'] == 14

    # Verify correct error message shows for duplicate nickname
    result = add_plant('Joe', 'Crassula', '2026-04-08', 14)
    assert result == "Error: Plant 'Joe' already exists. Run 'plantera show' to see your plants."


def test_show_plants(test_db, create_species) -> None:
    """
    Test showing plants filtered by all, species only, and due for watering.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up species and plants with varying last watered dates
    species = create_species()
    assert species is True

    add_plant('Joe', 'Crassula', str(date.today()), 14)   # not due
    add_plant('Jane', 'Crassula', str(date.today() - timedelta(days=15)), 14)       # overdue
    add_plant('Jim', 'Crassula', str(date.today() - timedelta(days=30)), 14)        # overdue

    # Show all plants
    plants_list = show_plants(None, False, False)
    assert len(plants_list) == 3

    # Show plant with nickname 'Jane'
    plants_list = show_plants('Jane', False, False)
    assert len(plants_list) == 1
    assert (
        plants_list[0]['nickname'] == 'Jane' and
        plants_list[0]['plant_species_id'] == 1 and
        plants_list[0]['next_watering'] == str(date.today() - timedelta(days=15) + timedelta(days=14)) and
        plants_list[0]['last_watered'] == str(date.today() - timedelta(days=15)) and
        plants_list[0]['interval'] == 14
    )

    # Show only species
    plant_list = show_plants(None, True, False)
    assert len(plant_list) == 1

    # Show only plants due for watering — Joe is not due, Jane and Jim are
    plant_list = show_plants(None, False, True)
    assert len(plant_list) == 2


def test_watered(test_db, create_species) -> None:
    """
    Test marking a plant as watered and verifying updated dates.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up species and plant
    species = create_species()
    assert species is True

    result = add_plant('Joe', 'Crassula', '2026-04-01', 14)
    assert result is True

    # Mark as watered and verify the returned next watering date
    success, result = watered('Joe')
    assert success is True

    next_watering = date.today() + timedelta(days=14)
    assert result == next_watering

    # Verify the database was updated correctly
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM my_plants where nickname = 'Joe'")
        plant = cursor.fetchone()

    assert plant['last_watered'] == str(date.today())
    assert plant['next_watering'] == str(date.today() + timedelta(days=14))

    # Test error case — non-existent plant
    success, result = watered('Jimbo')
    assert success is False
    assert result == "Error: Plant 'Jimbo' not found. Run 'plantera show' to see your plants."


def test_update_plant(test_db, create_species) -> None:
    """
    Test updating a plant's fields and handling invalid inputs.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up two species so we can test genus change
    species = create_species(1)
    assert species is True

    species = create_species(2)
    assert species is True

    result = add_plant('Joe', 'Crassula', '2026-04-01', 14)
    assert result is True

    # Update multiple fields at once
    result = update_plant('Joe', 'James', 'Rosa', None, '2026-04-30', 30)
    assert result is True

    # Verify all updated fields in the database
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM my_plants where nickname = 'James'")
        plant = cursor.fetchone()

    assert plant['nickname'] == 'James'
    assert plant['last_watered'] == '2026-04-01'
    assert plant['plant_species_id'] == 2
    assert plant['next_watering'] == '2026-04-30'
    assert plant['interval'] == 30

    # Test error case — non-existent species
    result = update_plant('James', None, 'pastry', None, None, None)
    assert str(result) == "Error: Species 'pastry' not found. Run 'plantera show --species' to see available species."


def test_update_species(test_db, create_species) -> None:
    """
    Test updating a plant species' fields.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up species to update
    species = create_species()
    assert species is True

    # Update all fields
    result = update_species(
        'Crassula',
        'Rosa',
        'Rose',
        "Water deeply at the base 2-3 times per week in warm weather, once a week in cooler weather.")
    assert result is True

    # Verify updated values in the database
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM plant_species where genus = 'Rosa'")
        species = cursor.fetchone()

    assert species['genus'] == 'Rosa'
    assert species['common_name'] == 'Rose'
    assert species['care_info'] == "Water deeply at the base 2-3 times per week in warm weather, once a week in cooler weather."


def test_delete_plant(test_db, create_species) -> None:
    """
    Test deleting a plant and handling non-existent plant errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up species and plant
    species = create_species()
    assert species is True

    result = add_plant('Joe', 'Crassula', '2026-04-01', 14)
    assert result is True

    # Test error case — non-existent plant
    result = delete_plant('Jim')
    assert result == "Error: Plant 'Jim' not found. Run 'plantera show' to see your plants."

    # Delete the plant and verify it's removed from the database
    result = delete_plant('Joe')
    assert result is True

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM my_plants where nickname = 'Joe'")
        plant = cursor.fetchone()

    assert plant is None


def test_delete_species(test_db, create_species) -> None:
    """
    Test deleting a plant species and handling non-existent species errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up species to delete
    species = create_species()
    assert species is True

    # Test error case — non-existent species
    result = delete_species('Rosa')
    assert result == "Error: Species 'Rosa' not found. Run 'plantera show --species' to see available species."

    # Test error case — species has plants associated with it
    add_plant('Joe', 'Crassula', '2026-04-01', 7)
    result = delete_species('Crassula')
    assert result == "Error: Species 'Crassula' has plants associated with it. Delete the plants first."

    # Delete the plant first, then delete the species
    delete_plant('Joe')
    result = delete_species('Crassula')
    assert result is True

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM plant_species where genus = 'Crassula'")
        species = cursor.fetchone()

    assert species is None


def test_validate_inputs() -> None:
    """
    Test _validate_inputs for all valid and invalid input combinations.
    """
    # Valid inputs — all fields provided correctly
    result = _validate_inputs(nickname='joe', genus='Crassula', common_name="Jade", last_watered='2026-04-01', next_watering='2026-04-15', interval=14)
    assert result is True

    # Invalid string inputs
    result = _validate_inputs(nickname=' ', genus='Crassula', common_name="Jade", last_watered='2026-04-01', next_watering='2026-04-15', interval=14)
    assert result == "Error: Nickname cannot be empty."
    result = _validate_inputs(nickname='joe', genus=' ', common_name="Jade", last_watered='2026-04-01', next_watering='2026-04-15', interval=14)
    assert result == "Error: Genus cannot be empty."
    result = _validate_inputs(nickname='joe', genus='Crassula', common_name="    ", last_watered='2026-04-01', next_watering='2026-04-15', interval=14)
    assert result == "Error: Common Name cannot be empty."

    # Invalid date formats
    result = _validate_inputs(nickname='joe', genus='Crassula', common_name="Jade", last_watered='2026-05=10231', next_watering='2026-04-15', interval=14)
    assert result == "Error: Invalid date format for Last Watered. Use YYYY-MM-DD."
    result = _validate_inputs(nickname='joe', genus='Crassula', common_name="Jade", last_watered='2026-04-01', next_watering='2026-04-15gs', interval=14)
    assert result == "Error: Invalid date format for Next Watering. Use YYYY-MM-DD."

    # Invalid interval
    result = _validate_inputs(nickname='joe', genus='Crassula', common_name="Jade", last_watered='2026-04-01', next_watering='2026-04-15', interval=-2)
    assert result == "Error: Interval must be a positive number."
