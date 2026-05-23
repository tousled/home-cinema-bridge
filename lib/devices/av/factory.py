from .denon import DenonAvReceiver
from .marantz import MarantzAvReceiver
from .nad import NadAvReceiver


MIGRATED_AV_MODELS = {"DENON", "MARANTZ", "NAD"}


def is_migrated_av_model(model):
    return str(model or "").upper() in MIGRATED_AV_MODELS


def create_av_receiver(config):
    model = str(config.get("AV_model", "")).upper()

    if model == "DENON":
        return DenonAvReceiver(config)

    if model == "MARANTZ":
        return MarantzAvReceiver(config)

    if model == "NAD":
        return NadAvReceiver(config)

    raise ValueError(f"Unsupported migrated AV model: {model}")