from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from enum import Enum


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
