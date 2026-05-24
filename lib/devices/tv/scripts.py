import logging
import subprocess

from .base import BaseTvController, TvStatus


class ScriptsTvController(BaseTvController):
    async def test_connection(self) -> TvStatus:
        return TvStatus.OK

    async def refresh_inputs(self) -> TvStatus:
        self.config["TV_SOURCES"] = []
        return TvStatus.OK

    async def switch_to_player_input(self) -> TvStatus:
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
