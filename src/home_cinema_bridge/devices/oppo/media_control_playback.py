from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from home_cinema_bridge.playback.startup.models import (
    DeviceCommandResult,
    OppoPlaybackPosition,
    OppoPlaybackStartRequest,
    OppoPlaybackStartResult,
    OppoPlaybackState,
)
from lib.devices.oppo.control_api_client import OppoControlApiClient
from lib.devices.oppo.mounted_share import parse_mounted_share_response
from lib.devices.oppo.playback_state_waiter import (
    PlaybackStartupWaitResult,
    wait_until_oppo_reports_active_playback,
)

logger = logging.getLogger(__name__)


class OppoNetworkProtocol(StrEnum):
    NFS = "nfs"
    CIFS = "cifs"

    @classmethod
    def from_device_sub_type(cls, sub_type: str) -> "OppoNetworkProtocol":
        if sub_type.lower() == cls.NFS:
            return cls.NFS

        return cls.CIFS


@dataclass(frozen=True)
class OppoNetworkFolder:
    media_server: str
    folder: str
    protocol: OppoNetworkProtocol

    @property
    def is_nfs(self) -> bool:
        return self.protocol == OppoNetworkProtocol.NFS


class OppoMediaControlPlayback:
    def __init__(
        self,
        config: dict[str, Any],
        *,
        client: OppoControlApiClient | None = None,
        playback_state_waiter: Callable[..., PlaybackStartupWaitResult]
        | None = None,
    ) -> None:
        self._config = config
        self._client = client or OppoControlApiClient.from_config(config)
        self._playback_state_waiter = (
            playback_state_waiter or wait_until_oppo_reports_active_playback
        )

    def start_playback(
        self,
        request: OppoPlaybackStartRequest,
        *,
        on_waiting: Callable[[int], None] | None = None,
    ) -> OppoPlaybackStartResult:
        try:
            self._client.sign_in()

            location = request.media_location
            device_list = json.loads(self._client.get_device_list())
            network_folder = OppoNetworkFolder(
                media_server=location.content_server,
                folder=location.content_directory,
                protocol=self._resolve_network_protocol(
                    device_list=device_list,
                    media_server=location.content_server,
                ),
            )

            self._login_network_server(network_folder)
            mount_response_text = self._mount_network_folder(network_folder)
            logger.info(
                "OPPO MediaControl mount response | server=%s | folder=%s | response=%s",
                network_folder.media_server,
                network_folder.folder,
                mount_response_text,
            )
            mount_response, mounted_share = parse_mounted_share_response(
                mount_response_text,
                server=network_folder.media_server,
                folder=network_folder.folder,
                is_nfs=network_folder.is_nfs,
            )

            if mounted_share is None:
                return OppoPlaybackStartResult(
                    media_mounted=False,
                    playback_command_accepted=False,
                    playback_started_on_device=False,
                    detail=_response_error_message(mount_response),
                )

            playback_response = self._start_mounted_share_playback(
                request=request,
                mounted_share=mounted_share,
            )
            logger.info(
                "OPPO MediaControl playback command response | mounted_path=%s | filename=%s | response=%s",
                mounted_share.mount_path,
                location.playback_file_name,
                playback_response,
            )

            if not playback_response.get("success"):
                return OppoPlaybackStartResult(
                    media_mounted=True,
                    playback_command_accepted=False,
                    playback_started_on_device=False,
                    detail=_response_error_message(playback_response),
                    mounted_path=mounted_share.mount_path,
                )

            startup_result = self._playback_state_waiter(
                config=self._config,
                timeout=request.startup_timeout_seconds,
                interval=request.poll_interval_seconds,
                on_playback_waiting=on_waiting,
            )

            playback_state = OppoPlaybackState(
                status=startup_result.status,
                category=startup_result.category,
                raw_response=startup_result.raw_response,
                ok=startup_result.raw_response.startswith("@OK"),
            )

            return OppoPlaybackStartResult(
                media_mounted=True,
                playback_command_accepted=True,
                playback_started_on_device=startup_result.started,
                detail=None
                if startup_result.started
                else "Timed out waiting for OPPO active playback.",
                mounted_path=mounted_share.mount_path,
                playback_state=playback_state,
            )
        except Exception as exc:
            logger.exception("OPPO MediaControl playback startup failed.")
            return OppoPlaybackStartResult(
                media_mounted=False,
                playback_command_accepted=False,
                playback_started_on_device=False,
                detail=(
                    "OPPO MediaControl playback startup failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

    def get_playback_position(self) -> OppoPlaybackPosition:
        response_text = self._client.get_playing_time()
        response = json.loads(response_text)

        return OppoPlaybackPosition(
            current_seconds=int(response.get("cur_time", 0)),
            total_seconds=int(response.get("total_time", 0)),
            raw_response=response_text,
        )

    def seek_to(self, position_ticks: int) -> DeviceCommandResult:
        try:
            response_text = self._client.set_play_time(position_ticks)
            return _command_sent_result("set OPPO playback time", response_text)
        except Exception as exc:
            logger.exception("OPPO seek failed.")
            return DeviceCommandResult.failed(
                f"OPPO seek failed: {type(exc).__name__}: {exc}"
            )

    def select_audio_track(self, audio_index: int) -> DeviceCommandResult:
        try:
            response_text = self._client.select_audio_track(audio_index)
            return _command_sent_result("select OPPO audio track", response_text)
        except Exception as exc:
            logger.exception("OPPO audio track selection failed.")
            return DeviceCommandResult.failed(
                f"OPPO audio track selection failed: {type(exc).__name__}: {exc}"
            )

    def select_subtitle_track(self, subtitle_index: int) -> DeviceCommandResult:
        try:
            current_track = self.get_current_subtitle_track()
            attempts = 0
            response_text = ""

            while current_track != subtitle_index and attempts < 10:
                response_text = self._client.select_subtitle_track(subtitle_index)
                time.sleep(1)
                current_track = self.get_current_subtitle_track()
                attempts += 1

            if current_track == subtitle_index:
                return DeviceCommandResult.success(
                    f"OPPO subtitle track selected: {subtitle_index}"
                )

            return _command_sent_result(
                "select OPPO subtitle track",
                response_text,
            )
        except Exception as exc:
            logger.exception("OPPO subtitle track selection failed.")
            return DeviceCommandResult.failed(
                f"OPPO subtitle track selection failed: {type(exc).__name__}: {exc}"
            )

    def get_current_subtitle_track(self) -> int:
        response_text = self._client.get_subtitle_menu()
        response = json.loads(response_text)

        for subtitle in response.get("subtitle_list", []):
            if subtitle.get("selected") is True:
                return int(subtitle.get("index", 0))

        return 0

    def _resolve_network_protocol(
        self,
        *,
        device_list: dict[str, Any],
        media_server: str,
    ) -> OppoNetworkProtocol:
        for device in device_list.get("devicelist", []):
            if str(device.get("name", "")).upper() == media_server.upper():
                return OppoNetworkProtocol.from_device_sub_type(
                    str(device.get("sub_type", ""))
                )

        if self._config.get("default_nfs") is True:
            return OppoNetworkProtocol.NFS

        return OppoNetworkProtocol.CIFS

    def _login_network_server(self, network_folder: OppoNetworkFolder) -> None:
        if network_folder.is_nfs:
            self._client.login_nfs_server(network_folder.media_server)
            return

        self._client.login_samba_without_id(network_folder.media_server)

    def _mount_network_folder(self, network_folder: OppoNetworkFolder) -> str:
        timeout = self._config["timeout_oppo_mount"]

        if network_folder.is_nfs:
            return self._client.mount_nfs_folder(
                server=network_folder.media_server,
                folder=network_folder.folder,
                timeout=timeout,
            )

        return self._client.mount_samba_folder(
            server=network_folder.media_server,
            folder=network_folder.folder,
            timeout=timeout,
        )

    def _start_mounted_share_playback(self, *, request, mounted_share) -> dict:
        location = request.media_location
        timeout = self._config["timeout_oppo_playitem"]

        if location.playback_file_format == "bluray":
            response_text = self._client.mounted_folder_contains_blu_ray_structure(
                mounted_share=mounted_share,
                relative_folder_path=location.playback_file_name,
                timeout=timeout,
            )
        else:
            response_text = self._client.play_normal_file(
                mounted_share=mounted_share,
                filename=location.playback_file_name,
                index="0",
                timeout=timeout,
            )

        return json.loads(response_text)


def _response_error_message(response: dict[str, Any]) -> str:
    message = response.get("msg") or response.get("retInfo")

    if isinstance(message, str) and message:
        return message

    return "No hay mas info"


def _command_sent_result(operation: str, response_text: str) -> DeviceCommandResult:
    try:
        response = json.loads(response_text)
    except json.JSONDecodeError:
        return DeviceCommandResult.success(f"{operation} response: {response_text}")

    if response.get("success") is False:
        message = response.get("msg") or response.get("retInfo") or response_text
        return DeviceCommandResult.success(
            f"{operation} command sent; OPPO returned success=false: {message}"
        )

    return DeviceCommandResult.success(f"{operation} response: {response_text}")
