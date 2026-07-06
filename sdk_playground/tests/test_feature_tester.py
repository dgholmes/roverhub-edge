import pytest

from sim_robot_client import SimulatedRobotClient
import feature_tester as ft


def test_action_get_state_name():
    client = SimulatedRobotClient(verbose=False)
    assert ft.action_get_state_name(client) == "stand_down"


def test_action_get_full_state_contains_position():
    client = SimulatedRobotClient(verbose=False)
    text = ft.action_get_full_state(client)
    assert "pos_body" in text


def test_action_get_motions_lists_quad_motions():
    client = SimulatedRobotClient(robot_type="quad", verbose=False)
    text = ft.action_get_motions(client)
    assert "[walk]" in text


def test_action_set_speed_ratio_clamped():
    client = SimulatedRobotClient(verbose=False)
    result = ft.action_set_speed_ratio(client, 500)
    assert "100" in result


def test_action_set_obstacle_avoidance():
    client = SimulatedRobotClient(verbose=False)
    result = ft.action_set_obstacle_avoidance(client, False)
    assert "False" in result


def test_valid_states_for_quad_excludes_wheel_loco():
    client = SimulatedRobotClient(robot_type="quad", verbose=False)
    states = ft.valid_states_for(client)
    assert "walk" in states
    assert "wheel_loco" not in states


def test_valid_states_for_wheel_excludes_walk():
    client = SimulatedRobotClient(robot_type="wheel", verbose=False)
    states = ft.valid_states_for(client)
    assert "wheel_loco" in states
    assert "walk" not in states


def test_action_set_target_state_valid():
    client = SimulatedRobotClient(verbose=False)
    result = ft.action_set_target_state(client, "walk")
    assert "success=True" in result
    assert client.get_current_state_name() == "walk"


def test_action_set_target_state_invalid_raises():
    client = SimulatedRobotClient(verbose=False)
    with pytest.raises(ValueError):
        ft.action_set_target_state(client, "not_a_state")


def test_action_call_wrapper_wave():
    client = SimulatedRobotClient(verbose=False)
    result = ft.action_call_wrapper(client, "wave")
    assert "wave ->" in result
    assert client.get_current_state_name() == "wave"


def test_action_change_mode():
    client = SimulatedRobotClient(robot_type="quad", verbose=False)
    result = ft.action_change_mode(client)
    assert "miniQuadW" in result
    assert client.is_quad_wheel() is True


def test_action_velocity_sequence_demo():
    client = SimulatedRobotClient(verbose=False)
    result = ft.action_velocity_sequence_demo(client, "walk")
    assert "success=True" in result


def test_action_line_walk():
    client = SimulatedRobotClient(verbose=False)
    result = ft.action_line_walk(client, "forward", 1.5)
    assert "success=True" in result


def test_action_rotate():
    client = SimulatedRobotClient(verbose=False)
    result = ft.action_rotate(client, "left", 90.0)
    assert "success=True" in result


def test_action_circle():
    client = SimulatedRobotClient(verbose=False)
    result = ft.action_circle(client, "right", 2)
    assert "success=True" in result


def test_action_balance_axis():
    client = SimulatedRobotClient(robot_type="quad", verbose=False)
    client.balance_stand()
    result = ft.action_balance_axis(client, "pitch", 15.0, 0.5, "dynamic")
    assert "success=True" in result


def test_action_balance_sequence_demo():
    client = SimulatedRobotClient(verbose=False)
    client.balance_stand()
    result = ft.action_balance_sequence_demo(client)
    assert "success=True" in result


def test_action_dynamic_pose_demo():
    client = SimulatedRobotClient(verbose=False)
    client.balance_stand()
    result = ft.action_dynamic_pose_demo(client)
    assert "success=True" in result


def test_action_static_pose_demo():
    client = SimulatedRobotClient(verbose=False)
    client.balance_stand()
    result = ft.action_static_pose_demo(client)
    assert "success=True" in result


def test_action_kill_robot_requires_exact_confirmation():
    client = SimulatedRobotClient(verbose=False)
    result = ft.action_kill_robot(client, "yes")
    assert "Aborted" in result
    assert client.get_current_state_name() != "passive"


def test_action_kill_robot_confirmed():
    client = SimulatedRobotClient(verbose=False)
    result = ft.action_kill_robot(client, "KILL")
    assert "success=True" in result
