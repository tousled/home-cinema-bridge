from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from home_cinema_bridge.devices.oppo.playback_command_control import (
    OppoPlaybackCommandControl,
)
from home_cinema_bridge.media_servers.emby.playback_request import (
    parse_playback_request_payload,
)
from home_cinema_bridge.playback.intent import PlaybackOrigin


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
        oppo_control_factory: Callable[
            [dict[str, Any]], OppoPlaybackCommandControl
        ] = OppoPlaybackCommandControl,
    ) -> None:
        self._emby_session = emby_session
        self._config_provider = config_provider
        self._playback_intent_dispatcher_factory = playback_intent_dispatcher_factory
        self._oppo_control_factory = oppo_control_factory

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
            params = self._current_playback_request_params()
            audio_index = self._emby_session.get_xnoppo_audio_index(
                params["ControllingUserId"],
                params["item_id"],
                int(args["Index"]),
            )
            self._oppo_control.select_audio_track(audio_index)
            self._emby_session.currentdata["AudioStreamIndex"] = int(args["Index"])
            return

        if command == "SetSubtitleStreamIndex":
            params = self._current_playback_request_params()
            subtitle_index = self._emby_session.get_xnoppo_subs_index(
                params["ControllingUserId"],
                params["item_id"],
                int(args["Index"]),
            )
            self._oppo_control.select_subtitle_track(subtitle_index)
            self._emby_session.currentdata["SubtitleStreamIndex"] = int(args["Index"])

    def handle_playback_state(self, data: dict) -> None:
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

        self._oppo_control.send_remote_key(remote_key)

    def _seek_to_absolute_position(self, data: dict) -> None:
        position_ticks = int(data["SeekPositionTicks"])
        logging.info(
            "Seeking OPPO playback to absolute media-server position | "
            "position_ticks=%s",
            position_ticks,
        )
        self._oppo_control.seek_to_position_ticks(position_ticks)

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
        self._oppo_control.seek_to_position_ticks(target_ticks)

    def _current_oppo_position_ticks(self) -> int:
        return self._oppo_control.current_position_ticks()

    def _current_playback_request_params(self) -> dict[str, Any]:
        return parse_playback_request_payload(
            self._emby_session.currentdata,
            config=self._config,
            load_item_info=self._emby_session.get_item_info,
        )

    @property
    def _config(self) -> dict[str, Any]:
        return self._config_provider()

    @property
    def _oppo_control(self) -> OppoPlaybackCommandControl:
        return self._oppo_control_factory(self._config)


def _remote_key_for_playstate_command(command: str) -> str | None:
    return {
        "Stop": "STP",
        "Pause": "PAU",
        "Unpause": "PLA",
        "NextTrack": "NXT",
        "PreviousTrack": "PRE",
        "PlayPause": "PAU",
    }.get(command)
