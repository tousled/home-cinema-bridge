from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from home_cinema_bridge.devices.av.factory import create_av_receiver
from home_cinema_bridge.devices.tv.factory import create_tv_controller
from home_cinema_bridge.playback.ports import OppoPlaybackPort
from home_cinema_bridge.playback.startup.device_output_adapters import (
    LegacyAvReceiverOutput,
    LegacyOppoMediaControlPlaybackOutput,
    LegacyTelevisionOutput,
)
from home_cinema_bridge.playback.startup.orchestrator import PlaybackStartupOrchestrator


@dataclass(frozen=True)
class PlaybackStartupWiring:
    startup_orchestrator: PlaybackStartupOrchestrator
    oppo_playback: OppoPlaybackPort


def create_playback_startup_wiring(
    config: dict[str, Any],
) -> PlaybackStartupWiring:
    oppo_playback = LegacyOppoMediaControlPlaybackOutput(config)
    startup_orchestrator = PlaybackStartupOrchestrator(
        television=LegacyTelevisionOutput(create_tv_controller(config)),
        av_receiver=LegacyAvReceiverOutput(create_av_receiver(config)),
        oppo_playback=oppo_playback,
    )
    return PlaybackStartupWiring(
        startup_orchestrator=startup_orchestrator,
        oppo_playback=oppo_playback,
    )
