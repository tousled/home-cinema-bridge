import json
import os
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from home_cinema_bridge.runtime import (
    HomeCinemaBridgeRuntime,
    build_runtime_paths,
    configure_logging,
)
from home_cinema_bridge.devices.oppo.web_control import (
    check_socket,
    sendnotifyremote,
    getmainfirmwareversion,
    getdevicelist,
    getsetupmenu,
    OppoSignin,
    getglobalinfo,
    sendremotekey,
    navigate_folder,
)
from home_cinema_bridge.media_servers.emby.web_config import (
    test_emby_connection,
    load_libraries,
    load_selectable_folders,
    load_devices,
)
from home_cinema_bridge.web.path_config import test_path_configuration
from home_cinema_bridge.web.static_assets import (
    load_json_asset,
    read_binary_asset,
)
from home_cinema_bridge.web.static_routes import load_static_route
from home_cinema_bridge.web.version_routes import (
    check_version_response,
    update_version_response,
)
from home_cinema_bridge.devices.av.web_control import (
    get_hdmi_list,
    av_check_power,
    av_power_off,
    av_change_hdmi,
)
from home_cinema_bridge.devices.tv.web_control import (
    tv_test_conn,
    get_tv_sources,
    tv_change_hdmi,
    tv_set_prev,
)
from lib.config_manager import (
    ensure_config_exists,
    sanitize_config_for_web,
    merge_existing_secrets,
)

import logging


def get_version():
    return "0.5.1"


@dataclass(frozen=True)
class WebServerContext:
    runtime: HomeCinemaBridgeRuntime
    config_file: str
    base_path: Path

    @property
    def html_path(self) -> str:
        return str(self.base_path / "web") + os.sep

    @property
    def resource_path(self) -> str:
        return str(self.base_path / "web" / "resources") + os.sep

    @property
    def lang_path(self) -> str:
        return str(self.base_path / "web" / "lang") + os.sep

    @property
    def log_file(self) -> str:
        return str(self.base_path / "emby_xnoppo_client_logging.log")


def restart():
    current_context().runtime.restart_process()


def save_config(config_file, config):
    current_context().runtime.save_config(config)


def get_state():
    return current_context().runtime.get_state()


def load_config(config_file, lang_path):
    return current_context().runtime.load_config()


def check_version(config):
    return check_version_response(config, get_version())


def update_version(config):
    return update_version_response(config, get_version())


def test_emby(config):
    return test_emby_connection(config)


def test_oppo(config):
    result = check_socket(config)
    if result == 0:
        return "OK"
    else:
        return "FAILED"


def carga_libraries(config):
    return load_libraries(config)


def get_selectableFolders(config):
    load_selectable_folders(config)


def get_devices(config):
    return load_devices(config)


def current_context() -> WebServerContext:
    return MyServer.context


def create_web_handler(context: WebServerContext):
    class ContextualWebServer(MyServer):
        pass

    MyServer.context = context
    ContextualWebServer.context = context
    return ContextualWebServer


