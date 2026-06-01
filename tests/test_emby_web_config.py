import unittest

from home_cinema_bridge.media_servers.emby.web_config import (
    build_control_device_config,
    build_library_config,
    build_selectable_folder_servers,
    is_library_active,
)


class EmbyWebConfigTest(unittest.TestCase):
    def test_build_library_config_preserves_existing_active_flags(self):
        libraries = build_library_config(
            [
                {"Name": "Movies", "Id": "movies"},
                {"Name": "Series", "Id": "series"},
            ],
            existing_libraries=[
                {"Name": "Old Movies", "Id": "movies", "Active": True}
            ],
        )

        self.assertEqual(
            [
                {"Name": "Movies", "Id": "movies", "Active": True},
                {"Name": "Series", "Id": "series", "Active": False},
            ],
            libraries,
        )

    def test_build_selectable_folder_servers_includes_active_libraries_only(self):
        servers = build_selectable_folder_servers(
            [
                {
                    "Name": "Movies",
                    "SubFolders": [
                        {"Id": "m1", "Path": "/volume1/Video/Movies"},
                        {"Id": "m2", "Path": "/volume1/Video/Movies 2"},
                    ],
                },
                {
                    "Name": "Series",
                    "SubFolders": [
                        {"Id": "s1", "Path": "/volume1/Video/Series"},
                    ],
                },
            ],
            libraries=[
                {"Name": "Movies", "Id": "movies", "Active": True},
                {"Name": "Series", "Id": "series", "Active": False},
            ],
            existing_servers=[
                {
                    "name": "Peliculas",
                    "Emby_Path": "/volume1/Video/Movies",
                    "Oppo_Path": "/NAS/Video/Movies",
                    "Test_OK": "OK",
                }
            ],
            enable_all_libraries=False,
        )

        self.assertEqual(
            [
                {
                    "Id": "m1",
                    "name": "Peliculas",
                    "Emby_Path": "/volume1/Video/Movies",
                    "Oppo_Path": "/NAS/Video/Movies",
                    "Test_OK": "OK",
                },
                {
                    "Id": "m2",
                    "name": "Movies(2)",
                    "Emby_Path": "/volume1/Video/Movies 2",
                    "Oppo_Path": "/",
                },
            ],
            servers,
        )

    def test_build_selectable_folder_servers_can_include_all_libraries(self):
        servers = build_selectable_folder_servers(
            [
                {
                    "Name": "Series",
                    "SubFolders": [{"Id": "s1", "Path": "/volume1/Video/Series"}],
                }
            ],
            libraries=[{"Name": "Series", "Id": "series", "Active": False}],
            existing_servers=[],
            enable_all_libraries=True,
        )

        self.assertEqual(
            [
                {
                    "Id": "s1",
                    "name": "Series",
                    "Emby_Path": "/volume1/Video/Series",
                    "Oppo_Path": "/",
                }
            ],
            servers,
        )

    def test_build_control_device_config_excludes_bridge_device(self):
        devices = build_control_device_config(
            [
                {
                    "ReportedDeviceId": "Xnoppo",
                    "Name": "Bridge",
                    "AppName": "home-cinema-bridge",
                },
                {
                    "ReportedDeviceId": "lg-tv",
                    "Name": "LG",
                    "AppName": "Emby",
                },
                {"Name": "Broken"},
            ]
        )

        self.assertEqual(
            [
                {
                    "ReportedDeviceId": "lg-tv",
                    "Name": "LG / Emby",
                    "AppName": "Emby",
                    "Id": "lg-tv",
                }
            ],
            devices,
        )

    def test_is_library_active_returns_false_for_unknown_library(self):
        self.assertFalse(is_library_active([], "Movies"))


if __name__ == "__main__":
    unittest.main()
