from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any
from warnings import deprecated

from home_cinema_bridge.devices.oppo.media_control_playback import (
    OppoMediaControlPlayback,
)
from home_cinema_bridge.devices.av.base import BaseAvReceiver
from home_cinema_bridge.devices.tv.base import BaseTvController
from home_cinema_bridge.playback.startup.models import (
    DeviceCommandResult,
    OppoPlaybackPosition,
    OppoPlaybackStartRequest,
    OppoPlaybackStartResult,
    OppoPlaybackState,
)
from home_cinema_bridge.playback.ports import (
    AvReceiverOutputPort,
    TelevisionOutputPort,
    OppoPlaybackPort,
)
from lib.devices.oppo.playback_status_client import OppoPlaybackStatusClient

logger = logging.getLogger(__name__)


@deprecated(
    "LegacyTelevisionOutput is a temporary bridge while Xnoppo.py still owns "
    "startup wiring. Replace it with a direct TV adapter port when the legacy "
    "entrypoint is removed."
)
class LegacyTelevisionOutput(TelevisionOutputPort):
    """
    Bridge from the new playback startup orchestrator to the existing TV factory.

    This is transitional code. It still receives the legacy config dict because the
    current TV factory expects it, but the orchestrator itself does not see that dict.
    """

    def __init__(self, controller: BaseTvController) -> None:
        self._controller = controller

    def get_current_app_id(self) -> str | None:
        try:
            result = _run(self._controller.get_current_app())
            value = _unwrap_value(result)
            return None if value is None else str(value)
        except Exception as exc:
            logger.exception("Could not read current TV app id.", exc)
            return None

    def switch_to_input(self, input_id: str) -> DeviceCommandResult:
        try:
            logger.info("Switching TV to playback input | input_id=%s", input_id)

            # The current TV adapter already reads the configured input from config.
            # input_id is kept here as the clean domain request value for the new flow.
            result = _run(self._controller.switch_to_hdmi_input())

            return _to_device_command_result(
                operation="switch TV input",
                legacy_result=_unwrap_value(result),
            )
        except Exception as exc:
            logger.exception("TV input switch failed | input_id=%s", input_id)
            return DeviceCommandResult.failed(
                f"TV input switch failed: {type(exc).__name__}: {exc}"
            )

    def return_to_app(self, app_id: str | None = None) -> DeviceCommandResult:
        try:
            if app_id and hasattr(self._controller, "config"):
                self._controller.config["current_LG"] = app_id

            logger.info("Returning TV to app | app_id=%s", app_id)
            result = _run(self._controller.return_to_previous_app())

            return _to_device_command_result(
                operation="return TV to app",
                legacy_result=_unwrap_value(result),
            )
        except Exception as exc:
            logger.exception("TV app restore failed | app_id=%s", app_id)
            return DeviceCommandResult.failed(
                f"TV app restore failed: {type(exc).__name__}: {exc}"
            )


@deprecated(
    "LegacyAvReceiverOutput is a temporary bridge while Xnoppo.py still owns "
    "startup wiring. Replace it with a direct AV receiver adapter port when the "
    "legacy entrypoint is removed."
)
class LegacyAvReceiverOutput(AvReceiverOutputPort):
    """
    Bridge from the new playback startup orchestrator to the existing AV factory.

    This is transitional code. It creates the configured AV receiver once and reuses it
    for power-on and input switching during the startup flow.
    """

    def __init__(self, receiver: BaseAvReceiver) -> None:
        self._receiver = receiver

    def power_on(self) -> DeviceCommandResult:
        try:
            logger.info("Ensuring AV receiver is powered on.")
            result = self._receiver.power_on()

            return _to_device_command_result(
                operation="power on AV receiver",
                legacy_result=_unwrap_value(result),
            )
        except Exception as exc:
            logger.exception("AV receiver power-on failed.")
            return DeviceCommandResult.failed(
                f"AV receiver power-on failed: {type(exc).__name__}: {exc}"
            )

    def switch_to_input(self, input_id: str) -> DeviceCommandResult:
        try:
            logger.info(
                "Switching AV receiver to playback input | input_id=%s", input_id
            )

            # The current AV adapter already reads the configured input from config.
            # input_id is kept here as the clean domain request value for the new flow.
            result = self._receiver.change_hdmi()

            return _to_device_command_result(
                operation="switch AV receiver input",
                legacy_result=_unwrap_value(result),
            )
        except Exception as exc:
            logger.exception("AV receiver input switch failed | input_id=%s", input_id)
            return DeviceCommandResult.failed(
                f"AV receiver input switch failed: {type(exc).__name__}: {exc}"
            )

    def restore_tv_audio(self) -> DeviceCommandResult:
        try:
            logger.info("Restoring AV receiver to TV audio.")
            result = self._receiver.restore_tv_audio()

            return _to_device_command_result(
                operation="restore AV receiver TV audio",
                legacy_result=_unwrap_value(result),
            )
        except Exception as exc:
            logger.exception("AV receiver TV audio restore failed.")
            return DeviceCommandResult.failed(
                f"AV receiver TV audio restore failed: {type(exc).__name__}: {exc}"
            )


