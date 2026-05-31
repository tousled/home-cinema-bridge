# Changelog

All notable changes to this project will be documented in this file.

The format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versioning follows semantic versioning where practical.

> This fork is currently in pre-1.0 modernization. Versions `0.x` may introduce breaking changes while the legacy architecture is progressively replaced.

## [0.5.1] - 2026-06-01

### Changed

- Updated the web-reported application version to `0.5.1`.
- Documented OPPO natural media-end behaviour in the public state-machine notes.

### Fixed

- Fixed natural media endings that could leave the user on a black OPPO screen
  for over a minute while QPL still reported `PLAY`.
- The during-playback orchestrator now confirms repeated end-of-media playback
  positions (`current >= total`) and reports a `NATURAL_END` stop reason.
- Final playback position is normalized to the media runtime before reporting
  stopped playback to Emby, avoiding values such as `3533 / 3529`.
- The finish orchestrator now closes OPPO playback with `STP` after a natural
  end if the player still reports an active state, then confirms idle before
  restoring LG/AV outputs.

### Validated

- Real episode-ending logs showed OPPO stuck at `PLAY` with
  `current=3533` / `total=3529` before eventually returning to `HOME_MENU`;
  this release models that state directly.
- Sending `STP` while OPPO was already idle (`SCREEN_SAVER`) returned success,
  left OPPO idle, and a follow-up NFS mount succeeded.

## [0.5.0] - 2026-05-31

### Added

- Added a parent playback orchestrator that coordinates startup, post-start
  completion, during-playback monitoring, finish, and centralized error
  recovery.
- Added a dedicated during-playback orchestrator based on OPPO QPL state
  observation and OPPO MediaControl playback time.
- Added a finish orchestrator that reports the final playback position to Emby,
  waits for OPPO to settle into an idle state, returns the LG TV to the correct
  app, and restores AV receiver TV audio.
- Added centralized playback error recovery that can stop OPPO playback with
  `STP` before restoring TV and AV outputs.
- Added active-playback replacement support: requesting another item while one
  is playing now stops the current parent flow, waits for a clean finish, and
  then starts the replacement item through the same orchestrated flow.
- Added explicit playback origins for observed TV-client playback and remote
  Emby control commands.
- Added an Emby playback command handler for PlayNow, pause/unpause, stop,
  chapter navigation, audio/subtitle changes, absolute seek, and 10-second
  forward/back remote seek commands.
- Added transport-level HTTP/TCP diagnostics with compact successful-response
  logging and richer failure logging.
- Added OPPO MediaControl handling for optical image startup cases where the
  mount endpoint fails or times out but OPPO later reports active playback.
- Added tests for playback orchestration, replacement, OPPO startup/finish,
  Emby playback command translation, and error recovery.

### Changed

- Replaced the legacy `lib/Xnoppo.py` playback entry point with cleaner
  playback application/orchestration modules.
- Reworked playback startup so OPPO MediaControl startup, TV input switching,
  AV input switching, resume, audio selection, and subtitle selection are
  coordinated through the new playback flow.
- Replaced the legacy `getglobalinfo` string loop for active playback with QPL
  state monitoring.
- Changed Emby progress handling to observe OPPO frequently for local stop
  detection while throttling Emby `Progress` check-ins to the media-server
  lifecycle interval.
- Changed active replacement stop semantics to use OPPO `STP` as the playback
  close command for all media types, including ISO/Blu-ray cases.
- Changed replacement finish semantics so the old item reports stopped and
  confirms OPPO idle state without restoring TV/AV outputs before the
  replacement item starts.
- Changed TV app restoration during replacements so the original non-HDMI app is
  preserved across the whole room playback flow instead of being overwritten by
  the intermediate OPPO HDMI input.
- Changed Emby playback status messages to target the active source/control
  session instead of broadcasting messages to every user session.
- Updated the web-reported application version to `0.5.0`.

### Fixed

- Fixed `bd_is_playing` and duplicate replay failures caused by legacy
  `playother`/replay paths remounting while OPPO was already playing.
