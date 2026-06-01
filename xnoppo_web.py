import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

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
from home_cinema_bridge.web.runtime_config import load_runtime_config
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
    is_configured,
    save_effective_config,
    sanitize_config_for_web,
    merge_existing_secrets,
)
import requests
from lib.Emby_ws import XnoppoWs

import shutil
import threading
import logging
import logging.handlers
import psutil
import sys


def get_version():
    return "0.5.1"


def thread_function(ws_object):
    print("Thread: starting")
    ws_object.start()
    print("Thread: finishing")


def restart():
    print("restart")
    try:
        emby_wsocket.stop()
    except:
        pass
    print("fin restart")
    os._exit(0)


def save_config(config_file, config):
    save_effective_config(config_file, config)

    try:
        emby_wsocket.ws_config = config
        emby_wsocket.EmbySession.config = config
    except:
        emby_wsocket.ws_config = config


def get_state():
    status = {}
    status["Version"] = get_version()
    try:
        status["Playstate"] = emby_wsocket.EmbySession.playstate
        status["playedtitle"] = emby_wsocket.EmbySession.playedtitle
        status["server"] = emby_wsocket.EmbySession.server
        status["folder"] = emby_wsocket.EmbySession.folder
        status["filename"] = emby_wsocket.EmbySession.filename
        status["CurrentData"] = emby_wsocket.EmbySession.currentdata
        # gives a single float value
    except:
        status["Playstate"] = "Not_Connected"
        status["playedtitle"] = ""
        status["server"] = ""
        status["folder"] = ""
        status["filename"] = ""
        status["CurrentData"] = ""
    status["cpu_perc"] = psutil.cpu_percent()
    status["mem_perc"] = psutil.virtual_memory().percent

    # you can have the percentage of used RAM
    logging.debug(psutil.virtual_memory().percent)
    logging.debug(status)
    return status


def load_config(config_file, lang_path):
    return load_runtime_config(config_file, lang_path, version=get_version())


def check_version(config):

    url = (
        "https://raw.githubusercontent.com/siberian-git/Xnoppo/main/versions/version.js"
    )
    headers = {}
    response = requests.get(url, headers=headers)
    version = json.loads(response.text)
    print(version)
    print(config["check_beta"])
    if config["check_beta"] == True:
        last_version = version["beta_version"]
        last_version_file = version["beta_version_file"]
    else:
        last_version = version["curr_version"]
        last_version_file = version["curr_version_file"]
    xno_version = get_version()
    resp = {}
    resp["version"] = last_version
    resp["file"] = last_version_file
    print(xno_version)
    print(last_version)
    if xno_version < last_version:
        resp["new_version"] = True
    else:
        resp["new_version"] = False
    print(resp)
    return resp


def update_version(config, vers_path, cwd):

    url = (
        "https://raw.githubusercontent.com/siberian-git/Xnoppo/main/versions/version.js"
    )
    headers = {}
    response = requests.get(url, headers=headers)
    version = json.loads(response.text)
    print(version)
    if config["check_beta"] == True:
        last_version = version["beta_version"]
        last_version_file = version["beta_version_file"]
    else:
        last_version = version["curr_version"]
        last_version_file = version["curr_version_file"]
    url2 = (
        "https://github.com/siberian-git/Xnoppo/raw/main/versions/" + last_version_file
    )
    headers = {}
    response2 = requests.get(url2, headers=headers)
    filename = vers_path + last_version_file
    with open(filename, "wb") as f:
        f.write(response2.content)
        f.close()
    shutil.unpack_archive(filename, cwd)

    resp = {}
    resp["version"] = last_version
    resp["file"] = last_version_file
    resp["new_version"] = False
    return resp


def cargar_lang(config_file):

    with open(
        config_file.encode(sys.getfilesystemencoding()), "r", encoding="utf-8"
    ) as f:
        config = json.load(f)
    f.close()
    ## new options default config values
    return config


def leer_file(web_file):

    with open(web_file, "r", encoding="utf8") as f:
        num = f.read()
    f.close
    return num


