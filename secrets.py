"""Load API credentials. Env vars take precedence over secrets.yaml.

Resolution order for each field:
  1. environment variable (e.g. ADZUNA_APP_KEY)
  2. secrets.yaml entry (e.g. adzuna.app_key)
  3. None — caller must handle missing creds with a user-friendly error
"""

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
SECRETS_FILE = ROOT / "secrets.yaml"


def _load_yaml() -> dict:
    if not SECRETS_FILE.exists():
        return {}
    try:
        data = yaml.safe_load(SECRETS_FILE.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve(env_var: str, yaml_section: str, yaml_key: str) -> str | None:
    val = os.environ.get(env_var)
    if val:
        return val.strip() or None
    section = _load_yaml().get(yaml_section) or {}
    if isinstance(section, dict):
        v = section.get(yaml_key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def adzuna_creds() -> tuple[str | None, str | None]:
    """Return (app_id, app_key). Either may be None — caller must check."""
    return (
        _resolve("ADZUNA_APP_ID",  "adzuna", "app_id"),
        _resolve("ADZUNA_APP_KEY", "adzuna", "app_key"),
    )


def adzuna_defaults() -> dict:
    """Return non-secret Adzuna config (country, where, distance_km).

    These also live in secrets.yaml for convenience — they are not secrets,
    but co-locating them keeps Adzuna config in one place.
    """
    section = _load_yaml().get("adzuna") or {}
    if not isinstance(section, dict):
        return {}
    return {
        "country":     str(section.get("country") or "us").strip().lower(),
        "where":       str(section.get("where") or "").strip(),
        "distance_km": int(section.get("distance_km") or 50),
    }
