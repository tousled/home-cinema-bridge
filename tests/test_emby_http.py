import unittest

from lib.Emby_http import EmbyHttp


class FakeResponse:
    status_code = 204
    text = ""


class RecordingEmbyClient:
    def __init__(self):
        self.calls = []

    def stop_session_playback(self, session_id, payload):
        self.calls.append(("stop_session_playback", session_id, payload))
        return FakeResponse()


class EmbyHttpTest(unittest.TestCase):
    def test_playback_stop_does_not_send_seek_to_zero(self):
        emby_session = _legacy_emby_session()

        emby_session.playback_stop("session-1")

        self.assertEqual(
            [("stop_session_playback", "session-1", {"Command": "Stop"})],
            emby_session.client.calls,
        )


def _legacy_emby_session():
    emby_session = object.__new__(EmbyHttp)
    emby_session.config = {"DebugLevel": 0}
    emby_session.user_info = {"User": {"Id": "auth-user"}}
    emby_session.client = RecordingEmbyClient()
    return emby_session


if __name__ == "__main__":
    unittest.main()
