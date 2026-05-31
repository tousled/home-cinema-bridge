import logging

from home_cinema_bridge.devices.av.base import BaseAvReceiver
from home_cinema_bridge.devices.av.input_retrier import (
    AVInputRetrier,
    extract_prefixed_response,
    wait_until_input_stable,
    wait_until_receiver_responsive,
)
from home_cinema_bridge.devices.av.tcp import TcpCommandSender

MARANTZ_INPUT_QUERY_COMMAND = "SI?\n"
MARANTZ_INPUT_QUERY_TIMEOUT_SECONDS = 1.0
MARANTZ_INPUT_RESPONSE_PREFIX = "SI"
MARANTZ_TV_AUDIO_INPUT = "SITV"

MARANTZ_POWER_QUERY_COMMAND = "PW?\n"
MARANTZ_POWER_QUERY_TIMEOUT_SECONDS = 2.0
MARANTZ_POWER_RESPONSE_PREFIX = "PW"
MARANTZ_STANDBY_RESPONSE = "PWSTANDBY"


class MarantzAvReceiver(BaseAvReceiver, TcpCommandSender):
    receiver_name = "Marantz"
    uses_observed_input_recovery = True

    def power_on(self):
        logging.info('llamada a av_power_on')
        in_standby = self._is_in_standby()
        self.send_command("ZMON\n")
        if in_standby:
            logging.info(
                "Marantz was in standby — waiting for input to stabilize (ARC/CEC settle)"
            )
            wait_until_input_stable(
                self._get_current_input,
                receiver_name=self.receiver_name,
            )
        else:
            wait_until_receiver_responsive(
                self._get_current_input,
                receiver_name=self.receiver_name,
            )
        return "OK"

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
            max_retries=2,
        ).change_input()

    def restore_tv_audio(self):
        logging.info("Restoring Marantz to TV audio input (SITV)")
        return self.send_command("SITV\n")

    def power_off(self):
        logging.info('Llamada a av_power_off')
        return self.send_command("ZMOFF\n")

    def _is_in_standby(self):
        try:
            response = self.query_command(
                MARANTZ_POWER_QUERY_COMMAND,
                timeout=MARANTZ_POWER_QUERY_TIMEOUT_SECONDS,
                expected_prefix=MARANTZ_POWER_RESPONSE_PREFIX,
            )
            return MARANTZ_STANDBY_RESPONSE in (response or "")
        except OSError as exc:
            logging.warning(
                "Unable to query %s power state | error=%s — assuming standby",
                self.receiver_name,
                exc,
            )
            return True

    def _get_current_input(self):
        try:
            raw_response = self.query_command(
                MARANTZ_INPUT_QUERY_COMMAND,
                timeout=MARANTZ_INPUT_QUERY_TIMEOUT_SECONDS,
                expected_prefix=MARANTZ_INPUT_RESPONSE_PREFIX,
            )
        except OSError as exc:
            logging.warning(
                "Unable to query %s input | error=%s", self.receiver_name, exc
            )
            return None

        return extract_prefixed_response(raw_response, MARANTZ_INPUT_RESPONSE_PREFIX)
