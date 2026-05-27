import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

import requests

from lib.devices.oppo.control_api_client import OppoControlApiClient
from lib.devices.oppo.mounted_share import (
    OppoMountedShare,
    parse_mounted_share_response,
)


class OppoNetworkFolderProtocol(StrEnum):
    NFS = "nfs"
    CIFS = "cifs"

    @classmethod
    def from_device_type(cls, device_type: str) -> "OppoNetworkFolderProtocol":
        if device_type.lower() == cls.NFS.value:
            return cls.NFS

        return cls.CIFS


@dataclass(frozen=True)
class OppoNetworkFolder:
    server_name: str
    folder_path: str
    protocol: OppoNetworkFolderProtocol

    @property
    def is_nfs(self) -> bool:
        return self.protocol == OppoNetworkFolderProtocol.NFS


@dataclass(frozen=True)
class OppoCommandResponse:
    raw_text: str
    payload: Mapping[str, object]
    parse_error: str = ""

    @classmethod
    def from_text(cls, response_text: str) -> "OppoCommandResponse":
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            return cls(
                raw_text=response_text,
                payload={},
                parse_error=f"{type(exc).__name__}: {exc}",
            )

        if not isinstance(payload, dict):
            return cls(
                raw_text=response_text,
                payload={},
                parse_error="OPPO response was not a JSON object",
            )

        return cls(
            raw_text=response_text,
            payload=payload,
        )

    @property
    def is_successful(self) -> bool:
        return not self.parse_error and self.payload.get("success") is True

    @property
    def error_message(self) -> str:
        if self.parse_error:
            return self.parse_error

        message = self.payload.get("msg") or self.payload.get("retInfo")

        if isinstance(message, str) and message:
            return message

        return "No hay mas info"


@dataclass(frozen=True)
class OppoNetworkFolderMountResult:
    oppo_response: OppoCommandResponse
    mounted_share: OppoMountedShare | None

    @property
    def is_mounted(self) -> bool:
        return self.mounted_share is not None

    @property
    def error_message(self) -> str:
        return self.oppo_response.error_message


@dataclass(frozen=True)
class OppoPlaybackLaunchResult:
    oppo_response: OppoCommandResponse

    @classmethod
    def from_response_text(cls, response_text: str) -> "OppoPlaybackLaunchResult":
        return cls(oppo_response=OppoCommandResponse.from_text(response_text))

    @property
    def is_started(self) -> bool:
        return self.oppo_response.is_successful

    @property
    def error_message(self) -> str:
        return self.oppo_response.error_message


