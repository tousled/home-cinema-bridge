from home_cinema_bridge.web.version_update import (
    check_application_version,
    trigger_configured_update,
)


def check_version_response(config, current_version):
    return check_application_version(config, current_version).as_legacy_response()


def update_version_response(config, current_version):
    return trigger_configured_update(config, current_version)
