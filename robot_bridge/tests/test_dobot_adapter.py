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
async def test_get_sdk_state_lowercases_real_sdk_uppercase_response():
    """The real dobot_quad SDK's get_current_state_name() returns uppercase
    (e.g. "WALK"), but every downstream comparison (state_machine.py,
    command_sender.py's RESET_ESTOP check) expects lowercase."""

    class _UppercaseStateClient:
        def enable_safety_ready(self):
            pass

        def is_quad_wheel(self):
            return False

        def get_current_state_name(self):
            return "WALK"

    adapter = DobotAdapter(lambda: _UppercaseStateClient())
    await adapter.connect()
    assert await adapter.get_sdk_state() == "walk"


@pytest.mark.asyncio
async def test_get_telemetry_snapshot_lowercases_real_sdk_uppercase_current_state():
    class _RealShapedRobotState:
        pos_body = (0.0, 0.0, 0.0)
        vel_body = (0.0, 0.0, 0.0)

    class _UppercaseStateResponse:
        current_state = "PASSIVE"
        current_speed_ratio = 0
        obstacle_avoidance_enabled = True
        robot_state = _RealShapedRobotState()

    class _UppercaseStateClient:
        def enable_safety_ready(self):
            pass

        def is_quad_wheel(self):
            return False

        def get_state(self):
            return _UppercaseStateResponse()

    adapter = DobotAdapter(lambda: _UppercaseStateClient())
    await adapter.connect()
    snapshot = await adapter.get_telemetry_snapshot()
    assert snapshot.current_state == "passive"


@pytest.mark.asyncio
async def test_get_telemetry_snapshot_defaults_battery_when_client_lacks_it():
    """Real dobot_quad.RobotClient has no battery_percent attribute (battery
    is DDS/BMS-only, out of scope this round) -- must degrade to 0.0 rather
    than raising AttributeError, unlike FakeRobotClient's test convenience."""

    class _RealShapedRobotState:
        pos_body = (1.0, 2.0, 0.0)
        vel_body = (0.0, 0.0, 0.0)

    class _RealShapedStateResponse:
        current_state = "balance_stand"
        current_speed_ratio = 50
        obstacle_avoidance_enabled = True
        robot_state = _RealShapedRobotState()

    class _RealShapedClient:
        def enable_safety_ready(self):
            pass

        def is_quad_wheel(self):
            return False

        def get_state(self):
            return _RealShapedStateResponse()

    adapter = DobotAdapter(lambda: _RealShapedClient())
    await adapter.connect()
    snapshot = await adapter.get_telemetry_snapshot()
    assert snapshot.battery_percent == 0.0
    assert snapshot.pos_body == (1.0, 2.0, 0.0)


@pytest.mark.asyncio
async def test_disconnect_closes_client_and_clears_state():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.disconnect()
    with pytest.raises(RuntimeError):
        await adapter.get_sdk_state()


@pytest.mark.asyncio
async def test_change_mode_flips_robot_type():
    client = FakeRobotClient(robot_type="quad")
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.change_mode()
    assert client.robot_type == "wheel"


@pytest.mark.asyncio
async def test_set_speed_ratio_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.set_speed_ratio(75)
    assert client.get_state().current_speed_ratio == 75


@pytest.mark.asyncio
async def test_set_speed_ratio_reflected_in_telemetry_snapshot():
    """set_speed_ratio must be observable end-to-end via telemetry, not just
    on the client -- get_telemetry_snapshot() reads FakeRobotClient.get_state(),
    which reads the same _speed_ratio attribute set_speed_ratio writes to."""
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.set_speed_ratio(75)
    snapshot = await adapter.get_telemetry_snapshot()
    assert snapshot.current_speed_ratio == 75


@pytest.mark.asyncio
async def test_send_velocity_sequence_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.send_velocity_sequence([(0.5, 0.0, 0.0, 0.25)], gait="walk", speed_ratio=60)
    assert client.last_velocity_sequence == {
        "steps": [(0.5, 0.0, 0.0, 0.25)],
        "gait": "walk",
        "speed_ratio": 60,
        "stand_down_after": False,
    }


@pytest.mark.asyncio
async def test_line_walk_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.line_walk("forward", 2.0)
    assert client.last_line_walk == {"direction": "forward", "distance": 2.0}


@pytest.mark.asyncio
async def test_rotate_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.rotate("left", 45.0)
    assert client.last_rotate == {"direction": "left", "angle": 45.0}


@pytest.mark.asyncio
async def test_circle_calls_client():
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    await adapter.circle("right", 2)
    assert client.last_circle == {"direction": "right", "turns": 2}
