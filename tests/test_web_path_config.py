import unittest
from unittest.mock import patch

from home_cinema_bridge.web.path_config import (
    build_test_media_path,
    get_mount_path,
    normalize_config_path,
    test_path_configuration,
)


class WebPathConfigTest(unittest.TestCase):
    def test_normalize_config_path_accepts_windows_separators(self):
        self.assertEqual(
            "/volume1/Video/Movies",
            normalize_config_path(r"\\volume1\Video\Movies"),
        )

    def test_build_test_media_path_requires_emby_path(self):
        with self.assertRaisesRegex(ValueError, "Emby_Path is required"):
            build_test_media_path({"Emby_Path": ""})

    def test_get_mount_path_maps_emby_path_to_oppo_path(self):
        mount_path = get_mount_path(
            "/volume1/Video/Movies/test.mkv",
            {
                "Emby_Path": "/volume1/Video/Movies",
                "Oppo_Path": "/192.168.50.110/volume1/Video/Movies",
            },
        )

        self.assertEqual(
            {
                "Servidor": "192.168.50.110",
                "Carpeta": "volume1/Video/Movies",
                "Fichero": "test.mkv",
            },
            mount_path,
        )

    def test_get_mount_path_requires_oppo_server_and_folder(self):
        with self.assertRaisesRegex(ValueError, "must include server and folder"):
            get_mount_path(
                "/volume1/Video/Movies/test.mkv",
                {
                    "Emby_Path": "/volume1/Video/Movies",
                    "Oppo_Path": "/NAS",
                },
            )

    @patch("home_cinema_bridge.web.path_config.test_mount_path")
    def test_path_configuration_tests_mapped_folder(self, test_mount_path):
        test_mount_path.return_value = "OK"

        result = test_path_configuration(
            {"DebugLevel": 0},
            {
                "Emby_Path": "/volume1/Video/Movies",
                "Oppo_Path": "/192.168.50.110/volume1/Video/Movies",
            },
        )

        self.assertEqual("OK", result)
        test_mount_path.assert_called_once_with(
            {"DebugLevel": 0}, "192.168.50.110", "volume1/Video/Movies"
        )

    @patch("home_cinema_bridge.web.path_config.test_mount_path")
    def test_path_configuration_returns_validation_error_without_mounting(
        self, test_mount_path
    ):
        result = test_path_configuration(
            {"DebugLevel": 0},
            {
                "Emby_Path": "/volume1/Video/Movies",
                "Oppo_Path": "/",
            },
        )

        self.assertEqual("INVALID PATH CONFIG: Oppo_Path is required.", result)
        test_mount_path.assert_not_called()


if __name__ == "__main__":
    unittest.main()
