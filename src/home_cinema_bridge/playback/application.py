from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

from home_cinema_bridge.devices.av.factory import create_av_receiver
from home_cinema_bridge.playback.factory import create_playback_orchestrator_wiring
from home_cinema_bridge.playback.intent import PlaybackOrigin
from home_cinema_bridge.playback.legacy_startup_preparation import (
    build_legacy_playback_startup_context,
    prepare_legacy_playback_startup,
)
from home_cinema_bridge.playback.orchestrator import PlaybackOrchestrationRequest
from home_cinema_bridge.playback.startup import (
    PlaybackOutputSwitchRequest,
    PlaybackStartupRequest,
)
from home_cinema_bridge.playback.startup.completion import (
    LegacyEmbyTrackResolver,
    PlayMediaItemRequest,
)
from home_cinema_bridge.playback.timing import PlaybackStartupTimer

from lib.devices.oppo.control_api_activation import OppoControlApiActivator
from lib.devices.oppo.control_api_client import OppoControlApiClient
from lib.devices.oppo.playback_status_client import OppoPlaybackStatusClient


logger = logging.getLogger(__name__)
MEDIA_SERVER_TICKS_PER_SECOND = 10_000_000
_qpl_last_observed_states = {}


@dataclass(frozen=True)
class PlaybackStartMessages:
    init_oppo: str
    wait_for_mount: str
    wait_for_play: str
    timeout_play: str
    error_mount: str
    error_play: str
    error_no_oppo: str


class PlaybackApplicationService:
    """Application entrypoint for playback requests.

    Start requests now enter the clean parent playback orchestrator from here.
    Replace requests are currently rejected until the active-playback
    replacement semantics are redesigned and validated.
    """

    def __init__(
        self,
        *,
        playback_session,
        reload_config,
    ) -> None:
        self._playback_session = playback_session
        self._reload_config = reload_config

    def start(self, playback_payload: dict, *, origin: PlaybackOrigin) -> None:
        thread = threading.Thread(
            target=self._run_start,
            args=(playback_payload, origin),
        )
        thread.start()

    def replace(self, playback_payload: dict, *, origin: PlaybackOrigin) -> bool:
        logger.warning(
            "Ignoring active-playback replacement request until the clean "
            "orchestrator replacement flow exists | origin=%s | payload=%s",
            origin.value,
            playback_payload,
        )
        return False

    def _run_start(self, playback_payload: dict, origin: PlaybackOrigin) -> None:
        print("Thread Play: starting")
        self._start_orchestrated_playback(playback_payload, origin=origin)
        self._reload_config()
        print("Thread Play: finishing")

    def _start_orchestrated_playback(
        self,
        playback_payload: dict,
        *,
        origin: PlaybackOrigin,
    ) -> None:
        playback_session = self._playback_session
        startup_timer = PlaybackStartupTimer()
        playback_session.playstate = "Loading"
        playback_session.currentdata = playback_payload
        _reset_qpl_observation_state()
        _log_oppo_qpl_state(playback_session.config, "playback_application_start")

        if playback_session.config["DebugLevel"] > 0:
            print("playback origin is " + origin.value)

        with startup_timer.measure_step("process_media_server_payload"):
            startup_context = build_legacy_playback_startup_context(
                emby_session=playback_session,
                playback_payload=playback_payload,
            )
            params = startup_context.params
            media_server_playback_context = (
                startup_context.media_server_playback_context
            )
            item_info = startup_context.item_info

        media_location = None
        movie = ""
        messages = _playback_start_messages(playback_session.lang)

        with startup_timer.measure_step("ensure_oppo_control_api_available"):
            control_api_available = _ensure_oppo_control_api_available(
                playback_session.config
            )

        if not control_api_available:
            _send_playback_message(
                playback_session,
                origin,
                params,
                messages.error_no_oppo,
            )
            _reset_legacy_playback_session_state(playback_session, movie)
            return

        _send_playback_message(playback_session, origin, params, messages.init_oppo)

        if _should_stop_source_client_before_handoff(playback_session.config, origin):
            with startup_timer.measure_step("stop_source_client_before_handoff"):
                response_data = playback_session.playback_stop(params["Session_id"])

            if playback_session.config["DebugLevel"] > 0:
                print(response_data)

        playback_wiring = create_playback_orchestrator_wiring(
            config=playback_session.config,
            media_server_client=playback_session.client,
            bridge_session_id=playback_session.user_info["SessionInfo"]["Id"],
            playback_context=media_server_playback_context,
            track_resolver=LegacyEmbyTrackResolver(playback_session),
            step_timer=startup_timer,
        )
        output_switch_request = PlaybackOutputSwitchRequest(
            tv_input_id=str(
                playback_session.config.get("Source", "configured_tv_input")
            ),
            av_input_id=playback_session.config.get("AV_Input"),
            tv_enabled=playback_session.config.get("TV") is True,
            av_enabled=playback_session.config.get("AV") is True,
        )
        playback_start_poll_interval = 0.5

        with startup_timer.measure_step("resolve_media_path"):
            startup_preparation = prepare_legacy_playback_startup(
                emby_session=playback_session,
                params=params,
                item_info=item_info,
                playback_start_poll_interval=playback_start_poll_interval,
            )
            item_info = startup_preparation.item_info
            media_location = startup_preparation.media_location
            oppo_playback_start_request = startup_preparation.oppo_start_request
            movie = item_info["Path"]

        logger.info("Servidor               : %s", media_location.content_server)
        logger.info("Fichero                : %s", media_location.playback_file_name)
        logger.info("Carpeta                : %s", media_location.content_directory)
        logger.info("-----------------------------------------------------------")
        playback_session.server = media_location.content_server
        playback_session.folder = media_location.content_directory
        playback_session.filename = media_location.playback_file_name
        playback_session.playedtitle = item_info["Name"]

        _send_playback_message(
            playback_session,
            origin,
            params,
            messages.wait_for_mount,
            timeout_ms=1999,
        )

        last_notified_second = -1

        def notify_playback_waiting(attempt: int) -> None:
            nonlocal last_notified_second

            elapsed_seconds = int(attempt * playback_start_poll_interval)
            notification_interval_seconds = 1

            if elapsed_seconds <= 0:
                return

            if elapsed_seconds % notification_interval_seconds != 0:
                return

            if elapsed_seconds == last_notified_second:
                return

            last_notified_second = elapsed_seconds
            _send_playback_message(
                playback_session,
                origin,
                params,
                messages.wait_for_play + str(elapsed_seconds) + "s",
                timeout_ms=999,
            )

        is_paused = False
        is_muted = False

        def complete_legacy_startup_logging(_oppo_playback_start_result) -> None:
            playback_session.playstate = "Playing"

            if playback_session.config["DebugLevel"] > 0:
                print(params["auto_resume"])

            if playback_session.config["TV"] != True:
                if origin == PlaybackOrigin.OBSERVED_TV_CLIENT:
                    playback_session.send_message2(
                        params["Session_id"],
                        playback_session.lang["x_msg_init_play"] + movie,
                    )
                logger.info("Reprodución iniciada: %s", movie)

            _log_oppo_qpl_state(playback_session.config, "after_playnormalfile")
            startup_timer.log_summary()

        startup_completion_request = PlayMediaItemRequest(
            start_position_seconds=_media_server_ticks_to_seconds(
                params["auto_resume"]
            ),
            source_user_id=params["ControllingUserId"],
            media_item_id=params["item_id"],
            selected_source_audio_track_id=params["audio_stream_index"],
            selected_source_subtitle_track_id=params["subtitle_stream_index"],
        )

        playback_orchestration_result = (
            playback_wiring.playback_orchestrator.play_until_stopped(
                PlaybackOrchestrationRequest(
                    startup_request=PlaybackStartupRequest(
                        output_switch_request=output_switch_request,
                        oppo_start_request=oppo_playback_start_request,
                    ),
                    startup_completion_request=startup_completion_request,
                    is_paused=is_paused,
                    is_muted=is_muted,
                    on_startup_waiting=notify_playback_waiting,
                    on_startup_completed=complete_legacy_startup_logging,
                )
            )
        )

        _handle_orchestration_result(
            playback_session=playback_session,
            origin=origin,
            params=params,
            item_info=item_info,
            media_location=media_location,
            playback_orchestration_result=playback_orchestration_result,
            messages=messages,
            movie=movie,
        )

        _power_down_after_playback_if_configured(playback_session.config)
        _reset_legacy_playback_session_state(playback_session, movie)


