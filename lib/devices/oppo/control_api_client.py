import logging
import urllib.parse
from dataclasses import dataclass

import requests


OPPO_HTTP_PORT = 436


@dataclass(frozen=True)
class OppoControlApiClient:
    host: str
    port: int = OPPO_HTTP_PORT

    @classmethod
    def from_config(cls, config: dict) -> "OppoControlApiClient":
        return cls(
            host=str(config["Oppo_IP"]),
            port=int(config.get("OPPO_HTTP_Port", OPPO_HTTP_PORT)),
        )

    def get_main_firmware_version(self) -> str:
        return self._get_text("getmainfirmwareversion")

    def get_setup_menu(self) -> str:
        return self._get_text("getsetupmenu")

    def sign_in(self, app_ip_address: str = "192.168.1.135") -> str:
        # Keep the legacy payload shape for now. The hardcoded IP already existed in Xnoppo.py.
        payload = urllib.parse.quote(
            f'{{"appIconType":1,"appIpAddress":"{app_ip_address}"}}'
        )
        return self._get_text("signin", payload)

    def get_device_list(self) -> str:
        return self._get_text("getdevicelist")

    def get_global_info(self) -> str:
        return self._get_text("getglobalinfo")

    def get_playing_time(self) -> str:
        return self._get_text("getplayingtime")

    def login_nfs_server(self, server: str) -> str:
        payload = f'{{"serverName":"{server}"}}'
        return self._get_text("loginNfsServer", payload)

    def login_samba_without_id(self, server: str) -> str:
        payload = f'{{"serverName":"{server}"}}'
        return self._get_text("loginSambaWithOutID", payload)

    def mount_samba_folder_with_id(
        self,
        server: str,
        folder: str,
        username: str,
        password: str,
        *,
        timeout: int | float,
    ) -> str:
        payload = (
            f'{{"server":"{server}",'
            f'"bWithID":1,'
            f'"folder":"{urllib.parse.quote(folder)}",'
            f'"userName":"{username}",'
            f'"password":"{password}",'
            f'"bRememberID":1}}'
        )

        return self._get_text_or_error(
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
        payload = (
            f'{{"server":"{server}",'
            f'"bWithID":0,'
            f'"folder":"{urllib.parse.quote(folder)}",'
            f'"userName":"",'
            f'"password":"",'
            f'"bRememberID":0}}'
        )

        return self._get_text_or_error(
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
        payload = (
            f'{{"server":"{server}",'
            f'"folder":"{urllib.parse.quote(folder)}"}}'
        )

        response_text = self._get_text_or_error(
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
        server: str,
        filename: str,
        index: str,
        *,
        nfs: bool,
        timeout: int | float,
    ) -> str:
        mount_prefix = "/mnt/nfs1" if nfs else "/mnt/cifs1"

        payload = urllib.parse.quote(
            f'"path":"{mount_prefix}/{filename}",'
            f'"index":{index},'
            f'"type":1,'
            f'"appDeviceType":2,'
            f'"extraNetPath":"{server}",'
            f'"playMode":0'
        )

        return self._get_text_or_error(
            "playnormalfile",
            f"{{{payload}}}",
            timeout=timeout,
            error='{"success":false,"retInfo":"Timeout in Play Request"}',
        )

    def check_folder_has_bdmv(
        self,
        folder: str,
        *,
        nfs: bool,
        timeout: int | float,
    ) -> str:
        mount_prefix = "/mnt/nfs1" if nfs else "/mnt/cifs1"
        payload = f'{{"folderpath":"{mount_prefix}/{urllib.parse.quote(folder)}"}}'

        return self._get_text_or_error(
            "checkfolderhasBDMV",
            payload,
            timeout=timeout,
            error='{"success":false,"retInfo":"Timeout in Play Request"}',
        )

    def _get_text(
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

    def _get_text_or_error(
        self,
        endpoint: str,
        query: str,
        *,
        timeout: int | float,
        error: str,
    ) -> str:
        try:
            return self._get_text(endpoint, query, timeout=timeout)
        except requests.RequestException:
            return error

    def _build_url(self, endpoint: str, query: str | None = None) -> str:
        url = f"http://{self.host}:{self.port}/{endpoint}"

        if query is not None:
            url = f"{url}?{query}"

        return url
