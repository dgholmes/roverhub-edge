from datetime import datetime, timezone

import pytest

from telemetry_reader import TelemetryReader
from shared.schemas.telemetry import TelemetrySnapshot


class _StubAdapter:
    def __init__(self, snapshots):
        self._snapshots = list(snapshots)

    async def get_telemetry_snapshot(self):
        item = self._snapshots.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _snapshot(captured_at="2026-07-20T00:00:00Z"):
    return TelemetrySnapshot(
        current_state="stand_down", current_speed_ratio=0,
        obstacle_avoidance_enabled=True, robot_type="quad",
        pos_body=(0.0, 0.0, 0.0), vel_body=(0.0, 0.0, 0.0),
        battery_percent=80.0, captured_at=captured_at,
    )


@pytest.mark.asyncio
async def test_first_successful_poll_is_live(make_config):
    frames = []
    adapter = _StubAdapter([_snapshot()])
    clock_ticks = iter([datetime(2026, 7, 20, 0, 0, 0, tzinfo=timezone.utc)])
    reader = TelemetryReader(adapter, make_config(), frames.append, clock=lambda: next(clock_ticks))

    await reader.poll_once()

    assert len(frames) == 1
    assert frames[0].grpc_freshness == "live"


@pytest.mark.asyncio
async def test_failed_poll_after_success_reports_stale_once_past_threshold(make_config):
    frames = []
    adapter = _StubAdapter([_snapshot(), RuntimeError("gRPC timeout")])
    clock_ticks = iter([
        datetime(2026, 7, 20, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 7, 20, 0, 0, 5, tzinfo=timezone.utc),
    ])
    reader = TelemetryReader(
        adapter, make_config(stale_telemetry_threshold_s=3.0), frames.append,
        clock=lambda: next(clock_ticks),
    )

    await reader.poll_once()
    await reader.poll_once()

    assert len(frames) == 2
    assert frames[1].grpc_freshness == "stale"
    assert frames[1].pos_body == (0.0, 0.0, 0.0)


@pytest.mark.asyncio
async def test_no_frame_emitted_before_first_successful_poll(make_config):
    frames = []
    adapter = _StubAdapter([RuntimeError("never connected")])
    reader = TelemetryReader(
        adapter, make_config(), frames.append,
        clock=lambda: datetime.now(timezone.utc),
    )

    await reader.poll_once()

    assert frames == []
