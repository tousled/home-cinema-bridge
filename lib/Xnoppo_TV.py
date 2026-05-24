import asyncio

from lib.devices.tv.factory import create_tv_controller


def _run(coroutine):
    result = asyncio.run(coroutine)
    return result.value


def tv_test_conn(config):
    return _run(create_tv_controller(config).test_connection())


def get_tv_sources(config):
    return _run(create_tv_controller(config).refresh_inputs())


def tv_change_hdmi(config):
    return _run(create_tv_controller(config).switch_to_player_input())


def tv_set_prev(config):
    return _run(create_tv_controller(config).return_to_previous_app())
