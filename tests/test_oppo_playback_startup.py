import unittest

from home_cinema_bridge.devices.oppo.playback_startup import OppoPlaybackStartup


class RecordingOppoControlApiClient:
    def __init__(self):
        self.calls = []

    def get_main_firmware_version(self):
        self.calls.append("get_main_firmware_version")

    def get_device_list(self):
        self.calls.append("get_device_list")
        return '{"sub_type":"nfs"}'

    def get_setup_menu(self):
        self.calls.append("get_setup_menu")

    def sign_in(self):
        self.calls.append("sign_in")

    def get_global_info(self):
        self.calls.append("get_global_info")

    def send_remote_key(self, key):
        self.calls.append(("send_remote_key", key))


class OppoPlaybackStartupTest(unittest.TestCase):
    def test_preparation_skips_redundant_legacy_refresh_calls(self):
        control_api = RecordingOppoControlApiClient()
        startup = OppoPlaybackStartup(
            {"BRDisc": False},
            control_api_client=control_api,
            network_playback=object(),
        )

        result = startup.prepare_for_playback_startup()

        self.assertTrue(result.successful)
        self.assertEqual(
            [
                "sign_in",
                ("send_remote_key", "EJT"),
            ],
            control_api.calls,
        )
        self.assertNotIn("get_main_firmware_version", control_api.calls)
        self.assertNotIn("get_setup_menu", control_api.calls)


if __name__ == "__main__":
    unittest.main()
