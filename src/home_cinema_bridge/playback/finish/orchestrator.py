from __future__ import annotations

import logging
import time
from typing import Protocol

from home_cinema_bridge.devices.oppo.playback_state import OppoPlaybackCategory
from home_cinema_bridge.playback.finish.models import (
    PlaybackFinishRequest,
    PlaybackFinishResult,
)
from home_cinema_bridge.playback.ports import (
    AvReceiverOutputPort,
    OppoPlaybackPort,
    TelevisionOutputPort,
)
from home_cinema_bridge.playback.startup.models import (
    DeviceCommandResult,
    DeviceCommandStatus,
    OppoPlaybackState,
)

logger = logging.getLogger(__name__)


class PlaybackStoppedReporter(Protocol):
    def stopped(
        self,
        *,
        position_seconds: int,
        duration_seconds: int,
        is_paused: bool = False,
        is_muted: bool = False,
    ): ...


class FinishPlaybackOrchestrator:
    """Completes normal playback and restores user-facing outputs."""

    def __init__(
        self,
        *,
        stopped_reporter: PlaybackStoppedReporter,
        television: TelevisionOutputPort,
        av_receiver: AvReceiverOutputPort | None,
        oppo_playback: OppoPlaybackPort | None = None,
        sleep=time.sleep,
    ) -> None:
        self._stopped_reporter = stopped_reporter
        self._television = television
        self._av_receiver = av_receiver
        self._oppo_playback = oppo_playback
        self._sleep = sleep

    def finish(self, request: PlaybackFinishRequest) -> PlaybackFinishResult:
        final_player_state, player_idle_result = self._close_and_confirm_player_state(
            request
        )
        media_server_stop_result = self._stopped_reporter.stopped(
            position_seconds=request.position_seconds,
            duration_seconds=request.duration_seconds,
            is_paused=request.is_paused,
            is_muted=request.is_muted,
        )

        logger.info(
            "Media server playback stopped | position_seconds=%s | "
            "duration_seconds=%s | played=%s",
            request.position_seconds,
            request.duration_seconds,
            _is_played(request.position_seconds, request.duration_seconds),
        )

        tv_app_result = self._return_tv_to_app(request)
        av_audio_result = self._restore_av_tv_audio(request)

        return PlaybackFinishResult(
            media_server_stop_result=media_server_stop_result,
            player_idle_result=player_idle_result,
            tv_app_result=tv_app_result,
            av_audio_result=av_audio_result,
            final_player_state=final_player_state,
        )

    def _close_and_confirm_player_state(
        self,
        request: PlaybackFinishRequest,
    ) -> tuple[OppoPlaybackState, DeviceCommandResult]:
        close_result = self._close_player_after_natural_end(request)
        if close_result.status == DeviceCommandStatus.FAILED:
            return request.final_player_state, close_result

        final_player_state, idle_result = self._confirm_idle_state(request)
        if close_result.successful and idle_result.successful:
            return final_player_state, DeviceCommandResult.success(
                f"{close_result.detail}; {idle_result.detail}"
            )

        return final_player_state, idle_result

    def _close_player_after_natural_end(
        self,
        request: PlaybackFinishRequest,
    ) -> DeviceCommandResult:
        if not request.media_ended:
            return DeviceCommandResult.skipped("Playback did not end by media position.")

        if request.final_player_state.category != OppoPlaybackCategory.ACTIVE:
            return DeviceCommandResult.skipped("Player is not active after media end.")

        if self._oppo_playback is None:
            return DeviceCommandResult.skipped(
                "No OPPO playback adapter configured for media-end close."
            )

        logger.info(
            "Closing OPPO playback after natural media end | state=%s | category=%s",
            request.final_player_state.status.value,
            request.final_player_state.category.value,
        )
        return self._oppo_playback.stop_playback()

    def _confirm_idle_state(
        self,
        request: PlaybackFinishRequest,
    ) -> tuple[OppoPlaybackState, DeviceCommandResult]:
        state = request.final_player_state
        if state.category == OppoPlaybackCategory.IDLE:
            return state, DeviceCommandResult.success("OPPO already idle.")

        if self._oppo_playback is None:
            logger.info(
                "Skipping OPPO idle confirmation; no player port is available | "
                "state=%s | category=%s",
                state.status.value,
                state.category.value,
            )
            return state, DeviceCommandResult.skipped(
                "No OPPO playback adapter configured for idle confirmation."
            )

        for poll_number in range(1, request.max_idle_confirmation_polls + 1):
            self._sleep(request.idle_confirmation_poll_interval_seconds)
            try:
                state = self._oppo_playback.get_playback_state()
            except Exception as exc:
                logger.exception(
                    "Unable to confirm OPPO idle state during playback finish; "
                    "continuing with last known state | state=%s | category=%s",
                    state.status.value,
                    state.category.value,
                )
                return state, DeviceCommandResult.failed(
                    f"OPPO idle confirmation failed: {type(exc).__name__}: {exc}"
                )

            logger.info(
                "OPPO finish idle confirmation | poll=%s | state=%s | category=%s",
                poll_number,
                state.status.value,
                state.category.value,
            )

            if state.category == OppoPlaybackCategory.IDLE:
                return state, DeviceCommandResult.success(
                    "OPPO idle state confirmed."
                )

        logger.warning(
            "OPPO did not report idle before finish continuation | state=%s | "
            "category=%s",
            state.status.value,
            state.category.value,
        )
        return state, DeviceCommandResult.failed(
            "OPPO did not report idle before finish continuation."
        )

    def _return_tv_to_app(
        self,
        request: PlaybackFinishRequest,
    ) -> DeviceCommandResult:
        if not request.tv_enabled:
            return DeviceCommandResult.skipped("TV app restore is disabled.")

        logger.info(
            "Returning TV after playback finish | app_id=%s",
            request.previous_tv_app_id,
        )
        try:
            return self._television.return_to_app(request.previous_tv_app_id)
        except Exception as exc:
            logger.exception("Unable to return TV after playback finish")
            return DeviceCommandResult.failed(
                f"TV app restore failed: {type(exc).__name__}: {exc}"
            )

    def _restore_av_tv_audio(
        self,
        request: PlaybackFinishRequest,
    ) -> DeviceCommandResult:
        if not request.av_enabled:
            return DeviceCommandResult.skipped("AV TV audio restore is disabled.")

        if self._av_receiver is None:
            return DeviceCommandResult.skipped("No AV receiver adapter configured.")

        logger.info("Restoring AV receiver after playback finish.")
        try:
            return self._av_receiver.restore_tv_audio()
        except Exception as exc:
            logger.exception("Unable to restore AV receiver after playback finish")
            return DeviceCommandResult.failed(
                f"AV TV audio restore failed: {type(exc).__name__}: {exc}"
            )


def _is_played(position_seconds: int, duration_seconds: int) -> bool:
    if duration_seconds <= 0:
        return False

    return (position_seconds / duration_seconds) > 0.95
