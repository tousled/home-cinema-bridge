from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from home_cinema_bridge.playback.startup.models import (
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
