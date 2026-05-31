from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from home_cinema_bridge.media_servers.emby.session_events import (
    is_same_media_item_request,
    playback_intent_to_legacy_payload,
    playback_request_media_item_id,
)
from home_cinema_bridge.playback.intent import PlaybackIntent


def bridge_playback_is_active(playstate: str) -> bool:
    return playstate in ("Loading", "Playing", "Replay")


class LegacyPlaybackIntentDispatcher:
    """
    Temporary bridge from clean playback intents to legacy Xnoppo entry points.

    Remove this when the websocket can call the parent PlaybackOrchestrator use
    case directly.
    """

    def __init__(
        self,
        *,
        emby_session,
        start_playback: Callable,
        switch_playback: Callable,
        reload_config: Callable[[], None],
        debug_level: int = 0,
        sleep=time.sleep,
    ) -> None:
        self._emby_session = emby_session
        self._start_playback = start_playback
        self._switch_playback = switch_playback
        self._reload_config = reload_config
        self._debug_level = debug_level
        self._sleep = sleep

    def dispatch(self, intent: PlaybackIntent, *, scripterx: bool) -> bool:
        legacy_payload = playback_intent_to_legacy_payload(intent)
        if self._is_duplicate_request(legacy_payload):
            logging.info(
                "Ignoring duplicate monitored playback event | item_id=%s | "
                "playstate=%s",
                playback_request_media_item_id(legacy_payload),
                self._emby_session.playstate,
            )
            return False

        self._wait_for_loading_to_finish()
        if self._emby_session.playstate in ("Playing", "Replay"):
            if self._debug_level > 0:
                print("ya se esta reproduciendo algo")
            self._switch_playback(self._emby_session, legacy_payload, scripterx)
            return True

        thread = threading.Thread(
            target=self._thread_function_play,
            args=(legacy_payload, scripterx),
        )
        thread.start()
        return True

    def _is_duplicate_request(self, legacy_payload: dict) -> bool:
        return bridge_playback_is_active(
            self._emby_session.playstate
        ) and is_same_media_item_request(
            self._emby_session.currentdata,
            legacy_payload,
        )

    def _wait_for_loading_to_finish(self) -> None:
        if self._emby_session.playstate not in ("Loading", "Replay"):
            return

        if self._debug_level > 0:
            print("Esta en la pantalla de Loading, tenemos que esperar")

        timeout = 60
        elapsed = 0
        while self._emby_session.playstate == "Loading" and elapsed < timeout:
            self._sleep(3)
            elapsed = elapsed + 3

    def _thread_function_play(self, legacy_payload: dict, scripterx: bool) -> None:
        print("Thread Play: starting")
        self._start_playback(self._emby_session, legacy_payload, scripterx)
        self._reload_config()
        print("Thread Play: finishing")
