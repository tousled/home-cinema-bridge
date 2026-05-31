from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from home_cinema_bridge.playback.startup.models import DeviceCommandResult
from lib.devices.oppo.control_api_client import OppoControlApiClient

from .media_control_playback import OppoMediaControlPlayback


MEDIA_SERVER_TICKS_PER_SECOND = 10_000_000


@dataclass(frozen=True)
class OppoPlaybackCommandControl:
    """OPPO command adapter for playback controls coming from a media server."""

    config: dict[str, Any]

    def send_remote_key(self, key: str) -> DeviceCommandResult:
        try:
            response = self._client().send_remote_key(key)
            return DeviceCommandResult.success(f"OPPO remote key sent: {response}")
        except Exception as exc:
            return DeviceCommandResult.failed(
                f"OPPO remote key failed: {type(exc).__name__}: {exc}"
            )

    def select_audio_track(self, audio_index: int) -> DeviceCommandResult:
        return self._playback().select_audio_track(audio_index)

    def select_subtitle_track(self, subtitle_index: int) -> DeviceCommandResult:
        return self._playback().select_subtitle_track(subtitle_index)

    def seek_to_position_ticks(self, position_ticks: int) -> DeviceCommandResult:
        return self._playback().seek_to(position_ticks)

    def current_position_ticks(self) -> int:
        position = self._playback().get_playback_position()
        return position.current_seconds * MEDIA_SERVER_TICKS_PER_SECOND

    def _client(self) -> OppoControlApiClient:
        return OppoControlApiClient.from_config(self.config)

    def _playback(self) -> OppoMediaControlPlayback:
        return OppoMediaControlPlayback(self.config)
