from __future__ import annotations

from typing import Any

from home_cinema_bridge.devices.av.factory import create_av_receiver
from home_cinema_bridge.devices.tv.factory import create_tv_controller
from home_cinema_bridge.media_servers.emby import (
    MediaServerPlaybackEventPublisher,
    MediaServerPlaybackStoppedReporter,
)
from home_cinema_bridge.playback.finish.orchestrator import FinishPlaybackOrchestrator
from home_cinema_bridge.playback.ports import OppoPlaybackPort
from home_cinema_bridge.playback.startup.device_output_adapters import (
    LegacyAvReceiverOutput,
    LegacyTelevisionOutput,
)


def create_finish_playback_orchestrator(
    config: dict[str, Any],
    playback_event_publisher: MediaServerPlaybackEventPublisher,
    *,
    oppo_playback: OppoPlaybackPort | None = None,
) -> FinishPlaybackOrchestrator:
    return FinishPlaybackOrchestrator(
        stopped_reporter=MediaServerPlaybackStoppedReporter(playback_event_publisher),
        television=LegacyTelevisionOutput(create_tv_controller(config)),
        av_receiver=LegacyAvReceiverOutput(create_av_receiver(config)),
        oppo_playback=oppo_playback,
    )
