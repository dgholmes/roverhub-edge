import pytest

from sim_robot_client import SimulatedRobotClient


def test_initial_state_is_stand_down():
    client = SimulatedRobotClient(verbose=False)
    assert client.get_current_state_name() == "stand_down"


def test_quad_type_detection():
    client = SimulatedRobotClient(robot_type="quad", verbose=False)
    assert client.is_quad() is True
    assert client.is_quad_wheel() is False
    assert client.get_robot_type() == "miniQuad"


def test_wheel_type_detection():
    client = SimulatedRobotClient(robot_type="wheel", verbose=False)
    assert client.is_quad_wheel() is True
    assert client.get_robot_type() == "miniQuadW"


def test_invalid_robot_type_raises():
    with pytest.raises(ValueError):
        SimulatedRobotClient(robot_type="bogus")


def test_set_target_state_valid():
    client = SimulatedRobotClient(verbose=False)
    res = client.set_target_state("walk")
    assert res.success is True
    assert client.get_current_state_name() == "walk"


def test_set_target_state_invalid_raises():
    client = SimulatedRobotClient(verbose=False)
    with pytest.raises(ValueError):
        client.set_target_state("not_a_real_state")


def test_set_target_state_does_not_cross_check_robot_type():
    # Matches real SDK behavior: validate_state() checks against the union of
    # quad+wheel state names, it does not reject a wheel-only state name just
    # because the client is currently in quad mode. Menu-level gating (which
    # states/actions are *offered*) happens in feature_tester.py, not here.
    client = SimulatedRobotClient(robot_type="quad", verbose=False)
    res = client.set_target_state("wheel_loco")
    assert res.success is True


def test_speed_ratio_clamped_high():
    client = SimulatedRobotClient(verbose=False)
    client.set_speed_ratio(500)
    assert client.get_speed_ratio() == 100


def test_speed_ratio_clamped_low():
    client = SimulatedRobotClient(verbose=False)
    client.set_speed_ratio(-10)
    assert client.get_speed_ratio() == 10


def test_obstacle_avoidance_accepts_bool_and_on_off_strings():
    client = SimulatedRobotClient(verbose=False)
    client.set_obstacle_avoidance("off")
    assert client.get_obstacle_avoidance() is False
    client.set_obstacle_avoidance("on")
    assert client.get_obstacle_avoidance() is True
    client.set_obstacle_avoidance(False)
    assert client.get_obstacle_avoidance() is False


def test_obstacle_avoidance_rejects_bad_string():
    client = SimulatedRobotClient(verbose=False)
    with pytest.raises(ValueError):
        client.set_obstacle_avoidance("maybe")


def test_velocity_sequence_moves_position_forward():
    client = SimulatedRobotClient(verbose=False)
    client.velocity_sequence([(1.0, 0.0, 0.0, 2.0)], gait="walk", stand_down_after=False)
    state = client.get_state()
    assert state.robot_state.pos_body[0] == pytest.approx(2.0)


def test_velocity_sequence_invalid_gait_raises():
    client = SimulatedRobotClient(verbose=False)
    with pytest.raises(ValueError):
        client.velocity_sequence([(0, 0, 0, 1)], gait="bogus_gait")


def test_velocity_sequence_stand_down_after():
    client = SimulatedRobotClient(verbose=False)
    client.velocity_sequence([(0.5, 0, 0, 1.0)], gait="walk", stand_down_after=True)
    assert client.get_current_state_name() == "stand_down"


def test_balance_pitch_clamped_and_applied():
    client = SimulatedRobotClient(verbose=False)
    client.balance_stand()
    client.balance_pitch(999.0, duration=0.5, mode="dynamic")
    state = client.get_state()
    assert state.robot_state.ori_body[1] == pytest.approx(11.5)  # BALANCE_PITCH_LIMIT_DEG


def test_balance_neutral_resets_pitch():
    client = SimulatedRobotClient(verbose=False)
    client.balance_stand()
    client.balance_pitch(10.0, duration=0.5)
    client.balance_neutral()
    state = client.get_state()
    assert state.robot_state.ori_body[1] == pytest.approx(0.0)


def test_balance_motion_invalid_id_raises():
    client = SimulatedRobotClient(verbose=False)
    with pytest.raises(ValueError):
        client._balance_motion("balance_bogus", 1.0, 1.0, "dynamic", False)


def test_line_walk_forward_moves_position():
    client = SimulatedRobotClient(verbose=False)
    client.line_walk("forward", 2.0)
    state = client.get_state()
    assert state.robot_state.pos_body[0] == pytest.approx(2.0)


def test_rotate_left_and_right_signs():
    client = SimulatedRobotClient(verbose=False)
    client.rotate("left", 90.0)
    state = client.get_state()
    assert state.robot_state.ori_body[2] == pytest.approx(-90.0)
    client.rotate("right", 90.0)
    state = client.get_state()
    assert state.robot_state.ori_body[2] == pytest.approx(0.0)


def test_get_motions_returns_quad_motions():
    client = SimulatedRobotClient(robot_type="quad", verbose=False)
    res = client.get_motions()
    assert res.success is True
    ids = {m.motion_id for m in res.motions}
    assert "walk" in ids
    assert "wheel_loco" not in ids


def test_get_motions_returns_wheel_motions():
    client = SimulatedRobotClient(robot_type="wheel", verbose=False)
    res = client.get_motions()
    ids = {m.motion_id for m in res.motions}
    assert "wheel_loco" in ids
    assert "walk" not in ids


def test_kill_robot_via_execute_reports_passive():
    client = SimulatedRobotClient(verbose=False)
    res = client.execute("kill_robot")
    assert res.success is True
    assert res.current_state == "passive"


def test_context_manager_closes_cleanly():
    with SimulatedRobotClient(verbose=False) as client:
        client.stand_down()
    # reaching here without an exception is the assertion
