from .lg import LgTvController
from .scripts import ScriptsTvController


TV_CONTROLLERS = {
    "LG": LgTvController,
    "SCRIPTS": ScriptsTvController,
}


def normalize_tv_model(model):
    return str(model or "").upper()


def get_supported_tv_models():
    return sorted(TV_CONTROLLERS.keys())


def create_tv_controller(config):
    model = normalize_tv_model(config.get("TV_model"))
    controller_class = TV_CONTROLLERS.get(model)

    if controller_class is None:
        raise ValueError(f"Unsupported TV model: {model}")

    return controller_class(config)
