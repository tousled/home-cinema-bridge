import logging

from home_cinema_bridge.devices.av.base import BaseAvReceiver
from home_cinema_bridge.network.http import get_http_session


class YamahaAvReceiver(BaseAvReceiver):
    def get_hdmi_list(self):
        return [
            {"Id": 1, "Name": "HDMI1", "Param": "HDMI1"},
            {"Id": 2, "Name": "HDMI2", "Param": "HDMI2"},
            {"Id": 3, "Name": "HDMI3", "Param": "HDMI3"},
            {"Id": 4, "Name": "HDMI4", "Param": "HDMI4"},
            {"Id": 5, "Name": "HDMI5", "Param": "HDMI5"},
            {"Id": 6, "Name": "HDMI6", "Param": "HDMI6"},
            {"Id": 7, "Name": "HDMI7", "Param": "HDMI7"},
            {"Id": 8, "Name": "HDMI8", "Param": "HDMI8"},
            {"Id": 9, "Name": "HDMI9", "Param": "HDMI9"},
        ]

    def _post(self, message_data):
        url = 'http://' + self.config["AV_Ip"] + '/YamahaRemoteControl/ctrl'
        get_http_session("yamaha-av").post(url, data=message_data, headers="")
        return "OK"

    def power_on(self):
        logging.info('Llamada a av_power_on')
        result = self._post(
            '<YAMAHA_AV cmd="PUT"><System><Power_Control><Power>On</Power></Power_Control></System></YAMAHA_AV>'
        )
        self._wait_after_power_on()
        return result

    def change_hdmi(self):
        logging.info('Llamada a av_change_hdmi')
        return self._post(
            '<Main_Zone><Input><Input_Sel>' + self.config["AV_Input"] + '</Input_Sel></Input></Main_Zone>'
        )

    def restore_tv_audio(self):
        tv_input = self.config.get("AV_TV_Input")
        if tv_input:
            logging.info("Restoring Yamaha to TV audio input | input=%s", tv_input)
            return self._post(
                f'<Main_Zone><Input><Input_Sel>{tv_input}</Input_Sel></Input></Main_Zone>'
            )
        super().restore_tv_audio()

    def power_off(self):
        logging.info('Llamada a av_power_off')
        return self._post(
            '<YAMAHA_AV cmd="PUT"><System><Power_Control><Power>Standby</Power></Power_Control></System></YAMAHA_AV>'
        )
