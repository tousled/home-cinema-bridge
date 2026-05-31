import unittest

from home_cinema_bridge.media_servers.emby.session_events import (
    build_playback_intent_from_session,
    find_monitored_session,
    is_same_media_item_request,
    playback_intent_to_legacy_payload,
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

    def test_finds_monitored_session_by_device_id(self):
        session = {"DeviceId": "lg-tv", "Id": "session-1"}

        self.assertEqual(
            session,
            find_monitored_session(
                [{"DeviceId": "phone"}, session],
                "lg-tv",
            ),
        )

    def test_builds_playback_intent_from_session_snapshot(self):
        intent = build_playback_intent_from_session(
            {
                "Id": "session-1",
                "DeviceId": "lg-tv",
                "DeviceName": "LG TV",
                "UserId": "user-1",
                "NowPlayingItem": {"Id": "11136"},
                "PlayState": {
                    "MediaSourceId": "source-1",
                    "PositionTicks": 120_000_000,
                    "AudioStreamIndex": 2,
                    "SubtitleStreamIndex": 4,
                },
            },
            monitored_device_id="lg-tv",
        )

        self.assertEqual("11136", intent.media_item_id)
        self.assertEqual("source-1", intent.media_source_id)
        self.assertEqual("session-1", intent.source_client_session_id)
        self.assertEqual("LG TV", intent.source_device_name)
        self.assertEqual(12, intent.start_position_seconds)
        self.assertEqual(2, intent.selected_audio_track_id)
        self.assertEqual(4, intent.selected_subtitle_track_id)

    def test_builds_playback_intent_from_user_data_position(self):
        intent = build_playback_intent_from_session(
            {
                "Id": "session-1",
                "DeviceId": "lg-tv",
                "UserId": "user-1",
                "NowPlayingItem": {"Id": "11136"},
                "PlayState": {},
            },
            monitored_device_id="lg-tv",
            item_user_data={"PlaybackPositionTicks": 420_000_000},
        )

        self.assertEqual(42, intent.start_position_seconds)

    def test_converts_playback_intent_to_legacy_payload(self):
        intent = build_playback_intent_from_session(
            {
                "Id": "session-1",
                "DeviceId": "lg-tv",
                "DeviceName": "LG TV",
                "UserId": "user-1",
                "NowPlayingItem": {"Id": "11136"},
                "PlayState": {
                    "MediaSourceId": "source-1",
                    "PositionTicks": 120_000_000,
                    "AudioStreamIndex": 2,
                    "SubtitleStreamIndex": -1,
                },
            },
            monitored_device_id="lg-tv",
        )

        payload = playback_intent_to_legacy_payload(intent)

        self.assertEqual([11136], payload["ItemIds"])
        self.assertEqual(120_000_000, payload["StartPositionTicks"])
        self.assertEqual("session-1", payload["SessionID"])
        self.assertEqual("lg-tv", payload["Device_Id"])


if __name__ == "__main__":
    unittest.main()
