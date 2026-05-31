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
    OppoPlaybackStartRequest,
    OppoPlaybackStartResult,
)
from home_cinema_bridge.playback.startup.orchestrator import PlaybackStartupOrchestrator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaybackOrchestrationRequest:
    oppo_start_request: OppoPlaybackStartRequest
    previous_tv_app_id: str | None
    tv_enabled: bool
    av_enabled: bool
    on_startup_waiting: Callable[[int], None] | None = None
    on_startup_completed: Callable[[OppoPlaybackStartResult], None] | None = None
    build_monitoring_request: Callable[
        [OppoPlaybackStartResult],
        PlaybackMonitoringRequest,
    ] | None = None
    build_finish_request: Callable[
        [PlaybackMonitoringResult],
        PlaybackFinishRequest,
    ] | None = None


@dataclass(frozen=True)
class PlaybackOrchestrationResult:
    startup_result: OppoPlaybackStartResult
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
        during_playback_orchestrator: PlaybackDuringPlaybackOrchestrator,
        finish_playback_orchestrator: FinishPlaybackOrchestrator,
        error_handler: PlaybackErrorHandler,
    ) -> None:
        self._startup_orchestrator = startup_orchestrator
        self._during_playback_orchestrator = during_playback_orchestrator
        self._finish_playback_orchestrator = finish_playback_orchestrator
        self._error_handler = error_handler

    def play_until_stopped(
        self,
        request: PlaybackOrchestrationRequest,
    ) -> PlaybackOrchestrationResult:
        startup_result = self._startup_orchestrator.start_oppo_playback(
            request=request.oppo_start_request,
            on_waiting=request.on_startup_waiting,
        )
        self._log_startup_result(startup_result)
        if request.on_startup_completed is not None:
            request.on_startup_completed(startup_result)

        if not startup_result.successful:
            recovery_result = self._recover("oppo_startup_failed", request)
            return PlaybackOrchestrationResult(
                startup_result=startup_result,
                error_recovery_result=recovery_result,
            )

        if request.build_monitoring_request is None:
            raise ValueError("Playback monitoring request builder is required.")

        try:
            monitoring_request = request.build_monitoring_request(startup_result)
            monitoring_result = self._during_playback_orchestrator.monitor_until_stopped(
                monitoring_request
            )
        except Exception:
            logger.exception("Playback during phase failed.")
            recovery_result = self._recover("playback_during_failed", request)
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

        if request.build_finish_request is None:
            raise ValueError("Playback finish request builder is required.")

        try:
            finish_result = self._finish_playback_orchestrator.finish(
                request.build_finish_request(monitoring_result)
            )
        except Exception:
            logger.exception("Playback finish phase failed.")
            recovery_result = self._recover("playback_finish_failed", request)
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
                self._recover("playback_finish_unsuccessful", request)
                if not finish_result.successful
                else None
            ),
        )

    def _recover(
        self,
        reason: str,
        request: PlaybackOrchestrationRequest,
    ) -> PlaybackErrorRecoveryResult:
        return self._error_handler.recover(
            PlaybackErrorRecoveryRequest(
                reason=reason,
                previous_tv_app_id=request.previous_tv_app_id,
                tv_enabled=request.tv_enabled,
                av_enabled=request.av_enabled,
            )
        )

    def _log_startup_result(self, startup_result: OppoPlaybackStartResult) -> None:
        playback_state = startup_result.playback_state
        logger.info(
            "OPPO playback startup result | successful=%s | media_mounted=%s | "
            "playback_command_accepted=%s | playback_started_on_device=%s | "
            "status=%s | category=%s | detail=%s",
            startup_result.successful,
            startup_result.media_mounted,
            startup_result.playback_command_accepted,
            startup_result.playback_started_on_device,
            playback_state.status.value if playback_state is not None else None,
            playback_state.category.value if playback_state is not None else None,
            startup_result.detail,
        )
