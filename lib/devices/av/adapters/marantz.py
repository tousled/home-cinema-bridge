import logging

from lib.devices.av.base import BaseAvReceiver
from lib.devices.av.input_retrier import AVInputRetrier, extract_prefixed_response
from lib.devices.av.tcp import TcpCommandSender

MARANTZ_INPUT_QUERY_COMMAND = "SI?\n"
MARANTZ_INPUT_QUERY_TIMEOUT_SECONDS = 1.0
MARANTZ_INPUT_RESPONSE_PREFIX = "SI"
MARANTZ_TV_AUDIO_INPUT = "SITV"


class MarantzAvReceiver(BaseAvReceiver, TcpCommandSender):
    receiver_name = "Marantz"
    uses_observed_input_recovery = True

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
        return AVInputRetrier(
            receiver_name=self.receiver_name,
            input_command=self.config["AV_Input"],
            send_input_command=self.send_command,
            get_current_input=self._get_current_input,
            redirected_input=MARANTZ_TV_AUDIO_INPUT,
        ).change_input()

    def _get_current_input(self):
        try:
            raw_response = self.query_command(
                MARANTZ_INPUT_QUERY_COMMAND,
                timeout=MARANTZ_INPUT_QUERY_TIMEOUT_SECONDS,
                expected_prefix=MARANTZ_INPUT_RESPONSE_PREFIX,
            )

        except OSError as exc:
            logging.warning("Unable to query %s input | error=%s", self.receiver_name, exc)
            return None

        return extract_prefixed_response(raw_response, MARANTZ_INPUT_RESPONSE_PREFIX)

    def power_off(self):
        logging.info('Llamada a av_power_off')
        return self.send_command("ZMOFF\n")
