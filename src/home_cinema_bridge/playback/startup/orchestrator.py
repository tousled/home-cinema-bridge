from __future__ import annotations

import logging
import time
from typing import Callable

from home_cinema_bridge.playback.startup.models import (
    DeviceCommandResult,
    PlaybackOutputSwitchRequest,
    PlaybackOutputSwitchResult,
    OppoPlaybackPosition,
    PlaybackStartupRequest,
    PlaybackStartupResult,
    OppoPlaybackState,
    OppoPlaybackStartRequest,
    OppoPlaybackStartResult,
)
from home_cinema_bridge.playback.ports import (
    AvReceiverOutputPort,
    TelevisionOutputPort,
    OppoPlaybackPort,
)

logger = logging.getLogger(__name__)


class PlaybackStartupOrchestrator:
    def __init__(
        self,
        *,
        television: TelevisionOutputPort,
        av_receiver: AvReceiverOutputPort,
        oppo_playback: OppoPlaybackPort,
    ) -> None:
        self._television = television
        self._av_receiver = av_receiver
        self._oppo_playback = oppo_playback

    def start_playback(
        self,
        request: PlaybackStartupRequest,
        *,
        on_waiting: Callable[[int], None] | None = None,
    ) -> PlaybackStartupResult:
        output_switch_result = self.switch_playback_output_to_oppo(
            request.output_switch_request
        )
        logger.info(
            "Playback output switch result | successful=%s | tv=%s | "
            "av_power=%s | av_input=%s",
            output_switch_result.successful,
            output_switch_result.tv_input_result.status.value,
            output_switch_result.av_power_result.status.value,
            output_switch_result.av_input_result.status.value,
        )

        oppo_start_result = self.start_oppo_playback(
            request=request.oppo_start_request,
            on_waiting=on_waiting,
        )

        return PlaybackStartupResult(
            output_switch_result=output_switch_result,
            oppo_start_result=oppo_start_result,
        )

    def switch_playback_output_to_oppo(
        self,
        request: PlaybackOutputSwitchRequest,
    ) -> PlaybackOutputSwitchResult:
        previous_tv_app_id = self._measure_output_switch_step(
            "read_current_tv_app",
            self._get_current_tv_app_id,
        )
        tv_input_result = self._measure_output_switch_step(
            "switch_tv_to_oppo_input",
            lambda: self._switch_tv_to_oppo_input(request),
        )

        if not tv_input_result.successful:
            logger.warning(
                "Skipping AV input switch because TV input switch failed | detail=%s",
                tv_input_result.detail,
            )

            return PlaybackOutputSwitchResult(
                previous_tv_app_id=previous_tv_app_id,
                tv_input_result=tv_input_result,
                av_power_result=DeviceCommandResult.skipped("TV input switch failed."),
                av_input_result=DeviceCommandResult.skipped("TV input switch failed."),
            )

        av_power_result = self._measure_output_switch_step(
            "power_on_av_receiver",
            lambda: self._power_on_av_receiver(request),
        )
        av_input_result = self._measure_output_switch_step(
            "switch_av_receiver_to_oppo_input",
            lambda: self._switch_av_receiver_to_oppo_input(
                request,
                av_power_result,
            ),
        )

        return PlaybackOutputSwitchResult(
            previous_tv_app_id=previous_tv_app_id,
            tv_input_result=tv_input_result,
            av_power_result=av_power_result,
            av_input_result=av_input_result,
        )

    def start_oppo_playback(
        self,
        *,
        request: OppoPlaybackStartRequest,
        on_waiting: Callable[[int], None] | None = None,
    ) -> OppoPlaybackStartResult:
        return self._oppo_playback.start_playback(
            request,
            on_waiting=on_waiting,
        )

    def get_oppo_playback_position(self) -> OppoPlaybackPosition:
        return self._oppo_playback.get_playback_position()

    def get_oppo_playback_state(self) -> OppoPlaybackState:
        return self._oppo_playback.get_playback_state()

    def seek_oppo_to(self, position_ticks: int) -> DeviceCommandResult:
        return self._oppo_playback.seek_to(position_ticks)

    def select_oppo_audio_track(self, audio_index: int) -> DeviceCommandResult:
        return self._oppo_playback.select_audio_track(audio_index)

    def select_oppo_subtitle_track(self, subtitle_index: int) -> DeviceCommandResult:
        return self._oppo_playback.select_subtitle_track(subtitle_index)

    def _get_current_tv_app_id(self) -> str | None:
        try:
            return self._television.get_current_app_id()
        except Exception:
            logger.exception(
                "Could not read current TV app id before switching output."
            )
            return None

    def _measure_output_switch_step(self, step_name: str, operation: Callable):
        started_at = time.perf_counter()
        result = operation()
        logger.info(
            "Playback output switch timing | step=%s | elapsed=%.3fs",
            step_name,
            time.perf_counter() - started_at,
        )
        return result

    def _switch_tv_to_oppo_input(
        self,
        request: PlaybackOutputSwitchRequest,
    ) -> DeviceCommandResult:
        if not request.tv_enabled:
            return DeviceCommandResult.skipped("TV input switching is disabled.")

        logger.info("Switching TV to OPPO input | input_id=%s", request.tv_input_id)
        return self._television.switch_to_input(request.tv_input_id)

    def _power_on_av_receiver(
        self,
        request: PlaybackOutputSwitchRequest,
    ) -> DeviceCommandResult:
        if not request.av_enabled:
            return DeviceCommandResult.skipped("AV receiver switching is disabled.")

        if self._av_receiver is None:
            return DeviceCommandResult.skipped("No AV receiver adapter configured.")

        logger.info("Ensuring AV receiver is powered on.")
        return self._av_receiver.power_on()

    def _switch_av_receiver_to_oppo_input(
        self,
        request: PlaybackOutputSwitchRequest,
        av_power_result: DeviceCommandResult,
    ) -> DeviceCommandResult:
        if not request.av_enabled:
            return DeviceCommandResult.skipped("AV receiver switching is disabled.")

        if self._av_receiver is None:
            return DeviceCommandResult.skipped("No AV receiver adapter configured.")

        if request.av_input_id is None:
            return DeviceCommandResult.skipped("No AV receiver input configured.")

        if not av_power_result.successful:
            return DeviceCommandResult.failed(
                f"AV receiver power-on failed: {av_power_result.detail}"
            )

        logger.info(
            "Switching AV receiver to OPPO input | input_id=%s",
            request.av_input_id,
        )
        return self._av_receiver.switch_to_input(request.av_input_id)
