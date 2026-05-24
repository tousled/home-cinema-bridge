import socket
from dataclasses import dataclass


OPPO_HTTP_PORT = 436


@dataclass(frozen=True)
class OppoAvailability:
    available: bool
    host: str
    port: int
    error: str = ""


def check_oppo_http_availability(
    config: dict,
    *,
    timeout: float = 0.5,
) -> OppoAvailability:
    """
    Lightweight OPPO availability check.

    This only checks whether the OPPO/Chinoppo HTTP control port is reachable.
    It does not send wake/login packets and it does not retry. Use this for
    passive health checks such as the watchdog.
    """
    host = str(config.get("Oppo_IP", "")).strip()
    port = OPPO_HTTP_PORT

    if not host:
        return OppoAvailability(
            available=False,
            host="",
            port=port,
            error="Oppo_IP is not configured",
        )

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return OppoAvailability(
                available=True,
                host=host,
                port=port,
            )

    except OSError as exc:
        return OppoAvailability(
            available=False,
            host=host,
            port=port,
            error=f"{type(exc).__name__}: {exc}",
        )
