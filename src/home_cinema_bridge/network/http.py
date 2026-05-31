from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import requests

logger = logging.getLogger(__name__)

_REDACTED = "***"
_SENSITIVE_KEYS = {
    "authorization",
    "password",
    "pw",
    "token",
    "x-emby-authorization",
    "x-mediabrowser-token",
}
_MAX_ERROR_BODY_LENGTH = 4000


class LoggingHttpSession:
    """Small requests-compatible HTTP wrapper with centralized diagnostics."""

    def __init__(self, *, name: str, session=requests) -> None:
        self._name = name
        self._session = session

    def get(self, url: str, **kwargs: Any):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any):
        return self.request("POST", url, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any):
        method = method.upper()
        safe_kwargs = _safe_request_kwargs(kwargs)

        logger.debug(
            "HTTP request | client=%s | method=%s | url=%s",
            self._name,
            method,
            url,
        )

        try:
            response = self._session.request(method, url, **kwargs)
        except requests.RequestException:
            logger.exception(
                "HTTP request raised exception | client=%s | method=%s | url=%s | kwargs=%s",
                self._name,
                method,
                url,
                safe_kwargs,
            )
            raise

        status_code = getattr(response, "status_code", None)
        if status_code is not None and status_code >= 400:
            logger.warning(
                "HTTP response failed | client=%s | method=%s | url=%s | "
                "status=%s | request=%s | body=%s",
                self._name,
                method,
                url,
                status_code,
                safe_kwargs,
                _truncate(getattr(response, "text", "")),
            )
            return response

        logger.debug(
            "HTTP response | client=%s | method=%s | url=%s | status=%s | body=%s",
            self._name,
            method,
            url,
            status_code,
            _success_body_summary(response),
        )
        return response


def _success_body_summary(response) -> str:
    text = getattr(response, "text", "")
    if not text:
        return ""
    return f"<{len(text)} chars>"


def _truncate(value: str) -> str:
    if len(value) <= _MAX_ERROR_BODY_LENGTH:
        return value
    return value[:_MAX_ERROR_BODY_LENGTH] + "...<truncated>"


def get_http_session(name: str):
    return LoggingHttpSession(name=name)


def _safe_request_kwargs(kwargs: Mapping[str, Any]) -> dict[str, Any]:
    safe = dict(kwargs)
    if "headers" in safe:
        safe["headers"] = _redact_mapping(safe["headers"])
    if "data" in safe:
        safe["data"] = _redact_value(safe["data"])
    if "json" in safe:
        safe["json"] = _redact_value(safe["json"])
    return safe


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _redact_mapping(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    redacted = {}
    for key, item in value.items():
        if str(key).lower() in _SENSITIVE_KEYS:
            redacted[key] = _REDACTED
        else:
            redacted[key] = _redact_value(item)
    return redacted
