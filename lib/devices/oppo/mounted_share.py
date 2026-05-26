from dataclasses import dataclass
import json


@dataclass(frozen=True)
class OppoMountedShare:
    server: str
    folder: str
    mount_path: str
    is_nfs: bool


def parse_mounted_share_response(
    response_text: str,
    *,
    server: str,
    folder: str,
    is_nfs: bool,
) -> tuple[dict, OppoMountedShare | None]:
    response = json.loads(response_text)

    if not response.get("success"):
        return response, None

    mount_path_key = "nfsMntPath" if is_nfs else "cifsMntPath"
    mount_path = response.get(mount_path_key)

    if not mount_path:
        response["success"] = False
        response["retInfo"] = (
            f"OPPO mount response did not include {mount_path_key}. "
            f"Cannot safely start playback without the real mount path."
        )
        return response, None

    return response, OppoMountedShare(
        server=server,
        folder=folder,
        mount_path=mount_path,
        is_nfs=is_nfs,
    )