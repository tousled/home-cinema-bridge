import logging
import urllib.parse
import requests
import json
import os
import socket
import time

from .Xnoppo_AVR import av_check_power, av_power_off, av_change_hdmi
from .Xnoppo_TV import tv_change_hdmi, tv_set_prev
from .devices.oppo.control_api_activation import OppoControlApiActivator
from .devices.oppo.control_api_client import OppoControlApiClient
from .devices.oppo.playback_state_waiter import wait_until_oppo_reports_active_playback
from .devices.oppo.playback_status_client import OppoPlaybackStatusClient
from .devices.oppo.mounted_share import parse_mounted_share_response, OppoMountedShare
from .oppo_autoscript import unmount_oppo_path
from .playback.timing import PlaybackStartupTimer

_qpl_last_observed_states = {}


def reset_qpl_observation_state():
    _qpl_last_observed_states.clear()


def log_oppo_qpl_state(config, label, changes_only=False):
    try:
        debug_level = int(config.get("DebugLevel", 0))
        if debug_level <= 0:
            return None

        oppo_ip = config.get("Oppo_IP")
        if not oppo_ip:
            print(f"QPL:{label} skipped | Oppo_IP is not configured")
            return None

        client = OppoPlaybackStatusClient(
            host=oppo_ip,
            port=int(config.get("OPPO_Port", 23)),
            timeout=float(config.get("timeout_oppo_conection", 3)),
        )

        result = client.query_playback_state()

        if changes_only and debug_level < 2:
            current_state = (result.status, result.category.value, result.ok)
            previous_state = _qpl_last_observed_states.get(label)

            if previous_state == current_state:
                return result

            _qpl_last_observed_states[label] = current_state

        print(
            f"QPL:{label} | "
            f"raw={result.raw_response!r} | "
            f"status={result.status} | "
            f"category={result.category.value} | "
            f"ok={result.ok}"
        )

        return result

    except Exception as exc:
        try:
            if config.get("DebugLevel", 0) > 0:
                print(f"QPL:{label} | ERROR {type(exc).__name__}: {exc}")
        except Exception:
            pass

        return None


def log_oppo_qpl_state_sequence(config, label, samples=5, interval=1):
    try:
        if config.get("DebugLevel", 0) <= 0:
            return

        print(f"QPL:{label}:sequence_start | samples={samples} | interval={interval}s")

        for index in range(samples):
            log_oppo_qpl_state(config, f"{label}[{index + 1}/{samples}]")

            if index < samples - 1:
                time.sleep(interval)

        print(f"QPL:{label}:sequence_end")

    except Exception as exc:
        try:
            if config.get("DebugLevel", 0) > 0:
                print(f"QPL:{label}:sequence | ERROR {type(exc).__name__}: {exc}")
        except Exception:
            pass


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
        max_attempts=int(config["timeout_oppo_conection"])
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


def getplayingtime(config):
    return oppo_control_api_client(config).get_playing_time()


def mountSharedFolderID(server, folder, Username, Password, config):
    if config["DebugLevel"] == 2:
        print("*** mountSharedFolderID ***")

    logging.debug("*** mountSharedFolderID ***")

    response_text = oppo_control_api_client(config).mount_samba_folder_with_id(
        server=server,
        folder=folder,
        username=Username,
        password=Password,
        timeout=config["timeout_oppo_mount"],
    )

    if config["DebugLevel"] == 2:
        print("*** Fin mountSharedFolderID ***")

    logging.debug("*** Mount Response: %s", response_text)
    return response_text


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


def LoginNFS(config, server):
    logging.debug("LoginNFS")
    response_text = oppo_control_api_client(config).login_nfs_server(server)

    if config["DebugLevel"] == 2:
        print("*** LoginNFS Response: " + response_text)

    logging.debug("*** LoginNFS Response: %s", response_text)
    return response_text


def playnormalfile(mounted_share: OppoMountedShare, filename, index, config):
    if config["DebugLevel"] == 2:
        print("*** playnormalfile ***")

    logging.debug("*** playnormalfile ***")

    response_text = oppo_control_api_client(config).play_normal_file(
        mounted_share=mounted_share,
        filename=filename,
        index=index,
        timeout=config["timeout_oppo_playitem"],
    )

    if config["DebugLevel"] == 2:
        print("*** Fin playnormalfile ***")
        print(response_text)

    logging.debug("*** Playnormalfile Response: %s", response_text)
    return response_text


def checkfolderhasbdmv(config, mounted_share: OppoMountedShare, relative_folder_path: str):
    if config["DebugLevel"] == 2:
        print("*** checkfolderhasbdmv ***")

    logging.debug("*** checkfolderhasbdmv ***")

    response_text = oppo_control_api_client(config).mounted_folder_contains_blu_ray_structure(
        mounted_share=mounted_share,
        relative_folder_path=relative_folder_path,
        timeout=config["timeout_oppo_playitem"],
    )

    if config["DebugLevel"] == 2:
        print("*** Fin checkfolderhasbdmv ***")
        print(response_text)

    logging.debug("*** Checkfolderhasbdmv Response: %s", response_text)
    return response_text


