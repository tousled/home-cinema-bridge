import unittest

from home_cinema_bridge.media_servers.emby.playback import (
    MediaServerPlaybackContext,
    MediaServerPlaybackEventPublisher,
)


class FakeResponse:
    status_code = 204
    text = ""


class RecordingEmbyClient:
    def __init__(self):
        self.calls = []

    def notify_playback_started(self, payload):
        self.calls.append(("started", payload))
        return FakeResponse()

    def report_playback_progress(self, payload):
        self.calls.append(("progress", payload))
        return FakeResponse()

    def notify_playback_stopped(self, payload):
        self.calls.append(("stopped", payload))
        return FakeResponse()


class MediaServerPlaybackContextTest(unittest.TestCase):
    def test_builds_context_from_playback_event(self):
        context = MediaServerPlaybackContext.from_event(
            {
                "ItemIds": ["movie-1"],
                "MediaSourceId": "source-1",
                "AudioStreamIndex": 4,
                "SubtitleStreamIndex": 7,
                "ControllingUserId": "tv-user",
                "SessionID": "tv-session",
                "PlaySessionId": "play-session",
                "StartPositionTicks": 420_000_000,
            },
            load_user_item=_unused_load_user_item,
        )

        self.assertEqual("movie-1", context.media_library_item_id)
        self.assertEqual("source-1", context.media_source_file_id)
        self.assertEqual(4, context.selected_audio_track_id)
        self.assertEqual(7, context.selected_subtitle_track_id)
        self.assertEqual("tv-user", context.media_server_user_id)
        self.assertEqual("tv-session", context.source_client_session_id)
        self.assertEqual(
            "play-session", context.media_server_playback_id
        )
        self.assertEqual(420_000_000, context.start_position_ticks)

    def test_loads_user_data_position_when_event_has_no_start_position(self):
        context = MediaServerPlaybackContext.from_event(
            {
                "ItemIds": ["movie-1"],
                "ControllingUserId": "tv-user",
            },
            load_user_item=lambda user_id, item_id: {
                "UserData": {"PlaybackPositionTicks": 120_000_000}
            },
        )

        self.assertEqual(120_000_000, context.start_position_ticks)

    def test_generates_playback_id_when_event_has_no_play_session_id(self):
        context = MediaServerPlaybackContext.from_event(
            {"ItemIds": ["movie-1"], "StartPositionTicks": 0},
            load_user_item=_unused_load_user_item,
        )

        self.assertNotEqual("", context.media_server_playback_id)
        self.assertEqual(36, len(context.media_server_playback_id))

    def test_uses_play_session_id_from_event_when_present(self):
        context = MediaServerPlaybackContext.from_event(
            {
                "ItemIds": ["movie-1"],
                "StartPositionTicks": 0,
                "PlaySessionId": "server-provided-session",
            },
            load_user_item=_unused_load_user_item,
        )

        self.assertEqual("server-provided-session", context.media_server_playback_id)


class MediaServerPlaybackEventPublisherTest(unittest.TestCase):
    def test_started_uses_resume_position_and_play_session_id(self):
        client = RecordingEmbyClient()
        publisher = MediaServerPlaybackEventPublisher(
            client,
            bridge_session_id="bridge-session",
            context=_context(start_position_ticks=420_000_000),
        )

        publisher.started()

        self.assertEqual("started", client.calls[0][0])
        payload = client.calls[0][1]
        self.assertEqual(420_000_000, payload["PositionTicks"])
        self.assertEqual("play-session", payload["PlaySessionId"])
        self.assertEqual("bridge-session", payload["SessionId"])
        self.assertEqual(["Video"], payload["QueueableMediaTypes"])

    def test_progress_uses_time_update_and_reports_every_configured_interval(self):
        client = RecordingEmbyClient()
        publisher = MediaServerPlaybackEventPublisher(
            client,
            bridge_session_id="bridge-session",
            context=_context(),
            progress_interval_seconds=10,
        )

        publisher.progress(position_ticks=100_000_000, runtime_ticks=1_000_000_000)
        publisher.progress(position_ticks=150_000_000, runtime_ticks=1_000_000_000)
        publisher.progress(position_ticks=200_000_000, runtime_ticks=1_000_000_000)

        self.assertEqual(["progress", "progress"], [call[0] for call in client.calls])
        self.assertEqual("TimeUpdate", client.calls[0][1]["EventName"])
        self.assertEqual(100_000_000, client.calls[0][1]["PositionTicks"])
        self.assertEqual(200_000_000, client.calls[1][1]["PositionTicks"])

    def test_stopped_reports_final_position_without_event_name(self):
        client = RecordingEmbyClient()
        publisher = MediaServerPlaybackEventPublisher(
            client,
            bridge_session_id="bridge-session",
            context=_context(),
        )

        publisher.stopped(position_ticks=660_000_000, runtime_ticks=1_000_000_000)

        self.assertEqual("stopped", client.calls[0][0])
        payload = client.calls[0][1]
        self.assertEqual(660_000_000, payload["PositionTicks"])
        self.assertEqual(1_000_000_000, payload["RunTimeTicks"])
        self.assertNotIn("EventName", payload)


def _context(start_position_ticks=0):
    return MediaServerPlaybackContext(
        media_library_item_id="movie-1",
        media_source_file_id="source-1",
        selected_audio_track_id=1,
        selected_subtitle_track_id=-1,
        media_server_user_id="tv-user",
        source_client_session_id="tv-session",
        media_server_playback_id="play-session",
        start_position_ticks=start_position_ticks,
    )


def _unused_load_user_item(user_id, item_id):
    raise AssertionError("load_user_item should not be called")


if __name__ == "__main__":
    unittest.main()
