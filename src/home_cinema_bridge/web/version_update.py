import re
from dataclasses import dataclass

import requests


DEFAULT_RELEASE_REPOSITORY = "tousled/home-cinema-bridge"


@dataclass(frozen=True)
class VersionInfo:
    current_version: str
    latest_version: str
    latest_tag: str
    release_url: str
    asset_url: str
    new_version: bool
    error: str = ""

    def as_legacy_response(self) -> dict:
        return {
            "version": self.latest_version,
            "file": self.asset_url,
            "new_version": self.new_version,
            "current_version": self.current_version,
            "latest_tag": self.latest_tag,
            "release_url": self.release_url,
            "error": self.error,
        }


def check_application_version(config, current_version, http_client=requests):
    repository = config.get("release_repository", DEFAULT_RELEASE_REPOSITORY)
    include_prereleases = bool(config.get("check_beta", False))
    timeout = config.get("version_check_timeout", 10)

    try:
        release = find_latest_release(
            repository,
            include_prereleases=include_prereleases,
            timeout=timeout,
            http_client=http_client,
        )
    except Exception as exc:
        return _current_version_info(current_version, error=str(exc))

    if release is None:
        return _current_version_info(current_version)

    latest_version = normalize_version(release["tag"])
    return VersionInfo(
        current_version=current_version,
        latest_version=latest_version,
        latest_tag=release["tag"],
        release_url=release["url"],
        asset_url=release["asset_url"],
        new_version=is_newer_version(latest_version, current_version),
    )


def trigger_configured_update(config, current_version, http_client=requests):
    version_info = check_application_version(config, current_version, http_client)
    return {
        "success": False,
        "message": "Automatic update is not supported yet.",
        **version_info.as_legacy_response(),
    }


def find_latest_release(
    repository,
    *,
    include_prereleases,
    timeout,
    http_client=requests,
):
    releases_url = f"https://api.github.com/repos/{repository}/releases"
    response = http_client.get(
        releases_url,
        headers={"Accept": "application/vnd.github+json"},
        timeout=timeout,
    )
    response.raise_for_status()

    releases = response.json()
    for release in releases:
        if release.get("draft"):
            continue
        if release.get("prerelease") and not include_prereleases:
            continue

        tag = release.get("tag_name", "")
        if not tag:
            continue

        assets = release.get("assets", [])
        asset_url = assets[0].get("browser_download_url", "") if assets else ""
        return {
            "tag": tag,
            "url": release.get("html_url", ""),
            "asset_url": asset_url,
        }

    return find_latest_tag(repository, timeout=timeout, http_client=http_client)


def _current_version_info(current_version, *, error=""):
    return VersionInfo(
        current_version=current_version,
        latest_version=current_version,
        latest_tag=current_version,
        release_url="",
        asset_url="",
        new_version=False,
        error=error,
    )


def find_latest_tag(repository, *, timeout, http_client=requests):
    tags_url = f"https://api.github.com/repos/{repository}/tags"
    response = http_client.get(
        tags_url,
        headers={"Accept": "application/vnd.github+json"},
        timeout=timeout,
    )
    response.raise_for_status()

    tags = response.json()
    if not tags:
        return None

    tag = tags[0].get("name", "")
    if not tag:
        return None

    return {
        "tag": tag,
        "url": f"https://github.com/{repository}/releases/tag/{tag}",
        "asset_url": "",
    }


def is_newer_version(candidate, current):
    return parse_version(candidate) > parse_version(current)


def normalize_version(version):
    return str(version).strip().removeprefix("v").removeprefix("V")


def parse_version(version):
    normalized = normalize_version(version)
    numbers = [int(part) for part in re.findall(r"\d+", normalized)]
    return tuple(numbers or [0])
