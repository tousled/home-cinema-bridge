from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from home_cinema_bridge.playback.startup.models import DeviceCommandResult

logger = logging.getLogger(__name__)

PLAYER_SEEK_UNITS_PER_SECOND = 10_000_000


class PlaybackStartedReporter(Protocol):
    def started(self): ...


class PlaybackTrackResolver(Protocol):
    def resolve_audio_track(
        self,
        *,
        source_user_id: str,
        media_item_id: str,
        selected_source_track_id: int,
    ) -> int: ...

    def resolve_subtitle_track(
        self,
        *,
        source_user_id: str,
        media_item_id: str,
        selected_source_track_id: int,
    ) -> int: ...


class PlaybackStartupCompletionPlayer(Protocol):
    def seek_to_seconds(self, position_seconds: int) -> DeviceCommandResult: ...

    def select_audio_track(self, audio_track_id: int) -> DeviceCommandResult: ...

    def select_subtitle_track(self, subtitle_track_id: int) -> DeviceCommandResult: ...


class StartupStepTimer(Protocol):
    def measure_step(self, step_name: str): ...


@dataclass(frozen=True)
class PlayMediaItemRequest:
    start_position_seconds: int
    source_user_id: str
    media_item_id: str
    selected_source_audio_track_id: int | None = None
    selected_source_subtitle_track_id: int | None = None


@dataclass(frozen=True)
class PlayMediaItemResponse:
    start_position_seconds: int
    started_reported: bool
    seek_result: DeviceCommandResult
    audio_result: DeviceCommandResult
    subtitle_result: DeviceCommandResult


class OppoStartupCompletionPlayer:
    """Adapts the startup orchestrator to post-start playback controls."""

    def __init__(self, startup_orchestrator) -> None:
        self._startup_orchestrator = startup_orchestrator

    def seek_to_seconds(self, position_seconds: int) -> DeviceCommandResult:
        position_units = max(0, position_seconds) * PLAYER_SEEK_UNITS_PER_SECOND
        return self._startup_orchestrator.seek_oppo_to(position_units)

    def select_audio_track(self, audio_track_id: int) -> DeviceCommandResult:
        return self._startup_orchestrator.select_oppo_audio_track(audio_track_id)

    def select_subtitle_track(self, subtitle_track_id: int) -> DeviceCommandResult:
        return self._startup_orchestrator.select_oppo_subtitle_track(subtitle_track_id)


class LegacyEmbyTrackResolver:
    """Resolves source media-server stream ids to OPPO track ids."""

    def __init__(self, emby_session) -> None:
        self._emby_session = emby_session

    def resolve_audio_track(
        self,
        *,
        source_user_id: str,
        media_item_id: str,
        selected_source_track_id: int,
    ) -> int:
        return self._emby_session.get_xnoppo_audio_index(
            source_user_id,
            media_item_id,
            selected_source_track_id,
        )

    def resolve_subtitle_track(
        self,
        *,
        source_user_id: str,
        media_item_id: str,
        selected_source_track_id: int,
    ) -> int:
        return self._emby_session.get_xnoppo_subs_index(
            source_user_id,
            media_item_id,
            selected_source_track_id,
        )


class PlaybackStartupCompletionService:
    """Completes the startup phase after the player has accepted playback."""

    def __init__(
        self,
        *,
        started_reporter: PlaybackStartedReporter,
        player: PlaybackStartupCompletionPlayer,
        track_resolver: PlaybackTrackResolver,
        step_timer: StartupStepTimer | None = None,
    ) -> None:
        self._started_reporter = started_reporter
        self._player = player
        self._track_resolver = track_resolver
        self._step_timer = step_timer

    def complete(
        self,
        request: PlayMediaItemRequest,
    ) -> PlayMediaItemResponse:
        self._measure(
            "notify_media_server_playback_started", self._started_reporter.started
        )

        start_position_seconds = max(0, request.start_position_seconds)
        seek_result = self._measure(
            "apply_resume_position",
            lambda: self._player.seek_to_seconds(start_position_seconds),
        )
        audio_result = self._measure(
            "apply_audio_track",
            lambda: self._select_audio_track(request),
        )
        subtitle_result = self._measure(
            "apply_subtitle_track",
            lambda: self._select_subtitle_track(request),
        )

        return PlayMediaItemResponse(
            start_position_seconds=start_position_seconds,
            started_reported=True,
            seek_result=seek_result,
            audio_result=audio_result,
            subtitle_result=subtitle_result,
        )

    def _select_audio_track(
        self,
        request: PlayMediaItemRequest,
    ) -> DeviceCommandResult:
        if request.selected_source_audio_track_id is None:
            return DeviceCommandResult.skipped("No audio track selected.")

        try:
            audio_track_id = self._track_resolver.resolve_audio_track(
                source_user_id=request.source_user_id,
                media_item_id=request.media_item_id,
                selected_source_track_id=request.selected_source_audio_track_id,
            )
            return self._player.select_audio_track(audio_track_id)
        except Exception as exc:
            logger.exception("Unable to apply selected audio track.")
            return DeviceCommandResult.failed(
                f"Audio track selection failed: {type(exc).__name__}: {exc}"
            )

    def _select_subtitle_track(
        self,
        request: PlayMediaItemRequest,
    ) -> DeviceCommandResult:
        if request.selected_source_subtitle_track_id is None:
            return DeviceCommandResult.skipped("No subtitle track selected.")

        if request.selected_source_subtitle_track_id < 0:
            return DeviceCommandResult.skipped("Subtitles disabled.")

        try:
            subtitle_track_id = self._measure(
                "subtitle_resolve_media_server_to_oppo_index",
                lambda: self._track_resolver.resolve_subtitle_track(
                    source_user_id=request.source_user_id,
                    media_item_id=request.media_item_id,
                    selected_source_track_id=request.selected_source_subtitle_track_id,
                ),
            )
            if subtitle_track_id is None or subtitle_track_id < 0:
                return DeviceCommandResult.skipped("No matching OPPO subtitle track.")

            return self._measure(
                "subtitle_set_oppo_track",
                lambda: self._player.select_subtitle_track(subtitle_track_id),
            )
        except Exception as exc:
            logger.exception("Unable to apply selected subtitle track.")
            return DeviceCommandResult.failed(
                f"Subtitle track selection failed: {type(exc).__name__}: {exc}"
            )

    def _measure(self, step_name: str, operation):
        if self._step_timer is None:
            return operation()

        with self._step_timer.measure_step(step_name):
            return operation()
