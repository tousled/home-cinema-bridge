from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PlaybackOrigin(Enum):
    OBSERVED_TV_CLIENT = "observed_tv_client"
    REMOTE_CONTROL_COMMAND = "remote_control_command"


@dataclass(frozen=True)
class PlaybackIntent:
    media_item_id: str
    media_source_id: str
    source_user_id: str
    source_client_session_id: str | None
    source_device_id: str
    source_device_name: str
    start_position_seconds: int
    selected_audio_track_id: int
    selected_subtitle_track_id: int
