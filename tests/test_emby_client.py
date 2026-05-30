import unittest

from home_cinema_bridge.media_servers.emby import EmbyClient


class FakeResponse:
    def __init__(self, *, text="", json_data=None, status_code=200):
        self.text = text
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data


class RecordingHttpSession:
    def __init__(self):
        self.calls = []

    def post(self, url, *, data=None, json=None, headers=None):
        self.calls.append(("post", url, data, json, headers))
        return FakeResponse(json_data={"AccessToken": "token", "User": {"Id": "user1"}})

    def get(self, url, *, headers=None):
        self.calls.append(("get", url, headers))
        return FakeResponse(text='{"ok":true}', json_data={"ok": True})


class EmbyClientTest(unittest.TestCase):
    def test_authenticate_uses_emby_auth_endpoint_and_stores_user_info(self):
        http = RecordingHttpSession()
        client = EmbyClient(
            "http://emby.local:8096",
            "pedro",
            "secret",
            http_session=http,
        )

        user_info = client.authenticate()

        method, url, data, json_payload, headers = http.calls[0]
        self.assertEqual("post", method)
        self.assertEqual(
            "http://emby.local:8096/Users/AuthenticateByName?format=json",
            url,
        )
        self.assertEqual("pedro", data["username"])
        self.assertEqual(b"secret", data["pw"])
        self.assertIsNone(json_payload)
        self.assertIn("X-Emby-Authorization", headers)
        self.assertEqual(user_info, client.user_info)

    def test_playback_started_posts_json_payload(self):
        http = RecordingHttpSession()
        client = EmbyClient(
            "http://emby.local:8096/",
            "pedro",
            "secret",
            http_session=http,
        )
        client.user_info = {"AccessToken": "token", "User": {"Id": "user1"}}

        client.notify_playback_started({"ItemId": "movie1"})

        method, url, data, json_payload, headers = http.calls[0]
        self.assertEqual("post", method)
        self.assertEqual(
            "http://emby.local:8096/emby/Sessions/Playing/?format=json",
            url,
        )
        self.assertIsNone(data)
        self.assertEqual({"ItemId": "movie1"}, json_payload)
        self.assertEqual("token", headers["X-MediaBrowser-Token"])

    def test_playback_progress_posts_json_payload(self):
        http = RecordingHttpSession()
        client = EmbyClient(
            "http://emby.local:8096/",
            "pedro",
            "secret",
            http_session=http,
        )
        client.user_info = {"AccessToken": "token", "User": {"Id": "user1"}}

        client.report_playback_progress({"ItemId": "movie1"})

        method, url, data, json_payload, headers = http.calls[0]
        self.assertEqual("post", method)
        self.assertEqual(
            "http://emby.local:8096/emby/Sessions/Playing/Progress?format=json",
            url,
        )
        self.assertIsNone(data)
        self.assertEqual({"ItemId": "movie1"}, json_payload)
        self.assertEqual("token", headers["X-MediaBrowser-Token"])

    def test_playback_stopped_posts_json_payload(self):
        http = RecordingHttpSession()
        client = EmbyClient(
            "http://emby.local:8096/",
            "pedro",
            "secret",
            http_session=http,
        )
        client.user_info = {"AccessToken": "token", "User": {"Id": "user1"}}

        client.notify_playback_stopped({"ItemId": "movie1"})

        method, url, data, json_payload, headers = http.calls[0]
        self.assertEqual("post", method)
        self.assertEqual(
            "http://emby.local:8096/emby/Sessions/Playing/Stopped?format=json",
            url,
        )
        self.assertIsNone(data)
        self.assertEqual({"ItemId": "movie1"}, json_payload)
        self.assertEqual("token", headers["X-MediaBrowser-Token"])

    def test_accepts_absolute_url_for_legacy_callers(self):
        http = RecordingHttpSession()
        client = EmbyClient(
            "http://emby.local:8096",
            "pedro",
            "secret",
            http_session=http,
        )
        client.user_info = {"AccessToken": "token", "User": {"Id": "user1"}}

        text = client.get_text("http://emby.local:8096/emby/Devices?")

        method, url, headers = http.calls[0]
        self.assertEqual("get", method)
        self.assertEqual("http://emby.local:8096/emby/Devices?", url)
        self.assertEqual("token", headers["X-MediaBrowser-Token"])
        self.assertEqual('{"ok":true}', text)


if __name__ == "__main__":
    unittest.main()