- Fixed normal stop after replacement returning the LG TV to HDMI instead of the
  Emby app.
- Fixed a UX issue where replacement temporarily returned LG/Denon to TV before
  the replacement item started.
- Fixed replacement startup being attempted before OPPO had confirmed an idle
  state after stopping the active item.
- Fixed finish success reporting so OPPO idle-confirmation failure makes the
  finish result unsuccessful.
- Fixed intermittent startup/finish failures leaving OPPO active by adding
  OPPO stop handling to centralized error recovery.
- Fixed remote seek from Emby mobile/web clients so relative seek changes OPPO
  position instead of restarting playback.
- Fixed direct Emby stop commands to send OPPO `STP` instead of home/navigation
  commands.
- Fixed stale LG monitored-session snapshots triggering duplicate playback
  requests while bridge-owned playback was already loading or playing.

### Removed

- Removed `lib/Xnoppo.py`.
- Removed legacy `playto_file` and `playother` playback paths.
- Removed the legacy web watchdog that mutated playback state outside the
  orchestrated playback flow.
- Removed legacy Emby `/Sessions/{session}/Viewing` reporting from the active
  playback path.
- Removed unused legacy OPPO helpers that were no longer referenced by
  productive code.

### Validated

- Validated MKV playback from the LG Emby app.
- Validated ISO / Full Blu-ray playback from remote Emby control.
- Validated MKV -> ISO replacement.
- Validated ISO -> MKV replacement when OPPO MediaControl mount state was
  healthy.
- Validated final stop after replacement returning LG to `com.emby.app` and
  Denon to `SITV`.
- Validated pause, chapter navigation, absolute seek, and 10-second
  forward/back seek from the Emby mobile/web controller.
- Validated preservation of the last valid OPPO playback position when
  `getplayingtime` returns transient zero values during stop/transition.

### Notes

- OPPO MediaControl can still enter a stale NFS mount state after some
  ISO/Blu-ray replacement flows. Command-level recovery attempts tested so far
  did not restore mounting; rebooting/power-cycling OPPO remains the only
  proven recovery for that specific device-side stale state.
- Startup timing improved mainly by removing legacy replay/remount paths,
  duplicate attempts, and redundant OPPO calls. Exact before/after timing should
  be measured later from comparable runs on `main` and `develop`; current logs
  are not a controlled benchmark.
- The legacy web configuration/remote-control surface still contains OPPO
  diagnostic flows that should be modernized separately.

## [0.4.0] - 2026-05-23

### Added

- Added Python 3.14 runtime support.
- Added an AV adapter layer under `lib/devices/av`.
- Added explicit AV receiver implementations for:
  - Denon
  - Marantz
  - NAD
  - Onkyo
  - Yamaha
  - script-based AV control
- Added AV adapter selection from `config["AV_model"]`.
- Added a socket-based TCP command sender for AV receivers that use simple TCP commands.
- Added `lib/oppo_autoscript.py` to isolate OPPO Autoscript-related unmount logic.

### Changed

- Replaced the legacy AV library-copying mechanism with an adapter/factory approach.
- Replaced AV `telnetlib` usage with socket-based command sending where appropriate.
- Renamed the internal AV `check_power` operation to `power_on`, keeping the legacy `av_check_power(config)` wrapper for compatibility.
- Updated AV web setup so changing AV model no longer copies Python files or restarts the application.
- Improved AV web setup responsiveness by removing the old `/move_av` restart flow.
- Kept legacy public AV function names used by `Xnoppo.py` and `xnoppo_web.py`, while routing implementation through adapters.
- Moved OPPO Autoscript unmount handling out of `Xnoppo.py`.

### Removed

- Removed the old `web/libraries/AV` runtime-copying structure.
- Removed AV runtime dependence on `telnetlib`.
- Removed the `/move_av` web flow.
- Removed unnecessary AV code duplication across vendor-specific files.

### Validated

- Validated Denon control with the receiver already powered on.
- Validated Denon control with the receiver suspended/off.
- Validated AV web interface after the adapter/factory migration.
- Validated normal playback and AV HDMI switching after the migration.

