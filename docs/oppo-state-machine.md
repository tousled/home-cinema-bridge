# OPPO / Chinoppo playback state machine

## Context

This document describes the playback-state observations made while integrating Home Cinema Bridge / Xnoppo with an OPPO UDP-203 / Chinoppo-compatible player.

The goal is to replace fragile assumptions based only on getglobalinfo() / getplayingtime() with a clearer state model based on the official OPPO IP control command QPL.

## OPPO IP control transport

The OPPO UDP-203/205 IP control protocol uses TCP port 23, but the player is not a Telnet server.

Commands must be sent as raw TCP messages, for example:

    #QPL\r
    #QPW\r

The official protocol states that clients should wait for a response before sending the next command. If verbose mode is enabled, the player can also send unsolicited status updates. Because of that, state observation should use a controlled raw-socket client and should avoid mixing multiple concurrent clients when exact sequencing matters.

## Standby/off behaviour in this environment

In this installation, OPPO standby/off behaves as:

    STANDBY_NETWORK_ALIVE_CONTROL_UNAVAILABLE

Observed behaviour:

    ARP/ICMP: available
    MAC: 00:22:de:85:dd:27
    TCP 23: timeout
    TCP 436: timeout
    QPW/QPL: timeout
    UDP NOTIFY OREMOTE LOGIN: does not wake control services
    Wake-on-LAN from Mac: does not wake
    ASUS Reactivar/WOL: does not wake

Therefore, this state is not considered manageable by the QPL state machine. The player must already be control-available: HOME_MENU, SCREEN_SAVER, PLAY, DISC_MENU, etc.

## QPL categories

Current classification:

    ACTIVE_PLAYBACK_STATES = {"PLAY", "PAUSE", "DISC_MENU"}
    IDLE_STATES = {"HOME_MENU", "SCREEN_SAVER", "MEDIA_CENTER", "NO_DISC"}
    TRANSITION_STATES = {"STOP", "OPEN", "CLOSE", "LOADING"}

## State meaning

| QPL state | Category | Meaning |
|---|---|---|
| PLAY | Active | Content is actively playing |
| PAUSE | Active | Playback is paused but content is still active |
| DISC_MENU | Active | Blu-ray/disc menu is visible; do not treat as stopped |
| HOME_MENU | Idle | Player is back at home menu |
| SCREEN_SAVER | Idle | Player is idle/screensaver |
| MEDIA_CENTER | Idle | Player is in media center/navigation |
| NO_DISC | Idle | No disc/media state |
| STOP | Transition | Startup or stop transition; do not treat as final immediately |
| OPEN | Transition | Stop/exit transition observed before returning to HOME_MENU |
| CLOSE | Transition | Short/early return transition observed before returning to HOME_MENU |
| LOADING | Transition | Loading state; wait for a stable state |

## Observed playback flow

Starting playback from Emby TV:

    HOME_MENU -> STOP -> PLAY

Stable playback:

    PLAY

Stopping/returning to TV:

    PLAY -> OPEN -> HOME_MENU

A short/early return flow also produced:

    PLAY -> CLOSE -> HOME_MENU

Therefore, OPEN and CLOSE are transition states, not errors.

## Mapping from legacy logic to QPL

| Legacy signal | QPL equivalent | Meaning |
|---|---|---|
| getglobalinfo reports video playing | PLAY, sometimes DISC_MENU | Active playback or disc menu |
| getglobalinfo stops reporting video playing | OPEN, CLOSE, HOME_MENU, SCREEN_SAVER, STOP | Playback is no longer active |
| PlayingTime cur_time > 0 | Usually PLAY | Valid progress candidate |
| PlayingTime cur_time == 0 after stop | Usually OPEN or HOME_MENU | Do not overwrite last valid progress |
| Timeout/reset while probing QPL | No state change | Ignore transient probe failures |

## Progress hardening note

A legacy issue was observed where playback reached a valid position, for example:

    PlayingTime: 84 de 7448

but after stopping, the OPPO returned:

    PlayingTime Final: 0 de 7448

Future hardening should preserve the last valid non-zero playback position and avoid overwriting it with zero during OPEN, CLOSE, HOME_MENU or other terminal/transition states.

## Implementation guidance

Recommended next steps:

1. Keep QPL probing through raw TCP sockets.
2. Do not use Telnet clients for OPPO IP control.
3. Treat QPW as useful for power checks only, not for playback-state observation.
4. Prefer QPL/internal container logs for playback-state decisions.
5. Add progress hardening by preserving the last valid non-zero playback position.
