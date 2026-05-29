from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from home_cinema_bridge.devices.av.factory import create_av_receiver
from home_cinema_bridge.devices.tv.factory import create_tv_controller
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
from lib.devices.oppo.control_api_client import OppoControlApiClient
from lib.devices.oppo.network_playback_starter import (
    OppoNetworkFolder,
    OppoNetworkPlaybackStarter,
)
from lib.devices.oppo.playback_state_waiter import (
    wait_until_oppo_reports_active_playback,
)
from lib.devices.oppo.playback_status_client import OppoPlaybackStatusClient

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


class LegacyOppoPlaybackOutput(OppoPlaybackPort):
    """
    Bridge from the startup orchestrator to the current OPPO playback helpers.

    This adapter is transitional: it hides the current OPPO HTTP/QPL and NAS mount
    details behind the playback port while the old Xnoppo.py flow is being reduced.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._control_api = OppoControlApiClient.from_config(config)
        self._network_playback = OppoNetworkPlaybackStarter(config)

    def prepare_for_playback_startup(self) -> DeviceCommandResult:
        started_at = time.perf_counter()

        try:
            self._measure_preparation_step(
                "initialize_control_session",
                self._initialize_control_session,
            )
            self._measure_preparation_step(
                "refresh_device_state_before_network_playback",
                self._refresh_device_state_before_network_playback,
            )
            self._measure_preparation_step(
                "clear_previous_playback_startup_state",
                self._clear_previous_playback_startup_state,
            )

            logger.info(
                "OPPO playback startup preparation timing | total=%.3fs",
                time.perf_counter() - started_at,
            )

            return DeviceCommandResult.success("OPPO prepared for playback startup.")
        except Exception as exc:
            logger.exception("OPPO playback startup preparation failed.")
            return DeviceCommandResult.failed(
                f"OPPO playback startup preparation failed: {type(exc).__name__}: {exc}"
            )

    def start_playback(
        self,
        request: OppoPlaybackStartRequest,
        *,
        on_waiting: Callable[[int], None] | None = None,
    ) -> OppoPlaybackStartResult:
        try:
            device_list_text = self._wait_for_playback_device_list(request)
            device_list = json.loads(device_list_text)

            location = request.media_location

            protocol = self._network_playback.resolve_network_folder_protocol(
                device_list=device_list,
                server_name=location.content_server,
            )

            network_folder = OppoNetworkFolder(
                server_name=location.content_server,
                folder_path=location.content_directory,
                protocol=protocol,
            )

            self._network_playback.prepare_network_folder_access(network_folder)

            if not request.assume_player_already_on:
                time.sleep(5)

            self._control_api.get_setup_menu()

            mount_result = self._network_playback.mount_network_folder(network_folder)
            mounted_share = mount_result.mounted_share

            if not mount_result.is_mounted or mounted_share is None:
                return OppoPlaybackStartResult(
                    media_mounted=False,
                    playback_command_accepted=False,
                    playback_started_on_device=False,
                    detail=mount_result.error_message,
                )

            playback_launch_result = self._network_playback.start_playback(
                mounted_share=mounted_share,
                filename=location.playback_file_name,
                container=location.playback_file_format,
            )

            if not playback_launch_result.is_started:
                return OppoPlaybackStartResult(
                    media_mounted=True,
                    playback_command_accepted=False,
                    playback_started_on_device=False,
                    detail=playback_launch_result.error_message,
                    mounted_path=mounted_share.mount_path,
                )

            startup_result = wait_until_oppo_reports_active_playback(
                config=self._config,
                timeout=request.startup_timeout_seconds,
                interval=request.poll_interval_seconds,
                on_playback_waiting=on_waiting,
            )

            playback_state = OppoPlaybackState(
                status=startup_result.status,
                category=startup_result.category,
                raw_response=startup_result.raw_response,
                ok=startup_result.raw_response.startswith("@OK"),
            )

            return OppoPlaybackStartResult(
                media_mounted=True,
                playback_command_accepted=True,
                playback_started_on_device=startup_result.started,
                detail=None
                if startup_result.started
                else "Timed out waiting for OPPO active playback.",
                mounted_path=mounted_share.mount_path,
                playback_state=playback_state,
            )
        except Exception as exc:
            logger.exception("OPPO playback startup failed.")
            return OppoPlaybackStartResult(
                media_mounted=False,
                playback_command_accepted=False,
                playback_started_on_device=False,
                detail=f"OPPO playback startup failed: {type(exc).__name__}: {exc}",
            )

    def _initialize_control_session(self) -> None:
        self._control_api.get_main_firmware_version()
        self._control_api.get_device_list()
        self._control_api.get_setup_menu()
        self._control_api.sign_in()

    def _refresh_device_state_before_network_playback(self) -> None:
        self._control_api.get_device_list()
        self._control_api.get_global_info()
        self._control_api.get_device_list()

    def _clear_previous_playback_startup_state(self) -> None:
        self._control_api.send_remote_key("EJT")

        if self._config["BRDisc"] is True:
            time.sleep(1)
            self._control_api.send_remote_key("EJT")

    def _measure_preparation_step(
        self,
        step_name: str,
        operation: Callable[[], None],
    ) -> None:
        started_at = time.perf_counter()
        operation()
        logger.info(
            "OPPO playback startup preparation timing | step=%s | elapsed=%.3fs",
            step_name,
            time.perf_counter() - started_at,
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
        raise NotImplementedError

    def seek_to(self, position_ticks: int) -> DeviceCommandResult:
        raise NotImplementedError

    def select_audio_track(self, audio_index: int) -> DeviceCommandResult:
        raise NotImplementedError

    def select_subtitle_track(self, subtitle_index: int) -> DeviceCommandResult:
        raise NotImplementedError

    def stop_playback(self) -> DeviceCommandResult:
        raise NotImplementedError

    def _wait_for_playback_device_list(
        self,
        request: OppoPlaybackStartRequest,
    ) -> str:
        expected_text = 'sub_type":"nfs' if request.wait_for_nfs_share else "sub_type"
        device_list_text = self._control_api.get_device_list()

        while device_list_text.find(expected_text) == 0:
            time.sleep(1)
            device_list_text = self._control_api.get_device_list()
            power_query_result = self._control_api.send_remote_key("QPW")
            logger.debug("Query POWER ON: %s", power_query_result)

        return device_list_text

    def _playback_status_client(self) -> OppoPlaybackStatusClient:
        return OppoPlaybackStatusClient(
            host=self._config["Oppo_IP"],
            port=int(self._config.get("OPPO_Port", 23)),
            timeout=float(self._config.get("timeout_oppo_conection", 3)),
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
