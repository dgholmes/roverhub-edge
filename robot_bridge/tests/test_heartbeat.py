import pytest

from heartbeat import HeartbeatSender
from shared.schemas.telemetry import TelemetrySnapshot


class _StubAdapter:
    def __init__(self, sdk_state="balance_stand", battery_percent=80.0, raise_on_state=False):
        self._sdk_state = sdk_state
        self._battery_percent = battery_percent
        self._raise_on_state = raise_on_state

    async def get_sdk_state(self):
        if self._raise_on_state:
            raise RuntimeError("not connected")
        return self._sdk_state

    async def get_telemetry_snapshot(self):
        return TelemetrySnapshot(
            current_state=self._sdk_state, current_speed_ratio=0,
            obstacle_avoidance_enabled=True, robot_type="quad",
            pos_body=(0.0, 0.0, 0.0), vel_body=(0.0, 0.0, 0.0),
            battery_percent=self._battery_percent, captured_at="2026-07-20T00:00:00Z",
        )

    async def get_motions(self):
        if self._raise_on_state:
            raise RuntimeError("not connected")
        return ["walk", "dance", "wave"]


@pytest.mark.asyncio
async def test_send_once_reports_connected_and_battery(make_config):
    payloads = []
    sender = HeartbeatSender(_StubAdapter(battery_percent=63.0), make_config(), payloads.append)

    await sender.send_once()

    assert len(payloads) == 1
    assert payloads[0].sdk_connected is True
    assert payloads[0].battery_pct == 63.0
    assert payloads[0].bridge_id == "bridge-dev-01"


@pytest.mark.asyncio
async def test_send_once_reports_disconnected_when_adapter_raises(make_config):
    payloads = []
    sender = HeartbeatSender(_StubAdapter(raise_on_state=True), make_config(), payloads.append)

    await sender.send_once()

    assert payloads[0].sdk_connected is False
    assert payloads[0].battery_pct == 0.0


@pytest.mark.asyncio
async def test_send_once_includes_available_motions(make_config):
    payloads = []
    sender = HeartbeatSender(_StubAdapter(), make_config(), payloads.append)

    await sender.send_once()

    assert payloads[0].available_motions == ["walk", "dance", "wave"]


@pytest.mark.asyncio
async def test_send_once_reports_empty_motions_when_adapter_raises(make_config):
    payloads = []
    sender = HeartbeatSender(_StubAdapter(raise_on_state=True), make_config(), payloads.append)

    await sender.send_once()

    assert payloads[0].available_motions == []
