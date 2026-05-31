import logging

from home_cinema_bridge.devices.av.base import BaseAvReceiver
from home_cinema_bridge.devices.av.tcp import TcpCommandSender


class NadAvReceiver(BaseAvReceiver, TcpCommandSender):
    def power_on(self):
        logging.info('llamada a av_power_on')
        result = self.send_command("Main.Power=On\n")
        self._wait_after_power_on()
        return result

    def get_hdmi_list(self):
        return [
            {"Id": 1, "Name": "HDMI 1", "Param": "Main.Source=1\n"},
            {"Id": 2, "Name": "HDMI 2", "Param": "Main.Source=2\n"},
            {"Id": 3, "Name": "HDMI 3", "Param": "Main.Source=3\n"},
        ]


    def change_hdmi(self):
        logging.info('Llamada a av_change_hdmi')
        return self.send_command(self.config["AV_Input"])

    def restore_tv_audio(self):
        tv_input = self.config.get("AV_TV_Input")
        if tv_input:
            logging.info("Restoring NAD to TV audio input | input=%s", tv_input.strip())
            return self.send_command(tv_input)
        super().restore_tv_audio()

    def power_off(self):
        logging.info('Llamada a av_power_off')
        return self.send_command("Main.Power=Off\n")