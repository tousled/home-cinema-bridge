import unittest

from lib.devices.oppo.control_api_activation import OppoControlApiActivator


class RecordingTcpClient:
    def __init__(self, failures_before_success=None):
        self.calls = []
        self.failures_before_success = failures_before_success

    def check_connection(self, **kwargs):
        self.calls.append(kwargs)
        if self.failures_before_success is None:
            raise TimeoutError("timed out")

        if len(self.calls) <= self.failures_before_success:
            raise ConnectionRefusedError("connection refused")

        return True


class OppoControlApiActivatorTest(unittest.TestCase):
    def test_from_config_uses_short_connect_timeout_independent_from_attempts(self):
        activator = OppoControlApiActivator.from_config(
            {
                "Oppo_IP": "192.168.50.35",
                "timeout_oppo_conection": 10,
            }
        )

        self.assertEqual(1.0, activator.timeout_seconds)

    def test_from_config_allows_explicit_connect_timeout(self):
        activator = OppoControlApiActivator.from_config(
            {
                "Oppo_IP": "192.168.50.35",
                "timeout_oppo_conection": 10,
                "oppo_control_api_connect_timeout": 0.25,
            }
        )

        self.assertEqual(0.25, activator.timeout_seconds)

    def test_availability_probe_does_not_request_stacktrace_logging(self):
        tcp = RecordingTcpClient()
        activator = OppoControlApiActivator(
            "192.168.50.35",
            timeout_seconds=0.25,
            tcp_client=tcp,
        )

        result = activator.check_control_api_availability()

        self.assertFalse(result.available)
        self.assertEqual(False, tcp.calls[0]["log_failure_stack"])
        self.assertEqual(0.25, tcp.calls[0]["timeout"])

    def test_ensure_stops_when_control_api_becomes_available(self):
        tcp = RecordingTcpClient(failures_before_success=2)
        sleeps = []
        activator = OppoControlApiActivator(
            "192.168.50.35",
            timeout_seconds=0.25,
            tcp_client=tcp,
            sleep=sleeps.append,
            remote_login_sender=lambda: None,
        )

        result = activator.ensure_control_api_available(max_attempts=5)

        self.assertTrue(result.available)
        self.assertEqual(3, result.attempts)
        self.assertEqual([1, 1], sleeps)


if __name__ == "__main__":
    unittest.main()
