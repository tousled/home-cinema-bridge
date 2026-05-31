import unittest

from home_cinema_bridge.devices.oppo.playback_state import (
    OppoPlaybackCategory,
    OppoPlaybackStatus,
)
from home_cinema_bridge.playback.during import PlaybackMonitoringResult
from home_cinema_bridge.playback.finish import (
    PlaybackFinishResult,
)
from home_cinema_bridge.playback.orchestrator import (
    PlaybackOrchestrationRequest,
    PlaybackOrchestrator,
)
from home_cinema_bridge.playback.startup.models import (
    DeviceCommandResult,
    OppoPlaybackStartRequest,
    OppoPlaybackStartResult,
    PlaybackOutputSwitchRequest,
    PlaybackOutputSwitchResult,
    PlaybackStartupRequest,
    PlaybackStartupResult,
    OppoPlaybackState,
    PlayerMediaFileLocation,
)
from home_cinema_bridge.playback.startup.completion import (
    PlayMediaItemRequest,
    PlayMediaItemResponse,
)


class RecordingStartupOrchestrator:
    def __init__(self, result, output_switch_result=None):
        self.result = result
        self.output_switch_result = output_switch_result or _output_switch_result()
        self.output_switch_calls = []
        self.start_calls = []

    def start_playback(self, request, *, on_waiting=None):
        self.output_switch_calls.append(request)
        self.start_calls.append((request.oppo_start_request, on_waiting))
        return PlaybackStartupResult(
            output_switch_result=self.output_switch_result,
            oppo_start_result=self.result,
        )


class RecordingDuringPlaybackOrchestrator:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def monitor_until_stopped(self, request):
        self.requests.append(request)
        return self.result


class RecordingStartupCompletionService:
    def __init__(self, result=None):
        self.result = result or PlayMediaItemResponse(
            start_position_seconds=42,
            started_reported=True,
            seek_result=DeviceCommandResult.success(),
            audio_result=DeviceCommandResult.success(),
            subtitle_result=DeviceCommandResult.success(),
        )
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return self.result


class RecordingErrorHandler:
    def __init__(self):
        self.requests = []

    def recover(self, request):
        self.requests.append(request)
        return _recovery_result()


class RecordingFinishPlaybackOrchestrator:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def finish(self, request):
        self.requests.append(request)
        return self.result


class PlaybackOrchestratorTest(unittest.TestCase):
    def test_success_runs_startup_during_and_finish(self):
        startup_result = _startup_result(successful=True)
        monitoring_result = _monitoring_result()
        startup = RecordingStartupOrchestrator(startup_result)
        startup_completion = RecordingStartupCompletionService()
        during = RecordingDuringPlaybackOrchestrator(monitoring_result)
        finish = RecordingFinishPlaybackOrchestrator(_finish_result())
        error_handler = RecordingErrorHandler()
        completed_startups = []
        orchestrator = PlaybackOrchestrator(
            startup_orchestrator=startup,
            startup_completion_service=startup_completion,
            during_playback_orchestrator=during,
            finish_playback_orchestrator=finish,
            error_handler=error_handler,
        )

        result = orchestrator.play_until_stopped(
            PlaybackOrchestrationRequest(
                startup_request=_startup_request(),
                startup_completion_request=_startup_completion_request(),
                on_startup_completed=completed_startups.append,
            )
        )

        self.assertTrue(result.successful)
        self.assertEqual([_startup_request()], startup.output_switch_calls)
        self.assertEqual(_output_switch_result(), result.startup_result.output_switch_result)
        self.assertEqual([_startup_completion_request()], startup_completion.requests)
        self.assertEqual(startup_result, completed_startups[0])
        self.assertEqual(1, len(during.requests))
        self.assertEqual(42, during.requests[0].initial_position_seconds)
        self.assertEqual(1, len(finish.requests))
        self.assertEqual(1, finish.requests[0].position_seconds)
        self.assertEqual([], error_handler.requests)

    def test_startup_failure_recovers_and_does_not_monitor_playback(self):
        startup_result = _startup_result(successful=False)
        startup = RecordingStartupOrchestrator(startup_result)
        startup_completion = RecordingStartupCompletionService()
        during = RecordingDuringPlaybackOrchestrator(_monitoring_result())
        finish = RecordingFinishPlaybackOrchestrator(_finish_result())
        error_handler = RecordingErrorHandler()
        orchestrator = PlaybackOrchestrator(
            startup_orchestrator=startup,
            startup_completion_service=startup_completion,
            during_playback_orchestrator=during,
            finish_playback_orchestrator=finish,
            error_handler=error_handler,
        )

        result = orchestrator.play_until_stopped(
            PlaybackOrchestrationRequest(
                startup_request=_startup_request(),
                startup_completion_request=_startup_completion_request(),
            )
        )

        self.assertFalse(result.successful)
        self.assertIsNotNone(result.error_recovery_result)
        self.assertEqual([], startup_completion.requests)
        self.assertEqual([], during.requests)
        self.assertEqual([], finish.requests)
        self.assertEqual("oppo_startup_failed", error_handler.requests[0].reason)
        self.assertEqual("com.emby.app", error_handler.requests[0].previous_tv_app_id)

    def test_finish_failure_runs_central_recovery(self):
        startup_result = _startup_result(successful=True)
        startup = RecordingStartupOrchestrator(startup_result)
        startup_completion = RecordingStartupCompletionService(
            PlayMediaItemResponse(
                start_position_seconds=0,
                started_reported=True,
                seek_result=DeviceCommandResult.success(),
                audio_result=DeviceCommandResult.success(),
                subtitle_result=DeviceCommandResult.success(),
            )
        )
        during = RecordingDuringPlaybackOrchestrator(_monitoring_result())
        finish = RecordingFinishPlaybackOrchestrator(_finish_result(successful=False))
        error_handler = RecordingErrorHandler()
        orchestrator = PlaybackOrchestrator(
            startup_orchestrator=startup,
            startup_completion_service=startup_completion,
            during_playback_orchestrator=during,
            finish_playback_orchestrator=finish,
            error_handler=error_handler,
        )

        result = orchestrator.play_until_stopped(
            PlaybackOrchestrationRequest(
                startup_request=_startup_request(),
                startup_completion_request=_startup_completion_request(),
            )
        )

        self.assertFalse(result.successful)
        self.assertEqual("playback_finish_unsuccessful", error_handler.requests[0].reason)


