import os
from dataclasses import dataclass

from home_cinema_bridge.web.static_assets import read_binary_asset, read_text_asset


HTML_ROUTES = {
    "/emby_conf.html": "emby_conf.html",
    "/oppo_conf.html": "oppo_conf.html",
    "/lib_conf.html": "lib_conf.html",
    "/path_conf.html": "path_conf.html",
    "/tv_conf.html": "tv_conf.html",
    "/av_conf.html": "av_conf.html",
    "/other_conf.html": "other_conf.html",
    "/status.html": "status.html",
    "/help.html": "help.html",
    "/remote.html": "remote.html",
}

RESOURCE_ROUTES = {
    "/android-chrome-36x36.png": ("android-chrome-36x36.png", "image/png"),
    "/av-receiver-icon-2.jpg": ("av-receiver-icon-2.jpg", "image/jpeg"),
    "/dragon.png": ("dragon.png", "image/png"),
}


@dataclass(frozen=True)
class StaticRouteResponse:
    body: bytes
    content_type: str


def load_static_route(request_path, *, html_path, resource_path):
    html_file = HTML_ROUTES.get(request_path)
    if html_file is not None:
        body = read_text_asset(os.path.join(html_path, html_file)).encode("utf-8")
        return StaticRouteResponse(body=body, content_type="text/html; charset=utf-8")

    resource = RESOURCE_ROUTES.get(request_path)
    if resource is not None:
        filename, content_type = resource
        body = bytes(read_binary_asset(os.path.join(resource_path, filename)))
        return StaticRouteResponse(body=body, content_type=content_type)

    return None
