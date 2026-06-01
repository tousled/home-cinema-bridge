from __future__ import annotations

from collections.abc import Callable
from typing import Any


def parse_playback_request_payload(
    data: dict[str, Any],
    *,
    config: dict[str, Any],
    load_item_info: Callable[[str, str], dict[str, Any]],
) -> dict[str, Any]:
    start_position_ticks = data.get("StartPositionTicks")

    if start_position_ticks is None:
        start_position_ticks = data.get("SavedPlaybackPositionTicks")

    if start_position_ticks is None:
        start_position_ticks = -1

    start_position_ticks = int(start_position_ticks)

    item_ids = data["ItemIds"]
    media_source_id = data.get("MediaSourceId", "")
    subtitle_stream_index = data.get("SubtitleStreamIndex", -1)
    audio_stream_index = data.get("AudioStreamIndex", 1)
    start_index = data.get("StartIndex", 0)

    if config["DebugLevel"] > 0:
        print(len(item_ids))

    if len(item_ids) > 0:
        item_ids = item_ids[0]

    if 0 < start_index < len(item_ids):
        item_ids = item_ids[start_index:]

    controlling_user_id = data.get("ControllingUserId", "")

    if start_position_ticks < 0:
        item_info = load_item_info(controlling_user_id, item_ids)
        start_position_ticks = int(
            item_info.get("UserData", {}).get("PlaybackPositionTicks", 0)
        )

    params = {
        "item_id": item_ids,
        "auto_resume": start_position_ticks,
        "media_source_id": media_source_id,
        "subtitle_stream_index": subtitle_stream_index,
        "audio_stream_index": audio_stream_index,
        "ControllingUserId": controlling_user_id,
        "Session_id": data.get("SessionID") or data.get("Id"),
        "play_session_id": data.get("PlaySessionId", ""),
        "DeviceName": data.get("DeviceName", ""),
        "Device_Id": data.get("Device_Id", ""),
    }

    if config.get("DebugLevel", 0) > 0:
        print(
            "Emby playback params | "
            f"item_id={params.get('item_id')} | "
            f"auto_resume={params.get('auto_resume')} | "
            f"media_source_id={params.get('media_source_id')} | "
            f"audio={params.get('audio_stream_index')} | "
            f"subtitle={params.get('subtitle_stream_index')} | "
            f"device={params.get('DeviceName')}"
        )

    return params
