import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from home_cinema_bridge.devices.oppo.playback_state import OppoPlaybackCategory
from lib.devices.oppo.playback_status_client import OppoCommandResult, OppoPlaybackStatusClient


@dataclass(frozen=True)
class PlaybackStartupWaitResult:
    started: bool
    attempts: int
    elapsed_seconds: float
    status: str
    category: OppoPlaybackCategory
    raw_response: str


def wait_until_oppo_reports_active_playback(
    config: dict,
    timeout: int | float,
    interval: float = 0.5,
    query_state: Callable[[], OppoCommandResult] | None = None,
    on_playback_waiting: Callable[[int], None] | None = None,
) -> PlaybackStartupWaitResult:
    """
    Wait until OPPO QPL reports an ACTIVE state.

    ACTIVE means the OPPO is already in a playback-related state:
    PLAY, PAUSE, DISC_MENU, FFWD, FREV, SFWD, SREV or STEP.

    The first QPL check runs immediately. The interval is only used between
    retries, so this does not add an artificial startup delay.
    """
    started_at = time.monotonic()
    deadline = started_at + float(timeout)
    attempts = 0
    last_result = _unknown_result()

    if query_state is None:
        query_state = _build_qpl_query(config)

    while time.monotonic() < deadline:
        attempts += 1

        try:
            last_result = query_state()

            logging.debug(
                "QPL playback startup wait | attempt=%s | status=%s | category=%s | raw=%r",
                attempts,
                last_result.status,
                last_result.category.value,
                last_result.raw_response,
            )

            if last_result.ok and last_result.category == OppoPlaybackCategory.ACTIVE:
                return _build_wait_result(
                    started=True,
                    attempts=attempts,
                    started_at=started_at,
                    result=last_result,
                )

        except Exception as exc:
            logging.debug(
                "QPL playback startup wait failed | attempt=%s | error_type=%s | error=%s",
                attempts,
                type(exc).__name__,
                exc,
            )

        if on_playback_waiting is not None:
            on_playback_waiting(attempts)

        time.sleep(interval)

    return _build_wait_result(
        started=False,
        attempts=attempts,
        started_at=started_at,
        result=last_result,
    )


def _build_qpl_query(config: dict) -> Callable[[], OppoCommandResult]:
    client = OppoPlaybackStatusClient(
        host=config["Oppo_IP"],
        port=int(config.get("OPPO_Port", 23)),
        timeout=float(config.get("timeout_oppo_conection", 3)),
    )

    return client.query_playback_state


def _build_wait_result(
    *,
    started: bool,
    attempts: int,
    started_at: float,
    result: OppoCommandResult,
) -> PlaybackStartupWaitResult:
    return PlaybackStartupWaitResult(
        started=started,
        attempts=attempts,
        elapsed_seconds=time.monotonic() - started_at,
        status=result.status,
        category=result.category,
        raw_response=result.raw_response,
    )


def _unknown_result() -> OppoCommandResult:
    return OppoCommandResult(
        command="QPL",
        raw_response="",
        ok=False,
        status="UNKNOWN",
        category=OppoPlaybackCategory.UNKNOWN,
    )