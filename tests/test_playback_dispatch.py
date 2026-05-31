import unittest

from home_cinema_bridge.playback.dispatch import (
    PlaybackIntentDispatcher,
    bridge_playback_is_active,
)
from home_cinema_bridge.playback.intent import PlaybackIntent, PlaybackOrigin


class RecordingPlaybackApplicationService:
    def __init__(self):
        self.calls = []

    def request_playback(self, playback_payload, *, origin):
        self.calls.append(("request_playback", playback_payload, origin))
        return True


class PlaybackDispatchTest(unittest.TestCase):
    def test_bridge_playback_is_active_for_bridge_owned_states(self):
        self.assertTrue(bridge_playback_is_active("Loading"))
        self.assertTrue(bridge_playback_is_active("Playing"))
        self.assertTrue(bridge_playback_is_active("Replay"))
        self.assertFalse(bridge_playback_is_active("Free"))

    def test_dispatches_intent_to_application_playback_flow(self):
        playback_service = RecordingPlaybackApplicationService()
        dispatcher = PlaybackIntentDispatcher(
            playback_application_service=playback_service,
        )

        dispatched = dispatcher.dispatch(
            _intent(media_item_id="11136"),
            origin=PlaybackOrigin.OBSERVED_TV_CLIENT,
        )

        self.assertTrue(dispatched)
        self.assertEqual("request_playback", playback_service.calls[0][0])
        self.assertEqual([11136], playback_service.calls[0][1]["ItemIds"])
        self.assertEqual(
            PlaybackOrigin.OBSERVED_TV_CLIENT,
            playback_service.calls[0][2],
        )

    def test_direct_legacy_payload_uses_same_switching_rules(self):
        playback_service = RecordingPlaybackApplicationService()
        dispatcher = PlaybackIntentDispatcher(
            playback_application_service=playback_service,
        )

        dispatched = dispatcher.dispatch_legacy_payload(
            {"ItemIds": [22222]},
            origin=PlaybackOrigin.REMOTE_CONTROL_COMMAND,
        )

        self.assertTrue(dispatched)
        self.assertEqual("request_playback", playback_service.calls[0][0])
        self.assertEqual(
            PlaybackOrigin.REMOTE_CONTROL_COMMAND,
            playback_service.calls[0][2],
        )


def _intent(*, media_item_id):
    return PlaybackIntent(
        media_item_id=media_item_id,
        media_source_id="source-1",
        source_user_id="user-1",
        source_client_session_id="session-1",
        source_device_id="lg-tv",
        source_device_name="LG TV",
        start_position_seconds=12,
        selected_audio_track_id=1,
        selected_subtitle_track_id=-1,
    )


if __name__ == "__main__":
    unittest.main()
