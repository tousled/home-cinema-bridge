from __future__ import annotations

import asyncio
import logging
from typing import Any

from home_cinema_bridge.devices.av.factory import create_av_receiver
from home_cinema_bridge.devices.tv.factory import create_tv_controller
from home_cinema_bridge.playback.startup.models import DeviceCommandResult
from home_cinema_bridge.playback.startup.ports import (
    AvReceiverOutputPort,
    TelevisionOutputPort,
)

logger = logging.getLogger(__name__)


class LegacyTelevisionOutput(TelevisionOutputPort):
    """
    Bridge from the new playback startup orchestrator to the existing TV factory.

    This is transitional code. It still receives the legacy config dict because the
    current TV factory expects it, but the orchestrator itself does not see that dict.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._controller = create_tv_controller(config)

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


class LegacyAvReceiverOutput(AvReceiverOutputPort):
    """
    Bridge from the new playback startup orchestrator to the existing AV factory.

    This is transitional code. It creates the configured AV receiver once and reuses it
    for power-on and input switching during the startup flow.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._receiver = create_av_receiver(config)

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


def _run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def _unwrap_value(result: Any) -> Any:
    return getattr(result, "value", result)


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
