import json
import tempfile
import unittest
from pathlib import Path

from home_cinema_bridge.runtime import (
    HomeCinemaBridgeRuntime,
    build_runtime_paths,
)


class FakeSession:
    playstate = "Free"
    playedtitle = "Movie"
    server = "NAS"
    folder = "Movies"
    filename = "movie.mkv"
    currentdata = "data"


class FakeWebSocket:
    def __init__(self):
        self.ws_config = None
        self.config_file = None
        self.ws_lang = None
        self.EmbySession = FakeSession()
        self.started = False
        self.played_data = None
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def _play(self, data):
        self.played_data = data


class RuntimeTest(unittest.TestCase):
    def test_build_runtime_paths(self):
        paths = build_runtime_paths("/app", "/config/config.json")

        self.assertEqual(Path("/app"), paths.base_dir)
        self.assertEqual(Path("/config/config.json"), paths.config_file)
        self.assertEqual(Path("/app/web/lang"), paths.lang_path)
        self.assertEqual(Path("/app/emby_xnoppo_client_logging.log"), paths.log_file)

    def test_reports_not_connected_without_playback_listener(self):
        with self._runtime(configured=False) as runtime:
            state = runtime.get_state()

        self.assertEqual("0.5.1", state["Version"])
        self.assertEqual("Not_Connected", state["Playstate"])

    def test_does_not_start_playback_listener_when_config_is_incomplete(self):
        with self._runtime(configured=False) as runtime:
            started = runtime.start_playback_listener_if_configured()

        self.assertFalse(started)
        self.assertIsNone(runtime.emby_websocket)

    def test_starts_playback_listener_when_config_is_complete(self):
        with self._runtime(configured=True) as runtime:
            started = runtime.start_playback_listener_if_configured()
            runtime.websocket_thread.join(timeout=1)

        self.assertTrue(started)
        self.assertIsInstance(runtime.emby_websocket, FakeWebSocket)
        self.assertTrue(runtime.emby_websocket.started)
        self.assertEqual("user", runtime.emby_websocket.ws_config["user_name"])
        self.assertEqual({"hello": "world"}, runtime.emby_websocket.ws_lang)

    def test_save_config_updates_active_websocket_config(self):
        with self._runtime(configured=True) as runtime:
            runtime.start_playback_listener_if_configured()
            runtime.websocket_thread.join(timeout=1)

            config = runtime.load_config()
            config["user_name"] = "updated"
            runtime.save_config(config)

        self.assertEqual("updated", runtime.emby_websocket.ws_config["user_name"])
        self.assertEqual("updated", runtime.emby_websocket.EmbySession.config["user_name"])

    def test_start_movie_delegates_to_active_websocket(self):
        with self._runtime(configured=True) as runtime:
            runtime.start_playback_listener_if_configured()
            runtime.websocket_thread.join(timeout=1)

            runtime.start_movie({"ItemIds": ["1"]})

        self.assertEqual({"ItemIds": ["1"]}, runtime.emby_websocket.played_data)

    def _runtime(self, *, configured):
        return RuntimeFixture(configured=configured)


class RuntimeFixture:
    def __init__(self, *, configured):
        self.configured = configured
        self.temp_dir = None
        self.runtime = None

    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base_dir = Path(self.temp_dir.name)
        config_file = base_dir / "config.json"
        secrets_file = base_dir / "config.secrets.json"
        lang_dir = base_dir / "web" / "lang" / "es-ES"
        lang_dir.mkdir(parents=True)
        (lang_dir / "lang.js").write_text(json.dumps({"hello": "world"}), "utf-8")

        config = {
            "emby_server": "http://emby.local" if self.configured else "",
            "user_name": "user" if self.configured else "",
            "TV": False,
            "AV": False,
            "servers": [],
            "language": "es-ES",
            "DebugLevel": 0,
        }
        config_file.write_text(json.dumps(config), "utf-8")
        secrets_file.write_text(
            json.dumps({"user_password": "secret" if self.configured else ""}),
            "utf-8",
        )

        self.runtime = HomeCinemaBridgeRuntime(
            paths=build_runtime_paths(base_dir, config_file),
            version="0.5.1",
            websocket_factory=FakeWebSocket,
            exit_process=lambda _code: None,
        )
        return self.runtime

    def __exit__(self, exc_type, exc, traceback):
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
