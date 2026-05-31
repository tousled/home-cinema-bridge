import unittest

from home_cinema_bridge.devices.av.input_retrier import (
    AVInputRetrier,
    extract_prefixed_response,
    wait_until_input_stable,
    wait_until_receiver_responsive,
)


class AVInputRetrierTest(unittest.TestCase):
    def test_sends_input_command_on_change(self):
        sent = []
        retrier = _retrier(
            send=lambda cmd: sent.append(cmd),
            observe=["SIMPLAY"],
        )

        retrier.change_input()

        self.assertIn("SIMPLAY\n", sent)

    def test_retries_once_when_redirected_to_sitv(self):
        sent = []
        retrier = _retrier(
            send=lambda cmd: sent.append(cmd),
            observe=["SITV", "SIMPLAY", "SIMPLAY", "SIMPLAY", "SIMPLAY"],
            max_retries=2,
        )

        retrier.change_input()

        self.assertEqual(2, sent.count("SIMPLAY\n"))

    def test_retries_twice_when_redirected_twice(self):
        sent = []
        retrier = _retrier(
            send=lambda cmd: sent.append(cmd),
            observe=["SITV", "SIMPLAY", "SITV", "SIMPLAY", "SIMPLAY"],
            max_retries=2,
        )

        retrier.change_input()

        self.assertEqual(3, sent.count("SIMPLAY\n"))

    def test_does_not_retry_beyond_max_retries(self):
        sent = []
        retrier = _retrier(
            send=lambda cmd: sent.append(cmd),
            observe=["SITV", "SITV", "SITV", "SITV", "SITV"],
            max_retries=1,
        )

        retrier.change_input()

        self.assertEqual(2, sent.count("SIMPLAY\n"))

    def test_retries_when_arc_redirects_after_initial_stable_observations(self):
        # Scenario: Denon cold start — SIMPLAY at 0s/1s/2s, ARC fires at 4s → SITV,
        # retry sends SIMPLAY, confirmed at 6s. This was broken with MIN_STABLE=2.0s.
        sent = []
        retrier = _retrier(
            send=lambda cmd: sent.append(cmd),
            observe=["SIMPLAY", "SIMPLAY", "SIMPLAY", "SITV", "SIMPLAY", "SIMPLAY"],
            max_retries=2,
            observation_delays=(0, 0, 0, 0, 0, 0),
            min_stable_seconds=4,
        )

        retrier.change_input()

        self.assertEqual(2, sent.count("SIMPLAY\n"))

    def test_does_not_retry_when_none_observed(self):
        sent = []
        retrier = _retrier(
            send=lambda cmd: sent.append(cmd),
            observe=[None, None, None, None, None],
            max_retries=2,
        )

        retrier.change_input()

        self.assertEqual(1, sent.count("SIMPLAY\n"))


class WaitUntilReceiverResponsiveTest(unittest.TestCase):
    def test_returns_immediately_when_receiver_already_responsive(self):
        calls = []

        def get_input():
            calls.append(1)
            return "SIMPLAY"

        wait_until_receiver_responsive(get_input, poll_interval=0.01)

        self.assertEqual(1, len(calls))

    def test_polls_until_receiver_responds(self):
        responses = [None, None, "SIMPLAY"]

        def get_input():
            return responses.pop(0)

        wait_until_receiver_responsive(get_input, poll_interval=0.01)

        self.assertEqual(0, len(responses))

    def test_returns_gracefully_on_timeout(self):
        def get_input():
            return None

        # Should not raise
        wait_until_receiver_responsive(get_input, timeout=0.05, poll_interval=0.01)


class ExtractPrefixedResponseTest(unittest.TestCase):
    def test_returns_matching_line(self):
        self.assertEqual("SIMPLAY", extract_prefixed_response("SIMPLAY\r", "SI"))

    def test_returns_first_matching_line_among_many(self):
        self.assertEqual("SIMPLAY", extract_prefixed_response("MV50\rSIMPLAY\rPWON\r", "SI"))

    def test_returns_none_when_no_matching_line(self):
        self.assertIsNone(extract_prefixed_response("CVEN\rMV50\rPWON\r", "SI"))

    def test_returns_none_for_denon_startup_burst_without_si_line(self):
        burst = "CVENDSSALSSET ONSSALSDSP OFFSSALSVAL 000MVMAX 98SDAUTOPSRSTR OFFDCAUTO"
        self.assertIsNone(extract_prefixed_response(burst, "SI"))

    def test_returns_none_for_empty_response(self):
        self.assertIsNone(extract_prefixed_response("", "SI"))
        self.assertIsNone(extract_prefixed_response(None, "SI"))


class WaitUntilInputStableTest(unittest.TestCase):
    def test_returns_when_input_is_stable_n_consecutive_times(self):
        responses = ["SIMPLAY", "SIMPLAY", "SIMPLAY"]

        result = wait_until_input_stable(
            lambda: responses.pop(0) if responses else "SIMPLAY",
            stable_count=3,
            poll_interval=0.01,
        )

        self.assertEqual("SIMPLAY", result)

    def test_waits_for_arc_redirect_to_settle_before_returning(self):
        # Sequence: SIMPLAY → SITV (ARC fires) → SITV → SITV (stable)
        responses = ["SIMPLAY", "SITV", "SITV", "SITV"]

        result = wait_until_input_stable(
            lambda: responses.pop(0) if responses else "SITV",
            stable_count=3,
            poll_interval=0.01,
        )

        self.assertEqual("SITV", result)

    def test_returns_last_known_input_on_timeout(self):
        result = wait_until_input_stable(
            lambda: "SIMPLAY",
            stable_count=10,
            poll_interval=0.01,
            timeout=0.05,
        )

        self.assertEqual("SIMPLAY", result)

    def test_handles_none_responses_during_boot(self):
        responses = [None, None, "SIMPLAY", "SIMPLAY", "SIMPLAY"]

        result = wait_until_input_stable(
            lambda: responses.pop(0) if responses else "SIMPLAY",
            stable_count=3,
            poll_interval=0.01,
        )

        self.assertEqual("SIMPLAY", result)


class WaitUntilReceiverResponsiveWithColdStartTest(unittest.TestCase):
    def test_waits_until_clean_si_response_not_garbled_burst(self):
        responses = [
            "CVENDSSALSSET ON",  # startup burst — no SI line → None after fix
            None,                # TCP timeout during boot
            "SIMPLAY",           # clean SI response → ready
        ]
        calls = []

        def get_input():
            calls.append(1)
            r = responses.pop(0) if responses else "SIMPLAY"
            # Simulate extract_prefixed_response behaviour after fix:
            # burst and None both return None, clean "SIMPLAY" returns "SIMPLAY"
            if r and r.startswith("SI"):
                return r
            return None

        wait_until_receiver_responsive(get_input, poll_interval=0.01)

        self.assertEqual(3, len(calls))


def _retrier(*, send, observe, max_retries=1, observation_delays=(0, 0, 0, 0, 0), min_stable_seconds=999):
    observations = list(observe)

    def get_current_input():
        return observations.pop(0) if observations else None

    return AVInputRetrier(
        receiver_name="TestReceiver",
        input_command="SIMPLAY\n",
        send_input_command=send,
        get_current_input=get_current_input,
        redirected_input="SITV",
        observation_delays=observation_delays,
        max_retries=max_retries,
        min_stable_seconds=min_stable_seconds,
    )


if __name__ == "__main__":
    unittest.main()
