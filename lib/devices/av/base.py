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
