#!/usr/bin/env python3
import argparse
import socket
import time
from datetime import datetime


def normalize_command(command: str) -> bytes:
    command = command.strip().upper()

    if not command.startswith("#"):
        command = f"#{command}"

    if not command.endswith("\r"):
        command = f"{command}\r"

    return command.encode("ascii")


def parse_status(raw_response: str) -> str:
    response = raw_response.strip()

    if response.startswith("@OK"):
        response = response[3:].strip()

    if not response:
        return "UNKNOWN"

    return response.upper().replace(" ", "_")


def query_oppo(host: str, port: int, command: str, timeout: float) -> tuple[str, str]:
    payload = normalize_command(command)

    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(payload)

        chunks: list[bytes] = []
        started = time.monotonic()

        while time.monotonic() - started < timeout:
            try:
                chunk = sock.recv(1024)
            except socket.timeout:
                break

            if not chunk:
                break

            chunks.append(chunk)

            # Typical OPPO responses are short, but allow tiny fragmented responses.
            time.sleep(0.05)

            try:
                more = sock.recv(1024)
                if more:
                    chunks.append(more)
            except socket.timeout:
                break

            break

    raw_response = b"".join(chunks).decode("utf-8", errors="replace").strip()
    return raw_response, parse_status(raw_response)


def print_sample(command: str, raw_response: str, status: str, previous_status: str | None) -> str:
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    changed = ""

    if previous_status is not None and status != previous_status:
        changed = f"  <<< CHANGED {previous_status} -> {status}"

    print(f"{now} {command}: raw={raw_response!r} status={status}{changed}", flush=True)
    return status


def run_once(host: str, port: int, timeout: float, commands: list[str]) -> int:
    for command in commands:
        try:
            raw_response, status = query_oppo(host, port, command, timeout)
            print_sample(command.upper().lstrip("#"), raw_response, status, None)
        except Exception as exc:
            now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"{now} {command}: ERROR {type(exc).__name__}: {exc}", flush=True)

    return 0


def run_watch(host: str, port: int, timeout: float, interval: float, command: str, changes_only: bool) -> int:
    previous_status: str | None = None

    print(
        f"Watching OPPO {host}:{port} command={command.upper().lstrip('#')} "
        f"interval={interval}s changes_only={changes_only}. Press Ctrl+C to stop.",
        flush=True,
    )

    try:
        while True:
            try:
                raw_response, status = query_oppo(host, port, command, timeout)

                if not changes_only or previous_status is None or status != previous_status:
                    previous_status = print_sample(
                        command.upper().lstrip("#"),
                        raw_response,
                        status,
                        previous_status,
                    )
                else:
                    previous_status = status

            except Exception as exc:
                now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"{now} {command}: ERROR {type(exc).__name__}: {exc}", flush=True)

            time.sleep(interval)

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

    if args.watch:
        return run_watch(
            host=args.host,
            port=args.port,
            timeout=args.timeout,
            interval=args.interval,
            command=args.watch_command,
            changes_only=args.changes_only,
        )

    return run_once(args.host, args.port, args.timeout, args.commands)


if __name__ == "__main__":
    raise SystemExit(main())
