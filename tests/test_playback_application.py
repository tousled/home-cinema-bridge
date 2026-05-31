import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace

from home_cinema_bridge.playback.application import (
    PlaybackApplicationService,
    _active_player_stop_command_for_replacement,
)
from home_cinema_bridge.playback.startup.models import (
    DeviceCommandResult,
    PlaybackOutputSwitchResult,
)
from home_cinema_bridge.playback.intent import PlaybackOrigin


class PlaybackApplicationServiceTest(unittest.TestCase):
    def test_start_runs_orchestrated_playback_and_reloads_config(self):
        calls = []
        service = PlaybackApplicationService(
            playback_session="session",
            reload_config=lambda: calls.append(("reload", None)),
        )
        service._start_orchestrated_playback = (
            lambda *args, **kwargs: calls.append(("start", args, kwargs))
        )

        with redirect_stdout(StringIO()):
            service._run_start(
                {"ItemIds": [1]},
                PlaybackOrigin.OBSERVED_TV_CLIENT,
            )

        self.assertEqual("start", calls[0][0])
        self.assertEqual(({"ItemIds": [1]},), calls[0][1])
        self.assertEqual(PlaybackOrigin.OBSERVED_TV_CLIENT, calls[0][2]["origin"])
        self.assertTrue(calls[0][2]["restore_outputs_on_finish"])
        self.assertEqual(("reload", None), calls[1])

    def test_replace_is_accepted_for_clean_replacement_flow(self):
        service = PlaybackApplicationService(
            playback_session="session",
            reload_config=lambda: None,
        )

        service._run_replace = lambda *args: None

        replaced = service.replace(
            {"ItemIds": [1]},
            origin=PlaybackOrigin.REMOTE_CONTROL_COMMAND,
        )

        self.assertTrue(replaced)
        service._replacement_thread.join(timeout=1)

    def test_replace_stops_active_playback_then_starts_replacement(self):
        calls = []
        service = PlaybackApplicationService(
            playback_session="session",
            reload_config=lambda: None,
            stop_active_playback=lambda: calls.append("stop_active"),
        )
        service._active_thread = FakeActiveThread(calls)
        service._run_start = lambda *args: calls.append(("start", args))

        service._run_replace(
            {"ItemIds": [2]},
            PlaybackOrigin.REMOTE_CONTROL_COMMAND,
        )
        service._active_thread.join(timeout=1)

        self.assertEqual("stop_active", calls[0])
        self.assertEqual("join_active", calls[1])
        self.assertEqual(
            (
                "start",
                ({"ItemIds": [2]}, PlaybackOrigin.REMOTE_CONTROL_COMMAND, True),
            ),
            calls[2],
        )

    def test_replace_marks_active_finish_as_replacement_until_joined(self):
        calls = []
        service = PlaybackApplicationService(
            playback_session="session",
            reload_config=lambda: None,
        )
        service._active_thread = FakeActiveThread(calls)

        def stop_active():
            calls.append(("stop_active", service._replacement_requested.is_set()))

        def start_replacement(*args):
            calls.append(("start", service._replacement_requested.is_set(), args))

        service._stop_active_playback = stop_active
        service._run_start = start_replacement

        service._run_replace(
            {"ItemIds": [2]},
            PlaybackOrigin.REMOTE_CONTROL_COMMAND,
        )
        service._active_thread.join(timeout=1)

        self.assertEqual(("stop_active", True), calls[0])
        self.assertEqual("join_active", calls[1])
        self.assertEqual(False, calls[2][1])

    def test_replace_does_not_start_next_item_when_active_finish_failed(self):
        calls = []
        service = PlaybackApplicationService(
            playback_session="session",
            reload_config=lambda: None,
        )
        service._active_thread = FakeActiveThread(calls)
        service._last_playback_result = FakePlaybackResult(successful=False)
        service._stop_active_playback = lambda: calls.append("stop_active")
        service._run_start = lambda *args: calls.append(("start", args))

        service._run_replace(
            {"ItemIds": [2]},
            PlaybackOrigin.REMOTE_CONTROL_COMMAND,
        )

        self.assertEqual(["stop_active", "join_active"], calls)

    def test_replace_ignores_request_when_replacement_is_already_running(self):
        service = PlaybackApplicationService(
            playback_session="session",
            reload_config=lambda: None,
        )
        service._replacement_thread = FakeAliveThread()

        replaced = service.replace(
            {"ItemIds": [2]},
            origin=PlaybackOrigin.REMOTE_CONTROL_COMMAND,
        )

        self.assertFalse(replaced)

    def test_request_playback_ignores_duplicate_active_item(self):
        calls = []
        service = PlaybackApplicationService(
            playback_session=FakePlaybackSession(
                playstate="Playing",
                currentdata={"ItemIds": [11136]},
            ),
            reload_config=lambda: None,
        )
        service.start = lambda *args, **kwargs: calls.append("start")
        service.replace = lambda *args, **kwargs: calls.append("replace")

        requested = service.request_playback(
            {"ItemIds": [11136]},
            origin=PlaybackOrigin.OBSERVED_TV_CLIENT,
        )

        self.assertFalse(requested)
        self.assertEqual([], calls)

    def test_request_playback_replaces_when_other_item_is_active(self):
        calls = []
        service = PlaybackApplicationService(
            playback_session=FakePlaybackSession(
                playstate="Playing",
                currentdata={"ItemIds": [11136]},
            ),
            reload_config=lambda: None,
        )
        service.replace = (
            lambda *args, **kwargs: calls.append(("replace", args, kwargs)) or True
        )

        requested = service.request_playback(
            {"ItemIds": [22222]},
            origin=PlaybackOrigin.REMOTE_CONTROL_COMMAND,
        )

        self.assertTrue(requested)
        self.assertEqual(
            (
                "replace",
                ({"ItemIds": [22222]},),
                {"origin": PlaybackOrigin.REMOTE_CONTROL_COMMAND},
            ),
            calls[0],
        )

    def test_request_playback_starts_when_playback_is_free(self):
        calls = []
        service = PlaybackApplicationService(
            playback_session=FakePlaybackSession(playstate="Free"),
            reload_config=lambda: None,
        )
        service.start = (
            lambda *args, **kwargs: calls.append(("start", args, kwargs))
        )

        requested = service.request_playback(
            {"ItemIds": [22222]},
            origin=PlaybackOrigin.REMOTE_CONTROL_COMMAND,
        )

        self.assertTrue(requested)
        self.assertEqual(
            (
                "start",
                ({"ItemIds": [22222]},),
                {"origin": PlaybackOrigin.REMOTE_CONTROL_COMMAND},
            ),
            calls[0],
        )

    def test_active_iso_replacement_uses_stop_command(self):
        session = FakePlaybackSession(playstate="Playing", filename="Aquaman.iso")

        command = _active_player_stop_command_for_replacement(session)

        self.assertEqual("STP", command)

    def test_active_file_replacement_uses_stop_command(self):
        session = FakePlaybackSession(
            playstate="Playing",
            filename="Blade Runner 2049.mkv",
        )

        command = _active_player_stop_command_for_replacement(session)

        self.assertEqual("STP", command)

    def test_remembers_non_hdmi_tv_return_app(self):
        service = PlaybackApplicationService(
            playback_session="session",
            reload_config=lambda: None,
        )

        service._remember_playback_return_tv_app_id(
            _playback_result_with_previous_tv_app("com.emby.app")
        )

        self.assertEqual("com.emby.app", service._playback_return_tv_app_id)

    def test_does_not_overwrite_return_app_with_hdmi_input(self):
        service = PlaybackApplicationService(
            playback_session="session",
            reload_config=lambda: None,
        )
        service._playback_return_tv_app_id = "com.emby.app"

        service._remember_playback_return_tv_app_id(
            _playback_result_with_previous_tv_app("com.webos.app.hdmi3")
        )

        self.assertEqual("com.emby.app", service._playback_return_tv_app_id)

    def test_keeps_return_app_while_replacement_finish_is_joining(self):
        service = PlaybackApplicationService(
            playback_session="session",
            reload_config=lambda: None,
        )
        service._playback_return_tv_app_id = "com.emby.app"
        service._replacement_requested.set()

        service._clear_playback_return_tv_app_id_after_final_finish(
            _playback_result_with_previous_tv_app("com.emby.app", finished=True)
        )

        self.assertEqual("com.emby.app", service._playback_return_tv_app_id)

    def test_clears_return_app_after_final_finish(self):
        service = PlaybackApplicationService(
            playback_session="session",
            reload_config=lambda: None,
        )
        service._playback_return_tv_app_id = "com.emby.app"

        service._clear_playback_return_tv_app_id_after_final_finish(
            _playback_result_with_previous_tv_app("com.emby.app", finished=True)
        )

        self.assertIsNone(service._playback_return_tv_app_id)


class FakeActiveThread:
    def __init__(self, calls):
        self._calls = calls

    def is_alive(self):
        return True

    def join(self, timeout=None):
        self._calls.append("join_active")


class FakeAliveThread:
    def is_alive(self):
        return True


class FakePlaybackSession:
    def __init__(self, *, playstate, currentdata=None, filename=""):
        self.playstate = playstate
        self.currentdata = currentdata
        self.filename = filename
        self.config = {"DebugLevel": 0}


class FakePlaybackResult:
    def __init__(self, *, successful):
        self.successful = successful


def _playback_result_with_previous_tv_app(previous_tv_app_id, *, finished=False):
    return SimpleNamespace(
        startup_result=SimpleNamespace(
            output_switch_result=PlaybackOutputSwitchResult(
                previous_tv_app_id=previous_tv_app_id,
                tv_input_result=DeviceCommandResult.success(),
                av_power_result=DeviceCommandResult.success(),
                av_input_result=DeviceCommandResult.success(),
            )
        ),
        finish_result=object() if finished else None,
    )


if __name__ == "__main__":
    unittest.main()
