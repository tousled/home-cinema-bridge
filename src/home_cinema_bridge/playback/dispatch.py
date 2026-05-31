from __future__ import annotations

import logging
import time

from home_cinema_bridge.media_servers.emby.session_events import (
    is_same_media_item_request,
    playback_intent_to_legacy_payload,
    playback_request_media_item_id,
)
from home_cinema_bridge.playback.intent import PlaybackIntent, PlaybackOrigin


def bridge_playback_is_active(playstate: str) -> bool:
    return playstate in ("Loading", "Playing", "Replay")


class PlaybackIntentDispatcher:
    """
    Application boundary for playback requests observed from a media server.

    The monitored-session path already enters with a clean PlaybackIntent. The
    direct PlayNow path still enters with a legacy payload shape, so this class
    keeps one explicit compatibility method until that path is migrated too.
    """

    def __init__(
        self,
        *,
        legacy_playback_session,
        playback_application_service,
        debug_level: int = 0,
        sleep=time.sleep,
    ) -> None:
        self._legacy_playback_session = legacy_playback_session
        self._playback_application_service = playback_application_service
        self._debug_level = debug_level
        self._sleep = sleep

    def dispatch(self, intent: PlaybackIntent, *, origin: PlaybackOrigin) -> bool:
        legacy_payload = playback_intent_to_legacy_payload(intent)
        return self.dispatch_legacy_payload(legacy_payload, origin=origin)

    def dispatch_legacy_payload(
        self,
        legacy_payload: dict,
        *,
        origin: PlaybackOrigin,
    ) -> bool:
        if self._is_duplicate_request(legacy_payload):
            logging.info(
                "Ignoring duplicate playback request | item_id=%s | playstate=%s",
                playback_request_media_item_id(legacy_payload),
                self._legacy_playback_session.playstate,
            )
            return False

        self._wait_for_loading_to_finish()
        if self._legacy_playback_session.playstate in ("Playing", "Replay"):
            if self._debug_level > 0:
                print("ya se esta reproduciendo algo")
            return self._playback_application_service.replace(
                legacy_payload,
                origin=origin,
            )

        self._playback_application_service.start(legacy_payload, origin=origin)
        return True

    def _is_duplicate_request(self, legacy_payload: dict) -> bool:
        return bridge_playback_is_active(
            self._legacy_playback_session.playstate
        ) and is_same_media_item_request(
            self._legacy_playback_session.currentdata,
            legacy_payload,
        )

    def _wait_for_loading_to_finish(self) -> None:
        if self._legacy_playback_session.playstate not in ("Loading", "Replay"):
            return

        if self._debug_level > 0:
            print("Esta en la pantalla de Loading, tenemos que esperar")

        timeout = 60
        elapsed = 0
        while self._legacy_playback_session.playstate == "Loading" and elapsed < timeout:
            self._sleep(3)
            elapsed = elapsed + 3
