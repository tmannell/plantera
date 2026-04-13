from typer.testing import CliRunner
from datetime import date, timedelta
from plantera.main import app
from plantera.service import add_plant

runner = CliRunner()


def test_cli_add_plant(test_db, create_species) -> None:
    """
    Test the add CLI command for success, missing species, and duplicate plant errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up required species
    result = create_species(1)
    assert result is True

    # Add a plant successfully
    result = runner.invoke(app, ['add', 'Joe', 'Crassula', '2026-04-01', '14'])
    assert result.exit_code == 0
    assert result.output == "Plant 'Joe' added successfully!\n"

    # Test error case — species does not exist
    result = runner.invoke(app, ['add', 'Jim', 'Rosa', '2026-04-01', '14'])
    assert result.exit_code == 0
    assert result.output == "Error: Species 'Rosa' not found. Run 'plantera show --species' to see available species.\n"

    # Test error case — duplicate nickname
    result = runner.invoke(app, ['add', 'Joe', 'Crassula', '2026-04-01', '14'])
    assert result.exit_code == 0
    assert result.output == "Error: Plant 'Joe' already exists. Run 'plantera show' to see your plants.\n"


def test_cli_add_species(test_db) -> None:
    """
    Test the add-species CLI command for success and duplicate species errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    """
    # Add a species successfully
    result = runner.invoke(app, ['add-species', 'Rosa', 'Rose', 'Soak when soil is completely dry for a day or two'])
    assert result.exit_code == 0
    assert result.output == "Species 'Rosa - Rose' added successfully!\n"

    # Test error case — duplicate genus
    result = runner.invoke(app, ['add-species', 'Rosa', 'Rose', 'Soak when soil is completely dry for a day or two'])
    assert result.exit_code == 0
    assert result.output == "Error: Species 'Rosa' already exists. Run 'plantera show --species' to see available species.\n"


def test_cli_show_plants(test_db, create_species) -> None:
    """
    Test the show CLI command for empty db, all plants, species, and due filtering.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Test empty database state
    result = runner.invoke(app, ['show'])
    assert result.exit_code == 0
    assert result.output == "No plants found.\n"

    result = create_species()
    assert result is True

    # Add a plant that is not yet due — next_watering will be 14 days from today
    future_watering_date = str(date.today() + timedelta(days=14))
    result = add_plant('Jim', 'Crassula', future_watering_date, 14)
    assert result is True

    # Verify all-watered message when no plants are overdue
    result = runner.invoke(app, ['show', '--due'])
    assert result.exit_code == 0
    assert result.output == "All plants are watered and up to date.\n"

    # Add an overdue plant — last watered 14 days ago
    overdue_watering_date = str(date.today() - timedelta(days=14))
    result = add_plant('Joe', 'Crassula', overdue_watering_date, 14)
    assert result is True

    # Show all plants
    result = runner.invoke(app, ['show'])
    assert result.exit_code == 0
    assert 'Joe' in result.output
    assert 'Crassula' in result.output

    # Show species only
    result = runner.invoke(app, ['show', '--species'])
    assert result.exit_code == 0
    assert 'Crassula' in result.output
    assert 'Jade' in result.output

    # Show overdue plants only — only Joe should appear
    result = runner.invoke(app, ['show', '--due'])
    assert result.exit_code == 0
    assert 'Joe' in result.output


def test_cli_watered(test_db, create_species) -> None:
    """
    Test the watered CLI command for success and non-existent plant errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up species and plant
    result = create_species()
    assert result is True
    result = add_plant('Joe', 'Crassula', '2026-03-01', 14)
    assert result is True

    # Mark as watered and verify the output includes the next watering date
    result = runner.invoke(app, ['watered', 'Joe'])
    assert result.exit_code == 0
    next_watering = date.today() + timedelta(days=14)
    assert result.output == f"'Joe' marked as watered, the next watering date is {next_watering}.\n"

    # Test error case — non-existent plant
    result = runner.invoke(app, ['watered', 'Jim'])
    assert result.exit_code == 0
    assert result.output == "Error: Plant 'Jim' not found. Run 'plantera show' to see your plants.\n"


def test_cli_update_plant(test_db, create_species) -> None:
    """
    Test the update CLI command for success, invalid species, and non-existent plant errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up two species so genus change can be tested
    result = create_species(1)
    assert result is True
    result = create_species(2)
    assert result is True

    result = add_plant('Joe', 'Crassula', '2026-03-01', 14)
    assert result is True

    # Update multiple fields successfully
    result = runner.invoke(app, ['update', 'Joe', '--nickname', 'James', '--genus', 'Rosa', '--last-watered', '2026-04-01', '--interval', '30'])
    assert result.exit_code == 0
    assert result.output == "Plant 'Joe' updated successfully!\n"

    # Test error case — non-existent species
    result = runner.invoke(app, ['update', 'James', '--genus', 'Maize', '--last-watered', '2026-04-01', '--interval', '30'])
    assert result.exit_code == 0
    assert result.output == "Error: Species 'Maize' not found. Run 'plantera show --species' to see available species.\n"

    # Test error case — non-existent plant
    result = runner.invoke(app, ['update', 'Joe', '--genus', 'Rosa', '--last-watered', '2026-04-01', '--interval', '30'])
    assert result.exit_code == 0
    assert result.output == "Error: Plant 'Joe' not found. Run 'plantera show' to see your plants.\n"


def test_cli_update_species(test_db, create_species) -> None:
    """
    Test the update-species CLI command for success and non-existent species errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up species to update
    result = create_species()
    assert result is True

    # Update the species successfully
    result = runner.invoke(app, ['update-species', 'Crassula', '--genus', 'Rosa', '--common-name', 'Rose', '--care-info', 'Bottom soak when dry'])
    assert result.exit_code == 0
    assert result.output == "Species 'Crassula' updated successfully!\n"

    # Test error case — non-existent species
    result = runner.invoke(app, ['update-species', 'Maize', '--genus', 'Rosa', '--common-name', 'Rose', '--care-info', 'Bottom soak when dry'])
    assert result.exit_code == 0
    assert result.output == "Error: Species 'Maize' not found. Run 'plantera show --species' to see available species.\n"


def test_cli_delete_plant(test_db, create_species) -> None:
    """
    Test the delete CLI command for cancel confirmation and successful deletion.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up species and plant
    result = create_species()
    assert result is True
    result = add_plant('Joe', 'Crassula', '2026-03-01', 14)
    assert result is True

    # Test cancelling the deletion prompt
    result = runner.invoke(app, ['delete', 'Joe'], input='n\n')
    assert "Deletion cancelled." in result.output

    # Confirm deletion
    result = runner.invoke(app, ['delete', 'Joe'], input='y\n')
    assert result.exit_code == 0
    assert "Plant 'Joe' deleted successfully!\n" in result.output


def test_cli_delete_species(test_db, create_species) -> None:
    """
    Test the delete-species CLI command for cancel confirmation and successful deletion.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    create_species : fixture
        Factory fixture to insert a test species.
    """
    # Set up species to delete
    result = create_species()
    assert result is True

    # Test cancelling the deletion prompt
    result = runner.invoke(app, ['delete-species', 'Crassula'], input='n\n')
    assert "Deletion cancelled." in result.output

    # Confirm deletion
    result = runner.invoke(app, ['delete-species', 'Crassula'], input='y\n')
    assert result.exit_code == 0
    assert "Species 'Crassula' deleted successfully!\n" in result.output
