import unittest

from lib.oppo.playback_state import (
    OppoPlaybackCategory,
    classify_oppo_status,
    normalize_oppo_status,
)


class OppoPlaybackStateTest(unittest.TestCase):
    def test_normalizes_raw_ok_response(self):
        self.assertEqual("PLAY", normalize_oppo_status("@OK PLAY"))
        self.assertEqual("DISC_MENU", normalize_oppo_status("@OK DISC MENU"))
        self.assertEqual("SCREEN_SAVER", normalize_oppo_status("@OK SCREEN SAVER"))

    def test_empty_status_is_unknown(self):
        self.assertEqual("UNKNOWN", normalize_oppo_status(""))
        self.assertEqual("UNKNOWN", normalize_oppo_status("@OK"))

    def test_active_states(self):
        for status in [
            "PLAY",
            "PAUSE",
            "DISC_MENU",
            "FFWD",
            "FREV",
            "SFWD",
            "SREV",
            "STEP",
        ]:
            with self.subTest(status=status):
                self.assertEqual(OppoPlaybackCategory.ACTIVE, classify_oppo_status(status))

    def test_idle_states(self):
        for status in [
            "HOME_MENU",
            "SCREEN_SAVER",
            "MEDIA_CENTER",
            "NO_DISC",
        ]:
            with self.subTest(status=status):
                self.assertEqual(OppoPlaybackCategory.IDLE, classify_oppo_status(status))

    def test_transition_states(self):
        for status in [
            "STOP",
            "OPEN",
            "CLOSE",
            "LOADING",
        ]:
            with self.subTest(status=status):
                self.assertEqual(OppoPlaybackCategory.TRANSITION, classify_oppo_status(status))

    def test_unknown_state(self):
        self.assertEqual(OppoPlaybackCategory.UNKNOWN, classify_oppo_status("SOMETHING_ELSE"))


if __name__ == "__main__":
    unittest.main()
