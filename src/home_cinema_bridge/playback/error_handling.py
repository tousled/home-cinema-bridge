from __future__ import annotations

import logging
from dataclasses import dataclass

from home_cinema_bridge.devices.av.factory import create_av_receiver
from home_cinema_bridge.devices.tv.factory import create_tv_controller
from home_cinema_bridge.playback.ports import AvReceiverOutputPort, TelevisionOutputPort
from home_cinema_bridge.playback.startup.device_output_adapters import (
    LegacyAvReceiverOutput,
    LegacyTelevisionOutput,
)
from home_cinema_bridge.playback.startup.models import (
    DeviceCommandResult,
    DeviceCommandStatus,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaybackErrorRecoveryRequest:
    reason: str
    previous_tv_app_id: str | None
    tv_enabled: bool = True
    av_enabled: bool = True


@dataclass(frozen=True)
class PlaybackErrorRecoveryResult:
    tv_app_result: DeviceCommandResult
    av_audio_result: DeviceCommandResult

    @property
    def successful(self) -> bool:
        return (
            self.tv_app_result.status != DeviceCommandStatus.FAILED
            and self.av_audio_result.status != DeviceCommandStatus.FAILED
        )


class PlaybackErrorHandler:
    """Central recovery point for playback errors across orchestration phases."""

    def __init__(
        self,
        *,
        television: TelevisionOutputPort,
        av_receiver: AvReceiverOutputPort | None,
    ) -> None:
        self._television = television
        self._av_receiver = av_receiver

    def recover(self, request: PlaybackErrorRecoveryRequest) -> PlaybackErrorRecoveryResult:
        logger.warning(
            "Recovering playback error | reason=%s | previous_tv_app_id=%s | "
            "tv_enabled=%s | av_enabled=%s",
            request.reason,
            request.previous_tv_app_id,
            request.tv_enabled,
            request.av_enabled,
        )

        tv_app_result = self._return_tv_to_app(request)
        av_audio_result = self._restore_av_tv_audio(request)
        result = PlaybackErrorRecoveryResult(
            tv_app_result=tv_app_result,
            av_audio_result=av_audio_result,
        )

        logger.info(
            "Playback error recovery result | successful=%s | tv=%s | av_audio=%s",
            result.successful,
            tv_app_result.status.value,
            av_audio_result.status.value,
        )
        return result

    def _return_tv_to_app(
        self,
        request: PlaybackErrorRecoveryRequest,
    ) -> DeviceCommandResult:
        if not request.tv_enabled:
            return DeviceCommandResult.skipped("TV app restore is disabled.")

        logger.info(
            "Returning TV during playback error recovery | app_id=%s",
            request.previous_tv_app_id,
        )
        return self._television.return_to_app(request.previous_tv_app_id)

    def _restore_av_tv_audio(
        self,
        request: PlaybackErrorRecoveryRequest,
    ) -> DeviceCommandResult:
        if not request.av_enabled:
            return DeviceCommandResult.skipped("AV TV audio restore is disabled.")

        if self._av_receiver is None:
            return DeviceCommandResult.skipped("No AV receiver adapter configured.")

        logger.info("Restoring AV receiver during playback error recovery.")
        return self._av_receiver.restore_tv_audio()


def create_playback_error_handler(config: dict) -> PlaybackErrorHandler:
    return PlaybackErrorHandler(
        television=LegacyTelevisionOutput(create_tv_controller(config)),
        av_receiver=LegacyAvReceiverOutput(create_av_receiver(config)),
    )
