import unittest
from unittest.mock import patch

from home_cinema_bridge.web.version_routes import (
    check_version_response,
    update_version_response,
)
from home_cinema_bridge.web.version_update import VersionInfo


class WebVersionRoutesTest(unittest.TestCase):
    def test_check_version_response_preserves_legacy_payload_shape(self):
        version_info = VersionInfo(
            current_version="0.5.1",
            latest_version="0.5.2",
            latest_tag="v0.5.2",
            release_url="https://github.test/release",
            asset_url="https://github.test/asset",
            new_version=True,
        )

        with patch(
            "home_cinema_bridge.web.version_routes.check_application_version",
            return_value=version_info,
        ):
            response = check_version_response({"check_beta": False}, "0.5.1")

        self.assertEqual("0.5.2", response["version"])
        self.assertEqual("https://github.test/asset", response["file"])
        self.assertTrue(response["new_version"])
        self.assertEqual("0.5.1", response["current_version"])
        self.assertEqual("v0.5.2", response["latest_tag"])
        self.assertEqual("https://github.test/release", response["release_url"])
        self.assertEqual("", response["error"])

    def test_update_version_response_keeps_automatic_update_disabled(self):
        with patch(
            "home_cinema_bridge.web.version_routes.trigger_configured_update",
            return_value={"success": False, "message": "disabled"},
        ):
            response = update_version_response({"check_beta": False}, "0.5.1")

        self.assertFalse(response["success"])
        self.assertEqual("disabled", response["message"])


if __name__ == "__main__":
    unittest.main()
