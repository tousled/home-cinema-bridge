from lib.devices.oppo.control_api_client import OppoControlApiClient
from lib.devices.oppo.mounted_share import OppoMountedShare
from lib.devices.oppo.network_playback_starter import (
    OppoNetworkFolder,
    OppoNetworkFolderProtocol,
    OppoNetworkPlaybackStarter,
)


def LoginSambaWithOutID(config, server):
    return OppoNetworkPlaybackStarter(config).login_samba_server(server)


def LoginNFS(config, server):
    return OppoNetworkPlaybackStarter(config).login_nfs_server(server)


def playnormalfile(mounted_share: OppoMountedShare, filename, index, config):
    response = OppoControlApiClient.from_config(config).play_normal_file(
        mounted_share=mounted_share,
        filename=filename,
        index=index,
        timeout=config["timeout_oppo_playitem"],
    )

    if config["DebugLevel"] == 2:
        print("*** Fin playnormalfile ***")
        print(response)

    return response


def checkfolderhasbdmv(
    config, mounted_share: OppoMountedShare, relative_folder_path: str
):
    response = OppoControlApiClient.from_config(
        config
    ).mounted_folder_contains_blu_ray_structure(
        mounted_share=mounted_share,
        relative_folder_path=relative_folder_path,
        timeout=config["timeout_oppo_playitem"],
    )

    if config["DebugLevel"] == 2:
        print("*** Fin checkfolderhasbdmv ***")
        print(response)

    return response


def smbtrick(path, config):
    server, folder = _parse_legacy_samba_path(path)

    network_folder = OppoNetworkFolder(
        server_name=server,
        folder_path=folder,
        protocol=OppoNetworkFolderProtocol.CIFS,
    )
    OppoNetworkPlaybackStarter(config).prime_samba_mount(network_folder)
    return 0


def _parse_legacy_samba_path(path: str) -> tuple[str, str]:
    path = path.replace("\\\\", "\\")
    path = path.replace("\\", "/")
    path = path.replace("//", "/")

    path_parts = path.strip("/").split("/", 2)

    if len(path_parts) < 2:
        return path_parts[0], ""

    return path_parts[0], path_parts[1]
