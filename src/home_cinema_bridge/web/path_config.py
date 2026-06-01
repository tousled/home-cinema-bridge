import json
import logging
import time

from home_cinema_bridge.devices.oppo.web_control import (
    LoginNFS,
    LoginSambaWithOutID,
    OppoSignin,
    check_socket,
    getdevicelist,
    getglobalinfo,
    getmainfirmwareversion,
    getsetupmenu,
    mountSharedFolder,
    mountSharedNFSFolder,
    sendremotekey,
)
from lib.devices.oppo.mounted_share import parse_mounted_share_response
from lib.oppo_autoscript import unmount_oppo_path


def test_path_configuration(config, server):
    try:
        test_media_path = build_test_media_path(server)
        mount_path = get_mount_path(test_media_path, server)
    except ValueError as exc:
        logging.warning(
            "Invalid path test configuration: %s | payload=%s",
            exc,
            server,
        )
        return str(exc)

    return test_mount_path(config, mount_path["Servidor"], mount_path["Carpeta"])


def build_test_media_path(server_data):
    emby_path = normalize_config_path(server_data.get("Emby_Path", ""))

    if not emby_path:
        raise ValueError("INVALID PATH CONFIG: Emby_Path is required.")

    return emby_path.rstrip("/") + "/test.mkv"


def get_mount_path(movie, server_data):
    emby_path = normalize_config_path(server_data.get("Emby_Path", ""))
    oppo_path = normalize_config_path(server_data.get("Oppo_Path", ""))

    if not emby_path:
        raise ValueError("INVALID PATH CONFIG: Emby_Path is required.")

    if not oppo_path or oppo_path == "/":
        raise ValueError("INVALID PATH CONFIG: Oppo_Path is required.")

    movie = normalize_config_path(movie)
    emby_prefix = emby_path.rstrip("/")
    oppo_prefix = oppo_path.rstrip("/")

    if movie != emby_prefix and not movie.startswith(emby_prefix + "/"):
        raise ValueError("INVALID PATH CONFIG: Emby_Path does not match the test path.")

    movie = oppo_prefix + movie[len(emby_prefix) :]
    path_parts = movie.strip("/").split("/")

    if len(path_parts) < 3:
        raise ValueError(
            "INVALID PATH CONFIG: Oppo_Path must include server and folder."
        )

    return {
        "Servidor": path_parts[0],
        "Carpeta": "/".join(path_parts[1:-1]),
        "Fichero": path_parts[-1],
    }


def normalize_config_path(path):
    return str(path or "").strip().replace("\\\\", "\\").replace("\\", "/")


def test_mount_path(config, servidor, carpeta):
    result = check_socket(config)
    if result != 0:
        print(
            "No se puede conectar, revisa las configuraciones o que el OPPO este encendido o en reposo"
        )
        return "FAILED"

    getmainfirmwareversion(config)
    getdevicelist(config)
    getsetupmenu(config)
    OppoSignin(config)
    getdevicelist(config)
    getglobalinfo(config)
    response_data6f = getdevicelist(config)
    sendremotekey("EJT", config)
    time.sleep(1)

    getsetupmenu(config)
    while response_data6f.find('devicelist":[]') > 0:
        time.sleep(1)
        response_data6f = getdevicelist(config)
        sendremotekey("QPW", config)

    device_list = json.loads(response_data6f)
    if config["DebugLevel"] > 0:
        print(device_list)

    nfs = config["default_nfs"]
    for device in device_list["devicelist"]:
        if device["name"].upper() == servidor.upper():
            nfs = device["sub_type"] == "nfs"
            break

    if nfs:
        LoginNFS(config, servidor)
    else:
        LoginSambaWithOutID(config, servidor)

    if config["Always_ON"] == False:
        time.sleep(5)

    getsetupmenu(config)
    if nfs:
        response_mount = mountSharedNFSFolder(servidor, carpeta, "", "", config)
    else:
        response_mount = mountSharedFolder(servidor, carpeta, "", "", config)

    if config["Autoscript"]:
        _, mounted_share = parse_mounted_share_response(
            response_text=response_mount,
            server=servidor,
            folder=carpeta,
            is_nfs=nfs,
        )
        if mounted_share:
            unmount_oppo_path(
                host=config["Oppo_IP"],
                port=int(config.get("OPPO_Port", 23)),
                mount_path=mounted_share.mount_path,
                debug=config["DebugLevel"] > 0,
                timeout=config["timeout_oppo_mount"],
            )

    response = json.loads(response_mount)
    if response["success"]:
        return "OK"

    return "FAILURE"
