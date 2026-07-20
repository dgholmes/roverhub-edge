import pytest

from dobot_adapter import DobotAdapter
from fake_robot_client import FakeRobotClient


@pytest.mark.asyncio
async def test_connect_detects_quad_type():
    adapter = DobotAdapter(lambda: FakeRobotClient(robot_type="quad"))
    await adapter.connect()
    assert await adapter.get_robot_config() == "quad"


@pytest.mark.asyncio
async def test_connect_detects_wheel_type():
    adapter = DobotAdapter(lambda: FakeRobotClient(robot_type="wheel"))
    await adapter.connect()
    assert await adapter.get_robot_config() == "wheel"


@pytest.mark.asyncio
async def test_connect_calls_enable_safety_ready():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    assert client.safety_ready_called is True


@pytest.mark.asyncio
async def test_get_sdk_state_before_connect_raises():
    adapter = DobotAdapter(lambda: FakeRobotClient())
    with pytest.raises(RuntimeError):
        await adapter.get_sdk_state()


@pytest.mark.asyncio
async def test_set_state_updates_sdk_state():
    adapter = DobotAdapter(lambda: FakeRobotClient())
    await adapter.connect()
    await adapter.set_state("balance_stand")
    assert await adapter.get_sdk_state() == "balance_stand"


@pytest.mark.asyncio
async def test_enable_obstacle_avoidance_toggles():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.enable_obstacle_avoidance(False)
    assert client.get_obstacle_avoidance() is False


@pytest.mark.asyncio
async def test_get_telemetry_snapshot_reflects_client_state():
    adapter = DobotAdapter(lambda: FakeRobotClient(robot_type="quad", battery_percent=55.0))
    await adapter.connect()
    snapshot = await adapter.get_telemetry_snapshot()
    assert snapshot.robot_type == "quad"
    assert snapshot.battery_percent == 55.0
    assert snapshot.pos_body == (0.0, 0.0, 0.0)


@pytest.mark.asyncio
async def test_disconnect_closes_client_and_clears_state():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.disconnect()
    with pytest.raises(RuntimeError):
        await adapter.get_sdk_state()
