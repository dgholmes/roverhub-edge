import pytest

from fake_robot_client import FakeRobotClient


def test_defaults_to_quad_stand_down():
    client = FakeRobotClient()
    assert client.is_quad_wheel() is False
    assert client.get_current_state_name() == "stand_down"


def test_wheel_type_reports_is_quad_wheel():
    client = FakeRobotClient(robot_type="wheel")
    assert client.is_quad_wheel() is True


def test_set_target_state_updates_state():
    client = FakeRobotClient()
    result = client.set_target_state("balance_stand")
    assert result.success is True
    assert client.get_current_state_name() == "balance_stand"


def test_set_target_state_rejects_unknown_state():
    client = FakeRobotClient()
    with pytest.raises(ValueError):
        client.set_target_state("moonwalk")


def test_obstacle_avoidance_toggle_round_trips():
    client = FakeRobotClient()
    client.set_obstacle_avoidance(False)
    assert client.get_obstacle_avoidance() is False


def test_get_state_reports_battery_and_position():
    client = FakeRobotClient(battery_percent=42.0)
    state = client.get_state()
    assert state.robot_state.pos_body == (0.0, 0.0, 0.0)
    assert client.battery_percent == 42.0
