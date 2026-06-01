import unittest

from home_cinema_bridge.devices.oppo.web_control import _web_control_api_attempts


class OppoWebControlTest(unittest.TestCase):
    def test_web_control_attempts_default_to_short_web_timeout(self):
        self.assertEqual(3, _web_control_api_attempts({"timeout_oppo_conection": 10}))

    def test_web_control_attempts_can_be_configured(self):
        self.assertEqual(5, _web_control_api_attempts({"oppo_web_control_api_attempts": 5}))

    def test_web_control_attempts_never_go_below_one(self):
        self.assertEqual(1, _web_control_api_attempts({"oppo_web_control_api_attempts": 0}))


if __name__ == "__main__":
    unittest.main()
