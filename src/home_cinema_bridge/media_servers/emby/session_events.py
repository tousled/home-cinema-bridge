from __future__ import annotations

from typing import Any


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
