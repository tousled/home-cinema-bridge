import os
import shutil
from pathlib import Path


CONFIG_ENV_VAR = "XNOPPO_CONFIG_FILE"
DEFAULT_CONFIG_FILE = "config.json"
EXAMPLE_CONFIG_FILE = "config.example.json"


def get_config_path() -> Path:
    return Path(os.environ.get(CONFIG_ENV_VAR, DEFAULT_CONFIG_FILE))


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def ensure_config_exists() -> Path:
    config_path = get_config_path()

    if config_path.exists():
        return config_path

    config_path.parent.mkdir(parents=True, exist_ok=True)

    project_root = get_project_root()
    legacy_config_path = project_root / DEFAULT_CONFIG_FILE
    example_path = project_root / EXAMPLE_CONFIG_FILE

    # Migration path for existing users:
    # if they already had config.json in the project root, copy it to the new runtime path.
    # Do not delete the original file, so rollback to older Xnoppo versions remains safe.
    if legacy_config_path.exists() and legacy_config_path.resolve() != config_path.resolve():
        shutil.copyfile(legacy_config_path, config_path)
        print(
            f"Existing config found at {legacy_config_path}. "
            f"Copied it to {config_path}. Original file was left untouched."
        )
        return config_path

    # First install path:
    # create an empty/safe config from config.example.json.
    if not example_path.exists():
        raise FileNotFoundError(f"Missing {EXAMPLE_CONFIG_FILE}; cannot create default config")

    shutil.copyfile(example_path, config_path)
    print(f"Config file created at {config_path}. Complete setup from the web UI.")

    return config_path


def is_configured(config: dict) -> bool:
    emby_server = str(config.get("emby_server", "")).strip()
    user_name = str(config.get("user_name", "")).strip()
    user_password = str(config.get("user_password", "")).strip()

    if not emby_server or not user_name or not user_password:
        return False

    return emby_server.startswith(("http://", "https://"))