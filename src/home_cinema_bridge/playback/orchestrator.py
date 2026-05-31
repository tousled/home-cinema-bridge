from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from home_cinema_bridge.playback.during import (
    PlaybackDuringPlaybackOrchestrator,
    PlaybackMonitoringRequest,
    PlaybackMonitoringResult,
)
from home_cinema_bridge.playback.error_handling import (
    PlaybackErrorHandler,
    PlaybackErrorRecoveryRequest,
    PlaybackErrorRecoveryResult,
)
from home_cinema_bridge.playback.finish import (
    FinishPlaybackOrchestrator,
    PlaybackFinishRequest,
    PlaybackFinishResult,
)
from home_cinema_bridge.playback.startup.models import (
    PlaybackOutputSwitchResult,
    PlaybackStartupRequest,
    PlaybackStartupResult,
    OppoPlaybackStartResult,
)
from home_cinema_bridge.playback.startup.completion import (
    PlayMediaItemRequest,
    PlaybackStartupCompletionService,
)
from home_cinema_bridge.playback.startup.orchestrator import PlaybackStartupOrchestrator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaybackOrchestrationRequest:
    startup_request: PlaybackStartupRequest
    startup_completion_request: PlayMediaItemRequest
    is_paused: bool = False
    is_muted: bool = False
    on_startup_waiting: Callable[[int], None] | None = None
    on_startup_completed: Callable[[OppoPlaybackStartResult], None] | None = None


@dataclass(frozen=True)
class PlaybackOrchestrationResult:
    startup_result: PlaybackStartupResult
    monitoring_result: PlaybackMonitoringResult | None = None
    finish_result: PlaybackFinishResult | None = None
    error_recovery_result: PlaybackErrorRecoveryResult | None = None

    @property
    def successful(self) -> bool:
        return (
            self.startup_result.successful
            and self.monitoring_result is not None
            and self.finish_result is not None
            and self.finish_result.successful
        )


