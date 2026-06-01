import unittest
from pathlib import Path

from xnoppo_web import WebServerContext, create_web_handler


class FakeRuntime:
    pass


class WebRuntimeContextTest(unittest.TestCase):
    def test_context_builds_legacy_web_paths(self):
        context = WebServerContext(
            runtime=FakeRuntime(),
            config_file="/config/config.json",
            base_path=Path("/app"),
        )

        self.assertEqual("/app/web/", context.html_path)
        self.assertEqual("/app/web/resources/", context.resource_path)
        self.assertEqual("/app/web/lang/", context.lang_path)
        self.assertEqual("/app/emby_xnoppo_client_logging.log", context.log_file)

    def test_create_web_handler_attaches_runtime_context(self):
        context = WebServerContext(
            runtime=FakeRuntime(),
            config_file="/config/config.json",
            base_path=Path("/app"),
        )

        handler = create_web_handler(context)

        self.assertIs(context, handler.context)


if __name__ == "__main__":
    unittest.main()