def leer_img(web_file):

    with open(web_file, "rb") as f:
        num = f.read()
    f.close
    return num


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


class MyServer(BaseHTTPRequestHandler):
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

    def do_GET(self):
        cwd = os.path.dirname(os.path.abspath(__file__))
        if sys.platform.startswith("win"):
            separador = "\\"
        else:
            separador = "/"
        resource_path = cwd + separador + "web" + separador + "resources" + separador
        html_path = cwd + separador + "web" + separador
        lang_path = cwd + separador + "web" + separador + "lang" + separador
        vers_path = cwd + separador + "versions" + separador

        print(self.path)
        if self.path == "/emby_conf.html":
            i = leer_file(html_path + "emby_conf.html")
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(bytes(i, "utf-8"))
            return 0
        if self.path == "/oppo_conf.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            i = leer_file(html_path + "oppo_conf.html")
            self.wfile.write(bytes(i, "utf-8"))
            return 0
        if self.path == "/lib_conf.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            i = leer_file(html_path + "lib_conf.html")
            self.wfile.write(bytes(i, "utf-8"))
            return 0
        if self.path == "/path_conf.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            i = leer_file(html_path + "path_conf.html")
            self.wfile.write(bytes(i, "utf-8"))
            return 0
        if self.path == "/tv_conf.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            i = leer_file(html_path + "tv_conf.html")
            self.wfile.write(bytes(i, "utf-8"))
            return 0
        if self.path == "/av_conf.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            i = leer_file(html_path + "av_conf.html")
            self.wfile.write(bytes(i, "utf-8"))
            return 0
        if self.path == "/other_conf.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            i = leer_file(html_path + "other_conf.html")
            self.wfile.write(bytes(i, "utf-8"))
            return 0
        if self.path == "/status.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            i = leer_file(html_path + "status.html")
            self.wfile.write(bytes(i, "utf-8"))
            return 0
        if self.path == "/help.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            i = leer_file(html_path + "help.html")
            self.wfile.write(bytes(i, "utf-8"))
            return 0
        if self.path == "/remote.html":
            i = leer_file(html_path + "remote.html")
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(bytes(i, "utf-8"))
            return 0
        if self.path == "/android-chrome-36x36.png":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            i = leer_img(resource_path + "android-chrome-36x36.png")
            self.wfile.write(bytes(i))
            return 0
        if self.path == "/av-receiver-icon-2.jpg":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            i = leer_img(resource_path + "av-receiver-icon-2.jpg")
            self.wfile.write(bytes(i))
            return 0
        if self.path == "/dragon.png":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            i = leer_img(resource_path + "dragon.png")
            self.wfile.write(bytes(i))
            return 0
        if self.path == "/xnoppo_config":
            a = load_config(config_file, lang_path)
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/xnoppo_config_lib":
            a = load_config(config_file, lang_path)
            carga_libraries(a)
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/xnoppo_config_dev":
            a = load_config(config_file, lang_path)
            get_devices(a)
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/check_version":
            config = load_config(config_file, lang_path)
            a = check_version(config)
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/update_version":
            config = load_config(config_file, lang_path)
            a = update_version(config, vers_path, cwd)
            restart()
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
            a = load_config(config_file, lang_path)
            get_selectableFolders(a)
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path == "/lang":
            config = load_config(config_file, lang_path)
            a = cargar_lang(lang_path + config["language"] + separador + "lang.js")
            self.send_json_response(200, sanitize_config_for_web(a))
            return 0
        if self.path.find("/send_key?") >= 0:
            get_data = self.path
            print(get_data)
            a = len("/send_key?sendkey=")
            b = get_data[a : len(get_data)]
            print(b)
            config = load_config(config_file, lang_path)
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
            load_config(config_file, lang_path)
            a = leer_img(cwd + separador + "emby_xnoppo_client_logging.log")
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
        cwd = os.path.dirname(os.path.abspath(__file__))
        if sys.platform.startswith("win"):
            separador = "\\"
        else:
            separador = "/"
        resource_path = cwd + separador + "web" + separador + "resources" + separador
        html_path = cwd + separador + "web" + separador
        tv_path = (
            cwd
            + separador
            + "web"
            + separador
            + "libraries"
            + separador
            + "TV"
            + separador
        )
        lib_path = cwd + separador + "lib" + separador
        lang_path = cwd + separador + "web" + separador + "lang" + separador
        vers_path = cwd + separador + "versions" + separador

        print(self.path)
        if self.path == "/save_config":
            content_length = int(
                self.headers["Content-Length"]
            )  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            config = json.loads(post_data.decode("utf-8"))
            config = merge_existing_secrets(config_file, config)
            save_config(config_file, config)
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
            config = merge_existing_secrets(config_file, config)
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
                    save_config(config_file, config)
                    emby_wsocket.ws_config = config
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
            config = load_config(config_file, lang_path)
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
            config = load_config(config_file, lang_path)
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
                save_config(config_file, config)
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
                save_config(config_file, config)
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
                save_config(config_file, config)
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
            emby_wsocket._play(data)
            a = "OK"
            if a == "OK":
                self.send_legacy_response(200, a)
            else:
                self.send_legacy_response(300, a)
            return 0


