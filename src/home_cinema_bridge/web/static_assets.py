import json


def load_json_asset(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def read_text_asset(path):
    with open(path, "r", encoding="utf8") as file:
        return file.read()


def read_binary_asset(path):
    with open(path, "rb") as file:
        return file.read()
