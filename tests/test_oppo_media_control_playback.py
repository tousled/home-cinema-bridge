import unittest

from home_cinema_bridge.devices.oppo.media_control_playback import (
    OppoMediaControlPlayback,
)
from home_cinema_bridge.devices.oppo.playback_state import (
    OppoPlaybackCategory,
    OppoPlaybackStatus,
)
from home_cinema_bridge.playback.startup.models import (
    OppoPlaybackStartRequest,
    PlayerMediaFileLocation,
)
from lib.devices.oppo.playback_state_waiter import PlaybackStartupWaitResult


class RecordingMediaControlClient:
    def __init__(self, *, device_sub_type="nfs"):
        self.calls = []
        self.device_sub_type = device_sub_type

    def sign_in(self):
        self.calls.append("sign_in")
        return '{"success":true}'

    def get_device_list(self):
        self.calls.append("get_device_list")
        return f'{{"devicelist":[{{"name":"NAS","sub_type":"{self.device_sub_type}"}}]}}'

    def login_nfs_server(self, server):
        self.calls.append(("login_nfs_server", server))
        return '{"success":true}'

    def login_samba_without_id(self, server):
        self.calls.append(("login_samba_without_id", server))
        return '{"success":true}'

    def mount_nfs_folder(self, *, server, folder, timeout):
        self.calls.append(("mount_nfs_folder", server, folder, timeout))
        return '{"success":true,"nfsMntPath":"/mnt/nfs1"}'

    def mount_samba_folder(self, *, server, folder, timeout):
        self.calls.append(("mount_samba_folder", server, folder, timeout))
        return '{"success":true,"cifsMntPath":"/mnt/cifs1"}'

    def play_normal_file(self, *, mounted_share, filename, index, timeout):
        self.calls.append(
            (
                "play_normal_file",
                mounted_share.mount_path,
                mounted_share.server,
                filename,
                index,
                timeout,
            )
        )
        return '{"success":true}'

    def mounted_folder_contains_blu_ray_structure(
        self, *, mounted_share, relative_folder_path, timeout
    ):
        self.calls.append(
            (
                "mounted_folder_contains_blu_ray_structure",
                mounted_share.mount_path,
                relative_folder_path,
                timeout,
            )
        )
        return '{"success":true}'

    def get_setup_menu(self):
        self.calls.append("get_setup_menu")
        return "{}"

    def send_remote_key(self, key):
        self.calls.append(("send_remote_key", key))
        return "{}"

    def get_playing_time(self):
        self.calls.append("get_playing_time")
        return '{"cur_time":12,"total_time":120}'

    def set_play_time(self, position_ticks):
        self.calls.append(("set_play_time", position_ticks))
        return '{"success":false,"msg":""}'

    def select_audio_track(self, audio_index):
        self.calls.append(("select_audio_track", audio_index))
        return '{"success":false,"msg":""}'

    def get_subtitle_menu(self):
        self.calls.append("get_subtitle_menu")
        return '{"subtitle_list":[{"index":1,"selected":true}]}'

    def select_subtitle_track(self, subtitle_index):
        self.calls.append(("select_subtitle_track", subtitle_index))
        return '{"success":true,"msg":""}'


