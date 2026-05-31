from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from home_cinema_bridge.playback.intent import PlaybackOrigin

from lib.oppo_control import (
    getplayingtime,
    sendremotekey,
    setaudiotrack,
    setplaytime,
    set_subtitles_track,
)


MEDIA_SERVER_TICKS_PER_SECOND = 10_000_000
DEFAULT_REMOTE_SKIP_SECONDS = 10


class EmbyPlaybackCommandHandler:
    """Translate Emby playback commands into bridge playback actions."""

    def __init__(
        self,
        *,
        emby_session,
        config_provider: Callable[[], dict[str, Any]],
        playback_intent_dispatcher_factory: Callable,
        send_remote_key=sendremotekey,
        set_audio_track=setaudiotrack,
        set_play_time=setplaytime,
        set_subtitle_track=set_subtitles_track,
        get_playing_time=getplayingtime,
    ) -> None:
        self._emby_session = emby_session
        self._config_provider = config_provider
        self._playback_intent_dispatcher_factory = playback_intent_dispatcher_factory
        self._send_remote_key = send_remote_key
        self._set_audio_track = set_audio_track
        self._set_play_time = set_play_time
        self._set_subtitle_track = set_subtitle_track
        self._get_playing_time = get_playing_time

    def handle_play(self, data: dict) -> None:
        command = data["PlayCommand"]
        if command != "PlayNow":
            return

        logging.info(
            "Emby websocket play command | command=%s | item_ids=%s | "
            "start_position_present=%s | start_position_ticks=%s | "
            "saved_position_ticks=%s | media_source_id=%s | "
            "audio_stream_index=%s | subtitle_stream_index=%s | "
            "device=%s",
            command,
            data.get("ItemIds"),
            "StartPositionTicks" in data,
            data.get("StartPositionTicks"),
            data.get("SavedPlaybackPositionTicks"),
            data.get("MediaSourceId"),
            data.get("AudioStreamIndex"),
            data.get("SubtitleStreamIndex"),
            data.get("DeviceName"),
        )
        self._playback_intent_dispatcher_factory().dispatch_legacy_payload(
            data,
            origin=PlaybackOrigin.REMOTE_CONTROL_COMMAND,
        )

    def handle_general_command(self, data: dict) -> None:
        command = data["Name"]
        args = data["Arguments"]

        if command == "SetAudioStreamIndex":
            params = self._emby_session.process_data(self._emby_session.currentdata)
            audio_index = self._emby_session.get_xnoppo_audio_index(
                params["ControllingUserId"],
                params["item_id"],
                int(args["Index"]),
            )
            self._set_audio_track(self._config, audio_index)
            self._emby_session.currentdata["AudioStreamIndex"] = int(args["Index"])
            return

        if command == "SetSubtitleStreamIndex":
            params = self._emby_session.process_data(self._emby_session.currentdata)
            subtitle_index = self._emby_session.get_xnoppo_subs_index(
                params["ControllingUserId"],
                params["item_id"],
                int(args["Index"]),
            )
            self._set_subtitle_track(self._config, subtitle_index)
            self._emby_session.currentdata["SubtitleStreamIndex"] = int(args["Index"])

    def handle_playstate(self, data: dict) -> None:
        command = data["Command"]
        if command == "Seek":
            self._seek_to_absolute_position(data)
            return

        if command == "SeekRelative":
            self._seek_to_relative_position(data)
            return

        if command == "FastForward":
            self._seek_to_relative_position(
                data,
                default_relative_ticks=(
                    DEFAULT_REMOTE_SKIP_SECONDS * MEDIA_SERVER_TICKS_PER_SECOND
                ),
            )
            return

        if command == "Rewind":
            self._seek_to_relative_position(
                data,
                default_relative_ticks=(
                    -DEFAULT_REMOTE_SKIP_SECONDS * MEDIA_SERVER_TICKS_PER_SECOND
                ),
            )
            return

        remote_key = _remote_key_for_playstate_command(command)
        if remote_key is None:
            logging.debug(
                "Ignoring unsupported Emby playstate command | command=%s | data=%s",
                command,
                data,
            )
            return

        self._send_remote_key(remote_key, self._config)

    def _seek_to_absolute_position(self, data: dict) -> None:
        position_ticks = int(data["SeekPositionTicks"])
        logging.info(
            "Seeking OPPO playback to absolute media-server position | "
            "position_ticks=%s",
            position_ticks,
        )
        self._set_play_time(self._config, position_ticks)

    def _seek_to_relative_position(
        self,
        data: dict,
        *,
        default_relative_ticks: int = 0,
    ) -> None:
        relative_ticks = int(data.get("SeekPositionTicks", default_relative_ticks))
        current_ticks = self._current_oppo_position_ticks()
        target_ticks = max(0, current_ticks + relative_ticks)

        logging.info(
            "Seeking OPPO playback to relative media-server position | "
            "current_ticks=%s | relative_ticks=%s | target_ticks=%s",
            current_ticks,
            relative_ticks,
            target_ticks,
        )
        self._set_play_time(self._config, target_ticks)

    def _current_oppo_position_ticks(self) -> int:
        response_text = self._get_playing_time(self._config)
        response = json.loads(response_text)
        current_seconds = int(response.get("cur_time", 0))
        return current_seconds * MEDIA_SERVER_TICKS_PER_SECOND

    @property
    def _config(self) -> dict[str, Any]:
        return self._config_provider()


def _remote_key_for_playstate_command(command: str) -> str | None:
    return {
        "Stop": "STP",
        "Pause": "PAU",
        "Unpause": "PLA",
        "NextTrack": "NXT",
        "PreviousTrack": "PRE",
        "PlayPause": "PAU",
    }.get(command)
