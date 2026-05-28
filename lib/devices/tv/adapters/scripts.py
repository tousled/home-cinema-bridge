import logging
import subprocess

from lib.devices.tv.base import BaseTvController, TvStatus


class ScriptsTvController(BaseTvController):
    async def test_connection(self) -> TvStatus:
        return TvStatus.OK

    async def retrieve_hdmi_inputs(self) -> TvStatus:
        self.config["TV_SOURCES"] = []
        return TvStatus.OK

    async def switch_to_hdmi_input(self) -> TvStatus:
        logging.info("Running TV init script")

        try:
            subprocess.Popen(self.config["TV_script_init"])
            return TvStatus.OK
        except OSError as exc:
            logging.warning("Unable to run TV init script: %s", exc)
            return TvStatus.FAILURE

    async def return_to_previous_app(self) -> TvStatus:
        logging.info("Running TV end script")

        try:
            subprocess.Popen(self.config["TV_script_end"])
            return TvStatus.OK
        except OSError as exc:
            logging.warning("Unable to run TV end script: %s", exc)
            return TvStatus.FAILURE

    async def get_current_app(self) -> str | None:
        logging.info("TV current app is not available for script-based TV control")
        return None
