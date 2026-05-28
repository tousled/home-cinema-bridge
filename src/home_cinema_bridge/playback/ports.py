from typing import Protocol

from home_cinema_bridge.playback.startup.models import DeviceCommandResult


class TvOutputSwitchPort(Protocol):
    def get_current_app_id(self) -> str | None:
        ...

    def switch_to_input(self, input_id: str) -> DeviceCommandResult:
        ...


class AvOutputSwitchPort(Protocol):
    def power_on(self) -> DeviceCommandResult:
        ...

    def switch_to_input(self, input_id: str) -> DeviceCommandResult:
        ...