from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from home_cinema_bridge.devices.oppo.playback_state import (
    OppoPlaybackCategory,
    OppoPlaybackStatus,
)


class DeviceCommandStatus(Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class DeviceCommandResult:
    status: DeviceCommandStatus
    detail: str | None = None

    @property
    def successful(self) -> bool:
        return self.status == DeviceCommandStatus.SUCCESS

    @classmethod
    def success(cls, detail: str | None = None) -> "DeviceCommandResult":
        return cls(status=DeviceCommandStatus.SUCCESS, detail=detail)

    @classmethod
    def skipped(cls, detail: str | None = None) -> "DeviceCommandResult":
        return cls(status=DeviceCommandStatus.SKIPPED, detail=detail)

    @classmethod
    def failed(cls, detail: str | None = None) -> "DeviceCommandResult":
        return cls(status=DeviceCommandStatus.FAILED, detail=detail)


@dataclass(frozen=True)
class PlaybackOutputSwitchRequest:
    tv_input_id: str
    av_input_id: str | None
    tv_enabled: bool = True
    av_enabled: bool = True


@dataclass(frozen=True)
class PlaybackOutputSwitchResult:
    previous_tv_app_id: str | None
    tv_input_result: DeviceCommandResult
    av_power_result: DeviceCommandResult
    av_input_result: DeviceCommandResult

    @property
    def successful(self) -> bool:
        return (
            self.tv_input_result.successful
            and self.av_power_result.status != DeviceCommandStatus.FAILED
            and self.av_input_result.status != DeviceCommandStatus.FAILED
        )


@dataclass(frozen=True)
class PlayerMediaFileLocation:
    content_server: str
    content_directory: str
    playback_file_name: str
    playback_file_format: str


@dataclass(frozen=True)
class OppoPlaybackStartRequest:
    media_location: PlayerMediaFileLocation
    wait_for_nfs_share: bool = False
    assume_player_already_on: bool = True
    startup_timeout_seconds: int | float = 30
    poll_interval_seconds: float = 0.5


@dataclass(frozen=True)
class OppoPlaybackState:
    status: OppoPlaybackStatus
    category: OppoPlaybackCategory
    raw_response: str
    ok: bool


@dataclass(frozen=True)
class OppoPlaybackStartResult:
    media_mounted: bool
    playback_command_accepted: bool
    playback_started_on_device: bool
    detail: str | None = None
    mounted_path: str | None = None
    playback_state: OppoPlaybackState | None = None

    @property
    def successful(self) -> bool:
        return (
            self.media_mounted
            and self.playback_command_accepted
            and self.playback_started_on_device
        )


@dataclass(frozen=True)
class OppoPlaybackPosition:
    current_seconds: int
    total_seconds: int
    raw_response: str | None = None

    @property
    def has_valid_position(self) -> bool:
        return self.total_seconds > 0 and self.current_seconds > 0
