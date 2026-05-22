import socket
import time
from dataclasses import dataclass
from enum import Enum


class OppoPlaybackCategory(str, Enum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OppoCommandResult:
    command: str
    raw_response: str
    ok: bool
    status: str
    category: OppoPlaybackCategory


class OppoStatusClient:
    """
    Minimal OPPO/Chinoppo TCP status client.

    The player accepts commands like:
      #QPW\r -> @OK ON
      #QPL\r -> @OK PLAY / @OK HOME MENU / @OK DISC MENU / ...

    This client only reads status. It does not change playback state.
    """

    ACTIVE_PLAYBACK_STATES = {"PLAY", "PAUSE", "DISC_MENU"}
    IDLE_STATES = {"SCREEN_SAVER", "HOME_MENU"}
    TRANSITION_STATES = {"STOP", "OPEN", "LOADING"}

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
        status = self._parse_status(raw_response)

        return OppoCommandResult(
            command=command.strip().lstrip("#").upper(),
            raw_response=raw_response,
            ok=raw_response.startswith("@OK"),
            status=status,
            category=self.classify_status(status),
        )

    def classify_status(self, status: str) -> OppoPlaybackCategory:
        if status in self.ACTIVE_PLAYBACK_STATES:
            return OppoPlaybackCategory.ACTIVE

        if status in self.IDLE_STATES:
            return OppoPlaybackCategory.IDLE

        if status in self.TRANSITION_STATES:
            return OppoPlaybackCategory.TRANSITION

        return OppoPlaybackCategory.UNKNOWN

    def is_active_playback_state(self, status: str) -> bool:
        return self.classify_status(status) == OppoPlaybackCategory.ACTIVE

    def is_idle_state(self, status: str) -> bool:
        return self.classify_status(status) == OppoPlaybackCategory.IDLE

    def is_transition_state(self, status: str) -> bool:
        return self.classify_status(status) == OppoPlaybackCategory.TRANSITION

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

    @staticmethod
    def _parse_status(raw_response: str) -> str:
        response = raw_response.strip()

        if response.startswith("@OK"):
            response = response[3:].strip()

        if not response:
            return "UNKNOWN"

        return response.upper().replace(" ", "_")
