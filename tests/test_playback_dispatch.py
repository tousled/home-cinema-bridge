import unittest

from home_cinema_bridge.playback.dispatch import (
    PlaybackIntentDispatcher,
    bridge_playback_is_active,
)
from home_cinema_bridge.playback.intent import PlaybackIntent


class FakeLegacyPlaybackSession:
    def __init__(self, *, playstate="Free", currentdata=None):
        self.playstate = playstate
        self.currentdata = currentdata


class PlaybackDispatchTest(unittest.TestCase):
    def test_bridge_playback_is_active_for_bridge_owned_states(self):
        self.assertTrue(bridge_playback_is_active("Loading"))
        self.assertTrue(bridge_playback_is_active("Playing"))
        self.assertTrue(bridge_playback_is_active("Replay"))
        self.assertFalse(bridge_playback_is_active("Free"))

    def test_ignores_duplicate_intent_for_current_item(self):
        session = FakeLegacyPlaybackSession(
            playstate="Playing",
            currentdata={"ItemIds": [11136]},
        )
        calls = []
        dispatcher = PlaybackIntentDispatcher(
            legacy_playback_session=session,
            start_playback=lambda *args: calls.append(("start", args)),
            switch_playback=lambda *args: calls.append(("switch", args)),
            reload_config=lambda: calls.append(("reload", None)),
            sleep=lambda seconds: None,
        )

        dispatched = dispatcher.dispatch(_intent(media_item_id="11136"), scripterx=True)

        self.assertFalse(dispatched)
        self.assertEqual([], calls)

    def test_switches_when_another_item_arrives_during_playback(self):
        session = FakeLegacyPlaybackSession(
            playstate="Playing",
            currentdata={"ItemIds": [11136]},
        )
        calls = []
        dispatcher = PlaybackIntentDispatcher(
            legacy_playback_session=session,
            start_playback=lambda *args: calls.append(("start", args)),
            switch_playback=lambda *args: calls.append(("switch", args)),
            reload_config=lambda: calls.append(("reload", None)),
            sleep=lambda seconds: None,
        )

        dispatched = dispatcher.dispatch(_intent(media_item_id="22222"), scripterx=True)

        self.assertTrue(dispatched)
        self.assertEqual("switch", calls[0][0])
        self.assertEqual([22222], calls[0][1][1]["ItemIds"])

    def test_direct_legacy_payload_uses_same_switching_rules(self):
        session = FakeLegacyPlaybackSession(
            playstate="Playing",
            currentdata={"ItemIds": [11136]},
        )
        calls = []
        dispatcher = PlaybackIntentDispatcher(
            legacy_playback_session=session,
            start_playback=lambda *args: calls.append(("start", args)),
            switch_playback=lambda *args: calls.append(("switch", args)),
            reload_config=lambda: calls.append(("reload", None)),
            sleep=lambda seconds: None,
        )

        dispatched = dispatcher.dispatch_legacy_payload(
            {"ItemIds": [22222]},
            scripterx=False,
        )

        self.assertTrue(dispatched)
        self.assertEqual("switch", calls[0][0])
        self.assertFalse(calls[0][1][2])


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
