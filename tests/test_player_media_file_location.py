import unittest

from home_cinema_bridge.playback.media_location import (
    PlayerMediaFileLocationError,
    resolve_player_media_file_location,
)


class PlayerMediaFileLocationTest(unittest.TestCase):
    def test_resolves_emby_path_to_player_media_file_location(self):
        location = resolve_player_media_file_location(
            emby_media_path="/volume1/Video/Movies/Full UHD/Movie.iso",
            playback_file_format="blurayiso",
            path_mappings=[
                {
                    "Emby_Path": "/volume1/Video/Movies",
                    "Oppo_Path": "/192.168.50.110/volume1/Video/Movies",
                }
            ],
        )

        self.assertEqual("192.168.50.110", location.content_server)
        self.assertEqual("volume1/Video/Movies/Full UHD", location.content_directory)
        self.assertEqual("Movie.iso", location.playback_file_name)
        self.assertEqual("blurayiso", location.playback_file_format)

    def test_normalizes_windows_path_separators_after_mapping(self):
        location = resolve_player_media_file_location(
            emby_media_path=r"\\nas\Video\Movies\Movie.mkv",
            playback_file_format="mkv",
            path_mappings=[
                {
                    "Emby_Path": r"\\nas\Video",
                    "Oppo_Path": "/192.168.50.110/volume1/Video",
                }
            ],
        )

        self.assertEqual("192.168.50.110", location.content_server)
        self.assertEqual("volume1/Video/Movies", location.content_directory)
        self.assertEqual("Movie.mkv", location.playback_file_name)

    def test_rejects_path_without_server_folder_and_file(self):
        with self.assertRaises(PlayerMediaFileLocationError):
            resolve_player_media_file_location(
                emby_media_path="/Movie.iso",
                playback_file_format="blurayiso",
                path_mappings=[],
            )


if __name__ == "__main__":
    unittest.main()