class PlaybackOrchestrator:
    """Coordinates the normal playback lifecycle between phase orchestrators."""

    def __init__(
        self,
        *,
        startup_orchestrator: PlaybackStartupOrchestrator,
        startup_completion_service: PlaybackStartupCompletionService,
        during_playback_orchestrator: PlaybackDuringPlaybackOrchestrator,
        finish_playback_orchestrator: FinishPlaybackOrchestrator,
        error_handler: PlaybackErrorHandler,
    ) -> None:
        self._startup_orchestrator = startup_orchestrator
        self._startup_completion_service = startup_completion_service
        self._during_playback_orchestrator = during_playback_orchestrator
        self._finish_playback_orchestrator = finish_playback_orchestrator
        self._error_handler = error_handler

    def play_until_stopped(
        self,
        request: PlaybackOrchestrationRequest,
    ) -> PlaybackOrchestrationResult:
        startup_result = self._startup_orchestrator.start_playback(
            request=request.startup_request,
            on_waiting=request.on_startup_waiting,
        )
        self._log_startup_result(startup_result)

        if not startup_result.successful:
            recovery_result = self._recover(
                "oppo_startup_failed",
                request,
                startup_result.output_switch_result,
            )
            return PlaybackOrchestrationResult(
                startup_result=startup_result,
                error_recovery_result=recovery_result,
            )

        try:
            startup_completion_result = self._startup_completion_service.complete(
                request.startup_completion_request
            )
            if request.on_startup_completed is not None:
                request.on_startup_completed(startup_result.oppo_start_result)

            monitoring_request = PlaybackMonitoringRequest(
                initial_position_seconds=(
                    startup_completion_result.start_position_seconds
                ),
                is_paused=request.is_paused,
                is_muted=request.is_muted,
            )
            monitoring_result = self._during_playback_orchestrator.monitor_until_stopped(
                monitoring_request
            )
        except Exception:
            logger.exception("Playback during phase failed.")
            recovery_result = self._recover(
                "playback_during_failed",
                request,
                startup_result.output_switch_result,
            )
            return PlaybackOrchestrationResult(
                startup_result=startup_result,
                error_recovery_result=recovery_result,
            )

        logger.info(
            "Playback orchestration completed | final_state=%s | category=%s | "
            "position_seconds=%s | duration_seconds=%s",
            monitoring_result.final_state.status.value,
            monitoring_result.final_state.category.value,
            monitoring_result.position_seconds,
            monitoring_result.duration_seconds,
        )

        try:
            finish_result = self._finish_playback_orchestrator.finish(
                PlaybackFinishRequest(
                    position_seconds=monitoring_result.position_seconds,
                    duration_seconds=monitoring_result.duration_seconds,
                    final_player_state=monitoring_result.final_state,
                    previous_tv_app_id=(
                        startup_result.output_switch_result.previous_tv_app_id
                    ),
                    tv_enabled=(
                        request.startup_request.output_switch_request.tv_enabled
                    ),
                    av_enabled=(
                        request.startup_request.output_switch_request.av_enabled
                    ),
                    is_paused=request.is_paused,
                    is_muted=request.is_muted,
                )
            )
        except Exception:
            logger.exception("Playback finish phase failed.")
            recovery_result = self._recover(
                "playback_finish_failed",
                request,
                startup_result.output_switch_result,
            )
            return PlaybackOrchestrationResult(
                startup_result=startup_result,
                monitoring_result=monitoring_result,
                error_recovery_result=recovery_result,
            )
        logger.info(
            "Playback finish completed | successful=%s | tv=%s | av_audio=%s | "
            "final_state=%s | category=%s",
            finish_result.successful,
            finish_result.tv_app_result.status.value,
            finish_result.av_audio_result.status.value,
            finish_result.final_player_state.status.value,
            finish_result.final_player_state.category.value,
        )
        return PlaybackOrchestrationResult(
            startup_result=startup_result,
            monitoring_result=monitoring_result,
            finish_result=finish_result,
            error_recovery_result=(
                self._recover(
                    "playback_finish_unsuccessful",
                    request,
                    startup_result.output_switch_result,
                )
                if not finish_result.successful
                else None
            ),
        )

    def _recover(
        self,
        reason: str,
        request: PlaybackOrchestrationRequest,
        output_switch_result: PlaybackOutputSwitchResult,
    ) -> PlaybackErrorRecoveryResult:
        return self._error_handler.recover(
            PlaybackErrorRecoveryRequest(
                reason=reason,
                previous_tv_app_id=output_switch_result.previous_tv_app_id,
                tv_enabled=request.startup_request.output_switch_request.tv_enabled,
                av_enabled=request.startup_request.output_switch_request.av_enabled,
            )
        )

    def _log_output_switch_result(
        self,
        output_switch_result: PlaybackOutputSwitchResult,
    ) -> None:
        logger.info(
            "Playback output switch result | successful=%s | tv=%s | "
            "av_power=%s | av_input=%s",
            output_switch_result.successful,
            output_switch_result.tv_input_result.status.value,
            output_switch_result.av_power_result.status.value,
            output_switch_result.av_input_result.status.value,
        )

    def _log_startup_result(self, startup_result: PlaybackStartupResult) -> None:
        self._log_output_switch_result(startup_result.output_switch_result)
        oppo_start_result = startup_result.oppo_start_result
        playback_state = oppo_start_result.playback_state
        logger.info(
            "OPPO playback startup result | successful=%s | media_mounted=%s | "
            "playback_command_accepted=%s | playback_started_on_device=%s | "
            "status=%s | category=%s | detail=%s",
            oppo_start_result.successful,
            oppo_start_result.media_mounted,
            oppo_start_result.playback_command_accepted,
            oppo_start_result.playback_started_on_device,
            playback_state.status.value if playback_state is not None else None,
            playback_state.category.value if playback_state is not None else None,
            oppo_start_result.detail,
        )
