from pathlib import Path

from home_cinema_bridge.devices.av.factory import get_supported_av_models
from home_cinema_bridge.devices.tv.factory import get_supported_tv_models
from lib.config_manager import load_effective_config


def load_runtime_config(config_file, lang_path, *, version):
    config = load_effective_config(config_file)
    apply_runtime_defaults(config, version=version, lang_path=lang_path)
    return config


def apply_runtime_defaults(config, *, version, lang_path):
    config["Version"] = version
    config["Autoscript"] = config.get("Autoscript", False)
    config["enable_all_libraries"] = config.get("enable_all_libraries", False)
    config["TV_model"] = config.get("TV_model", "")
    config["TV_MAC"] = config.get("TV_MAC", "")
    config["TV_SOURCES"] = config.get("TV_SOURCES", [])
    config["AV_model"] = config.get("AV_model", "")
    config["AV_SOURCES"] = config.get("AV_SOURCES", [])
    config["TV_script_init"] = config.get("TV_script_init", "")
    config["TV_script_end"] = config.get("TV_script_end", "")
    config["av_delay_hdmi"] = config.get("av_delay_hdmi", 0)
    config["AV_Port"] = config.get("AV_Port", 23)
    config["timeout_oppo_mount"] = config.get("timeout_oppo_mount", 60)
    config["language"] = config.get("language", "es-ES")
    config["default_nfs"] = config.get("default_nfs", False)
    config["wait_nfs"] = config.get("wait_nfs", False)
    config["refresh_time"] = config.get("refresh_time", 5)
    config["check_beta"] = config.get("check_beta", False)
    config["smbtrick"] = config.get("smbtrick", False)
    config["BRDisc"] = config.get("BRDisc", False)

    server_list = config["servers"]
    for server in server_list:
        server["Test_OK"] = server.get("Test_OK", False)

    config["TV"] = normalize_legacy_bool(config["TV"])
    config["AV"] = normalize_legacy_bool(config["AV"])
    config["servers"] = server_list
    config["tv_dirs"] = get_supported_tv_models()
    config["av_dirs"] = get_supported_av_models()
    config["langs"] = get_dir_folders(lang_path)

    return config


def normalize_legacy_bool(value):
    if value == "True":
        return True
    if value == "False":
        return False
    return value


def get_dir_folders(directory):
    return sorted(path.name for path in Path(directory).iterdir() if path.is_dir())
