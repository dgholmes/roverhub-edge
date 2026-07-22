from state_machine import compute_abstract_state


def test_estop_takes_priority_over_everything():
    assert compute_abstract_state("walk", estop_active=True, obstacle_avoidance_enabled=True) == "E_STOP"


def test_recovery_maps_to_fault():
    assert compute_abstract_state("recovery", estop_active=False, obstacle_avoidance_enabled=False) == "FAULT"


def test_stand_down_maps_to_passive():
    assert compute_abstract_state("stand_down", estop_active=False, obstacle_avoidance_enabled=False) == "PASSIVE"


def test_balance_stand_maps_to_stand():
    assert compute_abstract_state("balance_stand", estop_active=False, obstacle_avoidance_enabled=False) == "STAND"


def test_walk_without_obstacle_avoidance_is_manual():
    assert compute_abstract_state("walk", estop_active=False, obstacle_avoidance_enabled=False) == "MANUAL"


def test_walk_with_obstacle_avoidance_is_assisted():
    assert compute_abstract_state("walk", estop_active=False, obstacle_avoidance_enabled=True) == "ASSISTED"


def test_wheel_loco_without_obstacle_avoidance_is_manual():
    assert compute_abstract_state("wheel_loco", estop_active=False, obstacle_avoidance_enabled=False) == "MANUAL"


def test_unknown_sdk_state_defaults_to_fault():
    assert compute_abstract_state("some-future-sdk-state-not-yet-mapped", estop_active=False, obstacle_avoidance_enabled=False) == "FAULT"


def test_wave_quick_action_is_manual_not_fault():
    """Regression test: wave/jump/dance0/etc. (canned gesture quick actions)
    were previously unrecognized and fell through to the FAULT default,
    even though they're real, valid SDK states -- reported live via a wave
    quick action making the UI show the robot as faulty while it waved."""
    assert compute_abstract_state("wave", estop_active=False, obstacle_avoidance_enabled=False) == "MANUAL"


def test_wave_quick_action_is_assisted_with_obstacle_avoidance():
    assert compute_abstract_state("wave", estop_active=False, obstacle_avoidance_enabled=True) == "ASSISTED"


def test_change_mode_is_active_not_fault():
    assert compute_abstract_state("change_mode", estop_active=False, obstacle_avoidance_enabled=False) == "MANUAL"


def test_balance_axis_states_are_active_not_fault():
    for sdk_state in ("balance_pitch", "balance_yaw", "balance_roll", "balance_height"):
        assert compute_abstract_state(sdk_state, estop_active=False, obstacle_avoidance_enabled=False) == "MANUAL"


def test_pose_states_are_active_not_fault():
    assert compute_abstract_state("dynamic_pose", estop_active=False, obstacle_avoidance_enabled=False) == "MANUAL"
    assert compute_abstract_state("static_pose", estop_active=False, obstacle_avoidance_enabled=False) == "MANUAL"


def test_fine_movement_states_are_active_not_fault():
    for sdk_state in ("line_walk", "rotation", "walk_velocity_seq", "flying_trot_velocity_seq", "rl_velocity_seq"):
        assert compute_abstract_state(sdk_state, estop_active=False, obstacle_avoidance_enabled=False) == "MANUAL"


def test_canned_gesture_states_are_active_not_fault():
    for sdk_state in ("backflip", "choreo", "dance0", "jump", "rl"):
        assert compute_abstract_state(sdk_state, estop_active=False, obstacle_avoidance_enabled=False) == "MANUAL"


def test_active_motion_state_respects_mission_phase():
    assert compute_abstract_state("wave", estop_active=False, obstacle_avoidance_enabled=False, mission_active=True) == "AUTO_MISSION"
    assert compute_abstract_state(
        "wave", estop_active=False, obstacle_avoidance_enabled=False, mission_active=True, mission_phase="returning",
    ) == "RETURNING"


def test_estop_still_takes_priority_over_active_motion_states():
    assert compute_abstract_state("wave", estop_active=True, obstacle_avoidance_enabled=False) == "E_STOP"


def test_recovery_still_maps_to_fault_not_active():
    assert compute_abstract_state("recovery", estop_active=False, obstacle_avoidance_enabled=False) == "FAULT"
