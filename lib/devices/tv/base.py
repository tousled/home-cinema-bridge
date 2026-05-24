import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from enum import StrEnum


class TvStatus(StrEnum):
    OK = "OK"
    FAILURE = "FAILURE"


TvOperation = Callable[[], Awaitable[TvStatus]]


class BaseTvController(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def test_connection(self) -> TvStatus:
        pass

    @abstractmethod
    async def refresh_inputs(self) -> TvStatus:
        pass

    @abstractmethod
    async def switch_to_player_input(self) -> TvStatus:
        pass

    @abstractmethod
    async def return_to_previous_app(self) -> TvStatus:
        pass

    async def _execute_tv_operation(
        self,
        operation_name: str,
        operation: TvOperation,
    ) -> TvStatus:
        try:
            return await operation()

        except ValueError as exc:
            logging.error("TV configuration error while %s: %s", operation_name, exc)
            return TvStatus.FAILURE

        except TimeoutError as exc:
            logging.warning("TV timeout while %s: %s", operation_name, exc)
            return TvStatus.FAILURE

        except OSError as exc:
            logging.warning("TV network error while %s: %s", operation_name, exc)
            return TvStatus.FAILURE

        except Exception:
            # Integration boundary: avoid crashing the backend because of an unexpected TV/library error.
            logging.exception("Unexpected TV error while %s", operation_name)
            return TvStatus.FAILURE