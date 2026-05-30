import json
import unittest
import urllib.parse

from lib.devices.oppo.control_api_client import (
    OppoControlApiClient,
    extract_host_from_url,
)


class RecordingOppoControlApiClient(OppoControlApiClient):
    def _call_player_endpoint(self, endpoint, query=None, *, timeout=None):
        object.__setattr__(self, "last_endpoint", endpoint)
        object.__setattr__(self, "last_query", query)
        return "OK"


class OppoControlApiClientTest(unittest.TestCase):
    def test_extracts_host_from_emby_url_with_port(self):
        self.assertEqual(
            "192.168.50.110",
            extract_host_from_url("http://192.168.50.110:8096"),
        )

    def test_extracts_host_from_url_without_scheme(self):
        self.assertEqual(
            "emby.local",
            extract_host_from_url("emby.local:8096"),
        )

    def test_sign_in_uses_host_from_configured_emby_server(self):
        client = RecordingOppoControlApiClient(
            player_host="192.168.50.35",
            media_server_host=extract_host_from_url("http://192.168.50.110:8096"),
        )

        response = client.sign_in()
        payload = json.loads(urllib.parse.unquote(client.last_query))

        self.assertEqual("OK", response)
        self.assertEqual("signin", client.last_endpoint)
        self.assertEqual(
            {
                "appIconType": 1,
                "appIpAddress": "192.168.50.110",
            },
            payload,
        )

    def test_from_config_uses_emby_server_host_as_app_ip_address(self):
        client = OppoControlApiClient.from_config(
            {
                "Oppo_IP": "192.168.50.35",
                "emby_server": "http://192.168.50.110:8096",
            }
        )

        self.assertEqual("192.168.50.35", client.player_host)
        self.assertEqual("192.168.50.110", client.media_server_host)

    def test_set_play_time_uses_media_control_endpoint_payload(self):
        client = RecordingOppoControlApiClient(player_host="192.168.50.35")

        response = client.set_play_time(3_723_000_0000)

        self.assertEqual("OK", response)
        self.assertEqual("setplaytime", client.last_endpoint)
        self.assertEqual(
            {
                "h": 1,
                "m": 2,
                "s": 3,
            },
            json.loads(client.last_query),
        )

    def test_select_audio_track_uses_media_control_endpoint_payload(self):
        client = RecordingOppoControlApiClient(player_host="192.168.50.35")

        response = client.select_audio_track(2)

        self.assertEqual("OK", response)
        self.assertEqual("setaudiomenulist", client.last_endpoint)
        self.assertEqual({"cur_index": 2}, json.loads(client.last_query))

    def test_select_subtitle_track_uses_media_control_endpoint_payload(self):
        client = RecordingOppoControlApiClient(player_host="192.168.50.35")

        response = client.select_subtitle_track(1)

        self.assertEqual("OK", response)
        self.assertEqual("setsubttmenulist", client.last_endpoint)
        self.assertEqual({"cur_index": 1}, json.loads(client.last_query))

    def test_get_subtitle_menu_uses_media_control_endpoint(self):
        client = RecordingOppoControlApiClient(player_host="192.168.50.35")

        response = client.get_subtitle_menu()

        self.assertEqual("OK", response)
        self.assertEqual("getsubtitlemenulist", client.last_endpoint)
        self.assertEqual("", client.last_query)


if __name__ == "__main__":
    unittest.main()
