"""Tests for secrets.py — env vars take precedence over secrets.yaml."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import secrets as secrets_mod


@pytest.fixture
def fake_yaml(tmp_path, monkeypatch):
    """Redirect SECRETS_FILE to a tmp file we control."""
    f = tmp_path / "secrets.yaml"
    monkeypatch.setattr(secrets_mod, "SECRETS_FILE", f)
    return f


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID",  raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)


# ---------------------------------------------------------------------------
# adzuna_creds
# ---------------------------------------------------------------------------

class TestAdzunaCreds:
    def test_env_var_wins(self, fake_yaml, monkeypatch):
        fake_yaml.write_text(
            'adzuna:\n  app_id: "from_yaml"\n  app_key: "yaml_key"\n'
        )
        monkeypatch.setenv("ADZUNA_APP_ID",  "from_env")
        monkeypatch.setenv("ADZUNA_APP_KEY", "env_key")
        app_id, app_key = secrets_mod.adzuna_creds()
        assert app_id  == "from_env"
        assert app_key == "env_key"

    def test_yaml_used_when_env_absent(self, fake_yaml, clean_env):
        fake_yaml.write_text(
            'adzuna:\n  app_id: "yaml_id"\n  app_key: "yaml_key"\n'
        )
        assert secrets_mod.adzuna_creds() == ("yaml_id", "yaml_key")

    def test_returns_none_when_no_yaml_no_env(self, fake_yaml, clean_env):
        # fake_yaml does not exist
        assert secrets_mod.adzuna_creds() == (None, None)

    def test_empty_env_var_falls_back_to_yaml(self, fake_yaml, monkeypatch):
        fake_yaml.write_text('adzuna:\n  app_id: "yaml_id"\n')
        monkeypatch.setenv("ADZUNA_APP_ID", "")
        monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
        app_id, _ = secrets_mod.adzuna_creds()
        assert app_id == "yaml_id"

    def test_whitespace_stripped(self, fake_yaml, monkeypatch):
        fake_yaml.write_text('adzuna:\n  app_id: "  spaced_id  "\n')
        monkeypatch.delenv("ADZUNA_APP_ID",  raising=False)
        monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
        app_id, _ = secrets_mod.adzuna_creds()
        assert app_id == "spaced_id"

    def test_partial_creds_returned(self, fake_yaml, monkeypatch):
        # Only app_id in yaml, only app_key in env
        fake_yaml.write_text('adzuna:\n  app_id: "yaml_id"\n')
        monkeypatch.delenv("ADZUNA_APP_ID",  raising=False)
        monkeypatch.setenv("ADZUNA_APP_KEY", "env_key")
        app_id, app_key = secrets_mod.adzuna_creds()
        assert app_id  == "yaml_id"
        assert app_key == "env_key"

    def test_malformed_yaml_returns_none_safely(self, fake_yaml, clean_env):
        fake_yaml.write_text("adzuna:\n  app_id: [not, a, string\n")  # invalid
        assert secrets_mod.adzuna_creds() == (None, None)

    def test_yaml_with_non_dict_root_is_ignored(self, fake_yaml, clean_env):
        fake_yaml.write_text('"just a string"\n')
        assert secrets_mod.adzuna_creds() == (None, None)


# ---------------------------------------------------------------------------
# adzuna_defaults
# ---------------------------------------------------------------------------

class TestAdzunaDefaults:
    def test_uses_yaml_values(self, fake_yaml):
        fake_yaml.write_text(
            'adzuna:\n  country: gb\n  where: London\n  distance_km: 30\n'
        )
        d = secrets_mod.adzuna_defaults()
        assert d == {"country": "gb", "where": "London", "distance_km": 30}

    def test_defaults_when_yaml_missing(self, fake_yaml):
        # File doesn't exist
        d = secrets_mod.adzuna_defaults()
        assert d == {"country": "us", "where": "", "distance_km": 50}

    def test_country_lowercased(self, fake_yaml):
        fake_yaml.write_text('adzuna:\n  country: "US"\n')
        assert secrets_mod.adzuna_defaults()["country"] == "us"

    def test_distance_coerced_to_int(self, fake_yaml):
        fake_yaml.write_text('adzuna:\n  distance_km: "75"\n')
        assert secrets_mod.adzuna_defaults()["distance_km"] == 75