if __name__ == "__main__":
    cwd = os.path.dirname(os.path.abspath(__file__))
    if sys.platform.startswith("win"):
        separador = "\\"
    else:
        separador = "/"
    config_file = str(ensure_config_exists())
    resource_path = cwd + separador + "web" + separador + "resources" + separador
    html_path = cwd + separador + "web" + separador
    lib_path = cwd + separador + "lib" + separador
    lang_path = cwd + separador + "web" + separador + "lang" + separador
    vers_path = cwd + separador + "versions" + separador
    config = load_config(config_file, lang_path)
    logfile = cwd + separador + "emby_xnoppo_client_logging.log"
    lang = cargar_lang(lang_path + config["language"] + separador + "lang.js")

    if config["DebugLevel"] == 0:
        logging.basicConfig(
            format="%(asctime)s %(levelname)s: %(message)s",
            datefmt="%d/%m/%Y %I:%M:%S %p",
            level=logging.CRITICAL,
        )
    elif config["DebugLevel"] == 1:
        rfh = logging.handlers.RotatingFileHandler(
            filename=logfile,
            mode="a",
            maxBytes=50 * 1024 * 1024,
            backupCount=2,
            encoding="utf-8",
            delay=False,
        )
        logging.basicConfig(
            format="%(asctime)s %(levelname)s: %(message)s",
            datefmt="%d/%m/%Y %I:%M:%S %p",
            level=logging.INFO,
            handlers=[rfh, logging.StreamHandler(sys.stdout)],
        )
    elif config["DebugLevel"] == 2:
        rfh = logging.handlers.RotatingFileHandler(
            filename=logfile,
            mode="a",
            maxBytes=5 * 1024 * 1024,
            backupCount=2,
            encoding="utf-8",
            delay=False,
        )
        logging.basicConfig(
            format="%(asctime)s %(levelname)s: %(message)s",
            datefmt="%d/%m/%Y %I:%M:%S %p",
            level=logging.DEBUG,
            handlers=[rfh, logging.StreamHandler(sys.stdout)],
        )

    logging.getLogger("websocket").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    config = load_config(config_file, lang_path)
    config_ready = is_configured(config)
    emby_wsocket = None

    if config_ready:
        emby_wsocket = XnoppoWs()
        emby_wsocket.ws_config = config
        emby_wsocket.config_file = config_file
        emby_wsocket.ws_lang = lang
        x = threading.Thread(target=thread_function, args=(emby_wsocket,))
        x.daemon = True
        x.start()
    else:
        print(
            "Config is not complete yet. Web UI is available; Emby websocket will not start."
        )

    espera = 0
    estado_anterior = ""

    logging.debug("Arrancamos el Servidor Web\n")
    serverPort = 8090
    webServer = HTTPServer(("", serverPort), MyServer)
    print("Server started http://%s:%s" % ("", serverPort))
    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass
    webServer.server_close()
    logging.info("Fin proceso")
    logging.info("Finished")
    print("Server stopped.")