def _playback_start_messages(lang: dict[str, str]) -> PlaybackStartMessages:
    return PlaybackStartMessages(
        init_oppo=lang["x_msg_init_oppo"],
        wait_for_mount=lang["x_msg_wait_for_mount"],
        wait_for_play=lang["x_msg_wait_for_play"],
        timeout_play=lang["x_msg_timeout_play"],
        error_mount=lang["x_msg_error_mount"],
        error_play=lang["x_msg_error_play"],
        error_no_oppo=lang["x_msg_error_no_oppo"],
    )


def _ensure_oppo_control_api_available(config: dict[str, Any]) -> bool:
    activator = OppoControlApiActivator.from_config(config)
    result = activator.ensure_control_api_available(
        max_attempts=int(config["timeout_oppo_conection"])
    )

    if result.available:
        logger.debug(
            "OPPO control API available | host=%s | port=%s | attempts=%s",
            result.host,
            result.port,
            result.attempts,
        )
        return True

    logger.warning(
        "Timeout waiting for OPPO control API | host=%s | port=%s | attempts=%s | error=%s",
        result.host,
        result.port,
        result.attempts,
        result.error,
    )
    return False


def _should_stop_source_client_before_handoff(
    config: dict[str, Any],
    origin: PlaybackOrigin,
) -> bool:
    return config["TV"] is True and origin == PlaybackOrigin.OBSERVED_TV_CLIENT