def convert(s):
    try:
        return s.group(0).encode("ISO-8859-1").decode("utf8")
    except:
        return s.group(0)


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

    response = requests.get(url, headers=headers)
    test = response.content
    b = test.rsplit(b'\x01')

    files = []
    file = {}
    file["Id"] = 0
    file["Foldername"] = ".."
    files.append(file)

    indice = 1

    for c in b:
        if c.find(b'\x02') == -1:
            index = 0
            ult = 0
            d = c

            while index != -1:
                index = c.find(b'\x00', index)

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
    response = requests.get(url, headers=headers)
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
    response = requests.get(url, headers=headers)
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

            
def setplaytime(config,playticks):
    logging.debug("setplaytime")
    secs_total = playticks / 10000000
    h = secs_total // 3600
    m = (secs_total % 3600) // 60
    s = (secs_total % 3600) % 60
    url1 = "http://" + config["Oppo_IP"] + ":436/setplaytime?"
    url = ""
    url = url + '{"h":' + str(int(h)) + ","
    url = url + '"m":' + str(int(m)) + ","
    url = url + '"s":' + str(int(s)) + "}"
    headers = {}
    url = url1 + url
    logging.debug(url)
    response = requests.get(url, headers=headers)
    logging.debug("*** setplaytime Response: %s", response.text)
    return response.text


def smbtrick(path, config):
    path = path.replace("\\\\", "\\")
    path = path.replace("\\", "/")
    path = path.replace("//", "/")
    devices = getdevicelist(config)
    device_list = json.loads(devices)
    word = "/"
    inicio = path.find(word)
    inicio = inicio + 1
    final = path.find(word, inicio, len(path))
    servidor = path[inicio:final]
    final = final + 1
    result = path.find(word, final, len(path))
    carpeta = path[final:result]
    response_login = LoginSambaWithOutID(config, servidor)
    response = json.loads(response_login)
    if response["success"] == True:
        files = getSambaShareFolderlist(config)
        for file in files:
            if file["Foldername"] != "..":
                if file["Foldername"].upper() != carpeta.upper():
                    mountSharedFolder(
                        servidor, file["Foldername"], "", "", config, False
                    )
                    if config["DebugLevel"] > 0:
                        print(servidor + "-" + file["Foldername"])
                    return 0
    else:
        devices = getdevicelist(config)
        device_list = json.loads(devices)
        for device in device_list["devicelist"]:
            if device["name"].upper() != servidor.upper():
                if device["sub_type"] == "cifs":
                    LoginSambaWithOutID(config, device["name"])
                    files = getSambaShareFolderlist(config)
                    for file in files:
                        if file["Foldername"] != "..":
                            mountSharedFolder(
                                device["name"],
                                file["Foldername"],
                                "",
                                "",
                                config,
                                False,
                            )
                            return 0


def setaudiotrack(config, audio_index):
    logging.debug("setaudiotrack")
    url = (
        "http://"
        + config["Oppo_IP"]
        + ':436/setaudiomenulist?{"cur_index":'
        + str(int(audio_index))
        + "}"
    )
    headers = {}
    logging.debug(url)
    response = requests.get(url, headers=headers)
    logging.debug("*** setaudiotrack Response: %s", response.text)
    return response.text


def LoginSambaWithOutID(config, server):
    logging.debug("LoginSambaWithOutID")
    response_text = oppo_control_api_client(config).login_samba_without_id(server)

    if config["DebugLevel"] == 2:
        print("*** LoginSambaWithOutID Response: " + response_text)

    logging.debug("*** LoginSambaWithOutID Response: %s", response_text)
    return response_text


def getmaxaudiotrack(config):
    logging.debug("getaudiotrack")
    url = "http://" + config["Oppo_IP"] + ":436/getaudiomenulist?"
    headers = {}
    logging.debug(url)
    response = requests.get(url, headers=headers)
    logging.debug("*** getaudiotrack Response: %s", response.text)
    if config["DebugLevel"] == 2:
        print(response.text)
    audio_list = json.loads(response.text)
    return len(audio_list["audio_list"])


def apply_selected_subtitle_track(emby_session, params, startup_timer=None):
    logging.debug("apply_selected_subtitle_track")
    try:
        subtitle_stream_index = params.get("subtitle_stream_index")

        if subtitle_stream_index is not None and int(subtitle_stream_index) >= 0:
            if emby_session.config["DebugLevel"] > 0:
                print("llamamos a set_subtitles_track")
                print(subtitle_stream_index)

            if startup_timer is not None:
                with startup_timer.measure_step("subtitle_resolve_emby_to_oppo_index"):
                    subs_index = emby_session.get_xnoppo_subs_index(
                        params["ControllingUserId"],
                        params["item_id"],
                        subtitle_stream_index,
                    )
            else:
                subs_index = emby_session.get_xnoppo_subs_index(
                    params["ControllingUserId"],
                    params["item_id"],
                    subtitle_stream_index,
                )

            if subs_index is not None and int(subs_index) >= 0:
                if startup_timer is not None:
                    with startup_timer.measure_step("subtitle_set_oppo_track"):
                        set_subtitles_track(
                            emby_session.config,
                            subs_index,
                            startup_timer=startup_timer,
                        )
                else:
                    set_subtitles_track(emby_session.config, subs_index)

            elif emby_session.config["DebugLevel"] > 0:
                print("No valid OPPO subtitle index found")

        elif emby_session.config["DebugLevel"] > 0:
            print("No subtitle selected; skipping subtitle track selection")

    except:
        if emby_session.config["DebugLevel"] > 0:
            print("Error indicando el subtitulo")


