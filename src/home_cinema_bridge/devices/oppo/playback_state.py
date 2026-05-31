from enum import Enum


class OppoPlaybackCategory(str, Enum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"


class OppoPlaybackStatus(str, Enum):
    PLAY = "PLAY"
    PAUSE = "PAUSE"
    DISC_MENU = "DISC_MENU"
    FFWD = "FFWD"
    FREV = "FREV"
    SFWD = "SFWD"
    SREV = "SREV"
    STEP = "STEP"

    HOME_MENU = "HOME_MENU"
    SCREEN_SAVER = "SCREEN_SAVER"
    MEDIA_CENTER = "MEDIA_CENTER"
    NO_DISC = "NO_DISC"

    STOP = "STOP"
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    LOADING = "LOADING"

    UNKNOWN = "UNKNOWN"


ACTIVE_PLAYBACK_STATUSES = {
    OppoPlaybackStatus.PLAY,
    OppoPlaybackStatus.PAUSE,
    OppoPlaybackStatus.DISC_MENU,
    OppoPlaybackStatus.FFWD,
    OppoPlaybackStatus.FREV,
    OppoPlaybackStatus.SFWD,
    OppoPlaybackStatus.SREV,
    OppoPlaybackStatus.STEP,
}

IDLE_STATUSES = {
    OppoPlaybackStatus.HOME_MENU,
    OppoPlaybackStatus.SCREEN_SAVER,
    OppoPlaybackStatus.MEDIA_CENTER,
    OppoPlaybackStatus.NO_DISC,
}

TRANSITION_STATUSES = {
    OppoPlaybackStatus.STOP,
    OppoPlaybackStatus.OPEN,
    OppoPlaybackStatus.CLOSE,
    OppoPlaybackStatus.LOADING,
}


def normalize_oppo_status(raw_status: str) -> str:
    status = raw_status.strip()

    if status.startswith("@OK"):
        status = status[3:].strip()

    if not status:
        return "UNKNOWN"

    return status.upper().replace(" ", "_")


def parse_oppo_playback_status(raw_status: str) -> OppoPlaybackStatus:
    normalized_status = normalize_oppo_status(raw_status)

    try:
        return OppoPlaybackStatus(normalized_status)
    except ValueError:
        return OppoPlaybackStatus.UNKNOWN


def classify_oppo_status(status: str | OppoPlaybackStatus) -> OppoPlaybackCategory:

    playback_status = (
        status
        if isinstance(status, OppoPlaybackStatus)
        else parse_oppo_playback_status(status)
    )

    if playback_status in ACTIVE_PLAYBACK_STATUSES:
        return OppoPlaybackCategory.ACTIVE

    if playback_status in IDLE_STATUSES:
        return OppoPlaybackCategory.IDLE

    if playback_status in TRANSITION_STATUSES:
        return OppoPlaybackCategory.TRANSITION

    return OppoPlaybackCategory.UNKNOWN

