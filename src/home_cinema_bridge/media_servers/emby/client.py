import hashlib
from urllib.parse import quote

from home_cinema_bridge.network.http import get_http_session


class EmbyClient:
    """Low-level HTTP client for the Emby API."""

    def __init__(
        self,
        server_url: str,
        user_name: str,
        user_password: str,
        *,
        http_session=None,
    ):
        self.server_url = server_url.rstrip("/")
        self.user_name = user_name
        self.user_password = user_password
        self._http = http_session or get_http_session("emby")
        self.user_info = None

    @classmethod
    def from_config(cls, config):
        return cls(
            server_url=config.get("emby_server", ""),
            user_name=config.get("user_name", ""),
            user_password=config.get("user_password", ""),
        )

    def authenticate(self):
        password_bytes = self.user_password.encode("utf-8")
        password_sha = hashlib.sha1(password_bytes).hexdigest()

        response = self._http.post(
            self._url("/Users/AuthenticateByName?format=json"),
            data={
                "username": quote(self.user_name),
                "password": password_sha,
                "pw": password_bytes,
            },
            headers=self.get_headers(),
        )
        self.user_info = response.json()
        return self.user_info

    def get_headers(self, user_info=None):
        auth_string = (
            'MediaBrowser Client="Emby Xnoppo",'
            'Device="Xnoppo",'
            'DeviceId="Xnoppo",'
            'Version="0.5"'
        )

        if user_info:
            auth_string += ',UserId="' + user_info["User"]["Id"] + '"'

        headers = {
            "Accept-encoding": "gzip",
            "Accept-Charset": "UTF-8,*",
            "X-Emby-Authorization": auth_string,
        }

        if user_info:
            headers["X-MediaBrowser-Token"] = user_info["AccessToken"]

        return headers

    def notify_playback_started(self, payload):
        return self.post(
            "/emby/Sessions/Playing/?format=json",
            json=payload,
        )

    def report_playback_progress(self, payload):
        return self.post(
            "/emby/Sessions/Playing/Progress?format=json",
            json=payload,
        )

    def notify_playback_stopped(self, payload):
        return self.post(
            "/emby/Sessions/Playing/Stopped?format=json",
            json=payload,
        )

    def set_item_playback_position(self, user_id, item_id, payload):
        return self.post(
            f"/Users/{user_id}/Items/{item_id}/UserData?format=json",
            data=payload,
        )

    def stop_session_playback(self, session_id, payload):
        return self.post(
            f"/emby/Sessions/{session_id}/Playing/Stop?format=json",
            data=payload,
        )

    def send_session_message(self, session_id, message, timeout):
        return self.post(
            f"/emby/Sessions/{session_id}/Message"
            f"?Text={message}&Header=Notification&TimeoutMs={timeout}",
            data={},
        )

    def set_capabilities(self, payload):
        return self.post(
            "/emby/Sessions/Capabilities/Full?format=json",
            data=payload,
        )

    def get_sessions_by_user(self, user_id):
        return self.get_json(f"/emby/Sessions?ControllableByUserId={user_id}")

    def get_sessions_by_user_and_device(self, user_id, device_id):
        return self.get_json(
            f"/emby/Sessions?ControllableByUserId={user_id}&DeviceID={device_id}"
        )

    def get_sessions_by_device(self, device_id):
        return self.get_json(f"/emby/Sessions?DeviceId={device_id}")

    def get_item_info(self, user_id, item_id):
        return self.get_json(f"/emby/Users/{user_id}/Items/{item_id}")

    def get_item_ancestors(self, item_id):
        return self.get_json(f"/emby/Items/{item_id}/Ancestors")

    def get_user_views(self, user_id):
        return self.get_json(
            f"/emby/Users/{user_id}/Views?IncludeExternalContent=false"
        )

    def get_view_items(self, view_id):
        return self.get_json(f"/emby/Items?parentId={view_id}")

    def get_user_view_items(self, user_id, view_id, item_id):
        return self.get_json(
            f"/emby/Users/{user_id}/Items?parentId={view_id}&item_id={item_id}"
        )

    def get_devices(self):
        return self.get_json("/emby/Devices?")

    def get_selectable_media_folders(self):
        return self.get_json("/emby/Library/SelectableMediaFolders?")

    def get_text(self, path):
        response = self._http.get(
            self._url(path),
            headers=self.get_headers(self._authenticated_user_info()),
        )
        return response.text

    def get_json(self, path):
        response = self._http.get(
            self._url(path),
            headers=self.get_headers(self._authenticated_user_info()),
        )
        return response.json()

    def post(self, path, *, data=None, json=None):
        return self._http.post(
            self._url(path),
            data=data,
            json=json,
            headers=self.get_headers(self._authenticated_user_info()),
        )

    def _authenticated_user_info(self):
        if self.user_info is None:
            raise RuntimeError("EmbyClient must be authenticated before API calls.")

        return self.user_info

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path

        if not path.startswith("/"):
            path = "/" + path

        return self.server_url + path
