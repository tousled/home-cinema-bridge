#!/usr/bin/env python3
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.oppo_status_client import OppoStatusClient


def now() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def print_result(result, previous_status: str | None) -> str:
    changed = ""

    if previous_status is not None and result.status != previous_status:
        changed = f"  <<< CHANGED {previous_status} -> {result.status}"

    print(
        f"{now()} {result.command}: "
        f"raw={result.raw_response!r} "
        f"status={result.status} "
        f"category={result.category.value} "
        f"ok={result.ok}"
        f"{changed}",
        flush=True,
    )

    return result.status


def run_once(client: OppoStatusClient, commands: list[str]) -> int:
    for command in commands:
        try:
            result = client.query(command)
            print_result(result, None)
        except Exception as exc:
            print(f"{now()} {command}: ERROR {type(exc).__name__}: {exc}", flush=True)

    return 0


def run_watch(
    client: OppoStatusClient,
    command: str,
    interval: float,
    changes_only: bool,
) -> int:
    previous_status: str | None = None
    normalized_command = command.upper().lstrip("#")

    print(
        f"Watching OPPO {client.host}:{client.port} "
        f"command={normalized_command} interval={interval}s "
        f"changes_only={changes_only}. Press Ctrl+C to stop.",
        flush=True,
    )

    try:
        while True:
            started = time.monotonic()

            try:
                result = client.query(command)

                if not changes_only or previous_status is None or result.status != previous_status:
                    previous_status = print_result(result, previous_status)
                else:
                    previous_status = result.status

            except Exception as exc:
                print(f"{now()} {normalized_command}: ERROR {type(exc).__name__}: {exc}", flush=True)

            elapsed = time.monotonic() - started
            sleep_time = max(0.0, interval - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Query OPPO/Chinoppo player state over TCP port 23.")
    parser.add_argument("--host", default="192.168.50.35", help="OPPO/Chinoppo IP address")
    parser.add_argument("--port", type=int, default=23, help="OPPO/Chinoppo control port")
    parser.add_argument("--timeout", type=float, default=3.0, help="Socket timeout in seconds")
    parser.add_argument(
        "--commands",
        nargs="+",
        default=["QPW", "QPL"],
        help="Commands to send in one-shot mode, without or with # prefix. Example: QPW QPL",
    )
    parser.add_argument("--watch", action="store_true", help="Continuously query one command")
    parser.add_argument("--watch-command", default="QPL", help="Command to query in watch mode")
    parser.add_argument("--interval", type=float, default=0.5, help="Watch interval in seconds")
    parser.add_argument(
        "--changes-only",
        action="store_true",
        help="In watch mode, print only when status changes",
    )

    args = parser.parse_args()
    client = OppoStatusClient(host=args.host, port=args.port, timeout=args.timeout)

    if args.watch:
        return run_watch(
            client=client,
            command=args.watch_command,
            interval=args.interval,
            changes_only=args.changes_only,
        )

    return run_once(client, args.commands)


if __name__ == "__main__":
    raise SystemExit(main())
