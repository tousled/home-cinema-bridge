import logging

from lib.devices.av.base import BaseAvReceiver
from lib.devices.av.tcp import TcpCommandSender


class MarantzAvReceiver(BaseAvReceiver, TcpCommandSender):
    def power_on(self):
        logging.info('llamada a av_power_on')
        return self.send_command("ZMON\n")

    def get_hdmi_list(self):
        return [
            {"Id": 1, "Name": "CD", "Param": "SICD\n"},
            {"Id": 2, "Name": "DVD", "Param": "SIDVD\n"},
            {"Id": 3, "Name": "Blu-ray (BD)", "Param": "SIBD\n"},
            {"Id": 4, "Name": "TV AUDIO(TV)", "Param": "SITV\n"},
            {"Id": 5, "Name": "CBL/SAT", "Param": "SISAT/CBL\n"},
            {"Id": 5, "Name": "SAT", "Param": "SISAT\n"},
            {"Id": 5, "Name": "PEPE", "Param": "SICBL\n"},
            {"Id": 6, "Name": "GAME", "Param": "SIGAME\n"},
        ]

    def change_hdmi(self):
        logging.info('Llamada a av_change_hdmi')
        return self.send_command(self.config["AV_Input"])

    def power_off(self):
        logging.info('Llamada a av_power_off')
        return self.send_command("ZMOFF\n")