from home_cinema_bridge.devices.av.factory import create_av_receiver


def av_check_power(config):
    return create_av_receiver(config).power_on()


def get_hdmi_list(config):
    return create_av_receiver(config).get_hdmi_list()


def av_change_hdmi(config):
    return create_av_receiver(config).change_hdmi()


def av_power_off(config):
    return create_av_receiver(config).power_off()