def _start_request():
    return OppoPlaybackStartRequest(
        media_location=PlayerMediaFileLocation(
            content_server="nas",
            content_directory="Movies",
            playback_file_name="movie.mkv",
            playback_file_format="mkv",
        )
    )


def _startup_request():
    return PlaybackStartupRequest(
        output_switch_request=_output_switch_request(),
        oppo_start_request=_start_request(),
    )


def _output_switch_request():
    return PlaybackOutputSwitchRequest(
        tv_input_id="2",
        av_input_id="SIMPLAY",
        tv_enabled=True,
        av_enabled=True,
    )


def _output_switch_result():
    return PlaybackOutputSwitchResult(
        previous_tv_app_id="com.emby.app",
        tv_input_result=DeviceCommandResult.success(),
        av_power_result=DeviceCommandResult.success(),
        av_input_result=DeviceCommandResult.success(),
    )


def _startup_completion_request():
    return PlayMediaItemRequest(
        start_position_seconds=42,
        source_user_id="user-1",
        media_item_id="movie-1",
        selected_source_audio_track_id=1,
        selected_source_subtitle_track_id=-1,
    )


def _startup_result(*, successful):
    return OppoPlaybackStartResult(
        media_mounted=successful,
        playback_command_accepted=successful,
        playback_started_on_device=successful,
        playback_state=_state(OppoPlaybackStatus.PLAY),
    )


def _monitoring_result():
    return PlaybackMonitoringResult(
        position_seconds=1,
        duration_seconds=10,
        final_state=_state(OppoPlaybackStatus.STOP),
    )


def _finish_result(*, successful=True):
    return PlaybackFinishResult(
        media_server_stop_result=None,
        tv_app_result=(
            DeviceCommandResult.success()
            if successful
            else DeviceCommandResult.failed("tv failed")
        ),
        av_audio_result=DeviceCommandResult.success(),
        final_player_state=_state(OppoPlaybackStatus.MEDIA_CENTER),
    )


def _state(status):
    category = (
        OppoPlaybackCategory.ACTIVE
        if status == OppoPlaybackStatus.PLAY
        else OppoPlaybackCategory.TRANSITION
    )
    return OppoPlaybackState(
        status=status,
        category=category,
        raw_response=f"@OK {status.value}",
        ok=True,
    )


def _recovery_result():
    from home_cinema_bridge.playback.error_handling import PlaybackErrorRecoveryResult

    return PlaybackErrorRecoveryResult(
        tv_app_result=DeviceCommandResult.success(),
        av_audio_result=DeviceCommandResult.success(),
    )


if __name__ == "__main__":
    unittest.main()
