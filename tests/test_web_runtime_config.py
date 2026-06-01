import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from home_cinema_bridge.web.runtime_config import (
    apply_runtime_defaults,
    get_dir_folders,
    normalize_legacy_bool,
)


class WebRuntimeConfigTest(unittest.TestCase):
    def test_normalize_legacy_bool_converts_string_values_only(self):
        self.assertTrue(normalize_legacy_bool("True"))
        self.assertFalse(normalize_legacy_bool("False"))
        self.assertTrue(normalize_legacy_bool(True))
        self.assertEqual("yes", normalize_legacy_bool("yes"))

    @patch("home_cinema_bridge.web.runtime_config.get_supported_av_models")
    @patch("home_cinema_bridge.web.runtime_config.get_supported_tv_models")
    def test_apply_runtime_defaults_adds_web_runtime_fields(
        self, tv_models, av_models
    ):
        tv_models.return_value = ["lg"]
        av_models.return_value = ["denon"]

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "es-ES").mkdir()
            Path(temp_dir, "en-US").mkdir()
            Path(temp_dir, "lang.js").write_text("{}", encoding="utf-8")

            config = {
                "TV": "True",
                "AV": "False",
                "servers": [
                    {"name": "Movies"},
                    {"name": "Series", "Test_OK": True},
                ],
            }

            result = apply_runtime_defaults(
                config,
                version="0.5.1",
                lang_path=temp_dir,
            )

        self.assertIs(result, config)
        self.assertEqual("0.5.1", config["Version"])
        self.assertFalse(config["Autoscript"])
        self.assertFalse(config["enable_all_libraries"])
        self.assertEqual("", config["TV_model"])
        self.assertEqual("", config["TV_MAC"])
        self.assertEqual([], config["TV_SOURCES"])
        self.assertEqual("", config["AV_model"])
        self.assertEqual([], config["AV_SOURCES"])
        self.assertEqual("", config["TV_script_init"])
        self.assertEqual("", config["TV_script_end"])
        self.assertEqual(0, config["av_delay_hdmi"])
        self.assertEqual(23, config["AV_Port"])
        self.assertEqual(60, config["timeout_oppo_mount"])
        self.assertEqual("es-ES", config["language"])
        self.assertFalse(config["default_nfs"])
        self.assertFalse(config["wait_nfs"])
        self.assertEqual(5, config["refresh_time"])
        self.assertFalse(config["check_beta"])
        self.assertEqual("tousled/home-cinema-bridge", config["release_repository"])
        self.assertEqual(10, config["version_check_timeout"])
        self.assertFalse(config["smbtrick"])
        self.assertFalse(config["BRDisc"])
        self.assertTrue(config["TV"])
        self.assertFalse(config["AV"])
        self.assertFalse(config["servers"][0]["Test_OK"])
        self.assertTrue(config["servers"][1]["Test_OK"])
        self.assertEqual(["lg"], config["tv_dirs"])
        self.assertEqual(["denon"], config["av_dirs"])
        self.assertEqual(["en-US", "es-ES"], config["langs"])

    def test_get_dir_folders_returns_sorted_directories_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "z").mkdir()
            Path(temp_dir, "a").mkdir()
            Path(temp_dir, "file.txt").write_text("", encoding="utf-8")

            self.assertEqual(["a", "z"], get_dir_folders(temp_dir))


if __name__ == "__main__":
    unittest.main()
