import logging
import subprocess

from home_cinema_bridge.devices.av.base import BaseAvReceiver


class ScriptsAvReceiver(BaseAvReceiver):
    def get_hdmi_list(self):
        return []

    def power_on(self):
        logging.info('Llamada a av_power_on')
        subprocess.Popen(self.config["AV_CMD_POW_ON"])
        return "OK"

    def change_hdmi(self):
        logging.info('Llamada a av_change_hdmi')
        subprocess.Popen(self.config["AV_CMD_CHANGE_HDMI"])
        return "OK"

    def power_off(self):
        logging.info('Llamada a av_power_off')
        subprocess.Popen(self.config["AV_CMD_POW_OFF"])
        return "OK"