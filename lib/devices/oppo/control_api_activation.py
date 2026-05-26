import logging
import socket
import time
from dataclasses import dataclass


OPPO_CONTROL_API_PORT = 436
OPPO_REMOTE_LOGIN_PORT = 7624
OPPO_REMOTE_LOGIN_MESSAGE = "NOTIFY OREMOTE LOGIN"


@dataclass(frozen=True)
class OppoControlApiActivationResult:
    available: bool
    host: str
    port: int
    attempts: int
    error: str = ""


class OppoControlApiActivator:
    """
    Prepares the OPPO/Chinoppo HTTP control API.

    The OPPO can respond to ping and QPL/QPW while the HTTP control API
    on port 436 is still closed. Sending the legacy remote login NOTIFY
    packet activates that HTTP control API.
    """

    def __init__(
        self,
        host: str,
        *,
        control_api_port: int = OPPO_CONTROL_API_PORT,
        remote_login_port: int = OPPO_REMOTE_LOGIN_PORT,
        timeout_seconds: float = 1.0,
    ):
        self.host = host
        self.control_api_port = control_api_port
        self.remote_login_port = remote_login_port
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_config(cls, config: dict) -> "OppoControlApiActivator":
        return cls(
            host=str(config["Oppo_IP"]),
            control_api_port=int(config.get("OPPO_HTTP_Port", OPPO_CONTROL_API_PORT)),
            timeout_seconds=float(config.get("timeout_oppo_conection", 1.0)),
        )

    def check_control_api_availability(self) -> OppoControlApiActivationResult:
        try:
            with socket.create_connection(
                    (self.host, self.control_api_port),
                    timeout=self.timeout_seconds,
            ):
                return OppoControlApiActivationResult(
                    available=True,
                    host=self.host,
                    port=self.control_api_port,
                    attempts=1,
                )
        except OSError as exc:
            return OppoControlApiActivationResult(
                available=False,
                host=self.host,
                port=self.control_api_port,
                attempts=1,
                error=f"{type(exc).__name__}: {exc}",
            )


    def ensure_control_api_available(self, *, max_attempts: int) -> OppoControlApiActivationResult:
        last_error = ""

        for attempt in range(1, max_attempts + 1):
            if self._is_control_api_available():
                return OppoControlApiActivationResult(
                    available=True,
                    host=self.host,
                    port=self.control_api_port,
                    attempts=attempt,
                )

            try:
                self._send_remote_login_notification()
            except OSError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logging.debug(
                    "Failed to send OPPO remote login notification | attempt=%s | error=%s",
                    attempt,
                    last_error,
                )

            time.sleep(1)

        if self._is_control_api_available():
            return OppoControlApiActivationResult(
                available=True,
                host=self.host,
                port=self.control_api_port,
                attempts=max_attempts,
            )

        return OppoControlApiActivationResult(
            available=False,
            host=self.host,
            port=self.control_api_port,
            attempts=max_attempts,
            error=last_error or "Control API did not become available",
        )


    def _is_control_api_available(self) -> bool:
        return self.check_control_api_availability().available


    def _send_remote_login_notification(self) -> None:
        logging.debug("Sending OPPO remote login notification to %s:%s", self.host, self.remote_login_port)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(
                OPPO_REMOTE_LOGIN_MESSAGE.encode("utf-8"),
                (self.host, self.remote_login_port),
            )
