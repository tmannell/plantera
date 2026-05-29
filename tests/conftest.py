import pytest
import plantera.db as db
from unittest.mock import patch


@pytest.fixture
def test_db(monkeypatch, tmp_path):
    """Set up a temporary database for each test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_file)
    db.db_init()

@pytest.fixture
def mock_claude():
    with patch.multiple(
        'plantera.service',
        _ask_claude=mock_ask_claude,
        _ask_claude_stream=lambda *args, **kwargs: iter(["Plant seems healthy."])
    ):
        yield

def mock_ask_claude(prompt, api_key):
    new_care_info = "Water daily."
    current = prompt[0]['text']
    changed = new_care_info not in current
    return f'{{"care_info": "{new_care_info}", "changed": {str(changed).lower()}}}'