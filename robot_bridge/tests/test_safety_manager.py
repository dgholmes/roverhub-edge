from safety_manager import SafetyManager


def test_estop_command_is_always_approved(make_config):
    safety = SafetyManager(make_config())
    result = safety.check("ESTOP", sdk_connected=False, battery_percent=0.0)
    assert result.approved is True


def test_estop_active_blocks_other_commands(make_config):
    safety = SafetyManager(make_config())
    safety.trigger_estop()
    result = safety.check("SET_OBSTACLE_AVOIDANCE", sdk_connected=True, battery_percent=80.0)
    assert result.approved is False
    assert result.rejection_code == "REJECTED_ESTOP"


def test_estop_active_still_allows_reset_estop(make_config):
    safety = SafetyManager(make_config())
    safety.trigger_estop()
    result = safety.check("RESET_ESTOP", sdk_connected=True, battery_percent=80.0)
    assert result.approved is True


def test_clear_estop_unblocks_commands(make_config):
    safety = SafetyManager(make_config())
    safety.trigger_estop()
    safety.clear_estop()
    result = safety.check("SET_OBSTACLE_AVOIDANCE", sdk_connected=True, battery_percent=80.0)
    assert result.approved is True


def test_take_control_ignores_connection_state(make_config):
    safety = SafetyManager(make_config())
    result = safety.check("TAKE_CONTROL", sdk_connected=False, battery_percent=0.0)
    assert result.approved is True


def test_no_connection_rejects_sdk_backed_command(make_config):
    safety = SafetyManager(make_config())
    result = safety.check("SET_OBSTACLE_AVOIDANCE", sdk_connected=False, battery_percent=80.0)
    assert result.approved is False
    assert result.rejection_code == "REJECTED_NO_CONNECTION"


def test_low_battery_rejects_sdk_backed_command(make_config):
    safety = SafetyManager(make_config(safety_min_battery_pct=15.0))
    result = safety.check("SET_OBSTACLE_AVOIDANCE", sdk_connected=True, battery_percent=10.0)
    assert result.approved is False
    assert result.rejection_code == "REJECTED_LOW_BATTERY"
