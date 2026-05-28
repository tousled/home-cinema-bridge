import asyncio

from lib.devices.tv.factory import create_tv_controller


def _run(coroutine):
    return asyncio.run(coroutine)


def tv_test_conn(config):
    return _run(create_tv_controller(config).test_connection()).value


def get_tv_sources(config):
    return _run(create_tv_controller(config).retrieve_hdmi_inputs()).value


def tv_change_hdmi(config):
    return _run(create_tv_controller(config).switch_to_hdmi_input()).value


def tv_set_prev(config):
    return _run(create_tv_controller(config).return_to_previous_app()).value


def tv_get_current_app(config):
    return _run(create_tv_controller(config).get_current_app())