@deprecated(
    "LegacyOppoMediaControlPlaybackOutput adapts legacy config-based startup "
    "wiring to the clean OPPO MediaControl flow. Remove it when the main "
    "playback orchestrator owns OPPO adapter construction directly."
)
class LegacyOppoMediaControlPlaybackOutput(OppoPlaybackPort):
    """
    Adapter from the startup orchestrator to OPPO MediaControl network playback.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._playback = OppoMediaControlPlayback(config)

    def start_playback(
        self,
        request: OppoPlaybackStartRequest,
        *,
        on_waiting: Callable[[int], None] | None = None,
    ) -> OppoPlaybackStartResult:
        return self._playback.start_playback(
            request,
            on_waiting=on_waiting,
        )

    def get_playback_state(self) -> OppoPlaybackState:
        result = self._playback_status_client().query_playback_state()
        return OppoPlaybackState(
            status=result.status,
            category=result.category,
            raw_response=result.raw_response,
            ok=result.ok,
        )

    def get_playback_position(self) -> OppoPlaybackPosition:
        return self._playback.get_playback_position()

    def seek_to(self, position_ticks: int) -> DeviceCommandResult:
        return self._playback.seek_to(position_ticks)

    def select_audio_track(self, audio_index: int) -> DeviceCommandResult:
        return self._playback.select_audio_track(audio_index)

    def select_subtitle_track(self, subtitle_index: int) -> DeviceCommandResult:
        return self._playback.select_subtitle_track(subtitle_index)

    def stop_playback(self) -> DeviceCommandResult:
        raise NotImplementedError

    def _playback_status_client(self) -> OppoPlaybackStatusClient:
        player_host = self._config["Oppo_IP"]
        player_status_port = int(self._config.get("OPPO_Port", 23))

        return OppoPlaybackStatusClient(
            host=player_host,
            port=player_status_port,
            timeout=float(self._config.get("timeout_oppo_conection", 3)),
        )


@deprecated(
    "_run exists only because the current legacy TV adapter exposes async methods "
    "to synchronous Xnoppo.py startup code."
)
def _run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


@deprecated(
    "_unwrap_value exists only to normalize legacy adapter return shapes during "
    "the transitional startup wiring."
)
def _unwrap_value(result: Any) -> Any:
    return getattr(result, "value", result)


@deprecated(
    "_to_device_command_result exists only to translate legacy adapter return "
    "values into the new startup result model."
)
def _to_device_command_result(
    *,
    operation: str,
    legacy_result: Any,
) -> DeviceCommandResult:
    if isinstance(legacy_result, DeviceCommandResult):
        return legacy_result

    if legacy_result is None:
        return DeviceCommandResult.success(
            f"{operation} completed; command returned no result."
        )

    if isinstance(legacy_result, bool):
        if legacy_result:
            return DeviceCommandResult.success(f"{operation} returned true.")
        return DeviceCommandResult.failed(f"{operation} returned false.")

    status_code = getattr(legacy_result, "status_code", None)
    if isinstance(status_code, int):
        if 200 <= status_code < 400:
            return DeviceCommandResult.success(
                f"{operation} returned HTTP {status_code}."
            )
        return DeviceCommandResult.failed(f"{operation} returned HTTP {status_code}.")

    if isinstance(legacy_result, str):
        normalized = legacy_result.strip().upper()

        if normalized == "OK" or "SUCCESS" in normalized:
            return DeviceCommandResult.success(legacy_result)

        if "ERROR" in normalized or "FAIL" in normalized:
            return DeviceCommandResult.failed(legacy_result)

        return DeviceCommandResult.success(legacy_result)

    return DeviceCommandResult.success(
        f"{operation} returned {type(legacy_result).__name__}."
    )
