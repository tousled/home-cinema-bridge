import unittest

from home_cinema_bridge.playback.startup.completion import (
    OppoStartupCompletionPlayer,
    PlayMediaItemRequest,
    PlaybackStartupCompletionService,
)
from home_cinema_bridge.playback.startup.models import DeviceCommandResult


class RecordingStartedReporter:
    def __init__(self):
        self.calls = 0

    def started(self):
        self.calls += 1
        return "started"


class RecordingPlayer:
    def __init__(self):
        self.seeks = []
        self.audio_tracks = []
        self.subtitle_tracks = []

    def seek_to_seconds(self, position_seconds):
        self.seeks.append(position_seconds)
        return DeviceCommandResult.success()

    def select_audio_track(self, audio_track_id):
        self.audio_tracks.append(audio_track_id)
        return DeviceCommandResult.success()

    def select_subtitle_track(self, subtitle_track_id):
        self.subtitle_tracks.append(subtitle_track_id)
        return DeviceCommandResult.success()


class RecordingTrackResolver:
    def __init__(self, *, audio_track=2, subtitle_track=4):
        self.audio_track = audio_track
        self.subtitle_track = subtitle_track
        self.audio_requests = []
        self.subtitle_requests = []

    def resolve_audio_track(
        self,
        *,
        source_user_id,
        media_item_id,
        selected_source_track_id,
    ):
        self.audio_requests.append(
            (source_user_id, media_item_id, selected_source_track_id)
        )
        return self.audio_track

    def resolve_subtitle_track(
        self,
        *,
        source_user_id,
        media_item_id,
        selected_source_track_id,
    ):
        self.subtitle_requests.append(
            (source_user_id, media_item_id, selected_source_track_id)
        )
        return self.subtitle_track


class FailingTrackResolver(RecordingTrackResolver):
    def resolve_audio_track(self, **kwargs):
        raise RuntimeError("audio unavailable")


class RecordingStartupOrchestrator:
    def __init__(self):
        self.seek_positions = []

    def seek_oppo_to(self, position_units):
        self.seek_positions.append(position_units)
        return DeviceCommandResult.success()

    def select_oppo_audio_track(self, audio_index):
        return DeviceCommandResult.success()

    def select_oppo_subtitle_track(self, subtitle_index):
        return DeviceCommandResult.success()


class PlaybackStartupCompletionTest(unittest.TestCase):
    def test_completion_reports_started_and_applies_seek_audio_and_subtitle(self):
        reporter = RecordingStartedReporter()
        player = RecordingPlayer()
        resolver = RecordingTrackResolver(audio_track=3, subtitle_track=5)
        service = PlaybackStartupCompletionService(
            started_reporter=reporter,
            player=player,
            track_resolver=resolver,
        )

        result = service.complete(
            PlayMediaItemRequest(
                start_position_seconds=759,
                source_user_id="user-1",
                media_item_id="movie-1",
                selected_source_audio_track_id=1,
                selected_source_subtitle_track_id=7,
            )
        )

        self.assertEqual(1, reporter.calls)
        self.assertEqual([759], player.seeks)
        self.assertEqual([3], player.audio_tracks)
        self.assertEqual([5], player.subtitle_tracks)
        self.assertEqual(759, result.start_position_seconds)
        self.assertTrue(result.seek_result.successful)
        self.assertEqual([("user-1", "movie-1", 1)], resolver.audio_requests)
        self.assertEqual([("user-1", "movie-1", 7)], resolver.subtitle_requests)

    def test_disabled_subtitles_are_not_resolved_or_selected(self):
        reporter = RecordingStartedReporter()
        player = RecordingPlayer()
        resolver = RecordingTrackResolver()
        service = PlaybackStartupCompletionService(
            started_reporter=reporter,
            player=player,
            track_resolver=resolver,
        )

        result = service.complete(
            PlayMediaItemRequest(
                start_position_seconds=0,
                source_user_id="user-1",
                media_item_id="movie-1",
                selected_source_audio_track_id=None,
                selected_source_subtitle_track_id=-1,
            )
        )

        self.assertEqual([0], player.seeks)
        self.assertEqual([], player.audio_tracks)
        self.assertEqual([], player.subtitle_tracks)
        self.assertEqual([], resolver.subtitle_requests)
        self.assertEqual("skipped", result.subtitle_result.status.value)

    def test_audio_resolution_failure_is_reported_without_stopping_completion(self):
        reporter = RecordingStartedReporter()
        player = RecordingPlayer()
        service = PlaybackStartupCompletionService(
            started_reporter=reporter,
            player=player,
            track_resolver=FailingTrackResolver(subtitle_track=6),
        )

        with self.assertLogs(
            "home_cinema_bridge.playback.startup.completion",
            level="ERROR",
        ):
            result = service.complete(
                PlayMediaItemRequest(
                    start_position_seconds=12,
                    source_user_id="user-1",
                    media_item_id="movie-1",
                    selected_source_audio_track_id=1,
                    selected_source_subtitle_track_id=2,
                )
            )

        self.assertFalse(result.audio_result.successful)
        self.assertEqual([12], player.seeks)
        self.assertEqual([6], player.subtitle_tracks)

    def test_oppo_adapter_converts_seconds_to_player_seek_units(self):
        startup_orchestrator = RecordingStartupOrchestrator()
        player = OppoStartupCompletionPlayer(startup_orchestrator)

        player.seek_to_seconds(66)

        self.assertEqual([660_000_000], startup_orchestrator.seek_positions)


if __name__ == "__main__":
    unittest.main()