### Notes

- TV still uses the legacy TV implementation path and will be migrated separately.
- OPPO HTTP calls such as `getglobalinfo()` and `getplayingtime()` still need future hardening for the case where the OPPO is powered off or unreachable.

## [0.3.0] - 2026-05-23

### Added

- Added OPPO QPL diagnostics for playback-state observation.
- Added OPPO playback-state classification for active, idle and transition states.
- Added support for additional OPPO trick-play/navigation states observed during testing:
  - `FFWD`
  - `FREV`
  - `SFWD`
  - `SREV`
  - `STEP`
- Added preservation of the last valid non-zero playback position when OPPO reports zero at stop time.
- Added cleaner debug logging around playback, QPL state observation and subtitle handling.

### Changed

- Improved subtitle handling when no subtitle is selected.
- Improved subtitle handling when Emby sends a selected subtitle stream.
- Refactored duplicated subtitle-selection logic into a shared helper.
- Fixed `/check_emby` web configuration flow.
- Simplified Emby connection checking logic.
- Reduced noisy subtitle and MediaStreams logging.
- Improved WebSocket callback handling and session logging.
- Rotated exposed LG TV key after debugging.
- Rotated exposed Emby password after debugging and validated the system afterwards.

### Fixed

- Fixed repeated subtitle-setting attempts when no subtitle was selected.
- Fixed subtitle mapping from Emby subtitle stream index to OPPO subtitle index.
- Fixed the missing `EmbyHttp` import / broken `/check_emby` flow.
- Fixed playback progress being overwritten with zero in common stop scenarios.
- Fixed several noisy debug outputs that made real playback issues harder to diagnose.

### Validated

- Validated playback without subtitles.
- Validated playback with selected subtitles.
- Validated ISO / Full Blu-ray playback.
- Validated normal movie playback.
- Validated fast-forward, rewind and pause state observation.
- Validated web configuration flow after `/check_emby` fix.

### Notes

- Experimental segment-aware progress tracking was discarded because it introduced fragile heuristics. Future progress/timeline hardening should use a dedicated tested tracker instead of adding more logic inside `playto_file`.

## [0.2.0] - 2026-05-22

### Added

- Added Docker runtime support.
- Added Portainer stack deployment support from Git.
- Added persistent Docker volume for runtime configuration.
- Added `/config/config.json` runtime configuration support.
- Added `XNOPPO_CONFIG_FILE` environment variable support.
- Added `restart: unless-stopped` runtime behaviour.
- Added first-run configuration creation from `config.example.json`.
- Added safe startup behaviour when configuration is incomplete.

### Changed

- Container now starts the web UI even when Emby/OPPO configuration is incomplete.
- Emby WebSocket startup is skipped until configuration is valid.
- Runtime configuration is no longer tied to the project root.
- Docker deployment now uses host networking for the home-cinema integration.

### Fixed

- Fixed Docker runtime startup with persistent config.
- Fixed missing configuration bootstrapping for fresh deployments.
- Fixed runtime behaviour when config is incomplete.

### Validated

- Validated Docker build and runtime deployment on ASUSTOR.
- Validated Portainer deployment from Git.
- Validated persistent configuration volume.
- Validated Emby WebSocket startup after real config was copied into the Docker volume.
- Validated playback from Docker runtime.

## [0.1.1] - 2026-05-22

### Changed

- Sanitized runtime debug logs to avoid exposing sensitive values during troubleshooting.

### Notes

- This was a small maintenance release on top of the clean fork baseline.

## [0.1.0] - 2026-05-22

### Added

- Established the clean baseline for the project.
- Added the missing `lib/playback_manager.py` to the baseline.
- Created the initial stable tag used as the reference point for later work.

### Fixed

- Fixed Emby WebSocket callback binding by correcting callback method signatures.
- Fixed callback instance usage in `lib/Emby_ws.py`.

### Notes

- This version is the stable baseline before Docker/runtime, QPL, subtitle, AV adapter and Python 3.14 work.
