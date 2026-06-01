import logging

from .client import EmbyClient


def test_emby_connection(config):
    try:
        client = _authenticated_client(config)
        user_info = client.user_info or {}

        session_id = user_info.get("SessionInfo", {}).get("Id", "")
        access_token = user_info.get("AccessToken", "")
        user_id = user_info.get("User", {}).get("Id", "")

        if session_id or (access_token and user_id):
            return "OK"

        return "FAILED"

    except Exception:
        logging.exception("Error checking Emby connection")
        return "FAILED"


def load_libraries(config):
    try:
        client = _authenticated_client(config)
        views_list = client.get_user_views(client.user_info["User"]["Id"])
        config["Libraries"] = build_library_config(
            views_list,
            existing_libraries=config.get("Libraries", []),
        )
        return 0
    except Exception:
        return 1


def load_selectable_folders(config):
    client = _authenticated_client(config)
    media_folders = client.get_selectable_media_folders()
    config["servers"] = build_selectable_folder_servers(
        media_folders,
        libraries=config.get("Libraries", []),
        existing_servers=config.get("servers", []),
        enable_all_libraries=config["enable_all_libraries"],
    )


def load_devices(config):
    try:
        client = _authenticated_client(config)
        devices = client.get_devices()
        config["devices"] = build_control_device_config(devices.get("Items", []))
        return "OK"
    except Exception:
        return "FAILURE"


def build_library_config(views, *, existing_libraries):
    libraries = []

    for view in views:
        library = {
            "Name": view["Name"],
            "Id": view["Id"],
            "Active": False,
        }

        for existing_library in existing_libraries:
            if existing_library["Id"] == view["Id"]:
                library["Active"] = existing_library["Active"]

        libraries.append(library)

    return libraries


def build_selectable_folder_servers(
    media_folders,
    *,
    libraries,
    existing_servers,
    enable_all_libraries,
):
    servers = []

    for folder in media_folders:
        index = 1
        active = is_library_active(libraries, folder["Name"])
        if enable_all_libraries:
            active = True

        if active:
            for subfolder in folder["SubFolders"]:
                server = {
                    "Id": subfolder["Id"],
                    "name": (
                        folder["Name"] + "(" + str(index) + ")"
                        if index > 1
                        else folder["Name"]
                    ),
                    "Emby_Path": subfolder["Path"],
                    "Oppo_Path": "/",
                }

                for existing_server in existing_servers:
                    if server["Emby_Path"] == existing_server["Emby_Path"]:
                        server["name"] = existing_server["name"]
                        server["Oppo_Path"] = existing_server["Oppo_Path"]
                        server["Test_OK"] = existing_server["Test_OK"]

                servers.append(server)
                index = index + 1

    return servers


def build_control_device_config(devices):
    control_devices = []

    for device in devices:
        try:
            if device["ReportedDeviceId"] != "Xnoppo":
                device["Name"] = device["Name"] + " / " + device["AppName"]
                device["Id"] = device["ReportedDeviceId"]
                control_devices.append(device)
        except Exception:
            pass

    return control_devices


def is_library_active(libraries, libraryname):
    for library in libraries:
        if library["Name"] == libraryname:
            return library["Active"]
    return False


def _authenticated_client(config):
    emby_config = {
        "emby_server": config.get("emby_server", ""),
        "user_name": config.get("user_name", ""),
        "user_password": config.get("user_password", ""),
    }
    client = EmbyClient.from_config(emby_config)
    client.authenticate()
    return client
