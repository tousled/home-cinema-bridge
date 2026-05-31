import unittest

from home_cinema_bridge.devices.oppo.playback_state import (
    OppoPlaybackCategory,
    OppoPlaybackStatus,
)
from home_cinema_bridge.playback.during import (
    PlaybackMonitoringRequest,
    PlaybackMonitoringResult,
)
from home_cinema_bridge.playback.finish import (
    PlaybackFinishRequest,
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
    OppoPlaybackState,
    PlayerMediaFileLocation,
)


class RecordingStartupOrchestrator:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def start_oppo_playback(self, *, request, on_waiting=None):
        self.calls.append((request, on_waiting))
        return self.result


class RecordingDuringPlaybackOrchestrator:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def monitor_until_stopped(self, request):
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
        during = RecordingDuringPlaybackOrchestrator(monitoring_result)
        finish = RecordingFinishPlaybackOrchestrator(_finish_result())
        error_handler = RecordingErrorHandler()
        completed_startups = []
        orchestrator = PlaybackOrchestrator(
            startup_orchestrator=startup,
            during_playback_orchestrator=during,
            finish_playback_orchestrator=finish,
            error_handler=error_handler,
        )

        result = orchestrator.play_until_stopped(
            PlaybackOrchestrationRequest(
                oppo_start_request=_start_request(),
                previous_tv_app_id="com.emby.app",
                tv_enabled=True,
                av_enabled=True,
                on_startup_completed=completed_startups.append,
                build_monitoring_request=lambda _result: PlaybackMonitoringRequest(
                    initial_position_seconds=42
                ),
                build_finish_request=lambda result: PlaybackFinishRequest(
                    position_seconds=result.position_seconds,
                    duration_seconds=result.duration_seconds,
                    final_player_state=result.final_state,
                    previous_tv_app_id="com.emby.app",
                ),
            )
        )

        self.assertTrue(result.successful)
        self.assertEqual(startup_result, completed_startups[0])
        self.assertEqual(1, len(during.requests))
        self.assertEqual(42, during.requests[0].initial_position_seconds)
        self.assertEqual(1, len(finish.requests))
        self.assertEqual(1, finish.requests[0].position_seconds)
        self.assertEqual([], error_handler.requests)

    def test_startup_failure_recovers_and_does_not_monitor_playback(self):
        startup_result = _startup_result(successful=False)
        startup = RecordingStartupOrchestrator(startup_result)
        during = RecordingDuringPlaybackOrchestrator(_monitoring_result())
        finish = RecordingFinishPlaybackOrchestrator(_finish_result())
        error_handler = RecordingErrorHandler()
        orchestrator = PlaybackOrchestrator(
            startup_orchestrator=startup,
            during_playback_orchestrator=during,
            finish_playback_orchestrator=finish,
            error_handler=error_handler,
        )

        result = orchestrator.play_until_stopped(
            PlaybackOrchestrationRequest(
                oppo_start_request=_start_request(),
                previous_tv_app_id="com.emby.app",
                tv_enabled=True,
                av_enabled=True,
                build_monitoring_request=lambda _result: PlaybackMonitoringRequest(),
            )
        )

        self.assertFalse(result.successful)
        self.assertIsNotNone(result.error_recovery_result)
        self.assertEqual([], during.requests)
        self.assertEqual([], finish.requests)
        self.assertEqual("oppo_startup_failed", error_handler.requests[0].reason)
        self.assertEqual("com.emby.app", error_handler.requests[0].previous_tv_app_id)

    def test_finish_failure_runs_central_recovery(self):
        startup_result = _startup_result(successful=True)
        startup = RecordingStartupOrchestrator(startup_result)
        during = RecordingDuringPlaybackOrchestrator(_monitoring_result())
        finish = RecordingFinishPlaybackOrchestrator(_finish_result(successful=False))
        error_handler = RecordingErrorHandler()
        orchestrator = PlaybackOrchestrator(
            startup_orchestrator=startup,
            during_playback_orchestrator=during,
            finish_playback_orchestrator=finish,
            error_handler=error_handler,
        )

        result = orchestrator.play_until_stopped(
            PlaybackOrchestrationRequest(
                oppo_start_request=_start_request(),
                previous_tv_app_id="com.emby.app",
                tv_enabled=True,
                av_enabled=True,
                build_monitoring_request=lambda _result: PlaybackMonitoringRequest(),
                build_finish_request=lambda monitoring_result: PlaybackFinishRequest(
                    position_seconds=monitoring_result.position_seconds,
                    duration_seconds=monitoring_result.duration_seconds,
                    final_player_state=monitoring_result.final_state,
                    previous_tv_app_id="com.emby.app",
                ),
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
