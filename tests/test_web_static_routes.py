import tempfile
import unittest
from pathlib import Path

from home_cinema_bridge.web.static_routes import load_static_route


class WebStaticRoutesTest(unittest.TestCase):
    def test_loads_html_route(self):
        with tempfile.TemporaryDirectory() as directory:
            html_path = Path(directory) / "html"
            resource_path = Path(directory) / "resources"
            html_path.mkdir()
            resource_path.mkdir()
            (html_path / "status.html").write_text("<html>Status</html>", "utf-8")

            response = load_static_route(
                "/status.html",
                html_path=str(html_path),
                resource_path=str(resource_path),
            )

        self.assertIsNotNone(response)
        self.assertEqual(b"<html>Status</html>", response.body)
        self.assertEqual("text/html; charset=utf-8", response.content_type)

    def test_loads_resource_route_with_image_content_type(self):
        with tempfile.TemporaryDirectory() as directory:
            html_path = Path(directory) / "html"
            resource_path = Path(directory) / "resources"
            html_path.mkdir()
            resource_path.mkdir()
            (resource_path / "dragon.png").write_bytes(b"png")

            response = load_static_route(
                "/dragon.png",
                html_path=str(html_path),
                resource_path=str(resource_path),
            )

        self.assertIsNotNone(response)
        self.assertEqual(b"png", response.body)
        self.assertEqual("image/png", response.content_type)

    def test_returns_none_for_dynamic_routes(self):
        response = load_static_route(
            "/check_version",
            html_path="/tmp/html",
            resource_path="/tmp/resources",
        )

        self.assertIsNone(response)


if __name__ == "__main__":
    unittest.main()
