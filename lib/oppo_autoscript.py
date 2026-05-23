import logging
import socket
import time


IAC = 255
WILL = 251
WONT = 252
DO = 253
DONT = 254


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


def umount_shared_folder(config):
    logging.info('*** umountSharedFolder ***')

    host = config["Oppo_IP"]
    port = int(config.get("OPPO_Port", 23))
    user = "root"

    try:
        with socket.create_connection((host, port), timeout=10) as session:
            output = _read_until(session, b"login:", 10)

            session.sendall(user.encode("ascii") + b"\n")
            time.sleep(0.2)

            session.sendall(b"umount /mnt/cifs1\n")
            session.sendall(b"ls\n")
            session.sendall(b"exit\n")

            output += _read_available(session, 3)

        if config["DebugLevel"] > 0:
            print(output.decode("ascii", errors="replace"))

        return "OK"

    except Exception:
        logging.exception("ERROR unmounting shared OPPO folder")
        return "ERROR unmounting"