class OppoMediaControlPlaybackTest(unittest.TestCase):
    def test_starts_nfs_playback_without_legacy_refresh_or_remote_key(self):
        client = RecordingMediaControlClient()
        playback = OppoMediaControlPlayback(
            {
                "default_nfs": True,
                "timeout_oppo_mount": 30,
                "timeout_oppo_playitem": 30,
            },
            client=client,
            playback_state_waiter=_started_playback,
        )

        result = playback.start_playback(
            OppoPlaybackStartRequest(
                media_location=PlayerMediaFileLocation(
                    content_server="NAS",
                    content_directory="Movies",
                    playback_file_name="Movie.mkv",
                    playback_file_format="mkv",
                )
            )
        )

        self.assertTrue(result.successful)
        self.assertEqual("/mnt/nfs1", result.mounted_path)
        self.assertEqual(
            [
                "sign_in",
                "get_device_list",
                ("login_nfs_server", "NAS"),
                ("mount_nfs_folder", "NAS", "Movies", 30),
                ("play_normal_file", "/mnt/nfs1", "NAS", "Movie.mkv", "0", 30),
            ],
            client.calls,
        )
        self.assertNotIn("get_setup_menu", client.calls)
        self.assertNotIn(("send_remote_key", "EJT"), client.calls)
        self.assertNotIn(("send_remote_key", "QPW"), client.calls)

    def test_starts_samba_playback_when_oppo_reports_cifs_share(self):
        client = RecordingMediaControlClient(device_sub_type="cifs")
        playback = OppoMediaControlPlayback(
            {
                "default_nfs": True,
                "timeout_oppo_mount": 30,
                "timeout_oppo_playitem": 30,
            },
            client=client,
            playback_state_waiter=_started_playback,
        )

        result = playback.start_playback(
            OppoPlaybackStartRequest(
                media_location=PlayerMediaFileLocation(
                    content_server="NAS",
                    content_directory="Movies",
                    playback_file_name="Movie.mkv",
                    playback_file_format="mkv",
                )
            )
        )

        self.assertTrue(result.successful)
        self.assertEqual("/mnt/cifs1", result.mounted_path)
        self.assertEqual(
            [
                "sign_in",
                "get_device_list",
                ("login_samba_without_id", "NAS"),
                ("mount_samba_folder", "NAS", "Movies", 30),
                ("play_normal_file", "/mnt/cifs1", "NAS", "Movie.mkv", "0", 30),
            ],
            client.calls,
        )

    def test_reads_playback_position_from_media_control_endpoint(self):
        client = RecordingMediaControlClient()
        playback = OppoMediaControlPlayback(
            {
                "default_nfs": True,
                "timeout_oppo_mount": 30,
                "timeout_oppo_playitem": 30,
            },
            client=client,
            playback_state_waiter=_started_playback,
        )

        position = playback.get_playback_position()

        self.assertEqual(12, position.current_seconds)
        self.assertEqual(120, position.total_seconds)
        self.assertEqual(["get_playing_time"], client.calls)

    def test_sends_seek_and_audio_selection_through_media_control_client(self):
        client = RecordingMediaControlClient()
        playback = OppoMediaControlPlayback(
            {
                "default_nfs": True,
                "timeout_oppo_mount": 30,
                "timeout_oppo_playitem": 30,
            },
            client=client,
            playback_state_waiter=_started_playback,
        )

        seek_result = playback.seek_to(120_000_000)
        audio_result = playback.select_audio_track(2)

        self.assertTrue(seek_result.successful)
        self.assertTrue(audio_result.successful)
        self.assertEqual(
            [
                ("set_play_time", 120_000_000),
                ("select_audio_track", 2),
            ],
            client.calls,
        )

    def test_skips_subtitle_selection_when_requested_track_is_already_selected(self):
        client = RecordingMediaControlClient()
        playback = OppoMediaControlPlayback(
            {
                "default_nfs": True,
                "timeout_oppo_mount": 30,
                "timeout_oppo_playitem": 30,
            },
            client=client,
            playback_state_waiter=_started_playback,
        )

        result = playback.select_subtitle_track(1)

        self.assertTrue(result.successful)
        self.assertEqual(["get_subtitle_menu"], client.calls)


def _started_playback(**kwargs):
    return PlaybackStartupWaitResult(
        started=True,
        attempts=1,
        elapsed_seconds=0.1,
        status=OppoPlaybackStatus.PLAY,
        category=OppoPlaybackCategory.ACTIVE,
        raw_response="@OK PLAY",
    )


if __name__ == "__main__":
    unittest.main()
