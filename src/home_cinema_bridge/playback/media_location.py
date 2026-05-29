from __future__ import annotations

from collections.abc import Mapping, Sequence

from home_cinema_bridge.playback.startup.models import PlayerMediaFileLocation


class PlayerMediaFileLocationError(ValueError):
    pass


def resolve_player_media_file_location(
    *,
    emby_media_path: str,
    playback_file_format: str,
    path_mappings: Sequence[Mapping[str, str]],
) -> PlayerMediaFileLocation:
    player_path = _apply_path_mappings(emby_media_path, path_mappings)
    player_path = _normalize_path_separators(player_path)

    return _parse_player_media_file_location(
        player_path=player_path,
        playback_file_format=playback_file_format,
    )


def _apply_path_mappings(
    media_path: str,
    path_mappings: Sequence[Mapping[str, str]],
) -> str:
    player_path = media_path

    for mapping in path_mappings:
        emby_path = mapping["Emby_Path"]
        player_path = player_path.replace(emby_path, mapping["Oppo_Path"])

    return player_path


def _normalize_path_separators(path: str) -> str:
    return path.replace("\\\\", "\\").replace("\\", "/")


def _parse_player_media_file_location(
    *,
    player_path: str,
    playback_file_format: str,
) -> PlayerMediaFileLocation:
    path_parts = player_path.strip("/").split("/")

    if len(path_parts) < 3:
        raise PlayerMediaFileLocationError(
            f"Player media path must include server, folder and file: {player_path}"
        )

    content_server = path_parts[0]
    content_directory = "/".join(path_parts[1:-1])
    playback_file_name = path_parts[-1]

    if not content_server or not content_directory or not playback_file_name:
        raise PlayerMediaFileLocationError(
            f"Player media path must include server, folder and file: {player_path}"
        )

    return PlayerMediaFileLocation(
        content_server=content_server,
        content_directory=content_directory,
        playback_file_name=playback_file_name,
        playback_file_format=playback_file_format,
    )
