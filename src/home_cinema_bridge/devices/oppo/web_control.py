import json
import logging
import socket
import urllib.parse

from home_cinema_bridge.network.http import get_http_session
from lib.devices.oppo.control_api_activation import OppoControlApiActivator
from lib.devices.oppo.control_api_client import OppoControlApiClient
from lib.devices.oppo.legacy_network_compat import (
    LoginNFS,
    LoginSambaWithOutID,
    smbtrick,
)
from lib.devices.oppo.mounted_share import (
    OppoMountedShare,
    parse_mounted_share_response,
)


def oppo_control_api_client(config):
    return OppoControlApiClient.from_config(config)


def sendnotifyremote(UDP_IP):
    UDP_PORT = 7624
    MESSAGE = "NOTIFY OREMOTE LOGIN"

    logging.debug("UDP target IP: %s", UDP_IP)
    logging.debug("UDP target port: %s", UDP_PORT)
    logging.debug("message: %s", MESSAGE)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(bytes(MESSAGE, "utf-8"), (UDP_IP, UDP_PORT))

    return 0


def check_socket(config, session_id=None):
    activator = OppoControlApiActivator.from_config(config)
    result = activator.ensure_control_api_available(
        max_attempts=_web_control_api_attempts(config)
    )

    if result.available:
        logging.debug(
            "OPPO control API available | host=%s | port=%s | attempts=%s",
            result.host,
            result.port,
            result.attempts,
        )
        return 0

    logging.warning(
        "Timeout waiting for OPPO control API | host=%s | port=%s | attempts=%s | error=%s",
        result.host,
        result.port,
        result.attempts,
        result.error,
    )
    return 1


def _web_control_api_attempts(config) -> int:
    configured_attempts = int(config.get("oppo_web_control_api_attempts", 3))
    return max(1, configured_attempts)


def getmainfirmwareversion(config):
    return oppo_control_api_client(config).get_main_firmware_version()


def getsetupmenu(config):
    return oppo_control_api_client(config).get_setup_menu()


def OppoSignin(config):
    return oppo_control_api_client(config).sign_in()


def getdevicelist(config):
    return oppo_control_api_client(config).get_device_list()


def getglobalinfo(config):
    return oppo_control_api_client(config).get_global_info()


def mountSharedFolder(server, folder, Username, Password, config, checksmb=True):
    if config["DebugLevel"] == 2:
        print("*** mountSharedFolder ***")

    logging.debug("*** mountSharedFolder ***")

    if config["smbtrick"] is True and checksmb is True:
        smbtrick(server + "/" + folder, config)

    response_text = oppo_control_api_client(config).mount_samba_folder(
        server=server,
        folder=folder,
        timeout=config["timeout_oppo_mount"],
    )

    if config["DebugLevel"] == 2:
        print(response_text)
        print("*** Fin mountSharedFolder ***")

    logging.debug("*** Mount Response: %s", response_text)
    return response_text


def mountSharedNFSFolder(server, folder, Username, Password, config):
    if config["DebugLevel"] == 2:
        print("*** mountSharedNFSFolder ***")

    logging.debug("*** mountSharedNFSFolder ***")

    response_text = oppo_control_api_client(config).mount_nfs_folder(
        server=server,
        folder=folder,
        timeout=config["timeout_oppo_mount"],
    )

    if config["DebugLevel"] == 2:
        print(response_text)
        print("*** Fin mountSharedNFSFolder ***")

    logging.debug("*** Mount Response: %s", response_text)
    return response_text


def build_oppo_mounted_folder_path(mounted_share: OppoMountedShare, folder: str) -> str:
    mount_path = mounted_share.mount_path.rstrip("/")

    if not folder or folder == "/":
        return mount_path + "/"

    return mount_path + "/" + folder.lstrip("/")


