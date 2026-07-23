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


def _snapshot(captured_at="2026-07-20T00:00:00Z", current_state="stand_down"):
    return TelemetrySnapshot(
        current_state=current_state, current_speed_ratio=0,
        obstacle_avoidance_enabled=True, robot_type="quad",
        pos_body=(0.0, 0.0, 0.0), vel_body=(0.0, 0.0, 0.0),
        acc_body=(0.0, 0.0, 0.0), omega_body=(0.0, 0.0, 0.0), ori_body=(0.0, 0.0, 0.0),
        jpos_leg=[0.0] * 12, jvel_leg=[0.0] * 12, jtau_leg=[0.0] * 12,
        grf_left=(0.0, 0.0, 0.0), grf_right=(0.0, 0.0, 0.0),
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


@pytest.mark.asyncio
async def test_on_state_change_fires_when_abstract_state_changes(make_config):
    state_changes = []

    async def on_frame(frame):
        pass

    async def on_state_change(sdk_state, abstract_state):
        state_changes.append((sdk_state, abstract_state))

    adapter = _StubAdapter([
        _snapshot(current_state="stand_down"),
        _snapshot(current_state="balance_stand"),
    ])
    clock_ticks = iter([
        datetime(2026, 7, 20, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 7, 20, 0, 0, 1, tzinfo=timezone.utc),
    ])
    reader = TelemetryReader(
        adapter, make_config(), on_frame,
        clock=lambda: next(clock_ticks),
        on_state_change=on_state_change,
    )

    await reader.poll_once()
    await reader.poll_once()

    assert state_changes == [("stand_down", "PASSIVE"), ("balance_stand", "STAND")]


@pytest.mark.asyncio
async def test_on_state_change_does_not_fire_when_state_is_unchanged(make_config):
    state_changes = []

    async def on_frame(frame):
        pass

    async def on_state_change(sdk_state, abstract_state):
        state_changes.append((sdk_state, abstract_state))

    adapter = _StubAdapter([_snapshot(), _snapshot()])
    clock_ticks = iter([
        datetime(2026, 7, 20, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 7, 20, 0, 0, 1, tzinfo=timezone.utc),
    ])
    reader = TelemetryReader(
        adapter, make_config(), on_frame,
        clock=lambda: next(clock_ticks),
        on_state_change=on_state_change,
    )

    await reader.poll_once()
    await reader.poll_once()

    assert len(state_changes) == 1


@pytest.mark.asyncio
async def test_poll_once_propagates_full_body_and_joint_telemetry(make_config):
    """Regression test: pos_body/vel_body were the only fields telemetry_reader
    copied from the snapshot into the published frame, even after get_state()
    started returning acc_body/omega_body/ori_body/jpos_leg/jvel_leg/jtau_leg/
    grf_left/grf_right -- those fields were silently dropped at this hop."""
    frames = []
    snapshot = TelemetrySnapshot(
        current_state="walk", current_speed_ratio=50,
        obstacle_avoidance_enabled=True, robot_type="quad",
        pos_body=(1.0, 2.0, 0.0), vel_body=(0.5, 0.0, 0.0),
        acc_body=(0.1, 0.0, 0.0), omega_body=(0.0, 0.0, 0.2), ori_body=(0.0, 0.01, 0.0),
        jpos_leg=[0.1] * 12, jvel_leg=[0.2] * 12, jtau_leg=[0.3] * 12,
        grf_left=(1.0, 2.0, 3.0), grf_right=(4.0, 5.0, 6.0),
        battery_percent=80.0, captured_at="2026-07-23T00:00:00Z",
    )
    adapter = _StubAdapter([snapshot])
    reader = TelemetryReader(adapter, make_config(), frames.append, clock=lambda: datetime.now(timezone.utc))

    await reader.poll_once()

    frame = frames[0]
    assert frame.acc_body == (0.1, 0.0, 0.0)
    assert frame.omega_body == (0.0, 0.0, 0.2)
    assert frame.ori_body == (0.0, 0.01, 0.0)
    assert frame.jpos_leg == [0.1] * 12
    assert frame.jvel_leg == [0.2] * 12
    assert frame.jtau_leg == [0.3] * 12
    assert frame.grf_left == (1.0, 2.0, 3.0)
    assert frame.grf_right == (4.0, 5.0, 6.0)


@pytest.mark.asyncio
async def test_estop_active_reports_e_stop_instead_of_fault(make_config):
    state_changes = []

    async def on_frame(frame):
        pass

    async def on_state_change(sdk_state, abstract_state):
        state_changes.append((sdk_state, abstract_state))

    adapter = _StubAdapter([_snapshot(current_state="passive")])
    reader = TelemetryReader(
        adapter, make_config(), on_frame,
        clock=lambda: datetime.now(timezone.utc),
        on_state_change=on_state_change,
        estop_active_provider=lambda: True,
    )

    await reader.poll_once()

    assert state_changes == [("passive", "E_STOP")]
