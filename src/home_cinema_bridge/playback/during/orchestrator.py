from __future__ import annotations

import logging
import time
from typing import Protocol

from home_cinema_bridge.devices.oppo.playback_state import OppoPlaybackCategory
from home_cinema_bridge.playback.during.models import (
    PlaybackMonitoringRequest,
    PlaybackMonitoringResult,
    PlaybackMonitoringStopReason,
)
from home_cinema_bridge.playback.ports import OppoPlaybackPort
from home_cinema_bridge.playback.startup.models import OppoPlaybackPosition

logger = logging.getLogger(__name__)


class PlaybackProgressReporter(Protocol):
    def progress(
        self,
        *,
        position_seconds: int,
        duration_seconds: int,
        is_paused: bool = False,
        is_muted: bool = False,
    ): ...


class PlaybackDuringPlaybackOrchestrator:
    """Monitors active OPPO playback and reports media-server progress."""

    def __init__(
        self,
        *,
        oppo_playback: OppoPlaybackPort,
        progress_reporter: PlaybackProgressReporter | None = None,
        sleep=time.sleep,
    ) -> None:
        self._oppo_playback = oppo_playback
        self._progress_reporter = progress_reporter
        self._sleep = sleep

    def monitor_until_stopped(
        self,
        request: PlaybackMonitoringRequest,
    ) -> PlaybackMonitoringResult:
        last_position_seconds = request.initial_position_seconds
        last_duration_seconds = 0
        transition_polls = 0
        end_of_media_polls = 0
        seconds_since_progress_report = 0.0
        final_state = self._oppo_playback.get_playback_state()
        stop_reason = PlaybackMonitoringStopReason.PLAYER_IDLE

        while final_state.category in {
            OppoPlaybackCategory.ACTIVE,
            OppoPlaybackCategory.TRANSITION,
        }:
            self._sleep(request.poll_interval_seconds)
            final_state = self._oppo_playback.get_playback_state()

            if final_state.category != OppoPlaybackCategory.ACTIVE:
                transition_polls += 1
                if transition_polls >= request.max_transition_polls:
                    logger.warning(
                        "OPPO playback monitoring stopped after transition grace | "
                        "polls=%s | state=%s | category=%s",
                        transition_polls,
                        final_state.status.value,
                        final_state.category.value,
                    )
                    stop_reason = (
                        PlaybackMonitoringStopReason.TRANSITION_GRACE_EXCEEDED
                    )
                    break
                continue

            transition_polls = 0
            position = self._oppo_playback.get_playback_position()
            normalized_position = _normalize_playback_position(position)
            logger.debug(
                "OPPO playback position | current=%s | total=%s | state=%s",
                position.current_seconds,
                position.total_seconds,
                final_state.status.value,
            )

            if position.has_valid_position:
                last_position_seconds = normalized_position.current_seconds
                last_duration_seconds = position.total_seconds
                if _is_end_of_media_position(position):
                    end_of_media_polls += 1
                    if end_of_media_polls >= request.max_end_of_media_polls:
                        logger.info(
                            "OPPO playback monitoring stopped at natural media "
                            "end | polls=%s | position=%s | duration=%s | "
                            "state=%s",
                            end_of_media_polls,
                            normalized_position.current_seconds,
                            normalized_position.total_seconds,
                            final_state.status.value,
                        )
                        stop_reason = PlaybackMonitoringStopReason.NATURAL_END
                        break
                else:
                    end_of_media_polls = 0

                seconds_since_progress_report += request.poll_interval_seconds
                if (
                    request.progress_interval_seconds <= 0
                    or seconds_since_progress_report
                    >= request.progress_interval_seconds
                ):
                    self._report_progress(request, normalized_position)
                    seconds_since_progress_report = 0.0

        return PlaybackMonitoringResult(
            position_seconds=last_position_seconds,
            duration_seconds=last_duration_seconds,
            final_state=final_state,
            stop_reason=stop_reason,
        )

    def _report_progress(
        self,
        request: PlaybackMonitoringRequest,
        position: OppoPlaybackPosition,
    ) -> None:
        if not request.report_progress:
            return

        if self._progress_reporter is None:
            return

        self._progress_reporter.progress(
            position_seconds=position.current_seconds,
            duration_seconds=position.total_seconds,
            is_paused=request.is_paused,
            is_muted=request.is_muted,
        )


def _is_end_of_media_position(position: OppoPlaybackPosition) -> bool:
    return (
        position.total_seconds > 0
        and position.current_seconds >= position.total_seconds
    )


def _normalize_playback_position(
    position: OppoPlaybackPosition,
) -> OppoPlaybackPosition:
    if not _is_end_of_media_position(position):
        return position

    return OppoPlaybackPosition(
        current_seconds=position.total_seconds,
        total_seconds=position.total_seconds,
        raw_response=position.raw_response,
    )
