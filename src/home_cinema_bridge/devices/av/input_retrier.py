import logging
import time

DEFAULT_INPUT_OBSERVATION_DELAYS_SECONDS = (0.0, 0.5, 1.0, 2.0, 3.0)
MIN_STABLE_INPUT_CONFIRMATION_SECONDS = 2.0

_POWER_ON_WAIT_TIMEOUT_SECONDS = 15
_POWER_ON_POLL_INTERVAL_SECONDS = 0.5

_INPUT_STABLE_COUNT = 3
_INPUT_STABLE_POLL_INTERVAL_SECONDS = 1.0
_INPUT_STABLE_TIMEOUT_SECONDS = 25


class AVInputRetrier:
    def __init__(
        self,
        *,
        receiver_name,
        input_command,
        send_input_command,
        get_current_input,
        redirected_input,
        observation_delays=DEFAULT_INPUT_OBSERVATION_DELAYS_SECONDS,
        max_retries=1,
        min_stable_seconds=MIN_STABLE_INPUT_CONFIRMATION_SECONDS,
    ):
        self.receiver_name = receiver_name
        self.input_command = input_command
        self.expected_input = input_command.strip()
        self.send_input_command = send_input_command
        self.get_current_input = get_current_input
        self.redirected_input = redirected_input
        self.observation_delays = observation_delays
        self.max_retries = max_retries
        self.min_stable_seconds = min_stable_seconds

    def change_input(self):
        result = self.send_input_command(self.input_command)
        retries = 0
        start_time = time.monotonic()

        for delay in self.observation_delays:
            remaining_time = start_time + delay - time.monotonic()

            if remaining_time > 0:
                time.sleep(remaining_time)

            observed_input = self.get_current_input()
            logging.info(
                "%s input observed | delay=%.1fs | expected_input=%s | observed_input=%s",
                self.receiver_name,
                delay,
                self.expected_input,
                observed_input,
            )

            if self._should_retry(observed_input, retries):
                logging.warning(
                    "%s input redirected to %s. Reapplying expected input immediately | expected_input=%s | observed_input=%s",
                    self.receiver_name,
                    self.redirected_input,
                    self.expected_input,
                    observed_input,
                )
                self.send_input_command(self.input_command)
                retries += 1

            if self._is_expected_input_stable(observed_input, delay):
                logging.info(
                    "%s expected input confirmed; stopping input observation | "
                    "expected_input=%s | observed_input=%s | delay=%.1fs",
                    self.receiver_name,
                    self.expected_input,
                    observed_input,
                    delay,
                )
                break

        return result

    def _should_retry(self, observed_input, retries):
        return (
            observed_input == self.redirected_input
            and self.expected_input != self.redirected_input
            and retries < self.max_retries
        )

    def _is_expected_input_stable(self, observed_input, delay):
        return (
            observed_input == self.expected_input
            and delay >= self.min_stable_seconds
        )


def wait_until_receiver_responsive(
    get_current_input,
    *,
    timeout=_POWER_ON_WAIT_TIMEOUT_SECONDS,
    poll_interval=_POWER_ON_POLL_INTERVAL_SECONDS,
    receiver_name="AV receiver",
):
    """Poll until the receiver responds to an input query, or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if get_current_input() is not None:
            logging.info("%s is responsive after power-on", receiver_name)
            return
        time.sleep(poll_interval)
    logging.warning(
        "%s did not respond within %ss after power-on",
        receiver_name,
        timeout,
    )


def wait_until_input_stable(
    get_current_input,
    *,
    stable_count=_INPUT_STABLE_COUNT,
    poll_interval=_INPUT_STABLE_POLL_INTERVAL_SECONDS,
    timeout=_INPUT_STABLE_TIMEOUT_SECONDS,
    receiver_name="AV receiver",
):
    """Poll SI? until the same input is returned N consecutive times.

    After a cold power-on, ARC/CEC may redirect the input to TV audio shortly
    after HDMI link is established. This waits until the ARC/CEC storm has
    passed and the input reading is stable before proceeding.
    """
    last_input = None
    consecutive = 0
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        current = get_current_input()

        if current is not None:
            if current == last_input:
                consecutive += 1
                logging.debug(
                    "%s input stable reading %d/%d | input=%s",
                    receiver_name,
                    consecutive,
                    stable_count,
                    current,
                )
                if consecutive >= stable_count:
                    logging.info(
                        "%s input stabilized at %s after cold start (%d consecutive readings)",
                        receiver_name,
                        current,
                        consecutive,
                    )
                    return current
            else:
                logging.info(
                    "%s input changed during cold start | was=%s | now=%s",
                    receiver_name,
                    last_input,
                    current,
                )
                consecutive = 1
                last_input = current

        time.sleep(poll_interval)

    logging.warning(
        "%s input did not stabilize within %ss after cold start",
        receiver_name,
        timeout,
    )
    return last_input


def extract_prefixed_response(raw_response, expected_prefix):
    if not raw_response:
        return None

    for line in raw_response.replace("\r", "\n").splitlines():
        normalized_line = line.strip()

        if normalized_line.startswith(expected_prefix):
            return normalized_line

    return None
