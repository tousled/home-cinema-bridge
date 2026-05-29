from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from home_cinema_bridge.playback.startup.models import (
    DeviceCommandResult,
    OppoPlaybackStartRequest,
    OppoPlaybackStartResult,
    OppoPlaybackState,
)
from lib.devices.oppo.control_api_client import OppoControlApiClient
from lib.devices.oppo.network_playback_starter import (
    OppoNetworkFolder,
    OppoNetworkPlaybackStarter,
)
from lib.devices.oppo.playback_state_waiter import (
    wait_until_oppo_reports_active_playback,
)

logger = logging.getLogger(__name__)


class OppoPlaybackStartup:
    def __init__(
        self,
        config: dict[str, Any],
        *,
        control_api_client: OppoControlApiClient | None = None,
        network_playback: OppoNetworkPlaybackStarter | None = None,
    ) -> None:
        self._config = config
        self._control_api = control_api_client or OppoControlApiClient.from_config(
            config
        )
        self._network_playback = network_playback or OppoNetworkPlaybackStarter(
            config,
            control_api_client=self._control_api,
        )

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
