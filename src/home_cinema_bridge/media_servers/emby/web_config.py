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
        libraries = []

        for view in views_list:
            library = {
                "Name": view["Name"],
                "Id": view["Id"],
                "Active": False,
            }
            try:
                lib_list = config["Libraries"]
            except Exception:
                lib_list = {}

            for lib in lib_list:
                if lib["Id"] == view["Id"]:
                    library["Active"] = lib["Active"]

            libraries.append(library)

        config["Libraries"] = libraries
        return 0
    except Exception:
        return 1


def load_selectable_folders(config):
    client = _authenticated_client(config)
    media_folders = client.get_selectable_media_folders()
    servers = []

    for folder in media_folders:
        index = 1
        active = is_library_active(config, folder["Name"])
        if config["enable_all_libraries"] == True:
            active = True

        if active == True:
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
                try:
                    serv_list = config["servers"]
                except Exception:
                    serv_list = {}

                for serv in serv_list:
                    if server["Emby_Path"] == serv["Emby_Path"]:
                        server["name"] = serv["name"]
                        server["Oppo_Path"] = serv["Oppo_Path"]
                        server["Test_OK"] = serv["Test_OK"]

                servers.append(server)
                index = index + 1

    config["servers"] = servers


def load_devices(config):
    try:
        client = _authenticated_client(config)
        devices = client.get_devices()
        dev_temp = []

        for device in devices["Items"]:
            try:
                if device["ReportedDeviceId"] != "Xnoppo":
                    device["Name"] = device["Name"] + " / " + device["AppName"]
                    device["Id"] = device["ReportedDeviceId"]
                    dev_temp.append(device)
            except Exception:
                pass

        config["devices"] = dev_temp
        return "OK"
    except Exception:
        return "FAILURE"


def is_library_active(config, libraryname):
    for library in config["Libraries"]:
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