class MyServer(BaseHTTPRequestHandler):
    context: WebServerContext

    def read_json_request(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        return json.loads(post_data.decode("utf-8"))

    def send_json_response(self, response_status: int, body):
        response_body = json.dumps(body, ensure_ascii=False).encode("utf-8")

        self.send_response(response_status)
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response_body)

    def send_json_legacy_payload(self, response_status: int, body):
        response_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_binary_response(
            response_status,
            response_body,
            "text/html; charset=utf-8",
        )

    def send_legacy_response(self, response_status: int, body: str):
        self.send_binary_response(
            response_status,
            str(body).encode("utf-8"),
            "text/html; charset=utf-8",
        )

    def send_text_response(self, response_status: int, body: str, content_type: str):
        self.send_binary_response(response_status, body.encode("utf-8"), content_type)

    def send_binary_response(
        self, response_status: int, body: bytes, content_type: str
    ):
        self.send_response(response_status)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def load_effective_config(self):
        return load_config(self.context.config_file, self.context.lang_path)

    def save_effective_config(self, config):
        save_config(self.context.config_file, config)

    def handle_config_get(self, *, load_library_data=False, load_device_data=False):
        config = self.load_effective_config()
        if load_library_data:
            carga_libraries(config)
        if load_device_data:
            get_devices(config)

        self.send_json_response(200, sanitize_config_for_web(config))
        return 0

    def handle_version_check(self):
        config = self.load_effective_config()
        response = check_version(config)
        self.send_json_response(200, sanitize_config_for_web(response))
        return 0

    def handle_version_update(self):
        config = self.load_effective_config()
        response = update_version(config)
        self.send_json_response(200, sanitize_config_for_web(response))
        return 0

    def handle_state(self):
        response = get_state()
        self.send_json_response(200, sanitize_config_for_web(response))
        return 0

    def handle_refresh_paths(self):
        config = self.load_effective_config()
        get_selectableFolders(config)
        self.send_json_response(200, sanitize_config_for_web(config))
        return 0

    def handle_lang(self):
        config = self.load_effective_config()
        lang_file = Path(self.context.lang_path) / config["language"] / "lang.js"
        response = load_json_asset(str(lang_file))
        self.send_json_response(200, sanitize_config_for_web(response))
        return 0

    def handle_log_file(self):
        self.load_effective_config()
        body = read_binary_asset(self.context.log_file)
        self.send_binary_response(200, bytes(body), "text/plain; charset=utf-8")
        return 0

    def handle_save_config(self):
        config = self.read_json_request()
        config = merge_existing_secrets(self.context.config_file, config)
        self.save_effective_config(config)
        self.send_json_legacy_payload(200, config)
        return 0

    def handle_check_emby(self):
        config = self.read_json_request()
        config = merge_existing_secrets(self.context.config_file, config)
        response = test_emby(config)
        if response == "OK":
            self.send_json_response(200, config)
            status = get_state()
            if status["Playstate"] == "Not_Connected":
                self.save_effective_config(config)
                restart()
        else:
            self.send_legacy_response(300, response)
        return 0

    def handle_check_oppo(self):
        config = self.read_json_request()
        response = test_oppo(config)
        if response == "OK":
            self.send_legacy_response(200, response)
        else:
            self.send_legacy_response(300, response)
        return 0

    def handle_test_path(self):
        server = self.read_json_request()
        config = self.load_effective_config()
        response = test_path_configuration(config, server)
        if response == "OK":
            self.send_json_legacy_payload(200, server)
        else:
            self.send_legacy_response(300, response)
        return 0

    def handle_navigate_path(self):
        path_obj = self.read_json_request()
        config = self.load_effective_config()
        response = navigate_folder(path_obj["path"], config)
        print(len(json.dumps(response)))
        self.send_json_response(200, response)
        return 0

    def handle_device_test(self, operation, *, save_on_success=False):
        config = self.read_json_request()
        response = operation(config)
        if response == "OK":
            if save_on_success:
                self.save_effective_config(config)
            self.send_legacy_response(200, response)
        else:
            self.send_legacy_response(300, response)
        return 0

    def handle_start_movie(self):
        data = self.read_json_request()
        self.context.runtime.start_movie(data)
        self.send_legacy_response(200, "OK")
        return 0

    def do_GET(self):
        context = self.context

        print(self.path)
        static_response = load_static_route(
            self.path,
            html_path=context.html_path,
            resource_path=context.resource_path,
        )
        if static_response is not None:
            self.send_binary_response(
                200, static_response.body, static_response.content_type
            )
            return 0
        if self.path == "/xnoppo_config":
            return self.handle_config_get()
        if self.path == "/xnoppo_config_lib":
            return self.handle_config_get(load_library_data=True)
        if self.path == "/xnoppo_config_dev":
            return self.handle_config_get(load_device_data=True)
        if self.path == "/check_version":
            return self.handle_version_check()
        if self.path == "/update_version":
            return self.handle_version_update()
        if self.path == "/get_state":
            return self.handle_state()
        if self.path == "/restart":
            self.send_text_response(200, "Restarting", "text/html; charset=utf-8")
            restart()
        if self.path == "/refresh_paths":
            return self.handle_refresh_paths()
        if self.path == "/lang":
            return self.handle_lang()
        if self.path.find("/send_key?") >= 0:
            get_data = self.path
            print(get_data)
            a = len("/send_key?sendkey=")
            b = get_data[a : len(get_data)]
            print(b)
            config = load_config(context.config_file, context.lang_path)
            sendnotifyremote(config["Oppo_IP"])
            result = check_socket(config)
            if b == "PON":
                if result == 0:
                    getmainfirmwareversion(config)
                    getdevicelist(config)
                    getsetupmenu(config)
                    OppoSignin(config)
                    getdevicelist(config)
                    getglobalinfo(config)
                    getdevicelist(config)
                    sendremotekey("EJT", config)
                    if config["BRDisc"] == True:
                        time.sleep(1)
                        sendremotekey("EJT", config)
                    time.sleep(1)
                    getsetupmenu(config)
            else:
                sendremotekey(b, config)
            self.send_text_response(200, "ok", "text/plain; charset=utf-8")
            return 0
        if self.path == "/log.txt":
            return self.handle_log_file()
        else:
            body = (
                "<html><head><title>https://pythonbasics.org</title></head>"
                f"<p>Request: {self.path}</p>"
                "<body>"
                "<p>This is an example web server.</p>"
                "</body></html>"
            )
            self.send_text_response(200, body, "text/html; charset=utf-8")

    def do_POST(self):
        context = self.context

        print(self.path)
        if self.path == "/save_config":
            return self.handle_save_config()
        if self.path == "/check_emby":
            return self.handle_check_emby()
        if self.path == "/check_oppo":
            return self.handle_check_oppo()
        if self.path == "/test_path":
            return self.handle_test_path()
        if self.path == "/navigate_path":
            return self.handle_navigate_path()

        if self.path == "/tv_test_conn":
            config = self.read_json_request()
            a = tv_test_conn(config)
            if a == "OK":
                logging.info(
                    "TV test connection succeeded | model=%s | ip=%s | mac_detected=%s",
                    config.get("TV_model", ""),
                    config.get("TV_IP", ""),
                    bool(config.get("TV_MAC", "")),
                )
                save_config(context.config_file, config)
                self.send_legacy_response(200, a)
            else:
                logging.warning(
                    "TV test connection failed | result=%s | model=%s | ip=%s | mac_detected=%s",
                    a,
                    config.get("TV_model", ""),
                    config.get("TV_IP", ""),
                    bool(config.get("TV_MAC", "")),
                )
                self.send_legacy_response(300, a)
            return 0

        if self.path == "/get_tv_sources":
            config = self.read_json_request()
            a = get_tv_sources(config)
            if a == "OK":
                save_config(context.config_file, config)
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, a)
            return 0
        if self.path == "/get_av_sources":
            config = self.read_json_request()
            a = get_hdmi_list(config)
            if a != None:
                config["AV_SOURCES"] = a
                save_config(context.config_file, config)
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, "")
            return 0
        if self.path == "/tv_test_init":
            return self.handle_device_test(tv_change_hdmi)
        if self.path == "/tv_test_end":
            return self.handle_device_test(tv_set_prev)
        if self.path == "/av_test_on":
            return self.handle_device_test(av_check_power)
        if self.path == "/av_test_off":
            return self.handle_device_test(av_power_off)
        if self.path == "/av_test_hdmi":
            return self.handle_device_test(av_change_hdmi)
        if self.path == "/start_movie":
            return self.handle_start_movie()


if __name__ == "__main__":
    cwd = os.path.dirname(os.path.abspath(__file__))
    config_file = str(ensure_config_exists())
    runtime_paths = build_runtime_paths(cwd, config_file)
    app_runtime = HomeCinemaBridgeRuntime(paths=runtime_paths, version=get_version())
    web_context = WebServerContext(
        runtime=app_runtime,
        config_file=config_file,
        base_path=Path(cwd),
    )
    config = app_runtime.load_config()
    configure_logging(config, runtime_paths.log_file)
    app_runtime.start_playback_listener_if_configured()

    logging.debug("Arrancamos el Servidor Web\n")
    serverPort = 8090
    webServer = HTTPServer(("", serverPort), create_web_handler(web_context))
    print("Server started http://%s:%s" % ("", serverPort))
    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass
    webServer.server_close()
    logging.info("Fin proceso")
    logging.info("Finished")
    print("Server stopped.")
