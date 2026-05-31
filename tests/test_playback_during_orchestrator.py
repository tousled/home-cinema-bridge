import unittest

from home_cinema_bridge.devices.oppo.playback_state import (
    OppoPlaybackCategory,
    OppoPlaybackStatus,
)
from home_cinema_bridge.playback.during import (
    PlaybackDuringPlaybackOrchestrator,
    PlaybackMonitoringRequest,
    PlaybackMonitoringStopReason,
)
from home_cinema_bridge.playback.startup.models import (
    OppoPlaybackPosition,
    OppoPlaybackState,
)


class RecordingOppoPlayback:
    def __init__(self, *, states, positions):
        self.states = list(states)
        self.positions = list(positions)
        self.state_calls = 0
        self.position_calls = 0

    def get_playback_state(self):
        self.state_calls += 1
        if not self.states:
            raise AssertionError("Unexpected extra playback-state request")
        return self.states.pop(0)

    def get_playback_position(self):
        self.position_calls += 1
        if not self.positions:
            raise AssertionError("Unexpected extra playback-position request")
        return self.positions.pop(0)


class RecordingProgressPublisher:
    def __init__(self):
        self.calls = []

    def progress(self, **kwargs):
        self.calls.append(kwargs)


class PlaybackDuringPlaybackOrchestratorTest(unittest.TestCase):
    def test_monitors_qpl_until_idle_and_preserves_last_valid_position(self):
        oppo = RecordingOppoPlayback(
            states=[
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
                _state(OppoPlaybackStatus.MEDIA_CENTER, OppoPlaybackCategory.IDLE),
            ],
            positions=[
                OppoPlaybackPosition(current_seconds=12, total_seconds=120),
                OppoPlaybackPosition(current_seconds=0, total_seconds=0),
            ],
        )
        progress = RecordingProgressPublisher()
        orchestrator = PlaybackDuringPlaybackOrchestrator(
            oppo_playback=oppo,
            progress_reporter=progress,
            sleep=lambda seconds: None,
        )

        result = orchestrator.monitor_until_stopped(
            PlaybackMonitoringRequest(
                initial_position_seconds=0,
                progress_interval_seconds=1,
            )
        )

        self.assertEqual(12, result.position_seconds)
        self.assertEqual(120, result.duration_seconds)
        self.assertEqual(OppoPlaybackStatus.MEDIA_CENTER, result.final_state.status)
        self.assertEqual(
            PlaybackMonitoringStopReason.PLAYER_IDLE,
            result.stop_reason,
        )
        self.assertEqual(2, oppo.position_calls)
        self.assertEqual(1, len(progress.calls))
        self.assertEqual(12, progress.calls[0]["position_seconds"])

    def test_reports_progress_no_more_often_than_configured_interval(self):
        oppo = RecordingOppoPlayback(
            states=[
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
                _state(OppoPlaybackStatus.MEDIA_CENTER, OppoPlaybackCategory.IDLE),
            ],
            positions=[
                OppoPlaybackPosition(current_seconds=1, total_seconds=120),
                OppoPlaybackPosition(current_seconds=2, total_seconds=120),
            ],
        )
        progress = RecordingProgressPublisher()
        orchestrator = PlaybackDuringPlaybackOrchestrator(
            oppo_playback=oppo,
            progress_reporter=progress,
            sleep=lambda seconds: None,
        )

        orchestrator.monitor_until_stopped(
            PlaybackMonitoringRequest(
                initial_position_seconds=0,
                poll_interval_seconds=1,
                progress_interval_seconds=10,
            )
        )

        self.assertEqual([], progress.calls)

    def test_keeps_initial_position_when_no_valid_position_is_reported(self):
        oppo = RecordingOppoPlayback(
            states=[
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
                _state(OppoPlaybackStatus.MEDIA_CENTER, OppoPlaybackCategory.IDLE),
            ],
            positions=[
                OppoPlaybackPosition(current_seconds=0, total_seconds=0),
            ],
        )
        orchestrator = PlaybackDuringPlaybackOrchestrator(
            oppo_playback=oppo,
            sleep=lambda seconds: None,
        )

        result = orchestrator.monitor_until_stopped(
            PlaybackMonitoringRequest(initial_position_seconds=42)
        )

        self.assertEqual(42, result.position_seconds)
        self.assertEqual(0, result.duration_seconds)

    def test_stops_after_bounded_transition_grace(self):
        oppo = RecordingOppoPlayback(
            states=[
                _state(OppoPlaybackStatus.STOP, OppoPlaybackCategory.TRANSITION),
                _state(OppoPlaybackStatus.STOP, OppoPlaybackCategory.TRANSITION),
                _state(OppoPlaybackStatus.STOP, OppoPlaybackCategory.TRANSITION),
                _state(OppoPlaybackStatus.STOP, OppoPlaybackCategory.TRANSITION),
            ],
            positions=[],
        )
        orchestrator = PlaybackDuringPlaybackOrchestrator(
            oppo_playback=oppo,
            sleep=lambda seconds: None,
        )

        result = orchestrator.monitor_until_stopped(
            PlaybackMonitoringRequest(
                initial_position_seconds=42,
                max_transition_polls=3,
            )
        )

        self.assertEqual(42, result.position_seconds)
        self.assertEqual(OppoPlaybackStatus.STOP, result.final_state.status)
        self.assertEqual(
            PlaybackMonitoringStopReason.TRANSITION_GRACE_EXCEEDED,
            result.stop_reason,
        )
        self.assertEqual(0, oppo.position_calls)

    def test_stops_after_confirmed_natural_end_even_when_qpl_remains_playing(self):
        oppo = RecordingOppoPlayback(
            states=[
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
                _state(OppoPlaybackStatus.PLAY, OppoPlaybackCategory.ACTIVE),
            ],
            positions=[
                OppoPlaybackPosition(current_seconds=3528, total_seconds=3529),
                OppoPlaybackPosition(current_seconds=3533, total_seconds=3529),
                OppoPlaybackPosition(current_seconds=3533, total_seconds=3529),
            ],
        )
        progress = RecordingProgressPublisher()
        orchestrator = PlaybackDuringPlaybackOrchestrator(
            oppo_playback=oppo,
            progress_reporter=progress,
            sleep=lambda seconds: None,
        )

        result = orchestrator.monitor_until_stopped(
            PlaybackMonitoringRequest(
                progress_interval_seconds=1,
                max_end_of_media_polls=2,
            )
        )

        self.assertEqual(3529, result.position_seconds)
        self.assertEqual(3529, result.duration_seconds)
        self.assertEqual(OppoPlaybackStatus.PLAY, result.final_state.status)
        self.assertEqual(
            PlaybackMonitoringStopReason.NATURAL_END,
            result.stop_reason,
        )
        self.assertEqual(3, oppo.position_calls)
        self.assertEqual(3529, progress.calls[-1]["position_seconds"])


def _state(status, category):
    return OppoPlaybackState(
        status=status,
        category=category,
        raw_response=f"@OK {status.value}",
        ok=True,
    )


if __name__ == "__main__":
    unittest.main()
