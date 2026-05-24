import json
import os
import shutil
from pathlib import Path


CONFIG_ENV_VAR = "XNOPPO_CONFIG_FILE"

DEFAULT_CONFIG_FILE = "config.json"
DEFAULT_SECRETS_FILE = "config.secrets.json"

EXAMPLE_CONFIG_FILE = "config.example.json"
EXAMPLE_SECRETS_FILE = "config.secrets.example.json"

SECRET_KEYS = {"user_password"}


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_config_path() -> Path:
    return Path(os.environ.get(CONFIG_ENV_VAR, DEFAULT_CONFIG_FILE))


def get_secrets_path(config_path: Path | None = None) -> Path:
    if config_path is None:
        config_path = get_config_path()

    return config_path.with_name(DEFAULT_SECRETS_FILE)


def ensure_config_exists() -> Path:
    config_path = get_config_path()

    if not config_path.exists():
        _create_config_file(config_path)

    ensure_secrets_exists(config_path)
    migrate_secrets_from_config(config_path)

    return config_path


def ensure_secrets_exists(config_path: Path | None = None) -> Path:
    if config_path is None:
        config_path = get_config_path()

    secrets_path = get_secrets_path(config_path)

    if secrets_path.exists():
        return secrets_path

    secrets_path.parent.mkdir(parents=True, exist_ok=True)

    project_root = get_project_root()
    example_path = project_root / EXAMPLE_SECRETS_FILE

    if example_path.exists():
        shutil.copyfile(example_path, secrets_path)
    else:
        _write_json(secrets_path, {key: "" for key in sorted(SECRET_KEYS)})

    print(f"Secrets file created at {secrets_path}. Keep this file private.")
    return secrets_path


def load_effective_config(config_path: Path | str | None = None) -> dict:
    if config_path is None:
        config_path = ensure_config_exists()
    else:
        config_path = Path(config_path)
        ensure_secrets_exists(config_path)
        migrate_secrets_from_config(config_path)

    public_config = _read_json(config_path)
    secrets = _read_json(get_secrets_path(config_path))

    return public_config | secrets


def save_effective_config(config_path: Path | str, config: dict) -> None:
    config_path = Path(config_path)
    secrets_path = ensure_secrets_exists(config_path)

    public_config = dict(config)
    existing_secrets = _read_json(secrets_path)

    secrets = dict(existing_secrets)

    for key in SECRET_KEYS:
        if key in public_config:
            secrets[key] = public_config.pop(key) or ""

    _write_json(config_path, public_config)
    _write_json(secrets_path, secrets)


def migrate_secrets_from_config(config_path: Path | str) -> None:
    config_path = Path(config_path)

    if not config_path.exists():
        return

    public_config = _read_json(config_path)
    secrets_path = ensure_secrets_exists(config_path)
    secrets = _read_json(secrets_path)

    changed_public_config = False
    changed_secrets = False

    for key in SECRET_KEYS:
        value = public_config.get(key)

        if value not in (None, ""):
            secrets[key] = value
            public_config.pop(key, None)
            changed_public_config = True
            changed_secrets = True

    if changed_public_config:
        _write_json(config_path, public_config)
        print(f"Moved sensitive values from {config_path} to {secrets_path}.")

    if changed_secrets:
        _write_json(secrets_path, secrets)


def is_configured(config: dict) -> bool:
    emby_server = str(config.get("emby_server", "")).strip()
    user_name = str(config.get("user_name", "")).strip()
    user_password = str(config.get("user_password", "")).strip()

    if not emby_server or not user_name or not user_password:
        return False

    return emby_server.startswith(("http://", "https://"))


def _create_config_file(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)

    project_root = get_project_root()
    legacy_config_path = project_root / DEFAULT_CONFIG_FILE
    example_path = project_root / EXAMPLE_CONFIG_FILE

    if legacy_config_path.exists() and legacy_config_path.resolve() != config_path.resolve():
        shutil.copyfile(legacy_config_path, config_path)
        print(
            f"Existing config found at {legacy_config_path}. "
            f"Copied it to {config_path}. Original file was left untouched."
        )
        return

    if not example_path.exists():
        raise FileNotFoundError(f"Missing {EXAMPLE_CONFIG_FILE}; cannot create default config")

    shutil.copyfile(example_path, config_path)
    print(f"Config file created at {config_path}. Complete setup from the web UI.")


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
        file.write("\n")