def set_subtitles_track(config, subs_index, startup_timer=None):
    logging.debug("set_subtitles_track")

    if config["DebugLevel"] > 0:
        print(subs_index)

    if startup_timer is not None:
        with startup_timer.measure_step("subtitle_read_current_oppo_track"):
            actual_track = get_current_subtitle_track(config)
    else:
        actual_track = get_current_subtitle_track(config)

    if config["DebugLevel"] > 0:
        print(actual_track)

    url = (
        "http://"
        + config["Oppo_IP"]
        + ':436/setsubttmenulist?{"cur_index":'
        + str(int(subs_index))
        + "}"
    )
    headers = {}
    logging.debug(url)

    timeout = 0

    if startup_timer is not None:
        with startup_timer.measure_step("subtitle_set_and_confirm_oppo_track"):
            while actual_track != subs_index and timeout < 10:
                response = requests.get(url, headers=headers)
                logging.debug("*** set_subtitles_track Response: %s", response.text)

                if config["DebugLevel"] == 2:
                    print(response.text)

                time.sleep(1)
                actual_track = get_current_subtitle_track(config)
                timeout = timeout + 1
    else:
        while actual_track != subs_index and timeout < 10:
            response = requests.get(url, headers=headers)
            logging.debug("*** set_subtitles_track Response: %s", response.text)

            if config["DebugLevel"] == 2:
                print(response.text)

            time.sleep(1)
            actual_track = get_current_subtitle_track(config)
            timeout = timeout + 1

    return 0


def get_current_subtitle_track(config):
    logging.debug("get_current_subtitle_track")
    url = "http://" + config["Oppo_IP"] + ":436/getsubtitlemenulist?"
    headers = {}
    logging.debug(url)
    response = requests.get(url, headers=headers)
    logging.debug("*** getsubtitlemenulist Response: %s", response.text)
    response_subs = json.loads(response.text)
    try:
        for subs in response_subs["subtitle_list"]:
            if subs["selected"] == True:
                return subs["index"]
    except:
        return 0


def sendremotekey(key, config):
    url = (
        "http://"
        + config["Oppo_IP"]
        + ":436/sendremotekey?%7B%22key%22%3A%22"
        + key
        + "%22%7D"
    )
    headers = {}
    response = requests.get(url, headers=headers)
    return response.text


def parse_oppo_path(movie):
    word = "/"
    inicio = movie.find(word)
    inicio = inicio + 1
    final = movie.find(word, inicio, len(movie))
    servidor = movie[inicio:final]

    ultimo = final + 1
    result = final + 1
    while result > 0:
        ultimo = result + 1
        result = movie.find(word, ultimo, len(movie))

    fichero = movie[ultimo : len(movie)]

    final = final + 1
    ultimo = ultimo - 1
    carpeta = movie[final:ultimo]

    return servidor, carpeta, fichero


def resolve_server_is_nfs(config, device_list, server_name):
    nfs = config["default_nfs"]

    for device in device_list["devicelist"]:
        if device["name"].upper() == server_name.upper():
            return device["sub_type"] == "nfs"

    return nfs


def resolve_oppo_movie_path(movie, config):
    logging.info("Ruta antes de los reemplazos por server: %s", movie)

    for server in config["servers"]:
        logging.info("Sustituimos %s por %s", server["Emby_Path"], server["Oppo_Path"])
        movie = movie.replace(server["Emby_Path"], server["Oppo_Path"])
        logging.info("Resultado : %s", movie)

    logging.info("Ruta antes de los reemplazos de path: %s", movie)
    movie = movie.replace("\\\\", "\\")
    movie = movie.replace("\\", "/")
    logging.info("Ruta despues: %s", movie)

    return movie


def resolve_mocked_item_info(emby_session, params, item_info):
    file_path = item_info["Path"]
    file_mockup = file_path[: len(file_path) - 3] + "txt"
    logging.debug("File_mockup: %s", file_mockup)

    if not os.path.isfile(file_mockup):
        return item_info, False

    with open(file_mockup, "r") as f3:
        newitem = f3.read().strip()

    if emby_session.config["DebugLevel"] > 0:
        print("File_encontrado - contenido: " + newitem)
    logging.debug("File_encontrado - contenido: %s", newitem)

    if not newitem:
        return item_info, True

    mocked_item_info = emby_session.get_item_info2(
        emby_session.user_info["User"]["Id"], newitem, params["media_source_id"]
    )

    return mocked_item_info, True


