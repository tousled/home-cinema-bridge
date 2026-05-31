import unittest
from contextlib import redirect_stdout
from io import StringIO

from home_cinema_bridge.playback.application import PlaybackApplicationService
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

        self.assertEqual(("start", ({"ItemIds": [1]},), {"origin": PlaybackOrigin.OBSERVED_TV_CLIENT}), calls[0])
        self.assertEqual(("reload", None), calls[1])

    def test_replace_is_ignored_until_clean_replacement_flow_exists(self):
        service = PlaybackApplicationService(
            playback_session="session",
            reload_config=lambda: None,
        )

        with self.assertLogs(
            "home_cinema_bridge.playback.application",
            level="WARNING",
        ):
            replaced = service.replace(
                {"ItemIds": [1]},
                origin=PlaybackOrigin.REMOTE_CONTROL_COMMAND,
            )

        self.assertFalse(replaced)


if __name__ == "__main__":
    unittest.main()
