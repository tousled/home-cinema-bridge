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