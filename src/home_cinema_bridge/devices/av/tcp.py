import socket
import time


class TcpCommandSender:
    def send_command(self, command):
        host = self.config["AV_Ip"]
        port = int(self.config["AV_Port"])
        timeout = float(self.config.get("AV_Timeout", 5))

        if isinstance(command, str):
            command = command.encode("ascii")

        with socket.create_connection((host, port), timeout=timeout) as session:
            session.sendall(command)
            time.sleep(0.1)

        return "OK"

    def query_command(self, command, *, timeout=None, expected_prefix=None):
        host = self.config["AV_Ip"]
        port = int(self.config["AV_Port"])
        query_timeout = float(timeout or self.config.get("AV_Query_Timeout", 1))

        if isinstance(command, str):
            command = command.encode("ascii")

        with socket.create_connection((host, port), timeout=query_timeout) as session:
            deadline = time.monotonic() + query_timeout
            response_chunks = []

            session.sendall(command)

            while time.monotonic() < deadline:
                remaining_time = deadline - time.monotonic()
                session.settimeout(min(0.2, remaining_time))

                try:
                    response = session.recv(4096)

                except TimeoutError:
                    continue

                if not response:
                    break

                response_chunks.append(response)
                decoded_response = b"".join(response_chunks).decode(
                    "ascii",
                    errors="replace",
                )

                if expected_prefix and _has_response_with_prefix(
                    decoded_response,
                    expected_prefix,
                ):
                    break

        return b"".join(response_chunks).decode("ascii", errors="replace").strip()


def _has_response_with_prefix(response, expected_prefix):
    for line in response.replace("\r", "\n").splitlines():
        if line.strip().startswith(expected_prefix):
            return True

    return False