class OppoNetworkPlaybackStarter:
    def __init__(
        self, config: dict, control_api_client: OppoControlApiClient | None = None
    ):
        self.config = config
        self.control_api_client = (
            control_api_client or OppoControlApiClient.from_config(config)
        )

    def resolve_network_folder_protocol(
        self,
        *,
        device_list: dict,
        server_name: str,
    ) -> OppoNetworkFolderProtocol:
        default_protocol = self._default_network_folder_protocol()

        for device in device_list["devicelist"]:
            if device["name"].upper() == server_name.upper():
                return OppoNetworkFolderProtocol.from_device_type(device["sub_type"])

        return default_protocol

    def prepare_network_folder_access(self, network_folder: OppoNetworkFolder) -> None:
        if network_folder.is_nfs:
            self.login_nfs_server(network_folder.server_name)
            self._refresh_nfs_share_folder_list()
        else:
            self.login_samba_server(network_folder.server_name)
            self._refresh_samba_share_folder_list()

    def mount_network_folder(
        self, network_folder: OppoNetworkFolder
    ) -> OppoNetworkFolderMountResult:
        if network_folder.is_nfs:
            response_text = self.control_api_client.mount_nfs_folder(
                server=network_folder.server_name,
                folder=network_folder.folder_path,
                timeout=self.config["timeout_oppo_mount"],
            )
        else:
            if self.config["smbtrick"] is True:
                self.prime_samba_mount(network_folder)

            response_text = self.control_api_client.mount_samba_folder(
                server=network_folder.server_name,
                folder=network_folder.folder_path,
                timeout=self.config["timeout_oppo_mount"],
            )

        response, mounted_share = parse_mounted_share_response(
            response_text,
            server=network_folder.server_name,
            folder=network_folder.folder_path,
            is_nfs=network_folder.is_nfs,
        )

        return OppoNetworkFolderMountResult(
            oppo_response=OppoCommandResponse.from_text(json.dumps(response)),
            mounted_share=mounted_share,
        )

    def start_playback(
        self,
        *,
        mounted_share: OppoMountedShare,
        filename: str,
        container: str,
    ) -> OppoPlaybackLaunchResult:
        if container == "bluray":
            response_text = (
                self.control_api_client.mounted_folder_contains_blu_ray_structure(
                    mounted_share=mounted_share,
                    relative_folder_path=filename,
                    timeout=self.config["timeout_oppo_playitem"],
                )
            )
        else:
            response_text = self.control_api_client.play_normal_file(
                mounted_share=mounted_share,
                filename=filename,
                index="0",
                timeout=self.config["timeout_oppo_playitem"],
            )

        return OppoPlaybackLaunchResult.from_response_text(response_text)

    def _default_network_folder_protocol(self) -> OppoNetworkFolderProtocol:
        if self.config["default_nfs"]:
            return OppoNetworkFolderProtocol.NFS

        return OppoNetworkFolderProtocol.CIFS

    def login_nfs_server(self, server: str) -> str:
        logging.debug("LoginNFS")
        response_text = self.control_api_client.login_nfs_server(server)

        if self.config["DebugLevel"] == 2:
            print("*** LoginNFS Response: " + response_text)

        logging.debug("*** LoginNFS Response: %s", response_text)
        return response_text

    def login_samba_server(self, server: str) -> str:
        logging.debug("LoginSambaWithOutID")
        response_text = self.control_api_client.login_samba_without_id(server)

        if self.config["DebugLevel"] == 2:
            print("*** LoginSambaWithOutID Response: " + response_text)

        logging.debug("*** LoginSambaWithOutID Response: %s", response_text)
        return response_text

    def _refresh_nfs_share_folder_list(self) -> list[dict]:
        return self._refresh_share_folder_list("getNfsShareFolderlist")

    def _refresh_samba_share_folder_list(self) -> list[dict]:
        return self._refresh_share_folder_list("getSambaShareFolderlist")

    def _refresh_share_folder_list(self, endpoint: str) -> list[dict]:
        if self.config["DebugLevel"] == 2:
            print(f"*** {endpoint} ***")
        logging.debug("*** %s ***", endpoint)

        url = self.control_api_client._build_url(endpoint)
        logging.debug(url)

        response = requests.get(
            url,
            headers={},
            timeout=self.config.get("timeout_oppo_conection", 3),
        )
        files = parse_network_folder_list_response(response.content)

        if self.config["DebugLevel"] == 2:
            print(f"*** Fin {endpoint} ***")

        logging.debug("*** %s Response: %s", endpoint, response.text)
        return files

    def prime_samba_mount(self, network_folder: OppoNetworkFolder) -> None:
        path = f"{network_folder.server_name}/{network_folder.folder_path}"
        path = path.replace("\\\\", "\\")
        path = path.replace("\\", "/")
        path = path.replace("//", "/")

        server, folder = _parse_samba_prime_path(path)
        response_text = self.login_samba_server(server)
        response = json.loads(response_text)

        if response.get("success"):
            for share_folder in self._refresh_samba_share_folder_list():
                folder_name = share_folder["Foldername"]

                if folder_name != ".." and folder_name.upper() != folder.upper():
                    self.control_api_client.mount_samba_folder(
                        server=server,
                        folder=folder_name,
                        timeout=self.config["timeout_oppo_mount"],
                    )

                    if self.config["DebugLevel"] > 0:
                        print(server + "-" + folder_name)

                    return

        device_list = json.loads(self.control_api_client.get_device_list())

        for device in device_list["devicelist"]:
            if device["name"].upper() == server.upper():
                continue

            if device["sub_type"] != OppoNetworkFolderProtocol.CIFS.value:
                continue

            self.login_samba_server(device["name"])

            for share_folder in self._refresh_samba_share_folder_list():
                folder_name = share_folder["Foldername"]

                if folder_name != "..":
                    self.control_api_client.mount_samba_folder(
                        server=device["name"],
                        folder=folder_name,
                        timeout=self.config["timeout_oppo_mount"],
                    )
                    return


def parse_network_folder_list_response(response_content: bytes) -> list[dict]:
    chunks = response_content.rsplit(b"\x01")
    files = [{"Id": 0, "Foldername": ".."}]
    file_id = 1

    for chunk in chunks:
        if chunk.find(b"\x02") != -1:
            continue

        folder_name = _extract_share_folder_name(chunk)

        if folder_name:
            files.append({"Id": file_id, "Foldername": folder_name})
            file_id += 1

    return files


def _extract_share_folder_name(chunk: bytes) -> str:
    index = 0
    last_offset = 0
    folder_data = chunk

    while index != -1:
        index = chunk.find(b"\x00", index)

        if index == -1:
            folder_data = folder_data[last_offset:]
        else:
            last_offset = index + 1
            index += 1

    return folder_data.decode("utf-8")


def _parse_samba_prime_path(path: str) -> tuple[str, str]:
    path_parts = path.strip("/").split("/", 2)

    if len(path_parts) < 2:
        return path_parts[0], ""

    return path_parts[0], path_parts[1]
