import logging

from home_cinema_bridge.devices.av.base import BaseAvReceiver
from home_cinema_bridge.devices.av.tcp import TcpCommandSender


class NadAvReceiver(BaseAvReceiver, TcpCommandSender):
    def power_on(self):
        logging.info('llamada a av_power_on')
        return self.send_command("Main.Power=On\n")

    def get_hdmi_list(self):
        return [
            {"Id": 1, "Name": "HDMI 1", "Param": "Main.Source=1\n"},
            {"Id": 2, "Name": "HDMI 2", "Param": "Main.Source=2\n"},
            {"Id": 3, "Name": "HDMI 3", "Param": "Main.Source=3\n"},
        ]


    def change_hdmi(self):
        logging.info('Llamada a av_change_hdmi')
        return self.send_command(self.config["AV_Input"])

    def power_off(self):
        logging.info('Llamada a av_power_off')
        return self.send_command("Main.Power=Off\n")