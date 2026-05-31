from __future__ import annotations

from dataclasses import dataclass

from home_cinema_bridge.playback.startup.models import OppoPlaybackState


@dataclass(frozen=True)
class PlaybackMonitoringRequest:
    initial_position_seconds: int = 0
    poll_interval_seconds: float = 1.0
    max_transition_polls: int = 30
    progress_interval_seconds: float = 10.0
    report_progress: bool = True
    is_paused: bool = False
    is_muted: bool = False


@dataclass(frozen=True)
class PlaybackMonitoringResult:
    position_seconds: int
    duration_seconds: int
    final_state: OppoPlaybackState

    @property
    def played(self) -> bool:
        if self.duration_seconds <= 0:
            return False

        return (self.position_seconds / self.duration_seconds) > 0.95
