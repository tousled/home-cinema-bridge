import logging
import time

DEFAULT_INPUT_OBSERVATION_DELAYS_SECONDS = (0.0, 0.5, 1.0, 2.0, 3.0)


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
    ):
        self.receiver_name = receiver_name
        self.input_command = input_command
        self.expected_input = input_command.strip()
        self.send_input_command = send_input_command
        self.get_current_input = get_current_input
        self.redirected_input = redirected_input
        self.observation_delays = observation_delays
        self.max_retries = max_retries

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

        return result

    def _should_retry(self, observed_input, retries):
        return (
            observed_input == self.redirected_input
            and self.expected_input != self.redirected_input
            and retries < self.max_retries
        )


def extract_prefixed_response(raw_response, expected_prefix):
    if not raw_response:
        return None

    for line in raw_response.replace("\r", "\n").splitlines():
        normalized_line = line.strip()

        if normalized_line.startswith(expected_prefix):
            return normalized_line

    return raw_response.strip()
