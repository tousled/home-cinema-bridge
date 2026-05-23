import logging

import eiscp

from .base import BaseAvReceiver


class OnkyoAvReceiver(BaseAvReceiver):
    def get_hdmi_list(self):
        return [
            {"Id": 1, "Name": "VIDEO1 VCR/DVR STB/DVR", "Param": "SLI00"},
            {"Id": 2, "Name": "VIDEO2 CBL/SAT", "Param": "SLI01"},
            {"Id": 3, "Name": "VIDEO3 GAME/TV GAME GAME1", "Param": "SLI02"},
            {"Id": 4, "Name": "VIDEO4 AUX1(AUX)", "Param": "SLI03"},
            {"Id": 5, "Name": "VIDEO5 AUX2", "Param": "SLI04"},
            {"Id": 6, "Name": "VIDEO6 PC", "Param": "SLI05"},
            {"Id": 7, "Name": "VIDEO7", "Param": "SLI06"},
            {"Id": 11, "Name": "DVD BD/DVD", "Param": "SLI10"},
        ]

    def power_on(self):
        logging.info('Onkyo power_on')
        try:
            receiver = eiscp.eISCP(self.config["AV_Ip"])
            onk_status = receiver.command('power query')
            logging.info('Onkyo Power Status: %s', onk_status[1])

            if onk_status[1] == ('standby', 'off'):
                logging.info('Cambiamos a on')
                receiver.command('power on')

            receiver.disconnect()
            return "OK"
        except Exception:
            logging.exception('Error powering on Onkyo receiver')
            return "Error"

    def change_hdmi(self):
        logging.info('Onkyo change HDMI Input')
        try:
            receiver = eiscp.eISCP(self.config["AV_Ip"])
            receiver.raw(self.config["AV_Input"])
            receiver.disconnect()
            return "OK"
        except Exception:
            logging.exception('Error changing Onkyo HDMI input')
            return "Error en el cambio"

    def power_off(self):
        logging.info('Onkyo power_off')
        try:
            receiver = eiscp.eISCP(self.config["AV_Ip"])
            onk_status = receiver.command('power query')
            logging.info('Onkyo Power Status: %s', onk_status[1])
            receiver.raw('PWR00')
            receiver.disconnect()
            return "OK"
        except Exception:
            logging.exception('Error powering off Onkyo receiver')
            return "Error"