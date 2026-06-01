import logging
import logging.handlers
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

import psutil

from home_cinema_bridge.web.runtime_config import load_runtime_config
from home_cinema_bridge.web.static_assets import load_json_asset
from lib.config_manager import is_configured, save_effective_config
from lib.Emby_ws import XnoppoWs


@dataclass(frozen=True)
class RuntimePaths:
    base_dir: Path
    config_file: Path
    lang_path: Path
    log_file: Path


def build_runtime_paths(base_dir: str | Path, config_file: str | Path) -> RuntimePaths:
    base_dir = Path(base_dir)
    return RuntimePaths(
        base_dir=base_dir,
        config_file=Path(config_file),
        lang_path=base_dir / "web" / "lang",
        log_file=base_dir / "emby_xnoppo_client_logging.log",
    )


def configure_logging(config: dict, log_file: str | Path) -> None:
    debug_level = config.get("DebugLevel", 0)

    if debug_level == 0:
        logging.basicConfig(
            format="%(asctime)s %(levelname)s: %(message)s",
            datefmt="%d/%m/%Y %I:%M:%S %p",
            level=logging.CRITICAL,
        )
    elif debug_level == 1:
        _configure_rotating_logging(log_file, level=logging.INFO, max_bytes=50 * 1024 * 1024)
    elif debug_level == 2:
        _configure_rotating_logging(log_file, level=logging.DEBUG, max_bytes=5 * 1024 * 1024)

    logging.getLogger("websocket").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def _configure_rotating_logging(log_file: str | Path, *, level: int, max_bytes: int) -> None:
    handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        mode="a",
        maxBytes=max_bytes,
        backupCount=2,
        encoding="utf-8",
        delay=False,
    )
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%d/%m/%Y %I:%M:%S %p",
        level=level,
        handlers=[handler, logging.StreamHandler(sys.stdout)],
    )


class HomeCinemaBridgeRuntime:
    def __init__(
        self,
        *,
        paths: RuntimePaths,
        version: str,
        websocket_factory=XnoppoWs,
        exit_process=os._exit,
    ):
        self.paths = paths
        self.version = version
        self._websocket_factory = websocket_factory
        self._exit_process = exit_process
        self.emby_websocket = None
        self.websocket_thread = None

    def load_config(self) -> dict:
        return load_runtime_config(
            str(self.paths.config_file),
            str(self.paths.lang_path) + os.sep,
            version=self.version,
        )

    def load_language(self, config: dict | None = None) -> dict:
        if config is None:
            config = self.load_config()

        language = config["language"]
        return load_json_asset(str(self.paths.lang_path / language / "lang.js"))

    def save_config(self, config: dict) -> None:
        save_effective_config(self.paths.config_file, config)
        self.update_active_config(config)

    def update_active_config(self, config: dict) -> None:
        if self.emby_websocket is None:
            return

        self.emby_websocket.ws_config = config
        try:
            self.emby_websocket.EmbySession.config = config
        except AttributeError:
            pass

    def start_playback_listener_if_configured(self) -> bool:
        config = self.load_config()
        if not is_configured(config):
            print(
                "Config is not complete yet. Web UI is available; "
                "Emby websocket will not start."
            )
            return False

        language = self.load_language(config)
        self.start_playback_listener(config=config, language=language)
        return True

    def start_playback_listener(self, *, config: dict, language: dict) -> None:
        self.emby_websocket = self._websocket_factory()
        self.emby_websocket.ws_config = config
        self.emby_websocket.config_file = str(self.paths.config_file)
        self.emby_websocket.ws_lang = language

        self.websocket_thread = threading.Thread(
            target=_run_websocket,
            args=(self.emby_websocket,),
            daemon=True,
        )
        self.websocket_thread.start()

    def get_state(self) -> dict:
        status = {"Version": self.version}

        try:
            session = self.emby_websocket.EmbySession
            status["Playstate"] = session.playstate
            status["playedtitle"] = session.playedtitle
            status["server"] = session.server
            status["folder"] = session.folder
            status["filename"] = session.filename
            status["CurrentData"] = session.currentdata
        except AttributeError:
            status["Playstate"] = "Not_Connected"
            status["playedtitle"] = ""
            status["server"] = ""
            status["folder"] = ""
            status["filename"] = ""
            status["CurrentData"] = ""

        status["cpu_perc"] = psutil.cpu_percent()
        status["mem_perc"] = psutil.virtual_memory().percent
        logging.debug(psutil.virtual_memory().percent)
        logging.debug(status)
        return status

    def start_movie(self, data: dict) -> None:
        if self.emby_websocket is None:
            raise RuntimeError("Playback listener is not running")

        self.emby_websocket._play(data)

    def restart_process(self) -> None:
        print("restart")
        try:
            if self.emby_websocket is not None:
                self.emby_websocket.stop()
        except Exception:
            pass
        print("fin restart")
        self._exit_process(0)


def _run_websocket(ws_object) -> None:
    print("Thread: starting")
    ws_object.start()
    print("Thread: finishing")
