#!/usr/bin/env python3
import argparse
import socket
import time


def normalize_command(command: str) -> bytes:
    command = command.strip()
    if not command.startswith("#"):
        command = f"#{command}"
    if not command.endswith("\r"):
        command = f"{command}\r"
    return command.encode("ascii")


def query_oppo(host: str, port: int, command: str, timeout: float) -> str:
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

            # Typical OPPO responses are short, e.g. "@OK PLAY".
            # Give the player a tiny window in case the response arrives in pieces.
            time.sleep(0.05)

            try:
                more = sock.recv(1024)
                if more:
                    chunks.append(more)
            except socket.timeout:
                break

            break

    return b"".join(chunks).decode("utf-8", errors="replace").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Query OPPO/Chinoppo player state over TCP port 23.")
    parser.add_argument("--host", default="192.168.50.35", help="OPPO/Chinoppo IP address")
    parser.add_argument("--port", type=int, default=23, help="OPPO/Chinoppo control port")
    parser.add_argument("--timeout", type=float, default=3.0, help="Socket timeout in seconds")
    parser.add_argument(
        "--commands",
        nargs="+",
        default=["QPW", "QPL"],
        help="Commands to send, without or with # prefix. Example: QPW QPL",
    )

    args = parser.parse_args()

    for command in args.commands:
        try:
            response = query_oppo(args.host, args.port, command, args.timeout)
            print(f"{command}: {response}")
        except Exception as exc:
            print(f"{command}: ERROR {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
