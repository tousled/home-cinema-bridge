import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlaybackStartupStepTiming:
    name: str
    elapsed_seconds: float


@dataclass
class PlaybackStartupTimer:
    """
    Measures the startup path from the Emby playback request until the OPPO
    has started playback and the external devices have been prepared.

    This is intentionally lightweight: it only logs timings and does not change
    playback behaviour.
    """

    _started_at: float = field(default_factory=time.perf_counter)
    _steps: list[PlaybackStartupStepTiming] = field(default_factory=list)

    @contextmanager
    def measure_step(self, step_name: str) -> Iterator[None]:
        step_started_at = time.perf_counter()

        try:
            yield
        finally:
            elapsed_seconds = time.perf_counter() - step_started_at
            self._steps.append(
                PlaybackStartupStepTiming(
                    name=step_name,
                    elapsed_seconds=elapsed_seconds,
                )
            )

            logging.info(
                "Playback startup timing | step=%s | elapsed=%.3fs",
                step_name,
                elapsed_seconds,
            )

    def log_summary(self) -> None:
        total_elapsed_seconds = time.perf_counter() - self._started_at
        step_summary = " | ".join(
            f"{step.name}={step.elapsed_seconds:.3f}s"
            for step in self._steps
        )

        logging.info(
            "Playback startup timing summary | total=%.3fs | %s",
            total_elapsed_seconds,
            step_summary,
        )
