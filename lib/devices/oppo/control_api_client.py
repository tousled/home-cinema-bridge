import json
import logging
import urllib.parse
from dataclasses import dataclass

import requests

from lib.devices.oppo.mounted_share import OppoMountedShare

OPPO_HTTP_PORT = 436


@dataclass(frozen=True)
class OppoControlApiClient:
    player_host: str
    player_port: int = OPPO_HTTP_PORT
    media_server_host: str | None = None

    @classmethod
    def from_config(cls, config: dict) -> "OppoControlApiClient":
        return cls(
            player_host=str(config["Oppo_IP"]),
            player_port=int(config.get("OPPO_HTTP_Port", OPPO_HTTP_PORT)),
            media_server_host=extract_host_from_url(str(config.get("emby_server", ""))),
        )

    def get_main_firmware_version(self) -> str:
        return self._call_player_endpoint("getmainfirmwareversion")

    def get_setup_menu(self) -> str:
        return self._call_player_endpoint("getsetupmenu")

    def sign_in(self, app_ip_address: str | None = None) -> str:
        effective_app_ip_address = app_ip_address or self.media_server_host or ""
        payload = urllib.parse.quote(
            json.dumps(
                {
                    "appIconType": 1,
                    "appIpAddress": effective_app_ip_address,
                },
                separators=(",", ":"),
            )
        )
        return self._call_player_endpoint("signin", payload)

    def get_device_list(self) -> str:
        return self._call_player_endpoint("getdevicelist")

    def get_global_info(self) -> str:
        return self._call_player_endpoint("getglobalinfo")

    def get_playing_time(self) -> str:
        return self._call_player_endpoint("getplayingtime")

    def set_play_time(self, position_ticks: int) -> str:
        total_seconds = int(position_ticks / 10_000_000)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        payload = json.dumps(
            {
                "h": hours,
                "m": minutes,
                "s": seconds,
            },
            separators=(",", ":"),
        )

        return self._call_player_endpoint("setplaytime", payload)

    def select_audio_track(self, audio_index: int) -> str:
        payload = json.dumps(
            {
                "cur_index": int(audio_index),
            },
            separators=(",", ":"),
        )

        return self._call_player_endpoint("setaudiomenulist", payload)

    def get_subtitle_menu(self) -> str:
        return self._call_player_endpoint("getsubtitlemenulist", "")

    def select_subtitle_track(self, subtitle_index: int) -> str:
        payload = json.dumps(
            {
                "cur_index": int(subtitle_index),
            },
            separators=(",", ":"),
        )

        return self._call_player_endpoint("setsubttmenulist", payload)

    def send_remote_key(self, key: str) -> str:
        payload = urllib.parse.quote(json.dumps({"key": key}))
        return self._call_player_endpoint("sendremotekey", payload)

    def login_nfs_server(self, server: str) -> str:
        payload = json.dumps({"serverName": server})
        return self._call_player_endpoint("loginNfsServer", payload)

    def login_samba_without_id(self, server: str) -> str:
        payload = json.dumps({"serverName": server})
        return self._call_player_endpoint("loginSambaWithOutID", payload)

    def mount_samba_folder_with_id(
        self,
        server: str,
        folder: str,
        username: str,
        password: str,
        *,
        timeout: int | float,
    ) -> str:
        payload = json.dumps(
            {
                "server": server,
                "bWithID": 1,
                "folder": urllib.parse.quote(folder),
                "userName": username,
                "password": password,
                "bRememberID": 1,
            }
        )

        return self._call_player_endpoint_or_error(
            "mountSharedFolder",
            payload,
            timeout=timeout,
            error='{"success":false,"retInfo":"Timeout in Mount Request"}',
        )

    def mount_samba_folder(
        self,
        server: str,
        folder: str,
        *,
        timeout: int | float,
    ) -> str:
        payload = json.dumps(
            {
                "server": server,
                "bWithID": 0,
                "folder": urllib.parse.quote(folder),
                "userName": "",
                "password": "",
                "bRememberID": 0,
            }
        )

        return self._call_player_endpoint_or_error(
            "mountSharedFolder",
            payload,
            timeout=timeout,
            error='{"success":false,"retInfo":"Timeout in Mount Request"}',
        )

    def mount_nfs_folder(
        self,
        server: str,
        folder: str,
        *,
        timeout: int | float,
    ) -> str:
        payload = json.dumps(
            {
                "server": server,
                "folder": urllib.parse.quote(folder),
            }
        )

        response_text = self._call_player_endpoint_or_error(
            "mountNfsSharedFolder",
            payload,
            timeout=timeout,
            error='{"success":false,"retInfo":"Timeout in Mount Request"}',
        )

        # Legacy OPPO behaviour: successful NFS mount can return "{}".
        if response_text == "{}":
            return '{"success":true,"retInfo":""}'

        return response_text

    def play_normal_file(
        self,
        mounted_share: OppoMountedShare,
        filename: str,
        index: str,
        timeout: int | float,
    ) -> str:
        file_path = f"{mounted_share.mount_path.rstrip('/')}/{filename}"

        payload = urllib.parse.quote(
            json.dumps(
                {
                    "path": file_path,
                    "index": int(index),
                    "type": 1,
                    "appDeviceType": 2,
                    "extraNetPath": mounted_share.server,
                    "playMode": 0,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

        return self._call_player_endpoint_or_error(
            "playnormalfile",
            payload,
            timeout=timeout,
            error='{"success":false,"retInfo":"Timeout in Play Request"}',
        )

    def mounted_folder_contains_blu_ray_structure(
        self,
        mounted_share: OppoMountedShare,
        relative_folder_path: str,
        *,
        timeout: int | float,
    ) -> str:
        mounted_root = mounted_share.mount_path.rstrip("/")
        relative_path = relative_folder_path.strip("/")

        encoded_relative_path = urllib.parse.quote(relative_path, safe="/")
        folder_path = (
            mounted_root
            if not encoded_relative_path
            else f"{mounted_root}/{encoded_relative_path}"
        )

        payload = json.dumps({"folderpath": folder_path})

        return self._call_player_endpoint_or_error(
            "checkfolderhasBDMV",
            payload,
            timeout=timeout,
            error='{"success":false,"retInfo":"Timeout in Play Request"}',
        )

    def _call_player_endpoint(
        self,
        endpoint: str,
        query: str | None = None,
        *,
        timeout: int | float | None = None,
    ) -> str:
        url = self._build_url(endpoint, query)
        logging.debug(url)

        response = requests.get(url, headers={}, timeout=timeout)
        return response.text

    def _call_player_endpoint_or_error(
        self,
        endpoint: str,
        query: str,
        *,
        timeout: int | float,
        error: str,
    ) -> str:
        try:
            return self._call_player_endpoint(endpoint, query, timeout=timeout)
        except requests.RequestException:
            return error

    def _build_url(self, endpoint: str, query: str | None = None) -> str:
        url = f"http://{self.player_host}:{self.player_port}/{endpoint}"

        if query is not None:
            url = f"{url}?{query}"

        return url


def extract_host_from_url(url: str) -> str:
    normalized_url = url.strip()

    if not normalized_url:
        return ""

    if "://" not in normalized_url:
        normalized_url = f"//{normalized_url}"

    parsed_url = urllib.parse.urlparse(normalized_url)
    return parsed_url.hostname or ""
