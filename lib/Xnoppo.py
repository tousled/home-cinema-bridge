import json
import logging
import os
import socket
import time
import urllib.parse

from home_cinema_bridge.media_servers.emby import (
    MediaServerPlaybackContext,
    MediaServerPlaybackEventPublisher,
)
from home_cinema_bridge.network.http import get_http_session
from home_cinema_bridge.playback.error_handling import (
    PlaybackErrorRecoveryRequest,
    create_playback_error_handler,
)
from home_cinema_bridge.playback.startup import (
    OppoPlaybackStartRequest,
    PlaybackOutputSwitchRequest,
)
from home_cinema_bridge.playback.startup.factory import (
    create_playback_startup_orchestrator as build_playback_startup_orchestrator,
)
from home_cinema_bridge.playback.media_location import (
    resolve_player_media_file_location,
)
from .devices.oppo.control_api_activation import OppoControlApiActivator
from .devices.oppo.control_api_client import OppoControlApiClient
from .devices.oppo.mounted_share import (
    OppoMountedShare,
    parse_mounted_share_response,
)
from .devices.oppo.playback_state_waiter import (
    wait_until_oppo_reports_active_playback,
)
from .devices.oppo.playback_status_client import OppoPlaybackStatusClient
from .devices.oppo.legacy_network_compat import (
    checkfolderhasbdmv,
    playnormalfile,
    LoginNFS,
    LoginSambaWithOutID,
    smbtrick,
)

from home_cinema_bridge.playback.timing import PlaybackStartupTimer

from .Xnoppo_AVR import (
    av_power_off,
    av_restore_tv_audio,
)
from .Xnoppo_TV import tv_set_prev

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


def setplaytime(config, playticks):
    logging.debug("setplaytime")
    response_text = oppo_control_api_client(config).set_play_time(playticks)
    logging.debug("*** setplaytime Response: %s", response_text)
    return response_text


def setaudiotrack(config, audio_index):
    logging.debug("setaudiotrack")
    response_text = oppo_control_api_client(config).select_audio_track(audio_index)
    logging.debug("*** setaudiotrack Response: %s", response_text)
    return response_text


def apply_selected_subtitle_track(
    emby_session,
    params,
    startup_timer=None,
    startup_orchestrator=None,
):
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
                        if startup_orchestrator is None:
                            set_subtitles_track(
                                emby_session.config,
                                subs_index,
                                startup_timer=startup_timer,
                            )
                        else:
                            startup_orchestrator.select_oppo_subtitle_track(subs_index)
                else:
                    if startup_orchestrator is None:
                        set_subtitles_track(emby_session.config, subs_index)
                    else:
                        startup_orchestrator.select_oppo_subtitle_track(subs_index)

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

    client = oppo_control_api_client(config)
    timeout = 0

    if startup_timer is not None:
        with startup_timer.measure_step("subtitle_set_and_confirm_oppo_track"):
            while actual_track != subs_index and timeout < 10:
                response_text = client.select_subtitle_track(subs_index)
                logging.debug("*** set_subtitles_track Response: %s", response_text)

                if config["DebugLevel"] == 2:
                    print(response_text)

                time.sleep(1)
                actual_track = get_current_subtitle_track(config)
                timeout = timeout + 1
    else:
        while actual_track != subs_index and timeout < 10:
            response_text = client.select_subtitle_track(subs_index)
            logging.debug("*** set_subtitles_track Response: %s", response_text)

            if config["DebugLevel"] == 2:
                print(response_text)

            time.sleep(1)
            actual_track = get_current_subtitle_track(config)
            timeout = timeout + 1

    return 0


def get_current_subtitle_track(config):
    logging.debug("get_current_subtitle_track")
    response_text = oppo_control_api_client(config).get_subtitle_menu()
    logging.debug("*** getsubtitlemenulist Response: %s", response_text)
    response_subs = json.loads(response_text)
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
    response = get_http_session("oppo-legacy").get(url, headers=headers)
    return response.text


