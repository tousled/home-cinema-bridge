from __future__ import annotations

import logging
from dataclasses import dataclass

from home_cinema_bridge.devices.av.factory import create_av_receiver
from home_cinema_bridge.devices.tv.factory import create_tv_controller
from home_cinema_bridge.playback.ports import (
    AvReceiverOutputPort,
    OppoPlaybackPort,
    TelevisionOutputPort,
)
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
    player_stop_result: DeviceCommandResult
    tv_app_result: DeviceCommandResult
    av_audio_result: DeviceCommandResult

    @property
    def successful(self) -> bool:
        return (
            self.player_stop_result.status != DeviceCommandStatus.FAILED
            and
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
        oppo_playback: OppoPlaybackPort | None = None,
    ) -> None:
        self._television = television
        self._av_receiver = av_receiver
        self._oppo_playback = oppo_playback

    def recover(self, request: PlaybackErrorRecoveryRequest) -> PlaybackErrorRecoveryResult:
        logger.warning(
            "Recovering playback error | reason=%s | previous_tv_app_id=%s | "
            "tv_enabled=%s | av_enabled=%s",
            request.reason,
            request.previous_tv_app_id,
            request.tv_enabled,
            request.av_enabled,
        )

        player_stop_result = self._stop_player_playback()
        tv_app_result = self._return_tv_to_app(request)
        av_audio_result = self._restore_av_tv_audio(request)
        result = PlaybackErrorRecoveryResult(
            player_stop_result=player_stop_result,
            tv_app_result=tv_app_result,
            av_audio_result=av_audio_result,
        )

        logger.info(
            "Playback error recovery result | successful=%s | player_stop=%s | "
            "tv=%s | av_audio=%s",
            result.successful,
            player_stop_result.status.value,
            tv_app_result.status.value,
            av_audio_result.status.value,
        )
        return result

    def _stop_player_playback(self) -> DeviceCommandResult:
        if self._oppo_playback is None:
            return DeviceCommandResult.skipped("No OPPO playback adapter configured.")

        logger.info("Stopping OPPO playback during error recovery.")
        try:
            return self._oppo_playback.stop_playback()
        except Exception as exc:
            logger.exception("Unable to stop OPPO playback during error recovery.")
            return DeviceCommandResult.failed(
                f"OPPO playback stop failed: {type(exc).__name__}: {exc}"
            )

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


def create_playback_error_handler(
    config: dict,
    *,
    oppo_playback: OppoPlaybackPort | None = None,
) -> PlaybackErrorHandler:
    return PlaybackErrorHandler(
        television=LegacyTelevisionOutput(create_tv_controller(config)),
        av_receiver=LegacyAvReceiverOutput(create_av_receiver(config)),
        oppo_playback=oppo_playback,
    )
