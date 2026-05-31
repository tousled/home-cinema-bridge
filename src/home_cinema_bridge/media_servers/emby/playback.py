import logging
import uuid
from dataclasses import dataclass


PLAYBACK_PROGRESS_INTERVAL_SECONDS = 10
EMBY_TICKS_PER_SECOND = 10_000_000


@dataclass(frozen=True)
class MediaServerPlaybackContext:
    """Playback metadata translated from the media server event.

    Naming is intentionally project-domain oriented:

    - media_library_item_id: movie/episode/library entry being played.
    - media_source_file_id: concrete file/source/version selected for that item.
    - source_client_session_id: original TV/app client session that requested playback.
    - media_server_playback_id: server playback lifecycle id used for check-ins.
    - *_ticks: media-server time units. In Emby these are .NET ticks, 100ns each.
    """

    media_library_item_id: str
    media_source_file_id: str
    selected_audio_track_id: int
    selected_subtitle_track_id: int
    media_server_user_id: str
    source_client_session_id: str | None
    media_server_playback_id: str
    start_position_ticks: int

    @classmethod
    def from_event(cls, data, *, load_user_item):
        media_library_item_id = _selected_media_library_item_id(data)
        start_position_ticks = _start_position_ticks(data)
        media_server_user_id = data.get("ControllingUserId", "")

        if start_position_ticks < 0:
            item_info = load_user_item(media_server_user_id, media_library_item_id)
            start_position_ticks = int(
                item_info.get("UserData", {}).get("PlaybackPositionTicks", 0)
            )

        return cls(
            media_library_item_id=str(media_library_item_id),
            media_source_file_id=data.get("MediaSourceId", ""),
            selected_audio_track_id=int(data.get("AudioStreamIndex", 1)),
            selected_subtitle_track_id=int(data.get("SubtitleStreamIndex", -1)),
            media_server_user_id=media_server_user_id,
            source_client_session_id=data.get("SessionID"),
            media_server_playback_id=data.get("PlaySessionId") or str(uuid.uuid4()),
            start_position_ticks=start_position_ticks,
        )


class MediaServerPlaybackEventPublisher:
    """Publishes media-server playback lifecycle events for the external player."""

    def __init__(
        self,
        client,
        *,
        bridge_session_id: str,
        context: MediaServerPlaybackContext,
        progress_interval_seconds: int = PLAYBACK_PROGRESS_INTERVAL_SECONDS,
    ):
        self._client = client
        self._bridge_session_id = bridge_session_id
        self.context = context
        self.progress_interval_seconds = progress_interval_seconds
        self._last_reported_second: int | None = None

    def started(self):
        payload = self._base_payload(self.context.start_position_ticks)
        response = self._client.notify_playback_started(payload)
        self._log_response("started", payload, response)
        return response

    def progress(
        self,
        *,
        position_ticks: int,
        runtime_ticks: int,
        is_paused: bool = False,
        is_muted: bool = False,
        force: bool = False,
    ):
        position_seconds = position_ticks // 10_000_000
        if not force and not self._should_report_progress(position_seconds):
            return None

        payload = self._base_payload(
            position_ticks,
            runtime_ticks=runtime_ticks,
            is_paused=is_paused,
            is_muted=is_muted,
        )
        payload["EventName"] = "TimeUpdate"

        response = self._client.report_playback_progress(payload)
        self._last_reported_second = position_seconds
        self._log_response("progress", payload, response)
        return response

    def stopped(
        self,
        *,
        position_ticks: int,
        runtime_ticks: int = 0,
        is_paused: bool = False,
        is_muted: bool = False,
    ):
        payload = self._base_payload(
            position_ticks,
            runtime_ticks=runtime_ticks,
            is_paused=is_paused,
            is_muted=is_muted,
        )
        response = self._client.notify_playback_stopped(payload)
        self._log_response("stopped", payload, response)
        return response

    def _should_report_progress(self, position_seconds: int) -> bool:
        if position_seconds <= 0:
            return False

        if self._last_reported_second is None:
            return True

        return (
            position_seconds - self._last_reported_second
            >= self.progress_interval_seconds
        )

    def _base_payload(
        self,
        position_ticks: int,
        *,
        runtime_ticks: int = 0,
        is_paused: bool = False,
        is_muted: bool = False,
    ):
        payload = {
            "QueueableMediaTypes": ["Video"],
            "CanSeek": True,
            "ItemId": self.context.media_library_item_id,
            "SessionId": self._bridge_session_id,
            "MediaSourceId": self.context.media_source_file_id,
            "AudioStreamIndex": self.context.selected_audio_track_id,
            "SubtitleStreamIndex": self.context.selected_subtitle_track_id,
            "IsPaused": is_paused,
            "IsMuted": is_muted,
            "PositionTicks": position_ticks,
            "PlayMethod": "DirectPlay",
            "PlaySessionId": self.context.media_server_playback_id,
            "RepeatMode": "RepeatNone",
        }

        if runtime_ticks > 0:
            payload["RunTimeTicks"] = runtime_ticks

        return payload

    def _log_response(self, event_name, payload, response):
        logging.debug(
            "Media server playback lifecycle %s | media_library_item_id=%s | media_server_playback_id=%s | position_ticks=%s | status=%s | body=%s",
            event_name,
            self.context.media_library_item_id,
            self.context.media_server_playback_id,
            payload.get("PositionTicks"),
            response.status_code,
            response.text,
        )


class MediaServerPlaybackProgressReporter:
    """Reports playback-domain progress to the media server."""

    def __init__(self, publisher: MediaServerPlaybackEventPublisher):
        self._publisher = publisher

    def progress(
        self,
        *,
        position_seconds: int,
        duration_seconds: int,
        is_paused: bool = False,
        is_muted: bool = False,
    ):
        return self._publisher.progress(
            position_ticks=position_seconds * EMBY_TICKS_PER_SECOND,
            runtime_ticks=duration_seconds * EMBY_TICKS_PER_SECOND,
            is_paused=is_paused,
            is_muted=is_muted,
        )


class MediaServerPlaybackStoppedReporter:
    """Reports playback-domain stopped state to the media server."""

    def __init__(self, publisher: MediaServerPlaybackEventPublisher):
        self._publisher = publisher

    def stopped(
        self,
        *,
        position_seconds: int,
        duration_seconds: int,
        is_paused: bool = False,
        is_muted: bool = False,
    ):
        return self._publisher.stopped(
            position_ticks=position_seconds * EMBY_TICKS_PER_SECOND,
            runtime_ticks=duration_seconds * EMBY_TICKS_PER_SECOND,
            is_paused=is_paused,
            is_muted=is_muted,
        )


def _selected_media_library_item_id(data):
    item_ids = data["ItemIds"]
    start_index = int(data.get("StartIndex", 0))

    if isinstance(item_ids, list):
        if not item_ids:
            raise ValueError("Emby playback event has no ItemIds.")

        if start_index > 0 and start_index < len(item_ids):
            return item_ids[start_index]

        return item_ids[0]

    return item_ids


def _start_position_ticks(data):
    start_at = data.get("StartPositionTicks")

    if start_at is None:
        start_at = data.get("SavedPlaybackPositionTicks")

    if start_at is None:
        return -1

    return int(start_at)
