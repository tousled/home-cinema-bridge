import unittest

from home_cinema_bridge.web.version_update import (
    check_application_version,
    is_newer_version,
    trigger_configured_update,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttpClient:
    def __init__(self, releases, tags=None, post_status=204):
        self.releases = releases
        self.tags = tags or []
        self.post_status = post_status
        self.get_calls = []
        self.post_calls = []

    def get(self, url, headers=None, timeout=None):
        self.get_calls.append((url, headers, timeout))
        if url.endswith("/releases"):
            return FakeResponse(self.releases)
        if url.endswith("/tags"):
            return FakeResponse(self.tags)
        raise AssertionError(f"Unexpected URL: {url}")

class FailingHttpClient:
    def get(self, url, headers=None, timeout=None):
        raise RuntimeError("network down")


class WebVersionUpdateTest(unittest.TestCase):
    def test_version_comparison_handles_semver_numbers(self):
        self.assertTrue(is_newer_version("0.5.10", "0.5.2"))
        self.assertFalse(is_newer_version("0.5.1", "0.5.1"))
        self.assertTrue(is_newer_version("v0.6.0", "0.5.1"))

    def test_check_version_uses_latest_non_prerelease_release_by_default(self):
        http = FakeHttpClient(
            releases=[
                {"tag_name": "v0.6.0-beta.1", "prerelease": True, "draft": False},
                {
                    "tag_name": "v0.5.2",
                    "prerelease": False,
                    "draft": False,
                    "html_url": "https://github/release",
                    "assets": [{"browser_download_url": "https://asset"}],
                },
            ]
        )

        result = check_application_version(
            {
                "release_repository": "owner/repo",
                "check_beta": False,
                "version_check_timeout": 3,
            },
            "0.5.1",
            http,
        )

        self.assertTrue(result.new_version)
        self.assertEqual("0.5.2", result.latest_version)
        self.assertEqual("v0.5.2", result.latest_tag)
        self.assertEqual("https://asset", result.asset_url)
        self.assertEqual(
            "https://api.github.com/repos/owner/repo/releases",
            http.get_calls[0][0],
        )
        self.assertEqual(3, http.get_calls[0][2])

    def test_check_version_can_include_prereleases(self):
        http = FakeHttpClient(
            releases=[
                {
                    "tag_name": "v0.6.0-beta.1",
                    "prerelease": True,
                    "draft": False,
                    "html_url": "https://github/beta",
                    "assets": [],
                },
                {"tag_name": "v0.5.2", "prerelease": False, "draft": False},
            ]
        )

        result = check_application_version(
            {"release_repository": "owner/repo", "check_beta": True},
            "0.5.1",
            http,
        )

        self.assertTrue(result.new_version)
        self.assertEqual("0.6.0-beta.1", result.latest_version)
        self.assertEqual("https://github/beta", result.release_url)

    def test_check_version_falls_back_to_tags_when_no_release_matches(self):
        http = FakeHttpClient(
            releases=[{"tag_name": "v0.6.0-beta.1", "prerelease": True}],
            tags=[{"name": "v0.5.2"}],
        )

        result = check_application_version(
            {"release_repository": "owner/repo", "check_beta": False},
            "0.5.1",
            http,
        )

        self.assertTrue(result.new_version)
        self.assertEqual("0.5.2", result.latest_version)
        self.assertEqual(
            "https://api.github.com/repos/owner/repo/tags",
            http.get_calls[1][0],
        )

    def test_check_version_reports_errors_without_breaking_web_response(self):
        result = check_application_version(
            {"release_repository": "owner/repo"},
            "0.5.1",
            FailingHttpClient(),
        )

        self.assertFalse(result.new_version)
        self.assertEqual("0.5.1", result.latest_version)
        self.assertEqual("network down", result.error)

    def test_update_is_explicitly_disabled_for_now(self):
        http = FakeHttpClient(
            releases=[
                {"tag_name": "v0.5.2", "prerelease": False, "draft": False},
            ]
        )

        result = trigger_configured_update(
            {"release_repository": "owner/repo"},
            "0.5.1",
            http,
        )

        self.assertFalse(result["success"])
        self.assertEqual("Automatic update is not supported yet.", result["message"])
        self.assertEqual([], http.post_calls)


if __name__ == "__main__":
    unittest.main()
