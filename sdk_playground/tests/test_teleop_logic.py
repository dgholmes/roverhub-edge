import pytest

from sim_robot_client import SimulatedRobotClient
from teleop import (
    GAIT_VELOCITY_LIMITS,
    KeyState,
    MouseBalanceAccumulator,
    TeleopController,
    compute_velocity,
)


def test_compute_velocity_forward_walk():
    assert compute_velocity(frozenset({"w"}), "walk") == (0.8, 0.0, 0.0)


def test_compute_velocity_backward_walk():
    assert compute_velocity(frozenset({"s"}), "walk") == (-0.8, 0.0, 0.0)


def test_compute_velocity_backward_blocked_on_flying_trot():
    # docs/03-sdk-integration.md §4.5: flying_trot vx is 0-0.8 only, no backward
    assert compute_velocity(frozenset({"s"}), "flying_trot") == (0.0, 0.0, 0.0)


def test_compute_velocity_strafe_left_is_positive_vy():
    assert compute_velocity(frozenset({"a"}), "walk") == (0.0, 0.8, 0.0)


def test_compute_velocity_strafe_right_is_negative_vy():
    assert compute_velocity(frozenset({"d"}), "walk") == (0.0, -0.8, 0.0)


def test_compute_velocity_turn_left_is_positive_vz():
    assert compute_velocity(frozenset({"q"}), "walk") == (0.0, 0.0, 0.8)


def test_compute_velocity_turn_right_is_negative_vz():
    assert compute_velocity(frozenset({"e"}), "walk") == (0.0, 0.0, -0.8)


def test_compute_velocity_no_keys_is_zero():
    assert compute_velocity(frozenset(), "walk") == (0.0, 0.0, 0.0)


def test_compute_velocity_opposite_keys_cancel():
    assert compute_velocity(frozenset({"w", "s"}), "walk") == (0.0, 0.0, 0.0)


def test_compute_velocity_respects_wheel_loco_limits():
    vx, vy, vz = compute_velocity(frozenset({"w", "a", "q"}), "wheel_loco")
    assert vx == pytest.approx(0.8)
    assert vy == pytest.approx(0.3)
    assert vz == pytest.approx(0.4)


def test_gait_velocity_limits_has_all_three_gaits():
    assert set(GAIT_VELOCITY_LIMITS.keys()) == {"walk", "flying_trot", "wheel_loco"}


def test_key_state_press_and_release():
    ks = KeyState()
    ks.press("w")
    ks.press("a")
    assert ks.snapshot() == frozenset({"w", "a"})
    ks.release("w")
    assert ks.snapshot() == frozenset({"a"})


def test_key_state_ignores_non_movement_keys():
    ks = KeyState()
    ks.press("z")
    assert ks.snapshot() == frozenset()


def test_mouse_accumulator_deadzone():
    acc = MouseBalanceAccumulator()
    acc.add_delta(1, 1)
    assert acc.flush() is None


def test_mouse_accumulator_flush_resets():
    acc = MouseBalanceAccumulator()
    acc.add_delta(50, 0)
    result = acc.flush()
    assert result is not None
    yaw_deg, pitch_deg = result
    assert yaw_deg > 0
    assert pitch_deg == 0
    acc.add_delta(1, 1)
    assert acc.flush() is None  # accumulator was reset by the previous flush


def test_teleop_controller_tick_walk_calls_velocity_sequence():
    client = SimulatedRobotClient(verbose=False)
    controller = TeleopController(client, tick_seconds=0.1)
    controller.enter_walk_mode()
    controller.key_state.press("w")
    vx, vy, vz = controller.tick_walk()
    assert vx == pytest.approx(0.8)
    assert client.get_current_state_name() in ("walk", "flying_trot")


def test_teleop_controller_cycle_gait_quad():
    client = SimulatedRobotClient(robot_type="quad", verbose=False)
    controller = TeleopController(client)
    assert controller.gait == "walk"
    assert controller.cycle_gait() == "flying_trot"
    assert controller.cycle_gait() == "walk"


def test_teleop_controller_cycle_gait_wheel_is_single_option():
    client = SimulatedRobotClient(robot_type="wheel", verbose=False)
    controller = TeleopController(client)
    assert controller.gait == "wheel_loco"
    assert controller.cycle_gait() == "wheel_loco"


def test_teleop_controller_toggle_mode_enters_posture():
    client = SimulatedRobotClient(verbose=False)
    controller = TeleopController(client)
    controller.enter_walk_mode()
    assert controller.toggle_mode() == "POSTURE"
    assert client.get_current_state_name() == "balance_stand"


def test_teleop_controller_toggle_mode_back_to_walk():
    client = SimulatedRobotClient(verbose=False)
    controller = TeleopController(client)
    controller.enter_walk_mode()
    controller.toggle_mode()  # -> POSTURE
    assert controller.toggle_mode() == "WALK"
    assert client.get_current_state_name() == controller.gait


def test_teleop_controller_emergency_stop_sets_passive():
    client = SimulatedRobotClient(verbose=False)
    controller = TeleopController(client)
    controller.emergency_stop()
    assert client.get_current_state_name() == "passive"


def test_teleop_controller_adjust_speed():
    client = SimulatedRobotClient(verbose=False)
    controller = TeleopController(client)
    new_speed = controller.adjust_speed(20)
    assert new_speed == 70  # sim default speed_ratio is 50


def test_teleop_controller_toggle_obstacle_avoidance():
    client = SimulatedRobotClient(verbose=False)
    controller = TeleopController(client)
    assert controller.toggle_obstacle_avoidance() is False
    assert controller.toggle_obstacle_avoidance() is True


def test_teleop_controller_tick_posture_calls_balance():
    client = SimulatedRobotClient(verbose=False)
    controller = TeleopController(client)
    controller.enter_posture_mode()
    result = controller.tick_posture(dx=50, dy=0)
    assert result is not None
    state = client.get_state()
    assert state.robot_state.ori_body[2] != 0.0  # yaw was nudged


def test_teleop_controller_tick_posture_below_deadzone_returns_none():
    client = SimulatedRobotClient(verbose=False)
    controller = TeleopController(client)
    controller.enter_posture_mode()
    result = controller.tick_posture(dx=1, dy=1)
    assert result is None


def test_teleop_controller_adjust_height():
    client = SimulatedRobotClient(verbose=False)
    controller = TeleopController(client)
    controller.enter_posture_mode()
    controller.adjust_height(-0.05)
    state = client.get_state()
    assert state.robot_state.ori_body is not None  # height isn't tracked in ori_body; call must not raise


def test_teleop_controller_enter_walk_mode_skips_balance_stand_on_wheel():
    client = SimulatedRobotClient(robot_type="wheel", verbose=False)

    def _fail(*a, **kw):
        raise AssertionError("balance_stand must not be called for wheel robots")

    client.balance_stand = _fail
    controller = TeleopController(client, tick_seconds=0.1)
    controller.enter_walk_mode()
    assert client.get_current_state_name() == "wheel_loco"


def test_teleop_controller_posture_mode_unavailable_on_wheel():
    client = SimulatedRobotClient(robot_type="wheel", verbose=False)

    def _fail(*a, **kw):
        raise AssertionError("balance_stand must not be called for wheel robots")

    client.balance_stand = _fail
    controller = TeleopController(client, tick_seconds=0.1)
    controller.enter_walk_mode()
    assert controller.toggle_mode() == "WALK"
