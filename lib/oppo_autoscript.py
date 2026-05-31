import logging
import socket
import time
import shlex

from home_cinema_bridge.network.tcp import LoggingTcpClient


IAC = 255
WILL = 251
WONT = 252
DO = 253
DONT = 254
_tcp = LoggingTcpClient(name="oppo-telnet")


def _process_telnet_chunk(sock, chunk):
    output = bytearray()
    index = 0

    while index < len(chunk):
        byte = chunk[index]

        if byte != IAC:
            output.append(byte)
            index += 1
            continue

        if index + 1 >= len(chunk):
            break

        command = chunk[index + 1]

        if command == IAC:
            output.append(IAC)
            index += 2
            continue

        if command in (WILL, WONT, DO, DONT) and index + 2 < len(chunk):
            option = chunk[index + 2]

            if command == DO:
                sock.sendall(bytes([IAC, WONT, option]))
            elif command == WILL:
                sock.sendall(bytes([IAC, DONT, option]))

            index += 3
            continue

        index += 2

    return bytes(output)


def _read_until(sock, marker, timeout):
    sock.settimeout(timeout)
    data = b""

    try:
        while marker not in data:
            chunk = sock.recv(1024)
            if not chunk:
                break

            data += _process_telnet_chunk(sock, chunk)

    except socket.timeout:
        pass

    return data


def _read_available(sock, timeout):
    sock.settimeout(timeout)
    data = b""

    try:
        while True:
            chunk = sock.recv(1024)
            if not chunk:
                break

            data += _process_telnet_chunk(sock, chunk)

    except socket.timeout:
        pass

    return data


def unmount_oppo_path(*, host: str, port: int = 23, mount_path: str, debug: bool = False, timeout: int | float = 10) -> bool:
    logging.info('*** unmount OPPO path %s ***', mount_path)

    if not mount_path.startswith(("/mnt/nfs", "/mnt/cifs")):
        raise ValueError(f"Refusing to unmount unexpected OPPO path: {mount_path}")

    try:
        with _tcp.connect(host=host, port=port, timeout=timeout) as session:
            output = _read_until(session, b"login:", timeout)

            session.sendall(b"root\n")
            time.sleep(0.2)

            command = f"umount {shlex.quote(mount_path)}\n"
            session.sendall(command.encode("ascii"))
            session.sendall(b"ls\n")
            session.sendall(b"exit\n")

            output += _read_available(session, 3)

        if debug:
            print(output.decode("ascii", errors="replace"))

        return True

    except Exception:
        logging.exception("ERROR unmounting OPPO path: %s", mount_path)
        return False
