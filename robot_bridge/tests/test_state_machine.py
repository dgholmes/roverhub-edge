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
    assert compute_abstract_state("change_mode", estop_active=False, obstacle_avoidance_enabled=False) == "FAULT"
