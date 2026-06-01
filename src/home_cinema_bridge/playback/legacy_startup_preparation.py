from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from home_cinema_bridge.media_servers.emby import MediaServerPlaybackContext
from home_cinema_bridge.media_servers.emby.playback_request import (
    parse_playback_request_payload,
)
from home_cinema_bridge.playback.media_location import resolve_player_media_file_location
from home_cinema_bridge.playback.startup.models import (
    OppoPlaybackStartRequest,
    PlayerMediaFileLocation,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LegacyPlaybackStartupContext:
    params: dict
    media_server_playback_context: MediaServerPlaybackContext
    item_info: dict


@dataclass(frozen=True)
class LegacyPlaybackStartupPreparation:
    item_info: dict
    media_location: PlayerMediaFileLocation
    oppo_start_request: OppoPlaybackStartRequest


def build_legacy_playback_startup_context(
    *,
    emby_session,
    playback_payload: dict,
) -> LegacyPlaybackStartupContext:
    params = parse_playback_request_payload(
        playback_payload,
        config=emby_session.config,
        load_item_info=emby_session.get_item_info,
    )
    media_server_playback_context = MediaServerPlaybackContext.from_event(
        playback_payload,
        load_user_item=emby_session.get_item_info,
    )
    item_info = emby_session.get_item_info2(
        emby_session.user_info["User"]["Id"],
        params["item_id"],
        params["media_source_id"],
    )

    return LegacyPlaybackStartupContext(
        params=params,
        media_server_playback_context=media_server_playback_context,
        item_info=item_info,
    )


def prepare_legacy_playback_startup(
    *,
    emby_session,
    params: dict,
    item_info: dict,
    playback_start_poll_interval: float,
) -> LegacyPlaybackStartupPreparation:
    item_info = _resolve_mocked_item_info(emby_session, params, item_info)
    media_location = resolve_player_media_file_location(
        emby_media_path=item_info["Path"],
        playback_file_format=item_info["Container"],
        path_mappings=emby_session.config["servers"],
    )
    oppo_start_request = OppoPlaybackStartRequest(
        media_location=media_location,
        wait_for_nfs_share=emby_session.config["wait_nfs"] is True,
        assume_player_already_on=emby_session.config["Always_ON"] is True,
        startup_timeout_seconds=emby_session.config["timeout_oppo_playitem"],
        poll_interval_seconds=playback_start_poll_interval,
    )

    return LegacyPlaybackStartupPreparation(
        item_info=item_info,
        media_location=media_location,
        oppo_start_request=oppo_start_request,
    )


def _resolve_mocked_item_info(emby_session, params: dict, item_info: dict) -> dict:
    file_path = item_info["Path"]
    file_mockup = file_path[: len(file_path) - 3] + "txt"
    logger.debug("File_mockup: %s", file_mockup)

    if not os.path.isfile(file_mockup):
        return item_info

    with open(file_mockup, "r") as mocked_file:
        mocked_item_id = mocked_file.read().strip()

    if emby_session.config["DebugLevel"] > 0:
        print("File_encontrado - contenido: " + mocked_item_id)
    logger.debug("File_encontrado - contenido: %s", mocked_item_id)

    if not mocked_item_id:
        return item_info

    return emby_session.get_item_info2(
        emby_session.user_info["User"]["Id"],
        mocked_item_id,
        params["media_source_id"],
    )
