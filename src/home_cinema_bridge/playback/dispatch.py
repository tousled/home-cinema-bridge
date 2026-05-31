from __future__ import annotations

from home_cinema_bridge.media_servers.emby.session_events import (
    playback_intent_to_legacy_payload,
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
        playback_application_service,
    ) -> None:
        self._playback_application_service = playback_application_service

    def dispatch(self, intent: PlaybackIntent, *, origin: PlaybackOrigin) -> bool:
        legacy_payload = playback_intent_to_legacy_payload(intent)
        return self.dispatch_legacy_payload(legacy_payload, origin=origin)

    def dispatch_legacy_payload(
        self,
        legacy_payload: dict,
        *,
        origin: PlaybackOrigin,
    ) -> bool:
        return self._playback_application_service.request_playback(
            legacy_payload,
            origin=origin,
        )
