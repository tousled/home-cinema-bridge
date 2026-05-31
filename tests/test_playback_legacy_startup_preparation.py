import os
import tempfile
import unittest

from home_cinema_bridge.playback.legacy_startup_preparation import (
    build_legacy_playback_startup_context,
    prepare_legacy_playback_startup,
)


class RecordingLegacySession:
    def __init__(self, *, item_info=None, mocked_item_info=None):
        self.config = {
            "DebugLevel": 0,
            "servers": [
                {
                    "Emby_Path": "/volume1/Video",
                    "Oppo_Path": "/192.168.50.110/Video",
                }
            ],
            "wait_nfs": True,
            "Always_ON": True,
            "timeout_oppo_playitem": 30,
        }
        self.user_info = {
            "User": {"Id": "user-1"},
            "SessionInfo": {"Id": "bridge-session"},
        }
        self.item_info = item_info or {
            "Path": "/volume1/Video/Movies/Movie.mkv",
            "Container": "mkv",
            "Name": "Movie",
        }
        self.mocked_item_info = mocked_item_info or {
            "Path": "/volume1/Video/Movies/Mocked.mkv",
            "Container": "mkv",
            "Name": "Mocked",
        }
        self.loaded_items = []

    def process_data(self, payload):
        return {
            "item_id": payload["ItemIds"][0],
            "media_source_id": payload.get("MediaSourceId", ""),
            "ControllingUserId": payload.get("ControllingUserId", ""),
        }

    def get_item_info(self, user_id, item_id):
        return {
            "UserData": {"PlaybackPositionTicks": 120_000_000},
        }

    def get_item_info2(self, user_id, item_id, media_source_id):
        self.loaded_items.append((user_id, item_id, media_source_id))
        if str(item_id) == "mocked-item":
            return self.mocked_item_info

        return self.item_info


class LegacyStartupPreparationTest(unittest.TestCase):
    def test_builds_legacy_startup_context_from_payload(self):
        session = RecordingLegacySession()

        context = build_legacy_playback_startup_context(
            emby_session=session,
            playback_payload={
                "ItemIds": ["movie-1"],
                "MediaSourceId": "source-1",
                "ControllingUserId": "user-1",
            },
        )

        self.assertEqual("movie-1", context.params["item_id"])
        self.assertEqual("movie-1", context.media_server_playback_context.media_library_item_id)
        self.assertEqual(session.item_info, context.item_info)
        self.assertEqual([("user-1", "movie-1", "source-1")], session.loaded_items)

    def test_prepares_start_request_from_mocked_item_file_when_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            media_path = os.path.join(temp_dir, "Movie.mkv")
            mock_path = os.path.join(temp_dir, "Movie.txt")
            with open(mock_path, "w") as file:
                file.write("mocked-item")

            session = RecordingLegacySession(
                item_info={
                    "Path": media_path,
                    "Container": "mkv",
                    "Name": "Movie",
                },
                mocked_item_info={
                    "Path": "/volume1/Video/Movies/Mocked.mkv",
                    "Container": "mkv",
                    "Name": "Mocked",
                },
            )

            preparation = prepare_legacy_playback_startup(
                emby_session=session,
                params={"item_id": "movie-1", "media_source_id": "source-1"},
                item_info=session.item_info,
                playback_start_poll_interval=0.25,
            )

        self.assertEqual("Mocked", preparation.item_info["Name"])
        self.assertEqual("192.168.50.110", preparation.media_location.content_server)
        self.assertEqual("Video/Movies", preparation.media_location.content_directory)
        self.assertEqual("Mocked.mkv", preparation.media_location.playback_file_name)
        self.assertTrue(preparation.oppo_start_request.wait_for_nfs_share)
        self.assertEqual(0.25, preparation.oppo_start_request.poll_interval_seconds)


if __name__ == "__main__":
    unittest.main()
