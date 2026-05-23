# Home Cinema Bridge

Home Cinema Bridge is a modernized fork of **Xnoppo**, originally created by **siberian-git**.

The original project is available here:

https://github.com/siberian-git/Xnoppo

Home Cinema Bridge uses **Emby** as the browsing interface and an **OPPO / Chinoppo UDP-203** as the playback device.

The goal is to keep the best part of the original idea:

> Browse your media library comfortably from Emby, but play high-quality local media through the OPPO player.

This fork is currently in **pre-1.0 modernization**. The codebase is being progressively restructured to replace legacy copy-based code with cleaner, testable and maintainable modules.

## Project status

Current version line: `0.x`

This fork is not considered API-stable yet. Versions before `1.0.0` may introduce breaking changes while the legacy architecture is progressively replaced.

The intended `1.0.0` milestone is a stable, modernized version with:

- Docker-first runtime.
- Clean backend structure.
- AV and TV adapter/factory architecture.
- Safer configuration and secrets handling.
- More robust OPPO communication.
- Improved playback startup flow.
- Better web UI.

## What it does

Home Cinema Bridge listens to Emby playback events and redirects playback from an Emby client, such as an LG TV, to an OPPO / Chinoppo UDP-203 player.

Typical flow:

1. Select a movie or episode in Emby.
2. Home Cinema Bridge detects the playback session.
3. It resolves the media path and maps it to the OPPO-accessible network path.
4. It prepares the OPPO player.
5. It mounts the NFS/Samba share.
6. It starts playback on the OPPO.
7. It switches TV / AV inputs when configured.
8. It reports playback progress back to Emby.

## Main features

- Emby WebSocket integration.
- OPPO / Chinoppo UDP-203 playback control.
- NFS and Samba path support.
- Docker runtime support.
- Persistent `/config/config.json` runtime configuration.
- AV receiver integration through adapters/factory.
- LG TV integration inherited from the original project.
- Subtitle selection handling.
- OPPO QPL diagnostics for playback-state observation.
- Python 3.14 runtime support.

## Supported AV integrations

The AV layer has been migrated away from runtime Python file-copying and now uses explicit adapters selected from `AV_model`.

Currently supported AV adapters:

- Denon
- Marantz
- NAD
- Onkyo
- Yamaha
- Script-based custom AV commands

## Modernization highlights

This fork has already replaced several legacy areas:

- Added Docker deployment support.
- Added persistent runtime configuration.
- Added pre-1.0 semantic versioning.
- Added a changelog.
- Added Python 3.14 support.
- Removed `telnetlib` usage.
- Migrated AV handling from copied Python files to adapter/factory classes.
- Removed the legacy `web/libraries/AV` code-copying flow.
- Moved OPPO Autoscript unmount logic into its own module.

## Architecture direction

The project is moving away from legacy runtime file-copying and toward explicit adapters.

Current AV direction:

```text
lib/devices/av/
  base.py
  factory.py
  denon.py
  marantz.py
  nad.py
  onkyo.py
  yamaha.py
  scripts.py
```

Planned TV direction:

```text
lib/devices/tv/
  base.py
  factory.py
  lg.py
  scripts.py
```

The public compatibility functions used by the existing code are preserved for now, but their internal implementations are being moved to cleaner modules.

## Docker usage

The project is designed to run as a container.

The recommended runtime model is:

- app code inside the container
- persistent configuration mounted at `/config`
- runtime config file at `/config/config.json`
- host networking for local home-cinema device discovery/control

Expected runtime configuration:

```text
/config/config.json
XNOPPO_CONFIG_FILE=/config/config.json
network_mode: host
restart: unless-stopped
```

Build example:

```bash
docker build -t home-cinema-bridge .
```

Run example:

```bash
docker run --rm \
  --network host \
  -e XNOPPO_CONFIG_FILE=/config/config.json \
  -v home-cinema-bridge-config:/config \
  home-cinema-bridge
```

For NAS / Portainer deployments, using a Git-backed stack is recommended.

## Configuration

The app creates or uses a runtime `config.json`.

Do not commit real configuration files containing:

- Emby username/password.
- TV pairing keys.
- tokens.
- private IP-specific secrets.
- real user credentials.
- private device keys.

Use `config.example.json` as a template only.

## Secrets and sensitive data

This project should not store real secrets in Git.

Recommended approach:

- keep real `config.json` in the mounted `/config` volume
- keep `.env` files out of Git
- keep `config.example.json` free of real credentials
- avoid logging passwords, tokens or TV keys
- use GitHub Secrets for CI/CD when needed

## Versioning

This fork currently uses pre-1.0 semantic versioning:

```text
0.1.x  Clean fork baseline
0.2.x  Docker runtime
0.3.x  Playback / QPL / subtitle hardening
0.4.x  Python 3.14 + AV adapters/factory
```

The future `1.0.0` release will represent the first stable modernized version of this fork.

See [`CHANGELOG.md`](CHANGELOG.md) for details.

## Roadmap

Near-term:

- migrate TV handling to adapters/factory
- remove legacy `web/libraries/TV` copy-based flow
- integrate improved LG handling
- harden OPPO HTTP calls when the player is powered off or unreachable
- improve playback startup observability and performance

Later:

- lightweight modern web UI
- React + TypeScript + Vite frontend
- better update/release management from the web interface
- safer secrets handling
- branch protection and contribution workflow
- GitHub Releases

## Development workflow

Planned workflow:

```text
feature/* -> develop -> main
```

`main` should represent stable released code.

Feature work should happen in dedicated branches and be merged through pull requests once branch protection is configured.

## Attribution

This project is a modernized fork of the original **Xnoppo** project by **siberian-git**:

https://github.com/siberian-git/Xnoppo

Original idea:

> Xnoppo is a client that uses Emby as the interface and the OPPO 203 as the player, giving you the best of both worlds.

This fork keeps that original idea, while progressively modernizing the codebase, runtime, architecture and deployment model.

The current goal is not to erase the original work, but to build a cleaner and more maintainable modern version on top of it.

The original upstream changelog is preserved in [`docs/UPSTREAM_CHANGELOG.md`](docs/UPSTREAM_CHANGELOG.md) for historical reference.

## License

This project inherits licensing considerations from the original project and its dependencies.

Before publishing formal releases or accepting external contributions, review and clarify the final license file.

