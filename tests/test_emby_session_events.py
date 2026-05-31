import unittest

from home_cinema_bridge.media_servers.emby.session_events import (
    is_same_media_item_request,
    playback_request_media_item_id,
)


class EmbySessionEventsTest(unittest.TestCase):
    def test_extracts_selected_item_id_from_list(self):
        self.assertEqual(
            "movie-2",
            playback_request_media_item_id(
                {
                    "ItemIds": ["movie-1", "movie-2"],
                    "StartIndex": 1,
                }
            ),
        )

    def test_extracts_item_id_from_scalar_value(self):
        self.assertEqual("11136", playback_request_media_item_id({"ItemIds": 11136}))

    def test_detects_same_media_item_request(self):
        self.assertTrue(
            is_same_media_item_request(
                {"ItemIds": [11136]},
                {"ItemIds": ["11136"]},
            )
        )

    def test_does_not_match_missing_current_item(self):
        self.assertFalse(
            is_same_media_item_request(
                None,
                {"ItemIds": ["11136"]},
            )
        )


if __name__ == "__main__":
    unittest.main()
