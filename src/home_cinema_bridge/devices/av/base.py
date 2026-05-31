import logging
import time
from abc import ABC, abstractmethod


class BaseAvReceiver(ABC):
    uses_observed_input_recovery = False

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def get_hdmi_list(self):
        pass

    @abstractmethod
    def power_on(self):
        pass

    @abstractmethod
    def change_hdmi(self):
        pass

    @abstractmethod
    def power_off(self):
        pass

    def restore_tv_audio(self):
        """Switch back to the TV audio input after OPPO playback ends.

        Denon and Marantz override this with a hardcoded SITV command.
        Other adapters use AV_TV_Input from config if set.
        """
        tv_input = self.config.get("AV_TV_Input")
        if tv_input:
            logging.info(
                "Restoring AV receiver to TV audio input | input=%s",
                tv_input.strip(),
            )
        else:
            logging.debug(
                "AV_TV_Input not configured for this adapter; skipping TV audio restore"
            )

    def _wait_after_power_on(self):
        """Fallback delay for receivers that cannot query their own state.

        Uses the av_delay_hdmi config value (set in the web UI). Receivers
        that implement query-based readiness detection (e.g. Denon, Marantz)
        should override power_on() instead of relying on this.
        """
        delay = float(self.config.get("av_delay_hdmi", 0))
        if delay > 0:
            logging.info(
                "Waiting %.1fs for AV receiver after power-on (av_delay_hdmi)",
                delay,
            )
            time.sleep(delay)
