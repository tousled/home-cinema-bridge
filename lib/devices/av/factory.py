from .denon import DenonAvReceiver
from .marantz import MarantzAvReceiver
from .nad import NadAvReceiver
from .onkyo import OnkyoAvReceiver
from .scripts import ScriptsAvReceiver
from .yamaha import YamahaAvReceiver


AV_RECEIVERS = {
    "DENON": DenonAvReceiver,
    "MARANTZ": MarantzAvReceiver,
    "NAD": NadAvReceiver,
    "ONKYO": OnkyoAvReceiver,
    "SCRIPTS": ScriptsAvReceiver,
    "YAMAHA": YamahaAvReceiver,
}


def normalize_av_model(model):
    return str(model or "").upper()


def get_supported_av_models():
    return sorted(AV_RECEIVERS.keys())


def is_supported_av_model(model):
    return normalize_av_model(model) in AV_RECEIVERS


def create_av_receiver(config):
    model = normalize_av_model(config.get("AV_model"))
    receiver_class = AV_RECEIVERS.get(model)

    if receiver_class is None:
        raise ValueError(f"Unsupported AV model: {model}")

    return receiver_class(config)