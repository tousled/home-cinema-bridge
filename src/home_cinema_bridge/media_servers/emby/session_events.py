from __future__ import annotations

from typing import Any

from home_cinema_bridge.media_servers.emby.playback import EMBY_TICKS_PER_SECOND
from home_cinema_bridge.playback.intent import PlaybackIntent


def playback_request_media_item_id(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None

    item_ids = data.get("ItemIds")
    if item_ids is None:
        return None

    if isinstance(item_ids, list):
        if not item_ids:
            return None

        start_index = int(data.get("StartIndex", 0))
        if 0 <= start_index < len(item_ids):
            return str(item_ids[start_index])

        return str(item_ids[0])

    return str(item_ids)


def is_same_media_item_request(
    current_data: dict[str, Any] | None,
    next_data: dict[str, Any] | None,
) -> bool:
    current_item_id = playback_request_media_item_id(current_data)
    next_item_id = playback_request_media_item_id(next_data)
    return current_item_id is not None and current_item_id == next_item_id


def find_monitored_session(
    sessions: list[dict[str, Any]],
    monitored_device_id: str,
) -> dict[str, Any] | None:
    for session in sessions:
        if session.get("DeviceId") == monitored_device_id:
            return session

    return None


def build_playback_intent_from_session(
    session: dict[str, Any],
    *,
    monitored_device_id: str,
    item_user_data: dict[str, Any] | None = None,
) -> PlaybackIntent | None:
    now_playing = session.get("NowPlayingItem")
    if not now_playing:
        return None

    play_state = session.get("PlayState") or {}
    start_position_ticks = play_state.get("PositionTicks")
    if start_position_ticks is None:
        start_position_ticks = (item_user_data or {}).get("PlaybackPositionTicks", 0)

    return PlaybackIntent(
        media_item_id=str(now_playing["Id"]),
        media_source_id=play_state.get("MediaSourceId", ""),
        source_user_id=session.get("UserId", ""),
        source_client_session_id=session.get("Id"),
        source_device_id=monitored_device_id,
        source_device_name=session.get("DeviceName", ""),
        start_position_seconds=_ticks_to_seconds(start_position_ticks),
        selected_audio_track_id=int(play_state.get("AudioStreamIndex", 1)),
        selected_subtitle_track_id=int(play_state.get("SubtitleStreamIndex", -1)),
    )


def playback_intent_to_legacy_payload(intent: PlaybackIntent) -> dict[str, Any]:
    return {
        "ItemIds": [int(intent.media_item_id)],
        "StartIndex": 0,
        "MediaSourceId": intent.media_source_id,
        "AudioStreamIndex": intent.selected_audio_track_id,
        "SubtitleStreamIndex": intent.selected_subtitle_track_id,
        "ControllingUserId": intent.source_user_id,
        "SessionID": intent.source_client_session_id,
        "DeviceName": intent.source_device_name,
        "Device_Id": intent.source_device_id,
        "StartPositionTicks": intent.start_position_seconds * EMBY_TICKS_PER_SECOND,
    }


def _ticks_to_seconds(value: Any) -> int:
    return int(value or 0) // EMBY_TICKS_PER_SECOND
