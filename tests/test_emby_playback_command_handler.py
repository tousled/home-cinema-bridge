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
        sent_keys = []
        config = {"name": "old"}
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: config,
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            send_remote_key=lambda key, current_config: sent_keys.append(
                (key, current_config["name"])
            ),
        )

        config = {"name": "new"}
        handler.handle_playstate({"Command": "Stop"})

        self.assertEqual([("STP", "new")], sent_keys)

    def test_seek_uses_absolute_position_from_emby(self):
        seeks = []
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: {"name": "config"},
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            set_play_time=lambda current_config, position_ticks: seeks.append(
                (current_config["name"], position_ticks)
            ),
        )

        handler.handle_playstate(
            {
                "Command": "Seek",
                "SeekPositionTicks": 120_000_000,
            }
        )

        self.assertEqual([("config", 120_000_000)], seeks)

    def test_seek_relative_adds_delta_to_current_oppo_position(self):
        seeks = []
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: {"name": "config"},
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            get_playing_time=lambda current_config: '{"cur_time":100,"total_time":500}',
            set_play_time=lambda current_config, position_ticks: seeks.append(
                (current_config["name"], position_ticks)
            ),
        )

        handler.handle_playstate(
            {
                "Command": "SeekRelative",
                "SeekPositionTicks": 30_000_000,
            }
        )

        self.assertEqual([("config", 1_030_000_000)], seeks)

    def test_seek_relative_never_seeks_before_start(self):
        seeks = []
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: {"name": "config"},
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            get_playing_time=lambda current_config: '{"cur_time":10,"total_time":500}',
            set_play_time=lambda current_config, position_ticks: seeks.append(
                position_ticks
            ),
        )

        handler.handle_playstate(
            {
                "Command": "SeekRelative",
                "SeekPositionTicks": -30_000_0000,
            }
        )

        self.assertEqual([0], seeks)

    def test_fast_forward_defaults_to_ten_second_relative_seek(self):
        seeks = []
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: {"name": "config"},
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            get_playing_time=lambda current_config: '{"cur_time":100,"total_time":500}',
            set_play_time=lambda current_config, position_ticks: seeks.append(
                position_ticks
            ),
        )

        handler.handle_playstate({"Command": "FastForward"})

        self.assertEqual([1_100_000_000], seeks)

    def test_rewind_defaults_to_ten_second_relative_seek(self):
        seeks = []
        handler = EmbyPlaybackCommandHandler(
            emby_session=object(),
            config_provider=lambda: {"name": "config"},
            playback_intent_dispatcher_factory=lambda: RecordingDispatcher(),
            get_playing_time=lambda current_config: '{"cur_time":100,"total_time":500}',
            set_play_time=lambda current_config, position_ticks: seeks.append(
                position_ticks
            ),
        )

        handler.handle_playstate({"Command": "Rewind"})

        self.assertEqual([900_000_000], seeks)


class RecordingDispatcher:
    def __init__(self):
        self.legacy_payloads = []

    def dispatch_legacy_payload(self, payload, *, origin):
        self.legacy_payloads.append((payload, origin))


if __name__ == "__main__":
    unittest.main()