def getfilelist(config, folder, mounted_share: OppoMountedShare):
    if config["DebugLevel"] == 2:
        print("*** getfilelist ***")

    logging.debug("*** getfilelist ***")

    mounted_folder_path = build_oppo_mounted_folder_path(mounted_share, folder)

    payload = urllib.parse.quote(
        json.dumps(
            {
                "path": mounted_folder_path,
                "fileType": 1,
                "mediaType": 3,
                "flag": 1,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )

    url = "http://" + config["Oppo_IP"] + ":436/getfilelist?" + payload
    headers = {}

    logging.debug(url)

    response = get_http_session("oppo-legacy").get(url, headers=headers)
    test = response.content
    b = test.rsplit(b"\x01")

    files = []
    file = {}
    file["Id"] = 0
    file["Foldername"] = ".."
    files.append(file)

    indice = 1

    for c in b:
        if c.find(b"\x02") == -1:
            index = 0
            ult = 0
            d = c

            while index != -1:
                index = c.find(b"\x00", index)

                if index == -1:
                    d = d[ult:]
                else:
                    ult = index + 1
                    index = index + 1

            e = d.decode("utf-8")

            if e != "":
                file = {}
                file["Id"] = indice
                file["Foldername"] = e
                indice = indice + 1
                files.append(file)

    if config["DebugLevel"] == 2:
        print("*** Fin getfilelist ***")

    logging.debug("*** getfilelist Response: %s", response.text)
    return files


def getNfsShareFolderlist(config):
    if config["DebugLevel"] == 2:
        print("*** getNfsShareFolderlist ***")
    logging.debug("*** getNfsShareFolderlist ***")
    url = "http://" + config["Oppo_IP"] + ":436/getNfsShareFolderlist"
    headers = {}
    logging.debug(url)
    response = get_http_session("oppo-legacy").get(url, headers=headers)
    test = response.content
    b = test.rsplit(b"\x01")
    files = []
    file = {}
    file["Id"] = 0
    file["Foldername"] = ".."
    files.append(file)
    indice = 1
    for c in b:
        if c.find(b"\x02") == -1:
            index = 0
            ult = 0
            d = c
            while index != -1:
                index = c.find(b"\x00", index)
                if index == -1:
                    d = d[ult:]
                else:
                    ult = index + 1
                    index = index + 1
            e = d.decode("utf-8")
            if e != "":
                file = {}
                file["Id"] = indice
                file["Foldername"] = e
                indice = indice + 1
                files.append(file)
    if config["DebugLevel"] == 2:
        print("*** Fin getNfsShareFolderlist ***")
    logging.debug("*** getNfsShareFolderlist Response: %s", response.text)
    return files


def getSambaShareFolderlist(config):
    if config["DebugLevel"] == 2:
        print("*** getSambaShareFolderlist ***")
    logging.debug("*** getSambaShareFolderlist ***")
    url = "http://" + config["Oppo_IP"] + ":436/getSambaShareFolderlist"
    headers = {}
    logging.debug(url)
    response = get_http_session("oppo-legacy").get(url, headers=headers)
    test = response.content
    b = test.rsplit(b"\x01")
    files = []
    file = {}
    file["Id"] = 0
    file["Foldername"] = ".."
    files.append(file)
    indice = 1
    for c in b:
        if c.find(b"\x02") == -1:
            index = 0
            ult = 0
            d = c
            while index != -1:
                index = c.find(b"\x00", index)
                if index == -1:
                    d = d[ult:]
                else:
                    ult = index + 1
                    index = index + 1
            e = d.decode("utf-8")
            if e != "":
                file = {}
                file["Id"] = indice
                file["Foldername"] = e
                indice = indice + 1
                files.append(file)
    if config["DebugLevel"] == 2:
        print("*** Fin getSambaShareFolderlist ***")
    logging.debug("*** getSambaShareFolderlist Response: %s", response.text)
    return files


def navigate_folder(path, config):
    def build_error_files(message):
        return [
            {
                "Id": 0,
                "Foldername": "..",
            },
            {
                "Id": 1,
                "Foldername": message,
            },
        ]

    path = path.replace("\\\\", "\\")
    path = path.replace("\\", "/")
    path = path.replace("//", "/")

    devices = getdevicelist(config)
    device_list = json.loads(devices)

    if path == "/":
        files = []
        indice = 1

        for device in device_list["devicelist"]:
            file = {}
            file["Id"] = indice
            file["Foldername"] = device["name"]
            files.append(file)
            indice = indice + 1

        return files

    path_parts = path.strip("/").split("/", 1)
    servidor = path_parts[0]
    nfs = resolve_server_is_nfs(config, device_list, servidor)

    if len(path_parts) == 1 or not path_parts[1]:
        if nfs:
            response_login = LoginNFS(config, servidor)
            response = json.loads(response_login)

            if response.get("success") == True:
                return getNfsShareFolderlist(config)

            return build_error_files(
                "LOGIN FAILED:" + response.get("retInfo", "No hay mas info")
            )

        response_login = LoginSambaWithOutID(config, servidor)
        response = json.loads(response_login)

        if response.get("success") == True:
            return getSambaShareFolderlist(config)

        return build_error_files(
            "LOGIN FAILED:" + response.get("retInfo", "No hay mas info")
        )

    carpeta = path_parts[1]
    last_folder = "/"

    if nfs:
        response_login = LoginNFS(config, servidor)
        response = json.loads(response_login)

        if response.get("success") != True:
            return build_error_files(
                "LOGIN FAILED:" + response.get("retInfo", "No hay mas info")
            )

        response_data7 = mountSharedNFSFolder(servidor, carpeta, "", "", config)

    else:
        response_login = LoginSambaWithOutID(config, servidor)
        response = json.loads(response_login)

        if response.get("success") != True:
            return build_error_files(
                "LOGIN FAILED:" + response.get("retInfo", "No hay mas info")
            )

        response_data7 = mountSharedFolder(servidor, carpeta, "", "", config)

    response_mount, mounted_share = parse_mounted_share_response(
        response_data7,
        server=servidor,
        folder=carpeta,
        is_nfs=nfs,
    )

    if mounted_share is None:
        return build_error_files(
            "MOUNT FAILED:" + response_mount.get("retInfo", "No hay mas info")
        )

    return getfilelist(config, last_folder, mounted_share)


def sendremotekey(key, config):
    response_text = oppo_control_api_client(config).send_remote_key(key)
    return response_text


def resolve_server_is_nfs(config, device_list, server_name):
    nfs = config["default_nfs"]

    for device in device_list["devicelist"]:
        if device["name"].upper() == server_name.upper():
            return device["sub_type"] == "nfs"

    return nfs
