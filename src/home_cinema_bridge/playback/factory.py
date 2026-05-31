from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from home_cinema_bridge.media_servers.emby import (
    MediaServerPlaybackContext,
    MediaServerPlaybackEventPublisher,
    MediaServerPlaybackProgressReporter,
)
from home_cinema_bridge.playback.during import PlaybackDuringPlaybackOrchestrator
from home_cinema_bridge.playback.error_handling import create_playback_error_handler
from home_cinema_bridge.playback.finish.factory import create_finish_playback_orchestrator
from home_cinema_bridge.playback.orchestrator import PlaybackOrchestrator
from home_cinema_bridge.playback.startup.completion import (
    OppoStartupCompletionPlayer,
    PlaybackTrackResolver,
    PlaybackStartupCompletionService,
    StartupStepTimer,
)
from home_cinema_bridge.playback.startup.factory import (
    PlaybackStartupWiring,
    create_playback_startup_wiring,
)


@dataclass(frozen=True)
class PlaybackOrchestratorWiring:
    startup_wiring: PlaybackStartupWiring
    playback_event_publisher: MediaServerPlaybackEventPublisher
    playback_orchestrator: PlaybackOrchestrator


def create_playback_orchestrator_wiring(
    *,
    config: dict[str, Any],
    media_server_client,
    bridge_session_id: str,
    playback_context: MediaServerPlaybackContext,
    track_resolver: PlaybackTrackResolver,
    step_timer: StartupStepTimer | None = None,
) -> PlaybackOrchestratorWiring:
    startup_wiring = create_playback_startup_wiring(config)
    playback_event_publisher = MediaServerPlaybackEventPublisher(
        media_server_client,
        bridge_session_id=bridge_session_id,
        context=playback_context,
    )
    during_playback_orchestrator = PlaybackDuringPlaybackOrchestrator(
        oppo_playback=startup_wiring.oppo_playback,
        progress_reporter=MediaServerPlaybackProgressReporter(
            playback_event_publisher
        ),
    )
    finish_playback_orchestrator = create_finish_playback_orchestrator(
        config,
        playback_event_publisher,
        oppo_playback=startup_wiring.oppo_playback,
    )
    startup_completion_service = PlaybackStartupCompletionService(
        started_reporter=playback_event_publisher,
        player=OppoStartupCompletionPlayer(startup_wiring.startup_orchestrator),
        track_resolver=track_resolver,
        step_timer=step_timer,
    )
    playback_orchestrator = PlaybackOrchestrator(
        startup_orchestrator=startup_wiring.startup_orchestrator,
        startup_completion_service=startup_completion_service,
        during_playback_orchestrator=during_playback_orchestrator,
        finish_playback_orchestrator=finish_playback_orchestrator,
        error_handler=create_playback_error_handler(
            config,
            oppo_playback=startup_wiring.oppo_playback,
        ),
    )

    return PlaybackOrchestratorWiring(
        startup_wiring=startup_wiring,
        playback_event_publisher=playback_event_publisher,
        playback_orchestrator=playback_orchestrator,
    )
