from typer.testing import CliRunner
from datetime import date, timedelta
from tests.helpers import create_species
from plantera.main import app, __version__
from plantera.service import add_plant
from plantera.service import config_setting
from unittest.mock import patch

import humanize

runner = CliRunner()


def test_cli_version(test_db) -> None:
    """Test the --version option outputs the correct version."""
    result = runner.invoke(app, ['--version'])
    assert result.exit_code == 0
    assert result.output == f"Plantera v{__version__}\n"


def test_cli_add_plant(test_db) -> None:
    """
    Test the add CLI command for success, missing species, and duplicate plant errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    """
    # Set up required species
    result = create_species(1)
    assert result is True

    # Add a plant successfully
    result = runner.invoke(app, ['add', 'Joe', 'Crassula', '2026-04-01', '14'])
    assert result.exit_code == 0

    # Test error case — species does not exist
    result = runner.invoke(app, ['add', 'Jim', 'Rosa', '2026-04-01', '14'])
    assert result.exit_code == 1
    assert 'Error' in result.output

    # Test error case — duplicate nickname
    result = runner.invoke(app, ['add', 'Joe', 'Crassula', '2026-04-01', '14'])
    assert result.exit_code == 1
    assert "Error" in result.output


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

    # Test error case — duplicate genus
    result = runner.invoke(app, ['add-species', 'Rosa', 'Rose', 'Soak when soil is completely dry for a day or two'])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_cli_show_plants(test_db) -> None:
    """
    Test the show CLI command for empty db, all plants, species, and due filtering.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    """
    # Test empty database state
    result = runner.invoke(app, ['show'])
    assert result.exit_code == 0

    result = create_species(1)
    assert result is True

    # Add a plant that is not yet due — next_watering will be 14 days from today
    future_watering_date = str(date.today() + timedelta(days=14))
    result = add_plant('Jim', 'Crassula', future_watering_date, 14, '')
    assert result is True

    # Verify all-watered message when no plants are overdue
    result = runner.invoke(app, ['show', '--due'])
    assert result.exit_code == 0

    # Add an overdue plant — last watered 14 days ago
    overdue_watering_date = str(date.today() - timedelta(days=14))
    result = add_plant('Joe', 'Crassula', overdue_watering_date, 14, '')
    assert result is True

    # Show all plants
    result = runner.invoke(app, ['show'])
    assert result.exit_code == 0
    assert 'Joe' in result.output
    assert 'Crassula' in result.output

    # Show plant with a specific nickname
    result = runner.invoke(app, ['show', '--name', 'Jim'])
    assert result.exit_code == 0
    assert 'Jim' in result.output
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

    # Test error cases for invalid arguments
    result = runner.invoke(app, ['show', '--due', '--name', 'Joe'])
    assert result.exit_code == 1
    assert "Error" in result.output

    result = runner.invoke(app, ['show', '--species', '--name', 'Joe'])
    assert result.exit_code == 1
    assert "Error" in result.output

    result = runner.invoke(app, ['show', '--species', '--due'])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_cli_watered(test_db) -> None:
    """
    Test the watered CLI command for success and non-existent plant errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    """
    # Set up species and plant
    result = create_species()
    assert result is True
    result = add_plant('Joe', 'Crassula', '2026-03-01', 14, '')
    assert result is True

    # Mark as watered and verify the output includes the next watering date
    result = runner.invoke(app, ['watered', 'Joe'])
    assert result.exit_code == 0
    next_watering = date.today() + timedelta(days=14)
    assert humanize.naturalday(next_watering) in result.output

    # Test error case — non-existent plant
    result = runner.invoke(app, ['watered', 'Jim'])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_cli_update_plant(test_db) -> None:
    """
    Test the update CLI command for success, invalid species, and non-existent plant errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    """
    # Set up two species so genus change can be tested
    result = create_species(1)
    assert result is True
    result = create_species(2)
    assert result is True

    result = add_plant('Joe', 'Crassula', '2026-03-01', 14, '')
    assert result is True

    # Update multiple fields successfully
    result = runner.invoke(app, ['update', 'Joe', '--nickname', 'James', '--genus', 'Rosa', '--last-watered', '2026-04-01', '--interval', '30', '--environment', 'direct south facing window'])
    assert result.exit_code == 0

    # Test error case — non-existent species
    result = runner.invoke(app, ['update', 'James', '--genus', 'Maize', '--last-watered', '2026-04-01', '--interval', '30'])
    assert result.exit_code == 1
    assert "Error" in result.output

    # Test error case — non-existent plant
    result = runner.invoke(app, ['update', 'Joe', '--genus', 'Rosa', '--last-watered', '2026-04-01', '--interval', '30'])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_cli_update_species(test_db) -> None:
    """
    Test the update-species CLI command for success and non-existent species errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    """
    # Set up species to update
    result = create_species(1)
    assert result is True

    # Update the species successfully
    result = runner.invoke(app, ['update-species', 'Crassula', '--genus', 'Rosa', '--common-name', 'Rose', '--care-info', 'Bottom soak when dry'])
    assert result.exit_code == 0

    # Test error case — non-existent species
    result = runner.invoke(app, ['update-species', 'Maize', '--genus', 'Rosa', '--common-name', 'Rose', '--care-info', 'Bottom soak when dry'])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_cli_delete_plant(test_db) -> None:
    """
    Test the delete CLI command for cancel confirmation and successful deletion.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    """
    # Set up species and plant
    result = create_species(1)
    assert result is True
    result = add_plant('Joe', 'Crassula', '2026-03-01', 14, '')
    assert result is True

    # Test cancelling the deletion prompt
    result = runner.invoke(app, ['delete', 'Joe'], input='n\n')
    assert result.exit_code == 0
    assert "Deletion cancelled." in result.output

    # Confirm deletion
    result = runner.invoke(app, ['delete', 'Joe'], input='y\n')
    assert result.exit_code == 0
    assert "Joe" in result.output


