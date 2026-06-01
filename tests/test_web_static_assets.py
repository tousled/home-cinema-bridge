import tempfile
import unittest
from pathlib import Path

from home_cinema_bridge.web.static_assets import (
    load_json_asset,
    read_binary_asset,
    read_text_asset,
)


class WebStaticAssetsTest(unittest.TestCase):
    def test_load_json_asset_reads_utf8_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "lang.js")
            path.write_text('{"hello":"mundo"}', encoding="utf-8")

            self.assertEqual({"hello": "mundo"}, load_json_asset(path))

    def test_read_text_asset_reads_utf8_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "index.html")
            path.write_text("ñ", encoding="utf-8")

            self.assertEqual("ñ", read_text_asset(path))

    def test_read_binary_asset_reads_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "image.png")
            path.write_bytes(b"\x89PNG")

            self.assertEqual(b"\x89PNG", read_binary_asset(path))


if __name__ == "__main__":
    unittest.main()
