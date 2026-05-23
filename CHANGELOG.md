# Changelog

All notable changes to this project will be documented in this file.

The format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versioning follows semantic versioning where practical.

> This fork is currently in pre-1.0 modernization. Versions `0.x` may introduce breaking changes while the legacy architecture is progressively replaced.

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