def playother(EmbySession, data, scripterx=False):
    if EmbySession.config["DebugLevel"] > 0:
        print("Inicio Replay")
    logging.info("Con el OPPO iniciado le decimos que cambie de pelicula")
    reset_qpl_observation_state()
    EmbySession.playstate = "Replay"
    params = EmbySession.process_data(data)
    ItemInfo = EmbySession.get_item_info2(
        EmbySession.user_info["User"]["Id"],
        params["item_id"],
        params["media_source_id"],
    )
    logging.info("-----------------------------------------------------------")
    if scripterx:
        if EmbySession.config["DebugLevel"] > 0:
            print("Iniciando en el OPPO - X")
        EmbySession.send_message2(
            params["Session_id"], EmbySession.lang["x_msg_init_oppo"]
        )
    else:
        if EmbySession.config["DebugLevel"] > 0:
            print("Iniciando en el OPPO")
        EmbySession.send_user_message(
            params["ControllingUserId"], EmbySession.lang["x_msg_init_oppo"]
        )

    ItemInfo, mock_file_exists = resolve_mocked_item_info(EmbySession, params, ItemInfo)

    if not mock_file_exists and scripterx:
        if EmbySession.config["DebugLevel"] > 0:
            print("Paramos reproduccion en el dispositivo")
        EmbySession.playback_stop(params["Session_id"])

    movie = ItemInfo["Path"]
    Container = ItemInfo["Container"]
    movie = resolve_oppo_movie_path(movie, EmbySession.config)
    logging.info("-----------------------------------------------------------")
    servidor, carpeta, fichero = parse_oppo_path(movie)
    logging.info("Servidor               : %s", servidor)
    logging.info("Fichero                : %s", fichero)
    logging.info("Carpeta                : %s", carpeta)
    logging.info("-----------------------------------------------------------")
    EmbySession.server = servidor
    EmbySession.folder = carpeta
    EmbySession.filename = fichero
    EmbySession.playedtitle = ItemInfo["Name"]
    response_data6f = getdevicelist(EmbySession.config)
    device_list = json.loads(response_data6f)

    if EmbySession.config["DebugLevel"] > 0:
        print(device_list)

    nfs = resolve_server_is_nfs(EmbySession.config, device_list, servidor)

    if nfs:
        LoginNFS(EmbySession.config, servidor)
        response_data7 = mountSharedNFSFolder(
            servidor, carpeta, "", "", EmbySession.config
        )
    else:
        LoginSambaWithOutID(EmbySession.config, servidor)
        response_data7 = mountSharedFolder(
            servidor, carpeta, "", "", EmbySession.config
        )

    response_mount, mounted_share = parse_mounted_share_response(
        response_data7,
        server=servidor,
        folder=carpeta,
        is_nfs=nfs,
    )

    if mounted_share is None:
        error = response_mount.get("retInfo", "No hay mas info")
        logging.warning(
            "Replay mount failed | server=%s | folder=%s | error=%s",
            servidor,
            carpeta,
            error,
        )

        if scripterx:
            EmbySession.send_message2(
                params["Session_id"],
                EmbySession.lang["x_msg_error_mount"]
                + servidor
                + "/"
                + carpeta
                + " - info:"
                + error,
                5000,
            )
        else:
            EmbySession.send_user_message(
                params["ControllingUserId"],
                EmbySession.lang["x_msg_error_mount"]
                + servidor
                + "/"
                + carpeta
                + " - info:"
                + error,
                5000,
            )

        EmbySession.playstate = "Free"
        return

    if Container == "bluray":
        response_data8 = checkfolderhasbdmv(EmbySession.config, mounted_share, fichero)
    else:
        response_data8 = playnormalfile(
            mounted_share,
            fichero,
            "0",
            EmbySession.config,
        )

    json.loads(response_data8)
    log_oppo_qpl_state(EmbySession.config, "after_playnormalfile")
    timeout = EmbySession.config["timeout_oppo_playitem"]

    playback_start_poll_interval = 0.5
    last_notified_second = -1

    def notify_playback_waiting(attempt: int):
        nonlocal last_notified_second

        elapsed_seconds = int(attempt * playback_start_poll_interval)
        notification_interval_seconds = 2

        if elapsed_seconds <= 0:
            return

        if elapsed_seconds % notification_interval_seconds != 0:
            return

        if elapsed_seconds == last_notified_second:
            return

        last_notified_second = elapsed_seconds
        message = EmbySession.lang["x_msg_wait_for_play"] + str(elapsed_seconds) + "s"

        if scripterx:
            EmbySession.send_message2(params["Session_id"], message, 999)
        else:
            EmbySession.send_user_message(params["ControllingUserId"], message, 999)

    startup_result = wait_until_oppo_reports_active_playback(
        config=EmbySession.config,
        timeout=timeout,
        interval=playback_start_poll_interval,
        on_playback_waiting=notify_playback_waiting,
    )

    logging.info(
        "QPL playback startup result | started=%s | status=%s | category=%s | attempts=%s | elapsed=%.2fs",
        startup_result.started,
        startup_result.status,
        startup_result.category.value,
        startup_result.attempts,
        startup_result.elapsed_seconds,
    )

    if not startup_result.started:
        if scripterx:
            EmbySession.send_message2(
                params["Session_id"], EmbySession.lang["x_msg_timeout_play"]
            )
        else:
            EmbySession.send_user_message(
                params["ControllingUserId"], EmbySession.lang["x_msg_timeout_play"]
            )
            logging.info("Timeout Reproduciendo %s", movie)
        EmbySession.playstate = "Playing"
    else:
        if params["auto_resume"] <= 0:
            setplaytime(EmbySession.config, 0)
        else:
            playticks = params["auto_resume"]
            setplaytime(EmbySession.config, playticks)
        try:
            if params["audio_stream_index"]:
                audio_index = EmbySession.get_xnoppo_audio_index(
                    params["ControllingUserId"],
                    params["item_id"],
                    params["audio_stream_index"],
                )
                setaudiotrack(EmbySession.config, audio_index)
        except:
            pass
        apply_selected_subtitle_track(EmbySession, params)
        EmbySession.playnow(data)
        EmbySession.currentdata = data
        EmbySession.playstate = "Playing"
        if EmbySession.config["DebugLevel"] > 0:
            print("Fin Replay")


