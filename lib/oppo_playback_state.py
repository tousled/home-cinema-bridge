from enum import Enum


class OppoPlaybackCategory(str, Enum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"


ACTIVE_PLAYBACK_STATES = {
    "PLAY",
    "PAUSE",
    "DISC_MENU",
    "FFWD",
    "FREV",
    "SFWD",
    "SREV",
    "STEP",
}

IDLE_STATES = {
    "HOME_MENU",
    "SCREEN_SAVER",
    "MEDIA_CENTER",
    "NO_DISC",
}

TRANSITION_STATES = {
    "STOP",
    "OPEN",
    "CLOSE",
    "LOADING",
}


def normalize_oppo_status(raw_status: str) -> str:
    status = raw_status.strip()

    if status.startswith("@OK"):
        status = status[3:].strip()

    if not status:
        return "UNKNOWN"

    return status.upper().replace(" ", "_")


def classify_oppo_status(status: str) -> OppoPlaybackCategory:
    if status in ACTIVE_PLAYBACK_STATES:
        return OppoPlaybackCategory.ACTIVE

    if status in IDLE_STATES:
        return OppoPlaybackCategory.IDLE

    if status in TRANSITION_STATES:
        return OppoPlaybackCategory.TRANSITION

    return OppoPlaybackCategory.UNKNOWN

def is_active_playback_state(status: str) -> bool:
    return classify_oppo_status(status) == OppoPlaybackCategory.ACTIVE

def is_idle_state(status: str) -> bool:
    return classify_oppo_status(status) == OppoPlaybackCategory.IDLE

def is_transition_state(status: str) -> bool:
    return classify_oppo_status(status) == OppoPlaybackCategory.TRANSITION