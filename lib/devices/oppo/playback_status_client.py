import socket
import time
from dataclasses import dataclass

from lib.devices.oppo.playback_state import (
    OppoPlaybackCategory,
    classify_oppo_status,
    normalize_oppo_status,
)


@dataclass(frozen=True)
class OppoCommandResult:
    command: str
    raw_response: str
    ok: bool
    status: str
    category: OppoPlaybackCategory


class OppoPlaybackStatusClient:
    """
    Reads OPPO playback/power status using the OPPO TCP command interface.

    Examples:
      #QPW -> @OK ON
      #QPL -> @OK PLAY / @OK HOME MENU / @OK DISC MENU / ...
    """

    def __init__(self, host: str, port: int = 23, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def query_power_state(self) -> OppoCommandResult:
        return self.query("QPW")

    def query_playback_state(self) -> OppoCommandResult:
        return self.query("QPL")

    def query(self, command: str) -> OppoCommandResult:
        normalized_command = self._normalize_command(command)
        raw_response = self._send(normalized_command)
        status = normalize_oppo_status(raw_response)

        return OppoCommandResult(
            command=command.strip().lstrip("#").upper(),
            raw_response=raw_response,
            ok=raw_response.startswith("@OK"),
            status=status,
            category=classify_oppo_status(status),
        )

    def _send(self, payload: bytes) -> str:
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            sock.sendall(payload)

            chunks: list[bytes] = []
            started = time.monotonic()

            while time.monotonic() - started < self.timeout:
                try:
                    chunk = sock.recv(1024)
                except socket.timeout:
                    break

                if not chunk:
                    break

                chunks.append(chunk)

                # OPPO responses are short, e.g. "@OK PLAY".
                # Stop as soon as we get a complete-looking response instead of waiting
                # for the socket timeout on every sample.
                decoded = b"".join(chunks).decode("utf-8", errors="replace")
                if decoded.strip().startswith("@OK"):
                    break

        return b"".join(chunks).decode("utf-8", errors="replace").strip()

    @staticmethod
    def _normalize_command(command: str) -> bytes:
        command = command.strip().upper()

        if not command.startswith("#"):
            command = f"#{command}"

        if not command.endswith("\r"):
            command = f"{command}\r"

        return command.encode("ascii")
