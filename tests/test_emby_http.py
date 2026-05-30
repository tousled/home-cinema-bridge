import unittest

from lib.Emby_http import EmbyHttp


class FakeResponse:
    status_code = 204
    text = ""


class RecordingEmbyClient:
    def __init__(self):
        self.calls = []

    def set_item_playback_position(self, user_id, item_id, payload):
        self.calls.append(("set_item_playback_position", user_id, item_id, payload))
        return FakeResponse()

    def stop_session_playback(self, session_id, payload):
        self.calls.append(("stop_session_playback", session_id, payload))
        return FakeResponse()


class EmbyHttpTest(unittest.TestCase):
    def test_setitemplaybackposition_uses_controlling_user_id(self):
        emby_session = _legacy_emby_session()

        emby_session.setitemplaybackposition(
            {
                "ItemIds": ["3092"],
                "StartPositionTicks": 0,
                "ControllingUserId": "tv-user",
            },
            270_000_000,
            False,
        )

        self.assertEqual(
            [
                (
                    "set_item_playback_position",
                    "tv-user",
                    "3092",
                    {"played": False, "PlaybackPositionTicks": 270_000_000},
                )
            ],
            emby_session.client.calls,
        )

    def test_setitemplaybackposition_falls_back_to_authenticated_user(self):
        emby_session = _legacy_emby_session()

        emby_session.setitemplaybackposition(
            {
                "ItemIds": ["3092"],
                "StartPositionTicks": 0,
            },
            270_000_000,
            False,
        )

        self.assertEqual("auth-user", emby_session.client.calls[0][1])

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