def playto_file(EmbySession, data, scripterx=False):
    startup_timer = PlaybackStartupTimer()
    EmbySession.playstate = "Loading"
    EmbySession.currentdata = data
    reset_qpl_observation_state()
    log_oppo_qpl_state(EmbySession.config, "playto_file_start")
    if EmbySession.config["DebugLevel"] > 0:
        print("scripterx is " + str(scripterx))

    with startup_timer.measure_step("sendnotifyremote"):
        sendnotifyremote(EmbySession.config["Oppo_IP"])

    with startup_timer.measure_step("process_emby_payload"):
        params = EmbySession.process_data(data)

    with startup_timer.measure_step("load_emby_item_info"):
        item_info = EmbySession.get_item_info2(
            EmbySession.user_info["User"]["Id"],
            params["item_id"],
            params["media_source_id"],
        )

    with startup_timer.measure_step("stop_emby_client_playback"):
        if scripterx:
            if EmbySession.config["DebugLevel"] > 0:
                print("Paramos reproduccion en el dispositivo")
            EmbySession.playback_stop(params["Session_id"])
    movie = ""
    with startup_timer.measure_step("ensure_oppo_control_api_available"):
        if scripterx:
            result = check_socket(EmbySession.config, params["Session_id"])
        else:
            result = check_socket(EmbySession.config)

    if result == 0:
        if scripterx:
            if EmbySession.config["DebugLevel"] > 0:
                print("Iniciando en el OPPO - X")
            EmbySession.send_message2(
                params["Session_id"], EmbySession.lang["x_msg_init_oppo"]
            )
        else:
            if EmbySession.config["DebugLevel"] > 0:
                print("Iniciando en el OPPO")
            EmbySession.send_user_message(
                params["ControllingUserId"], EmbySession.lang["x_msg_init_oppo"]
            )

        with startup_timer.measure_step("oppo_initial_control_queries"):
            getmainfirmwareversion(EmbySession.config)
            getdevicelist(EmbySession.config)
            getsetupmenu(EmbySession.config)
            OppoSignin(EmbySession.config)
            getdevicelist(EmbySession.config)
            getglobalinfo(EmbySession.config)
            response_data6f = getdevicelist(EmbySession.config)

        with startup_timer.measure_step("eject_oppo_disc_or_media"):
            sendremotekey("EJT", EmbySession.config)
            if EmbySession.config["BRDisc"] == True:
                time.sleep(1)
                sendremotekey("EJT", EmbySession.config)

        with startup_timer.measure_step("ensure_av_power_on"):
            if EmbySession.config["AV"] == True:
                if EmbySession.config["DebugLevel"] > 0:
                    print("AV POWER")
                logging.info("Comprobamos que esta encendido el AV")
                try:
                    result = av_check_power(EmbySession.config)
                    if EmbySession.config["DebugLevel"] > 0:
                        print(result)
                    logging.info("Resultado: %s", str(result))
                except:
                    pass

        with startup_timer.measure_step("refresh_setup_menu_before_mount"):
            time.sleep(1)
            getsetupmenu(EmbySession.config)

        with startup_timer.measure_step("resolve_media_path"):
            item_info, _ = resolve_mocked_item_info(EmbySession, params, item_info)
            movie = item_info["Path"]
            container = item_info["Container"]
            logging.info("-----------------------------------------------------------")
            movie = resolve_oppo_movie_path(movie, EmbySession.config)
            logging.info("-----------------------------------------------------------")
            servidor, carpeta, fichero = parse_oppo_path(movie)

        logging.info("Servidor               : %s", servidor)
        logging.info("Fichero                : %s", fichero)
        logging.info("Carpeta                : %s", carpeta)
        logging.info("-----------------------------------------------------------")
        EmbySession.server = servidor
        EmbySession.folder = carpeta
        EmbySession.filename = fichero
        EmbySession.playedtitle = item_info["Name"]

        if EmbySession.config["wait_nfs"] == True:
            text = 'sub_type":"nfs'
        else:
            text = "sub_type"

        with startup_timer.measure_step("wait_for_oppo_device_list"):
            while response_data6f.find(text) == 0:
                time.sleep(1)
                response_data6f = getdevicelist(EmbySession.config)
                response_data_on = sendremotekey("QPW", EmbySession.config)
                logging.debug("Query POWER ON: %s", response_data_on)

        with startup_timer.measure_step("resolve_share_protocol"):
            device_list = json.loads(response_data6f)
            if EmbySession.config["DebugLevel"] > 0:
                print(device_list)

            nfs = resolve_server_is_nfs(EmbySession.config, device_list, servidor)

        with startup_timer.measure_step("login_share_protocol"):
            if nfs:
                LoginNFS(EmbySession.config, servidor)
                getNfsShareFolderlist(EmbySession.config)
            else:
                LoginSambaWithOutID(EmbySession.config, servidor)
                getSambaShareFolderlist(EmbySession.config)
        with startup_timer.measure_step("legacy_wait_when_oppo_not_always_on"):
            if EmbySession.config["Always_ON"] == False:
                time.sleep(5)

        with startup_timer.measure_step("refresh_setup_menu_after_share_login"):
            getsetupmenu(EmbySession.config)

        if scripterx:
            EmbySession.send_message2(params["Session_id"], EmbySession.lang["x_msg_wait_for_mount"], 1999)
        else:
            EmbySession.send_user_message(params["ControllingUserId"], EmbySession.lang["x_msg_wait_for_mount"], 1999)

        with startup_timer.measure_step("mount_shared_folder"):
            if nfs:
                response_data7 = mountSharedNFSFolder(
                    servidor, carpeta, "", "", EmbySession.config
                )
            else:
                response_data7 = mountSharedFolder(
                    servidor, carpeta, "", "", EmbySession.config
                )

        response_mount, mounted_share = parse_mounted_share_response(response_data7, server=servidor, folder=carpeta, is_nfs=nfs)
        if mounted_share is not None:
            with startup_timer.measure_step("start_oppo_playback"):
                if container == "bluray":
                    response_data8 = checkfolderhasbdmv(
                        config=EmbySession.config, mounted_share=mounted_share, relative_folder_path=fichero
                    )
                else:
                    response_data8 = playnormalfile(mounted_share, fichero, "0",  EmbySession.config)

            response_play = json.loads(response_data8)
            log_oppo_qpl_state(EmbySession.config, "after_playnormalfile")

            if response_play["success"] == True:
                timeout = EmbySession.config["timeout_oppo_playitem"]
                playback_start_poll_interval = 0.5
                last_notified_second = -1

                def notify_playback_waiting(attempt: int):
                    nonlocal last_notified_second

                    elapsed_seconds = int(attempt * playback_start_poll_interval)

                    notification_interval_seconds = 1

                    if elapsed_seconds <= 0:
                        return

                    if elapsed_seconds % notification_interval_seconds != 0:
                        return

                    if elapsed_seconds == last_notified_second:
                        return

                    last_notified_second = elapsed_seconds
                    message = EmbySession.lang["x_msg_wait_for_play"] + str(elapsed_seconds) + "s"

                    if scripterx:
                        EmbySession.send_message2(params["Session_id"], message, 999)
                    else:
                        EmbySession.send_user_message(params["ControllingUserId"], message, 999)

                with startup_timer.measure_step(
                    "wait_until_oppo_reports_active_playback"
                ):
                    startup_result = wait_until_oppo_reports_active_playback(
                        config=EmbySession.config,
                        timeout=timeout,
                        interval=playback_start_poll_interval,
                        on_playback_waiting=notify_playback_waiting,
                    )

                logging.info(
                    "QPL playback startup result | started=%s | status=%s | category=%s | attempts=%s | elapsed=%.2fs",
                    startup_result.started,
                    startup_result.status,
                    startup_result.category.value,
                    startup_result.attempts,
                    startup_result.elapsed_seconds,
                )

                if not startup_result.started:
                    if scripterx:
                        EmbySession.send_message2(
                            params["Session_id"], EmbySession.lang["x_msg_timeout_play"]
                        )
                    else:
                        EmbySession.send_user_message(
                            params["ControllingUserId"],
                            EmbySession.lang["x_msg_timeout_play"],
                        )
                    logging.info("Timeout Reproduciendo %s", movie)
                else:
                    with startup_timer.measure_step("notify_emby_playback_started"):
                        EmbySession.playstate = "Playing"
                        EmbySession.playnow(data)

                    if EmbySession.config["DebugLevel"] > 0:
                        print(params["auto_resume"])

                    with startup_timer.measure_step("apply_resume_position"):
                        if params["auto_resume"] <= 0:
                            playticks = 0
                        else:
                            playticks = params["auto_resume"]

                        setplaytime(EmbySession.config, playticks)

                        if EmbySession.config["DebugLevel"] > 0:
                            print("Se restablece la reproduccion en " + str(playticks))

                    with startup_timer.measure_step("apply_audio_track"):
                        try:
                            if params["audio_stream_index"]:
                                audio_index = EmbySession.get_xnoppo_audio_index(
                                    params["ControllingUserId"],
                                    params["item_id"],
                                    params["audio_stream_index"],
                                )
                                setaudiotrack(EmbySession.config, audio_index)
                        except:
                            pass

                    if EmbySession.config["TV"] == True:
                        with startup_timer.measure_step("switch_tv_to_oppo_input"):
                            logging.info("Cambiamos HDMI de la TV")
                            try:
                                result = tv_change_hdmi(EmbySession.config)
                                if EmbySession.config["DebugLevel"] > 0:
                                    print(result)
                                logging.info("Resultado: %s", str(result))
                            except:
                                pass

                        if scripterx:
                            with startup_timer.measure_step(
                                "stop_emby_client_after_tv_handoff"
                            ):
                                response_data5 = EmbySession.playback_stop(
                                    params["Session_id"]
                                )

                            if EmbySession.config["DebugLevel"] > 0:
                                print(response_data5)
                    else:
                        if scripterx == True:
                            EmbySession.send_message2(
                                params["Session_id"],
                                EmbySession.lang["x_msg_init_play"] + movie,
                            )
                        logging.info("Reprodución iniciada: %s", movie)
                    if EmbySession.config["AV"] == True:
                        if EmbySession.config["DebugLevel"] > 0:
                            print("AV")

                        with startup_timer.measure_step("switch_av_to_oppo_input"):
                            logging.info("Cambiamos HDMI del AV")
                            try:
                                time.sleep(EmbySession.config["av_delay_hdmi"])
                                result = av_change_hdmi(EmbySession.config)
                                if EmbySession.config["DebugLevel"] > 0:
                                    print(result)
                                logging.info("Resultado: %s", str(result))
                            except:
                                pass

                    with startup_timer.measure_step(
                        "initial_global_info_before_progress_loop"
                    ):
                        response_data_gb = getglobalinfo(EmbySession.config)
                        log_oppo_qpl_state(
                            EmbySession.config,
                            "before_getglobalinfo_loop",
                            changes_only=True,
                        )
                    cur_time = 0
                    total_time = 0
                    playingtime = {}
                    playingtime["total_time"] = total_time
                    playingtime["cur_time"] = cur_time

                    positionticks = 0
                    totalticks = 0
                    last_valid_positionticks = 0
                    last_valid_totalticks = 0
                    last_valid_cur_time = 0
                    last_valid_total_time = 0
                    ispaused = False
                    ismuted = False
                    with startup_timer.measure_step("apply_subtitle_track"):
                        apply_selected_subtitle_track(
                            EmbySession, params, startup_timer=startup_timer
                        )
                    startup_timer.log_summary()

                    while response_data_gb.find('"is_video_playing":true') > 0:
                        time.sleep(1)
                        if EmbySession.playstate != "Replay":
                            response_data_gb = getglobalinfo(EmbySession.config)
                            log_oppo_qpl_state(
                                EmbySession.config,
                                "before_getglobalinfo_loop",
                                changes_only=True,
                            )
                            if response_data_gb.find('"is_video_playing":true') > 0:
                                response_playing_time = getplayingtime(
                                    EmbySession.config
                                )
                                playingtime = json.loads(response_playing_time)
                        if response_data_gb.find('"is_video_playing":true') > 0:
                            if EmbySession.config["DebugLevel"] > 0:
                                print(
                                    "PlayingTime: "
                                    + str(playingtime["cur_time"])
                                    + " de "
                                    + str(playingtime["total_time"])
                                )
                            logging.debug(
                                "PlayingTime: %s de %s",
                                str(playingtime["cur_time"]),
                                str(playingtime["total_time"]),
                            )
                            if (
                                playingtime["cur_time"] > 0
                                and playingtime["total_time"] > 0
                            ):
                                positionticks = playingtime["cur_time"] * 10000000
                                total_time = playingtime["total_time"]
                                totalticks = total_time * 10000000

                                last_valid_positionticks = positionticks
                                last_valid_totalticks = totalticks
                                last_valid_cur_time = playingtime["cur_time"]
                                last_valid_total_time = total_time

                            if scripterx == False:
                                EmbySession.playingprogress(
                                    EmbySession.currentdata,
                                    positionticks,
                                    totalticks,
                                    ispaused,
                                    ismuted,
                                )
                                EmbySession.setitemplaybackposition(
                                    EmbySession.currentdata, positionticks, False
                                )

                    if playingtime["cur_time"] <= 0 and last_valid_positionticks > 0:
                        if EmbySession.config["DebugLevel"] > 0:
                            print(
                                "Ignoring zero PlayingTime after stop. "
                                + "Using last valid position: "
                                + str(last_valid_cur_time)
                                + " de "
                                + str(last_valid_total_time)
                            )
                        logging.info(
                            "Ignoring zero PlayingTime after stop. Using last valid position: %s de %s",
                            str(last_valid_cur_time),
                            str(last_valid_total_time),
                        )

                        positionticks = last_valid_positionticks
                        totalticks = last_valid_totalticks
                        total_time = last_valid_total_time
                        playingtime["cur_time"] = last_valid_cur_time
                        playingtime["total_time"] = last_valid_total_time

                    logging.info(
                        "-----------------------------------------------------------"
                    )
                    logging.debug("getglobalinfo: %s", response_data_gb)
                    logging.debug(
                        "PlayingTime: %s de %s",
                        str(playingtime["cur_time"]),
                        str(total_time),
                    )
                    if EmbySession.config["DebugLevel"] > 0:
                        print(
                            "PlayingTime Final: "
                            + str(playingtime["cur_time"])
                            + " de "
                            + str(total_time)
                        )
                    log_oppo_qpl_state(EmbySession.config, "after_getglobalinfo_loop")

                    EmbySession.playingstopped(
                        EmbySession.currentdata, positionticks, ispaused, ismuted
                    )
                    played = False
                    if totalticks > 0:
                        if (positionticks / totalticks) > 0.95:
                            played = True
                    EmbySession.setitemplaybackposition(
                        EmbySession.currentdata, positionticks, played
                    )
                    log_oppo_qpl_state(
                        EmbySession.config,
                        "before_return_to_tv",
                        changes_only=False,
                    )
                    if EmbySession.config["TV"] == True:
                        if EmbySession.config["DebugLevel"] > 0:
                            print("Cambiamos a la app anterior en la TV")
                        logging.info("Cambiamos a la app anterior en la TV")
                        try:
                            result = tv_set_prev(EmbySession.config)
                            if EmbySession.config["DebugLevel"] > 0:
                                print(result)
                            logging.info("Resultado: %s", str(result))
                        except:
                            pass
            else:
                try:
                    error = response_play["msg"]
                except:
                    error = "No hay mas info"
                if scripterx:
                    EmbySession.send_message2(
                        params["Session_id"],
                        EmbySession.lang["x_msg_error_play"]
                        + fichero
                        + "- info:"
                        + error,
                        5000,
                    )
                else:
                    EmbySession.send_user_message(
                        params["ControllingUserId"],
                        EmbySession.lang["x_msg_error_play"]
                        + fichero
                        + " - info:"
                        + error,
                        5000,
                    )
        else:
            try:
                error = response_mount["retInfo"]
            except:
                error = "No hay mas info"

            mount_path = servidor + "/" + carpeta
            mount_path_len = len(mount_path)
            error_message = (
                EmbySession.lang["x_msg_error_mount"]
                + mount_path
                + " - info:"
                + error
                + " long:"
                + str(mount_path_len)
            )

            if scripterx:
                EmbySession.send_message2(params["Session_id"], error_message, 5000)
            else:
                EmbySession.send_user_message(
                    params["ControllingUserId"], error_message, 5000
                )
        if EmbySession.config["Autoscript"] and mounted_share is not None:
            result = unmount_oppo_path(host=EmbySession.config["Oppo_IP"], port=EmbySession.config.get("OPPO_Port", 23), mount_path=mounted_share.mount_path, debug=EmbySession.config["DebugLevel"] > 0, timeout=EmbySession.config["timeout_oppo_mount"])
            if EmbySession.config["DebugLevel"] > 0:
                print(f"Unmount result: {result}")
        if (
            EmbySession.config["AV"] == True
            and EmbySession.config["AV_Always_ON"] == False
        ):
            if EmbySession.config["DebugLevel"] > 0:
                print("AV POWER OFF")
            av_power_off(EmbySession.config)
        if EmbySession.config["Always_ON"] == False:
            sendremotekey("POF", EmbySession.config)
    else:
        if scripterx == True:
            EmbySession.send_message2(
                params["Session_id"], EmbySession.lang["x_msg_error_no_oppo"]
            )
        else:
            EmbySession.send_user_message(
                params["ControllingUserId"], EmbySession.lang["x_msg_error_no_oppo"]
            )
    if scripterx == True:
        EmbySession.set_movie(
            params["Session_id"],
            params["item_id"],
            item_info["Type"],
            item_info["Name"],
        )
    EmbySession.playstate = "Free"
    EmbySession.server = ""
    EmbySession.playedtitle = ""
    EmbySession.folder = ""
    EmbySession.filename = ""
    logging.info("Fin Playto_File %s", movie)
