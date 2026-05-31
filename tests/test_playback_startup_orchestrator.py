import unittest

from home_cinema_bridge.playback.startup.models import (
    DeviceCommandResult,
    PlaybackOutputSwitchRequest,
)
from home_cinema_bridge.playback.startup.orchestrator import (
    PlaybackStartupOrchestrator,
)


class PlaybackStartupOrchestratorTest(unittest.TestCase):
    def test_output_switch_uses_preserved_return_app_without_reading_current_tv_app(self):
        television = RecordingTelevisionOutput(current_app_id="com.webos.app.hdmi3")
        orchestrator = PlaybackStartupOrchestrator(
            television=television,
            av_receiver=RecordingAvReceiverOutput(),
            oppo_playback=UnusedOppoPlayback(),
        )

        result = orchestrator.switch_playback_output_to_oppo(
            PlaybackOutputSwitchRequest(
                tv_input_id="HDMI_3",
                av_input_id="SIMPLAY",
                previous_tv_app_id_override="com.emby.app",
            )
        )

        self.assertEqual("com.emby.app", result.previous_tv_app_id)
        self.assertEqual(0, television.current_app_reads)
        self.assertEqual(["HDMI_3"], television.input_switches)

    def test_output_switch_reads_current_tv_app_when_no_preserved_app_exists(self):
        television = RecordingTelevisionOutput(current_app_id="com.emby.app")
        orchestrator = PlaybackStartupOrchestrator(
            television=television,
            av_receiver=RecordingAvReceiverOutput(),
            oppo_playback=UnusedOppoPlayback(),
        )

        result = orchestrator.switch_playback_output_to_oppo(
            PlaybackOutputSwitchRequest(
                tv_input_id="HDMI_3",
                av_input_id="SIMPLAY",
            )
        )

        self.assertEqual("com.emby.app", result.previous_tv_app_id)
        self.assertEqual(1, television.current_app_reads)


class RecordingTelevisionOutput:
    def __init__(self, *, current_app_id):
        self._current_app_id = current_app_id
        self.current_app_reads = 0
        self.input_switches = []

    def get_current_app_id(self):
        self.current_app_reads += 1
        return self._current_app_id

    def switch_to_input(self, input_id):
        self.input_switches.append(input_id)
        return DeviceCommandResult.success()

    def return_to_app(self, app_id=None):
        return DeviceCommandResult.success()


class RecordingAvReceiverOutput:
    def power_on(self):
        return DeviceCommandResult.success()

    def switch_to_input(self, input_id):
        return DeviceCommandResult.success()

    def restore_tv_audio(self):
        return DeviceCommandResult.success()


class UnusedOppoPlayback:
    pass


if __name__ == "__main__":
    unittest.main()