def resolve_server_is_nfs(config, device_list, server_name):
    nfs = config["default_nfs"]

    for device in device_list["devicelist"]:
        if device["name"].upper() == server_name.upper():
            return device["sub_type"] == "nfs"

    return nfs


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
    media_location = resolve_player_media_file_location(
        emby_media_path=movie,
        playback_file_format=Container,
        path_mappings=EmbySession.config["servers"],
    )
    logging.info("-----------------------------------------------------------")
    logging.info("Servidor               : %s", media_location.content_server)
    logging.info("Fichero                : %s", media_location.playback_file_name)
    logging.info("Carpeta                : %s", media_location.content_directory)
    logging.info("-----------------------------------------------------------")
    EmbySession.server = media_location.content_server
    EmbySession.folder = media_location.content_directory
    EmbySession.filename = media_location.playback_file_name
    EmbySession.playedtitle = ItemInfo["Name"]
    response_data6f = getdevicelist(EmbySession.config)
    device_list = json.loads(response_data6f)

    if EmbySession.config["DebugLevel"] > 0:
        print(device_list)

    nfs = resolve_server_is_nfs(
        EmbySession.config,
        device_list,
        media_location.content_server,
    )

    if nfs:
        LoginNFS(EmbySession.config, media_location.content_server)
        response_data7 = mountSharedNFSFolder(
            media_location.content_server,
            media_location.content_directory,
            "",
            "",
            EmbySession.config,
        )
    else:
        LoginSambaWithOutID(EmbySession.config, media_location.content_server)
        response_data7 = mountSharedFolder(
            media_location.content_server,
            media_location.content_directory,
            "",
            "",
            EmbySession.config,
        )

    response_mount, mounted_share = parse_mounted_share_response(
        response_data7,
        server=media_location.content_server,
        folder=media_location.content_directory,
        is_nfs=nfs,
    )

    if mounted_share is None:
        error = response_mount.get("retInfo", "No hay mas info")
        logging.warning(
            "Replay mount failed | server=%s | folder=%s | error=%s",
            media_location.content_server,
            media_location.content_directory,
            error,
        )

        if scripterx:
            EmbySession.send_message2(
                params["Session_id"],
                EmbySession.lang["x_msg_error_mount"]
                + media_location.content_server
                + "/"
                + media_location.content_directory
                + " - info:"
                + error,
                5000,
            )
        else:
            EmbySession.send_user_message(
                params["ControllingUserId"],
                EmbySession.lang["x_msg_error_mount"]
                + media_location.content_server
                + "/"
                + media_location.content_directory
                + " - info:"
                + error,
                5000,
            )

        EmbySession.playstate = "Free"
        return

    if Container == "bluray":
        response_data8 = checkfolderhasbdmv(
            EmbySession.config,
            mounted_share,
            media_location.playback_file_name,
        )
    else:
        response_data8 = playnormalfile(
            mounted_share,
            media_location.playback_file_name,
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

def create_playback_startup_orchestrator(config):
    return build_playback_startup_orchestrator(config)


def switch_playback_output_to_oppo(emby_session, startup_orchestrator, startup_timer):

    request = PlaybackOutputSwitchRequest(
        tv_input_id=str(emby_session.config.get("Source", "configured_tv_input")),
        av_input_id=emby_session.config.get("AV_Input"),
        tv_enabled=emby_session.config.get("TV") is True,
        av_enabled=emby_session.config.get("AV") is True,
    )

    with startup_timer.measure_step("switch_playback_output_to_oppo"):
        result = startup_orchestrator.switch_playback_output_to_oppo(request)

    logging.info(
        "Playback output switch result | successful=%s | tv=%s | av_power=%s | av_input=%s",
        result.successful,
        result.tv_input_result.status.value,
        result.av_power_result.status.value,
        result.av_input_result.status.value,
    )

    return result


def playto_file(EmbySession, data, scripterx=False):
    startup_timer = PlaybackStartupTimer()
    EmbySession.playstate = "Loading"
    EmbySession.currentdata = data
    tv_handoff_completed_at = None
    reset_qpl_observation_state()
    log_oppo_qpl_state(EmbySession.config, "playto_file_start")
    if EmbySession.config["DebugLevel"] > 0:
        print("scripterx is " + str(scripterx))

    with startup_timer.measure_step("sendnotifyremote"):
        sendnotifyremote(EmbySession.config["Oppo_IP"])

    with startup_timer.measure_step("process_emby_payload"):
        params = EmbySession.process_data(data)
        media_server_playback_context = MediaServerPlaybackContext.from_event(
            data,
            load_user_item=EmbySession.get_item_info,
        )
        media_server_playback_event_publisher = MediaServerPlaybackEventPublisher(
            EmbySession.client,
            bridge_session_id=EmbySession.user_info["SessionInfo"]["Id"],
            context=media_server_playback_context,
        )

    with startup_timer.measure_step("load_emby_item_info"):
        item_info = EmbySession.get_item_info2(
            EmbySession.user_info["User"]["Id"],
            params["item_id"],
            params["media_source_id"],
        )

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

        if EmbySession.config["TV"] is True and scripterx:
            with startup_timer.measure_step("stop_emby_client_before_device_handoff"):
                response_data5 = EmbySession.playback_stop(params["Session_id"])

            if EmbySession.config["DebugLevel"] > 0:
                print(response_data5)

        startup_orchestrator = create_playback_startup_orchestrator(EmbySession.config)
        output_switch_result = switch_playback_output_to_oppo(
            EmbySession,
            startup_orchestrator,
            startup_timer,
        )

        with startup_timer.measure_step("resolve_media_path"):
            item_info, _ = resolve_mocked_item_info(EmbySession, params, item_info)
            movie = item_info["Path"]
            container = item_info["Container"]
            logging.info("-----------------------------------------------------------")
            media_location = resolve_player_media_file_location(
                emby_media_path=movie,
                playback_file_format=container,
                path_mappings=EmbySession.config["servers"],
            )
            logging.info("-----------------------------------------------------------")

        logging.info("Servidor               : %s", media_location.content_server)
        logging.info("Fichero                : %s", media_location.playback_file_name)
        logging.info("Carpeta                : %s", media_location.content_directory)
        logging.info("-----------------------------------------------------------")
        EmbySession.server = media_location.content_server
        EmbySession.folder = media_location.content_directory
        EmbySession.filename = media_location.playback_file_name
        EmbySession.playedtitle = item_info["Name"]


        if scripterx:
            EmbySession.send_message2(
                params["Session_id"], EmbySession.lang["x_msg_wait_for_mount"], 1999
            )
        else:
            EmbySession.send_user_message(
                params["ControllingUserId"],
                EmbySession.lang["x_msg_wait_for_mount"],
                1999,
            )

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
            message = (
                EmbySession.lang["x_msg_wait_for_play"] + str(elapsed_seconds) + "s"
            )

            if scripterx:
                EmbySession.send_message2(params["Session_id"], message, 999)
            else:
                EmbySession.send_user_message(params["ControllingUserId"], message, 999)

        oppo_playback_start_request = OppoPlaybackStartRequest(
            media_location=media_location,
            wait_for_nfs_share=EmbySession.config["wait_nfs"] is True,
            assume_player_already_on=EmbySession.config["Always_ON"] is True,
            startup_timeout_seconds=EmbySession.config["timeout_oppo_playitem"],
            poll_interval_seconds=playback_start_poll_interval,
        )

        with startup_timer.measure_step("start_oppo_playback"):
            oppo_playback_start_result = startup_orchestrator.start_oppo_playback(
                request=oppo_playback_start_request,
                on_waiting=notify_playback_waiting,
            )

        log_oppo_qpl_state(EmbySession.config, "after_playnormalfile")

        playback_state = oppo_playback_start_result.playback_state
        logging.info(
            "OPPO playback startup result | successful=%s | media_mounted=%s | playback_command_accepted=%s | playback_started_on_device=%s | status=%s | category=%s | detail=%s",
            oppo_playback_start_result.successful,
            oppo_playback_start_result.media_mounted,
            oppo_playback_start_result.playback_command_accepted,
            oppo_playback_start_result.playback_started_on_device,
            playback_state.status.value if playback_state is not None else None,
            playback_state.category.value if playback_state is not None else None,
            oppo_playback_start_result.detail,
        )

        if not oppo_playback_start_result.successful:
            with startup_timer.measure_step("recover_after_oppo_startup_failure"):
                error_handler = create_playback_error_handler(EmbySession.config)
                error_handler.recover(
                    PlaybackErrorRecoveryRequest(
                        reason="oppo_startup_failed",
                        previous_tv_app_id=output_switch_result.previous_tv_app_id,
                        tv_enabled=EmbySession.config.get("TV") is True,
                        av_enabled=EmbySession.config.get("AV") is True,
                    )
                )

            if not oppo_playback_start_result.media_mounted:
                error_message = (
                    EmbySession.lang["x_msg_error_mount"]
                    + media_location.content_server
                    + "/"
                    + media_location.content_directory
                    + " - info:"
                    + str(oppo_playback_start_result.detail)
                )
            elif not oppo_playback_start_result.playback_command_accepted:
                error_message = (
                    EmbySession.lang["x_msg_error_play"]
                    + media_location.playback_file_name
                    + " - info:"
                    + str(oppo_playback_start_result.detail)
                )
            else:
                error_message = EmbySession.lang["x_msg_timeout_play"]
                logging.info("Timeout Reproduciendo %s", movie)

            if scripterx:
                EmbySession.send_message2(params["Session_id"], error_message, 5000)
            else:
                EmbySession.send_user_message(
                    params["ControllingUserId"], error_message, 5000
                )
        else:
            with startup_timer.measure_step("notify_media_server_playback_started"):
                EmbySession.playstate = "Playing"
                media_server_playback_event_publisher.started()

            if EmbySession.config["DebugLevel"] > 0:
                print(params["auto_resume"])

            with startup_timer.measure_step("apply_resume_position"):
                if params["auto_resume"] <= 0:
                    playticks = 0
                else:
                    playticks = params["auto_resume"]

                startup_orchestrator.seek_oppo_to(playticks)

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
                        startup_orchestrator.select_oppo_audio_track(audio_index)
                except:
                    pass

            if EmbySession.config["TV"] != True:
                if scripterx == True:
                    EmbySession.send_message2(
                        params["Session_id"],
                        EmbySession.lang["x_msg_init_play"] + movie,
                    )
                logging.info("Reprodución iniciada: %s", movie)

            with startup_timer.measure_step("initial_global_info_before_progress_loop"):
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

            positionticks = playticks
            totalticks = 0
            last_valid_positionticks = playticks
            last_valid_totalticks = 0
            last_valid_cur_time = int(playticks / 10_000_000)
            last_valid_total_time = 0
            ispaused = False
            ismuted = False
            with startup_timer.measure_step("apply_subtitle_track"):
                apply_selected_subtitle_track(
                    EmbySession,
                    params,
                    startup_timer=startup_timer,
                    startup_orchestrator=startup_orchestrator,
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
                        playback_position = (
                            startup_orchestrator.get_oppo_playback_position()
                        )
                        playingtime = {
                            "cur_time": playback_position.current_seconds,
                            "total_time": playback_position.total_seconds,
                        }
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
                    if playingtime["cur_time"] > 0 and playingtime["total_time"] > 0:
                        positionticks = playingtime["cur_time"] * 10000000
                        total_time = playingtime["total_time"]
                        totalticks = total_time * 10000000

                        last_valid_positionticks = positionticks
                        last_valid_totalticks = totalticks
                        last_valid_cur_time = playingtime["cur_time"]
                        last_valid_total_time = total_time

                    if scripterx == False:
                        media_server_playback_event_publisher.progress(
                            position_ticks=positionticks,
                            runtime_ticks=totalticks,
                            is_paused=ispaused,
                            is_muted=ismuted,
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

            logging.info("-----------------------------------------------------------")
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

            media_server_playback_event_publisher.stopped(
                position_ticks=positionticks,
                runtime_ticks=totalticks,
                is_paused=ispaused,
                is_muted=ismuted,
            )
            played = False
            if totalticks > 0:
                if (positionticks / totalticks) > 0.95:
                    played = True
            logging.info(
                "Emby playback stopped | position_ticks=%s | runtime_ticks=%s | played=%s",
                positionticks,
                totalticks,
                played,
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
                except Exception:
                    logging.exception("Unable to return LG TV to previous app")
            if EmbySession.config["AV"] == True:
                try:
                    result = av_restore_tv_audio(EmbySession.config)
                    logging.info("AV receiver TV audio restore result: %s", str(result))
                except Exception:
                    logging.exception("Unable to restore AV receiver to TV audio")
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
