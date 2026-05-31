from __future__ import annotations

from dataclasses import dataclass

from home_cinema_bridge.playback.startup.models import (
    DeviceCommandResult,
    DeviceCommandStatus,
    OppoPlaybackState,
)


@dataclass(frozen=True)
class PlaybackFinishRequest:
    position_seconds: int
    duration_seconds: int
    final_player_state: OppoPlaybackState
    previous_tv_app_id: str | None
    tv_enabled: bool = True
    av_enabled: bool = True
    is_paused: bool = False
    is_muted: bool = False
    media_ended: bool = False
    max_idle_confirmation_polls: int = 5
    idle_confirmation_poll_interval_seconds: float = 1.0


@dataclass(frozen=True)
class PlaybackFinishResult:
    media_server_stop_result: object | None
    player_idle_result: DeviceCommandResult
    tv_app_result: DeviceCommandResult
    av_audio_result: DeviceCommandResult
    final_player_state: OppoPlaybackState

    @property
    def successful(self) -> bool:
        return (
            self.player_idle_result.status != DeviceCommandStatus.FAILED
            and self.tv_app_result.status != DeviceCommandStatus.FAILED
            and self.av_audio_result.status != DeviceCommandStatus.FAILED
        )
