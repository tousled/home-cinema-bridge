import unittest

from home_cinema_bridge.playback.error_handling import (
    PlaybackErrorHandler,
    PlaybackErrorRecoveryRequest,
)
from home_cinema_bridge.playback.startup.models import DeviceCommandResult


class RecordingTelevisionOutput:
    def __init__(self):
        self.calls = []

    def get_current_app_id(self):
        self.calls.append("get_current_app_id")
        return "com.emby.app"

    def switch_to_input(self, input_id):
        self.calls.append(("switch_to_input", input_id))
        return DeviceCommandResult.success("tv input switched")

    def return_to_app(self, app_id=None):
        self.calls.append(("return_to_app", app_id))
        return DeviceCommandResult.success("tv app restored")


class RecordingAvReceiverOutput:
    def __init__(self):
        self.calls = []

    def power_on(self):
        self.calls.append("power_on")
        return DeviceCommandResult.success("av powered")

    def switch_to_input(self, input_id):
        self.calls.append(("switch_to_input", input_id))
        return DeviceCommandResult.success("av input switched")

    def restore_tv_audio(self):
        self.calls.append("restore_tv_audio")
        return DeviceCommandResult.success("tv audio restored")


class RecordingOppoPlayback:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or DeviceCommandResult.success("oppo stopped")

    def stop_playback(self):
        self.calls.append("stop_playback")
        return self.result


class PlaybackErrorHandlerTest(unittest.TestCase):
    def test_stops_player_and_recovers_tv_app_and_av_audio(self):
        television = RecordingTelevisionOutput()
        av_receiver = RecordingAvReceiverOutput()
        oppo = RecordingOppoPlayback()
        handler = PlaybackErrorHandler(
            television=television,
            av_receiver=av_receiver,
            oppo_playback=oppo,
        )

        result = handler.recover(
            PlaybackErrorRecoveryRequest(
                reason="oppo_startup_failed",
                previous_tv_app_id="com.emby.app",
                tv_enabled=True,
                av_enabled=True,
            )
        )

        self.assertTrue(result.successful)
        self.assertEqual(["stop_playback"], oppo.calls)
        self.assertEqual([("return_to_app", "com.emby.app")], television.calls)
        self.assertEqual(["restore_tv_audio"], av_receiver.calls)

    def test_recovery_skips_disabled_outputs(self):
        television = RecordingTelevisionOutput()
        av_receiver = RecordingAvReceiverOutput()
        oppo = RecordingOppoPlayback()
        handler = PlaybackErrorHandler(
            television=television,
            av_receiver=av_receiver,
            oppo_playback=oppo,
        )

        result = handler.recover(
            PlaybackErrorRecoveryRequest(
                reason="oppo_startup_failed",
                previous_tv_app_id="com.emby.app",
                tv_enabled=False,
                av_enabled=False,
            )
        )

        self.assertTrue(result.successful)
        self.assertEqual(["stop_playback"], oppo.calls)
        self.assertEqual([], television.calls)
        self.assertEqual([], av_receiver.calls)


if __name__ == "__main__":
    unittest.main()
