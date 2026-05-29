from __future__ import annotations

from typing import Any

from home_cinema_bridge.devices.av.factory import create_av_receiver
from home_cinema_bridge.devices.tv.factory import create_tv_controller
from home_cinema_bridge.playback.startup.device_output_adapters import (
    LegacyAvReceiverOutput,
    LegacyOppoMediaControlPlaybackOutput,
    LegacyTelevisionOutput,
)
from home_cinema_bridge.playback.startup.orchestrator import PlaybackStartupOrchestrator


def create_playback_startup_orchestrator(
    config: dict[str, Any],
) -> PlaybackStartupOrchestrator:
    return PlaybackStartupOrchestrator(
        television=LegacyTelevisionOutput(create_tv_controller(config)),
        av_receiver=LegacyAvReceiverOutput(create_av_receiver(config)),
        oppo_playback=LegacyOppoMediaControlPlaybackOutput(config),
    )