def test_cli_delete_species(test_db) -> None:
    """
    Test the delete-species CLI command for cancel confirmation and successful deletion.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    """
    # Set up species to delete
    result = create_species(1)
    assert result is True

    # Test cancelling the deletion prompt
    result = runner.invoke(app, ['delete-species', 'Crassula'], input='n\n')
    assert result.exit_code == 0
    assert "Deletion cancelled." in result.output

    # Test error case — species has plants associated with it
    runner.invoke(app, ['add', 'Joe', 'Crassula', '2026-04-01', '7'])
    result = runner.invoke(app, ['delete-species', 'Crassula'], input='y\n')
    assert result.exit_code == 1
    assert "Error" in result.output

    # Delete plant first, then confirm species deletion
    runner.invoke(app, ['delete', 'Joe'], input='y\n')
    result = runner.invoke(app, ['delete-species', 'Crassula'], input='y\n')
    assert result.exit_code == 0
    assert "Crassula" in result.output

def test_cli_config(test_db) -> None:
    """
    Test the config CLI command for no-args display, upsert, delete, and validation errors.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    """
    # No args with empty settings table
    result = runner.invoke(app, ['config'])
    assert result.exit_code == 0

    # Set auto_interval with default value
    result = runner.invoke(app, ['config', 'auto_interval'])
    assert result.exit_code == 0

    # No args shows the settings table
    result = runner.invoke(app, ['config'])
    assert result.exit_code == 0
    assert 'auto_interval' in result.output
    assert '0.4' in result.output

    # Set auto_interval with a custom value
    result = runner.invoke(app, ['config', 'auto_interval', '--value', '0.3'])
    assert result.exit_code == 0

    # Set claude_api_key with a value
    result = runner.invoke(app, ['config', 'claude_api_key', '--value', 'sk-abc123'])
    assert result.exit_code == 0

    # Delete a setting
    result = runner.invoke(app, ['config', 'auto_interval', '--delete'])
    assert result.exit_code == 0

    # Test error case — claude_api_key requires a value
    result = runner.invoke(app, ['config', 'claude_api_key'])
    assert result.exit_code == 1
    assert "Error" in result.output

    # Test error case — invalid setting
    result = runner.invoke(app, ['config', 'bad_setting'])
    assert result.exit_code == 1
    assert "Error" in result.output

    # Test error case — --value and --delete together
    result = runner.invoke(app, ['config', 'auto_interval', '--value', '0.4', '--delete'])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_cli_remind(test_db) -> None:
    """
    Test the remind CLI command for no plants due and plants due cases.

    Parameters
    ----------
    test_db : fixture
        Pytest fixture providing an isolated temporary database.
    """
    # Test with empty database — no plants due
    result = runner.invoke(app, ['remind'])
    assert result.exit_code == 0

    # Set up an overdue plant
    result = create_species(1)
    assert result is True
    result = add_plant('Joe', 'Crassula', str(date.today() - timedelta(days=14)), 14, '')
    assert result is True

    # Test with overdue plant — mock notify-send to avoid firing a real notification
    with patch('subprocess.call'):
        result = runner.invoke(app, ['remind'])
    assert result.exit_code == 0
    assert "Joe" in result.output

def test_cli_update_care_info(test_db, mock_claude) -> None:

    # Test without API Key configured.
    result = runner.invoke(app, ['update-care-info', 'Crassula'])
    assert result.exit_code == 1
    assert "Error" in result.output

    # Test with API key configured but missing genus / species.
    result = config_setting('claude_api_key', 'sk-abc123', False)
    assert result is True
    result = runner.invoke(app, ['update-care-info', 'Crassula'])
    assert result.exit_code == 1
    assert "Error" in result.output

    # Test with API key configured and species found.
    result = create_species(1)
    assert result is True
    result = runner.invoke(app, ['update-care-info', 'Crassula'])
    assert "Water daily." in result.output

    # Test with API key configured and species found and care info already up to date.
    result = runner.invoke(app, ["update-care-info", "Crassula"])
    assert "Care info is already up to date." in result.output

def test_cli_diagnose(test_db, mock_claude) -> None:

    # Test without a condition or picture path.
    result = runner.invoke(app, ['diagnose', 'Joe'])
    assert result.exit_code == 1
    assert "Error" in result.output

    # Test with a condition but no API Key configured.
    result = runner.invoke(app, ['diagnose', 'Joe', '--condition', 'Brown leaves'])
    assert result.exit_code == 1
    assert "Error" in result.output

    # Test with a condition and API key configured but plant doesn't exist.
    result = config_setting('claude_api_key', 'sk-abc123', False)
    assert result is True
    result = runner.invoke(app, ['diagnose', 'Joe', '--condition', 'Brown leaves'])
    assert result.exit_code == 1
    assert "Error" in result.output

    # Test with a condition and API key configured and plant exists.
    result = create_species(1)
    assert result is True
    result = add_plant('Joe', 'Crassula', '2026-03-01', 14, 'North facing window')
    assert result is True
    result = runner.invoke(app, ['diagnose', 'Joe', '--condition', 'Brown leaves'])
    assert result.exit_code == 0
    assert 'Plant seems healthy.' in result.output

    # Test with a picture and API key configured and plant exists.
    result = runner.invoke(app, ['diagnose', 'Joe', '--picture', 'tests/test_plant.jpg'])
    # Expecting a failure because we don't have a real picture in the testing suite.
    assert result.exit_code == 1
    assert "Error" in result.output