def _send_playback_message(
    playback_session,
    origin: PlaybackOrigin,
    params: dict,
    message: str,
    timeout_ms: int | None = None,
) -> None:
    if origin == PlaybackOrigin.OBSERVED_TV_CLIENT:
        if timeout_ms is None:
            playback_session.send_message2(params["Session_id"], message)
        else:
            playback_session.send_message2(params["Session_id"], message, timeout_ms)
        return

    if timeout_ms is None:
        playback_session.send_user_message(params["ControllingUserId"], message)
    else:
        playback_session.send_user_message(
            params["ControllingUserId"],
            message,
            timeout_ms,
        )


def _handle_orchestration_result(
    *,
    playback_session,
    origin: PlaybackOrigin,
    params: dict,
    item_info: dict,
    media_location,
    playback_orchestration_result,
    messages: PlaybackStartMessages,
    movie: str,
) -> None:
    oppo_playback_start_result = (
        playback_orchestration_result.startup_result.oppo_start_result
    )

    if not oppo_playback_start_result.successful:
        if not oppo_playback_start_result.media_mounted:
            error_message = (
                messages.error_mount
                + media_location.content_server
                + "/"
                + media_location.content_directory
                + " - info:"
                + str(oppo_playback_start_result.detail)
            )
        elif not oppo_playback_start_result.playback_command_accepted:
            error_message = (
                messages.error_play
                + media_location.playback_file_name
                + " - info:"
                + str(oppo_playback_start_result.detail)
            )
        else:
            error_message = messages.timeout_play
            logger.info("Timeout Reproduciendo %s", movie)

        _send_playback_message(
            playback_session,
            origin,
            params,
            error_message,
            timeout_ms=5000,
        )
        return

    if not playback_orchestration_result.successful:
        finish_result = playback_orchestration_result.finish_result
        recovery_result = playback_orchestration_result.error_recovery_result
        logger.warning(
            "Playback orchestration ended with non-startup failure | "
            "finish_successful=%s | recovery_successful=%s",
            finish_result.successful if finish_result is not None else None,
            recovery_result.successful if recovery_result is not None else None,
        )
        return

    playback_monitoring_result = playback_orchestration_result.monitoring_result
    finish_result = playback_orchestration_result.finish_result

    logger.info("-----------------------------------------------------------")
    logger.debug(
        "PlayingTime: %s de %s",
        playback_monitoring_result.position_seconds,
        playback_monitoring_result.duration_seconds,
    )
    if playback_session.config["DebugLevel"] > 0:
        print(
            "PlayingTime Final: "
            + str(playback_monitoring_result.position_seconds)
            + " de "
            + str(playback_monitoring_result.duration_seconds)
        )
    logger.info(
        "OPPO playback monitoring stopped | final_state=%s | category=%s | "
        "position_seconds=%s | duration_seconds=%s",
        playback_monitoring_result.final_state.status.value,
        playback_monitoring_result.final_state.category.value,
        playback_monitoring_result.position_seconds,
        playback_monitoring_result.duration_seconds,
    )
    logger.info(
        "Playback finish result | successful=%s | tv=%s | av_audio=%s | "
        "final_state=%s | category=%s",
        finish_result.successful,
        finish_result.tv_app_result.status.value,
        finish_result.av_audio_result.status.value,
        finish_result.final_player_state.status.value,
        finish_result.final_player_state.category.value,
    )


def _power_down_after_playback_if_configured(config: dict[str, Any]) -> None:
    if config["AV"] == True and config["AV_Always_ON"] == False:
        if config["DebugLevel"] > 0:
            print("AV POWER OFF")
        create_av_receiver(config).power_off()

    if config["Always_ON"] == False:
        OppoControlApiClient.from_config(config).send_remote_key("POF")


def _reset_legacy_playback_session_state(playback_session, movie: str) -> None:
    playback_session.playstate = "Free"
    playback_session.server = ""
    playback_session.playedtitle = ""
    playback_session.folder = ""
    playback_session.filename = ""
    logger.info("Fin PlaybackApplicationService.start %s", movie)


def _media_server_ticks_to_seconds(position_ticks: int) -> int:
    return int(position_ticks / MEDIA_SERVER_TICKS_PER_SECOND)


def _reset_qpl_observation_state() -> None:
    _qpl_last_observed_states.clear()


def _log_oppo_qpl_state(config: dict[str, Any], label: str) -> None:
    try:
        debug_level = int(config.get("DebugLevel", 0))
        if debug_level <= 0:
            return

        oppo_ip = config.get("Oppo_IP")
        if not oppo_ip:
            print(f"QPL:{label} skipped | Oppo_IP is not configured")
            return

        client = OppoPlaybackStatusClient(
            host=oppo_ip,
            port=int(config.get("OPPO_Port", 23)),
            timeout=float(config.get("timeout_oppo_conection", 3)),
        )

        result = client.query_playback_state()
        print(
            f"QPL:{label} | "
            f"raw={result.raw_response!r} | "
            f"status={result.status} | "
            f"category={result.category.value} | "
            f"ok={result.ok}"
        )
    except Exception as exc:
        try:
            if config.get("DebugLevel", 0) > 0:
                print(f"QPL:{label} | ERROR {type(exc).__name__}: {exc}")
        except Exception:
            pass
