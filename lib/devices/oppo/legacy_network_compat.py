from lib.devices.oppo.network_playback_starter import (
    OppoNetworkFolder,
    OppoNetworkFolderProtocol,
    OppoNetworkPlaybackStarter,
)


def LoginSambaWithOutID(config, server):
    return OppoNetworkPlaybackStarter(config).login_samba_server(server)


def LoginNFS(config, server):
    return OppoNetworkPlaybackStarter(config).login_nfs_server(server)


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
