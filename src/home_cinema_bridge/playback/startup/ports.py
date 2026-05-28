from __future__ import annotations

from typing import Protocol

from home_cinema_bridge.playback.startup.models import DeviceCommandResult


class TelevisionOutputPort(Protocol):
    def get_current_app_id(self) -> str | None:
        """Return the current TV app id, if available."""
        ...

    def switch_to_input(self, input_id: str) -> DeviceCommandResult:
        """Switch the TV to the requested input id."""
        ...


class AvReceiverOutputPort(Protocol):
    def power_on(self) -> DeviceCommandResult:
        """Ensure the AV receiver is powered on."""
        ...

    def switch_to_input(self, input_id: str) -> DeviceCommandResult:
        """Switch the AV receiver to the requested input id."""
        ...
