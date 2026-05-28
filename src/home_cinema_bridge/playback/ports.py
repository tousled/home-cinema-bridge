from typing import Protocol, Callable

from home_cinema_bridge.playback.startup.models import (
    DeviceCommandResult,
    OppoPlaybackStartRequest,
    OppoPlaybackStartResult,
    OppoPlaybackPosition,
    OppoPlaybackState,
)


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


class OppoPlaybackPort(Protocol):
    def prepare_for_playback_startup(self) -> DeviceCommandResult: ...

    def start_playback(
        self,
        request: OppoPlaybackStartRequest,
        *,
        on_waiting: Callable[[int], None] | None = None,
    ) -> OppoPlaybackStartResult: ...

    def get_playback_state(self) -> OppoPlaybackState: ...

    def get_playback_position(self) -> OppoPlaybackPosition: ...

    def seek_to(self, position_ticks: int) -> DeviceCommandResult: ...

    def select_audio_track(self, audio_index: int) -> DeviceCommandResult: ...

    def select_subtitle_track(self, subtitle_index: int) -> DeviceCommandResult: ...

    def stop_playback(self) -> DeviceCommandResult: ...
