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

    def send_json_response(self, response_status: int, body):
        response_body = json.dumps(body, ensure_ascii=False).encode("utf-8")

        self.send_response(response_status)
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response_body)

    def send_legacy_response(self, response_status: int, body: str):
        response_body = str(body).encode("utf-8")
        self.send_response(response_status)
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response_body)

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
            a = load_config(context.config_file, context.lang_path)
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/xnoppo_config_lib":
            a = load_config(context.config_file, context.lang_path)
            carga_libraries(a)
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/xnoppo_config_dev":
            a = load_config(context.config_file, context.lang_path)
            get_devices(a)
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/check_version":
            config = load_config(context.config_file, context.lang_path)
            a = check_version(config)
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/update_version":
            config = load_config(context.config_file, context.lang_path)
            a = update_version(config)
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/get_state":
            a = get_state()
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/restart":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            a = "Restarting"
            self.wfile.write(bytes(a, "utf-8"))
            restart()
        if self.path == "/refresh_paths":
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            a = load_config(context.config_file, context.lang_path)
            get_selectableFolders(a)
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/lang":
            config = load_config(context.config_file, context.lang_path)
            a = load_json_asset(
                str(Path(context.lang_path) / config["language"] / "lang.js")
            )
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
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
            self.send_response(200)
            self.send_header("Content-type", "text")
            self.end_headers()
            a = "ok"
            self.wfile.write(bytes(a, "utf-8"))
            return 0
        if self.path == "/log.txt":
            self.send_response(200)
            self.send_header("Content-type", "text")
            self.end_headers()
            load_config(context.config_file, context.lang_path)
            a = read_binary_asset(context.log_file)
            self.wfile.write(bytes(a))
            return 0
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                bytes(
                    "<html><head><title>https://pythonbasics.org</title></head>",
                    "utf-8",
                )
            )
            self.wfile.write(bytes("<p>Request: %s</p>" % self.path, "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))
            self.wfile.write(bytes("<p>This is an example web server.</p>", "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))

    def do_POST(self):
        context = self.context

        print(self.path)
        if self.path == "/save_config":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
            config = merge_existing_secrets(context.config_file, config)
            save_config(context.config_file, config)
            self.send_response(200)
            self.send_header("Content-Length", len(config))
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(bytes(json.dumps(config), "utf-8"))
        if self.path == "/check_emby":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
            config = merge_existing_secrets(context.config_file, config)
            a = test_emby(config)
            if a == "OK":
                response_body = json.dumps(config).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(response_body)))
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(response_body)
                status = get_state()
                if status["Playstate"] == "Not_Connected":
                    save_config(context.config_file, config)
                    restart()
            else:
                self.send_legacy_response(300, a)
            return 0
        if self.path == "/check_oppo":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
            a = test_oppo(config)
            if a == "OK":
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, a)
            return 0
        if self.path == "/test_path":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            server = json.loads(post_data.decode("utf-8"))
            config = load_config(context.config_file, context.lang_path)
            a = test_path_configuration(config, server)
            if a == "OK":
                self.send_response(200)
                self.send_header("Content-Length", len(server))
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(bytes(json.dumps(server), "utf-8"))
            else:
                self.send_legacy_response(300, a)
            return 0
        if self.path == "/navigate_path":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            path_obj = json.loads(post_data.decode("utf-8"))
            path = path_obj["path"]
            config = load_config(context.config_file, context.lang_path)
            a = navigate_folder(path, config)
            a_json = json.dumps(a)
            print(len(a_json))
            self.send_json_response(200, a)
            return 0

        if self.path == "/tv_test_conn":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
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
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
            a = get_tv_sources(config)
            if a == "OK":
                save_config(context.config_file, config)
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, a)
            return 0
        if self.path == "/get_av_sources":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
            a = get_hdmi_list(config)
            if a != None:
                config["AV_SOURCES"] = a
                save_config(context.config_file, config)
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, "")
            return 0
        if self.path == "/tv_test_init":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
            a = tv_change_hdmi(config)
            if a == "OK":
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, a)
            return 0
        if self.path == "/tv_test_end":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
            a = tv_set_prev(config)
            if a == "OK":
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, a)
            return 0
        if self.path == "/av_test_on":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
            a = av_check_power(config)
            if a == "OK":
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, a)
            return 0
        if self.path == "/av_test_off":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
            a = av_power_off(config)
            if a == "OK":
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, a)
            return 0
        if self.path == "/av_test_hdmi":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
            a = av_change_hdmi(config)
            if a == "OK":
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, a)
            return 0
        if self.path == "/start_movie":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            data = json.loads(post_data.decode("utf-8"))
            context.runtime.start_movie(data)
            a = "OK"
            if a == "OK":
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, a)
            return 0


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
