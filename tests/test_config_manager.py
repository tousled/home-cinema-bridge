import unittest

from lib.config_manager import sanitize_config_for_web


class ConfigManagerTest(unittest.TestCase):
    def test_sanitize_config_for_web_removes_sensitive_password(self):
        sanitized = sanitize_config_for_web(
            {
                "user_password": "secret",
                "release_repository": "tousled/home-cinema-bridge",
            }
        )

        self.assertNotIn("user_password", sanitized)
        self.assertTrue(sanitized["user_password_configured"])
        self.assertEqual(
            "tousled/home-cinema-bridge", sanitized["release_repository"]
        )


if __name__ == "__main__":
    unittest.main()
