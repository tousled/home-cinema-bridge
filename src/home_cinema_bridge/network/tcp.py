from __future__ import annotations

import logging
import socket
import time
from collections.abc import Callable
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class LoggingTcpClient:
    """Centralized TCP request/response logging for device command protocols."""

    def __init__(self, *, name: str) -> None:
        self._name = name

    def send_only(self, *, host: str, port: int, payload: bytes, timeout: float) -> None:
        logger.debug(
            "TCP send | client=%s | host=%s | port=%s | timeout=%s | payload=%r",
            self._name,
            host,
            port,
            timeout,
            payload,
        )
        try:
            with socket.create_connection((host, port), timeout=timeout) as session:
                session.sendall(payload)
        except OSError:
            logger.exception(
                "TCP send failed | client=%s | host=%s | port=%s | timeout=%s | payload=%r",
                self._name,
                host,
                port,
                timeout,
                payload,
            )
            raise

    def check_connection(
        self,
        *,
        host: str,
        port: int,
        timeout: float,
        log_failure_stack: bool = True,
    ) -> bool:
        logger.debug(
            "TCP connect | client=%s | host=%s | port=%s | timeout=%s",
            self._name,
            host,
            port,
            timeout,
        )
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError as exc:
            if log_failure_stack:
                logger.exception(
                    "TCP connect failed | client=%s | host=%s | port=%s | timeout=%s",
                    self._name,
                    host,
                    port,
                    timeout,
                )
            else:
                logger.debug(
                    "TCP connect unavailable | client=%s | host=%s | port=%s | timeout=%s | error=%s: %s",
                    self._name,
                    host,
                    port,
                    timeout,
                    type(exc).__name__,
                    exc,
                )
            raise

    @contextmanager
    def connect(self, *, host: str, port: int, timeout: float):
        logger.debug(
            "TCP connect | client=%s | host=%s | port=%s | timeout=%s",
            self._name,
            host,
            port,
            timeout,
        )
        try:
            with socket.create_connection((host, port), timeout=timeout) as session:
                yield session
        except OSError:
            logger.exception(
                "TCP connection failed | client=%s | host=%s | port=%s | timeout=%s",
                self._name,
                host,
                port,
                timeout,
            )
            raise

    def request(
        self,
        *,
        host: str,
        port: int,
        payload: bytes,
        timeout: float,
        encoding: str = "ascii",
        complete: Callable[[str], bool] | None = None,
    ) -> str:
        logger.debug(
            "TCP request | client=%s | host=%s | port=%s | timeout=%s | payload=%r",
            self._name,
            host,
            port,
            timeout,
            payload,
        )
        try:
            with socket.create_connection((host, port), timeout=timeout) as session:
                deadline = time.monotonic() + timeout
                response_chunks: list[bytes] = []
                session.sendall(payload)

                while time.monotonic() < deadline:
                    remaining_time = deadline - time.monotonic()
                    session.settimeout(min(0.2, remaining_time))

                    try:
                        chunk = session.recv(4096)
                    except TimeoutError:
                        continue
                    except socket.timeout:
                        continue

                    if not chunk:
                        break

                    response_chunks.append(chunk)
                    decoded = b"".join(response_chunks).decode(
                        encoding,
                        errors="replace",
                    )
                    if complete and complete(decoded):
                        break
        except OSError:
            logger.exception(
                "TCP request failed | client=%s | host=%s | port=%s | timeout=%s | payload=%r",
                self._name,
                host,
                port,
                timeout,
                payload,
            )
            raise

        response = b"".join(response_chunks).decode(encoding, errors="replace").strip()
        response_log = logger.debug
        if not response or (complete is not None and not complete(response)):
            response_log = logger.warning

        response_log(
            "TCP response | client=%s | host=%s | port=%s | payload=%r | response=%r",
            self._name,
            host,
            port,
            payload,
            response,
        )
        return response
