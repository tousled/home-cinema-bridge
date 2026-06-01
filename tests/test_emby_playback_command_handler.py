import unittest

from home_cinema_bridge.media_servers.emby.playback_command_handler import (
    EmbyPlaybackCommandHandler,
)
from home_cinema_bridge.playback.intent import PlaybackOrigin


class EmbyPlaybackCommandHandlerTest(unittest.TestCase):
    def test_play_now_goes_to_parent_playback_flow(self):
        dispatcher = RecordingDispatcher()
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: {},
            playback_intent_dispatcher_factory=lambda: dispatcher,
        )
        payload = {"PlayCommand": "PlayNow", "ItemIds": [1234]}

        handler.handle_play(payload)

        self.assertEqual(
            [(payload, PlaybackOrigin.REMOTE_CONTROL_COMMAND)],
            dispatcher.legacy_payloads,
        )

    def test_playstate_command_uses_latest_config(self):
        controls = []
        config = {"name": "old"}
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: config,
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            oppo_control_factory=lambda current_config: RecordingOppoControl(
                current_config, controls
            ),
        )

        config = {"name": "new"}
        handler.handle_playback_state({"Command": "Stop"})

        self.assertEqual([("remote_key", "new", "STP")], controls)

    def test_seek_uses_absolute_position_from_emby(self):
        controls = []
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: {"name": "config"},
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            oppo_control_factory=lambda current_config: RecordingOppoControl(
                current_config, controls
            ),
        )

        handler.handle_playback_state(
            {
                "Command": "Seek",
                "SeekPositionTicks": 120_000_000,
            }
        )

        self.assertEqual([("seek", "config", 120_000_000)], controls)

    def test_seek_relative_adds_delta_to_current_oppo_position(self):
        controls = []
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: {"name": "config"},
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            oppo_control_factory=lambda current_config: RecordingOppoControl(
                current_config, controls, current_position_ticks=1_000_000_000
            ),
        )

        handler.handle_playback_state(
            {
                "Command": "SeekRelative",
                "SeekPositionTicks": 30_000_000,
            }
        )

        self.assertEqual([("seek", "config", 1_030_000_000)], controls)

    def test_seek_relative_never_seeks_before_start(self):
        controls = []
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: {"name": "config"},
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            oppo_control_factory=lambda current_config: RecordingOppoControl(
                current_config, controls, current_position_ticks=100_000_000
            ),
        )

        handler.handle_playback_state(
            {
                "Command": "SeekRelative",
                "SeekPositionTicks": -30_000_0000,
            }
        )

        self.assertEqual([("seek", "config", 0)], controls)

    def test_fast_forward_defaults_to_ten_second_relative_seek(self):
        controls = []
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: {"name": "config"},
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            oppo_control_factory=lambda current_config: RecordingOppoControl(
                current_config, controls, current_position_ticks=1_000_000_000
            ),
        )

        handler.handle_playback_state({"Command": "FastForward"})

        self.assertEqual([("seek", "config", 1_100_000_000)], controls)

    def test_rewind_defaults_to_ten_second_relative_seek(self):
        controls = []
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: {"name": "config"},
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            oppo_control_factory=lambda current_config: RecordingOppoControl(
                current_config, controls, current_position_ticks=1_000_000_000
            ),
        )

        handler.handle_playback_state({"Command": "Rewind"})

        self.assertEqual([("seek", "config", 900_000_000)], controls)


class RecordingDispatcher:
    def __init__(self):
        self.legacy_payloads = []

    def dispatch_legacy_payload(self, payload, *, origin):
        self.legacy_payloads.append((payload, origin))


class RecordingOppoControl:
    def __init__(self, config, calls, *, current_position_ticks=0):
        self._config = config
        self._calls = calls
        self._current_position_ticks = current_position_ticks

    def send_remote_key(self, key):
        self._calls.append(("remote_key", self._config["name"], key))

    def select_audio_track(self, audio_index):
        self._calls.append(("audio", self._config["name"], audio_index))

    def select_subtitle_track(self, subtitle_index):
        self._calls.append(("subtitle", self._config["name"], subtitle_index))

    def seek_to_position_ticks(self, position_ticks):
        self._calls.append(("seek", self._config["name"], position_ticks))

    def current_position_ticks(self):
        return self._current_position_ticks


if __name__ == "__main__":
    unittest.main()
