import pytest

from command_sender import CommandSender
from safety_manager import SafetyManager
from shared.schemas.commands import Command


class _StubAdapter:
    def __init__(self, sdk_state="passive", raise_on_get_state=False):
        self._sdk_state = sdk_state
        self._raise_on_get_state = raise_on_get_state
        self.set_state_calls = []
        self.obstacle_avoidance_calls = []
        self.robot_type = "quad"
        self.change_mode_called = False
        self.set_speed_ratio_calls = []
        self.velocity_sequence_calls = []
        self.line_walk_calls = []
        self.rotate_calls = []
        self.circle_calls = []
        self.balance_axis_calls = []
        self.balance_neutral_called = False
        self.balance_sequence_calls = []
        self.dynamic_pose_calls = []
        self.static_pose_calls = []
        self.set_led_calls = []
        self.speak_calls = []

    async def get_sdk_state(self):
        if self._raise_on_get_state:
            raise RuntimeError("not connected")
        return self._sdk_state

    async def set_state(self, target):
        self.set_state_calls.append(target)
        self._sdk_state = target

    async def enable_obstacle_avoidance(self, enabled):
        self.obstacle_avoidance_calls.append(enabled)

    async def get_robot_config(self):
        return self.robot_type

    async def change_mode(self):
        self.change_mode_called = True

    async def set_speed_ratio(self, ratio):
        self.set_speed_ratio_calls.append(ratio)

    async def send_velocity_sequence(self, steps, gait, speed_ratio):
        self.velocity_sequence_calls.append((steps, gait, speed_ratio))

    async def line_walk(self, direction, distance):
        self.line_walk_calls.append((direction, distance))

    async def rotate(self, direction, angle):
        self.rotate_calls.append((direction, angle))

    async def circle(self, direction, turns):
        self.circle_calls.append((direction, turns))

    async def balance_axis(self, axis, value, duration, mode):
        self.balance_axis_calls.append((axis, value, duration, mode))

    async def balance_neutral(self):
        self.balance_neutral_called = True

    async def balance_sequence(self, steps):
        self.balance_sequence_calls.append(steps)

    async def dynamic_pose(self, duration, roll_deg, pitch_deg, yaw_deg, height_m):
        self.dynamic_pose_calls.append((duration, roll_deg, pitch_deg, yaw_deg, height_m))

    async def static_pose(self, duration, roll_deg, pitch_deg, yaw_deg, height_m):
        self.static_pose_calls.append((duration, roll_deg, pitch_deg, yaw_deg, height_m))

    async def set_led(self, pattern):
        self.set_led_calls.append(pattern)

    async def speak(self, file_path):
        self.speak_calls.append(file_path)


def _command(command_type, params=None):
    return Command(
        command_id="cmd-1", robot_id="robot-dev-01", type=command_type,
        label=command_type, params=params, initiated_by="operator-1",
    )


@pytest.mark.asyncio
async def test_estop_command_completes_and_sets_estop_state(make_config):
    acks = []
    adapter = _StubAdapter(sdk_state="walk")
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("ESTOP"))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.set_state_calls == ["emergency"]
    assert safety.estop_active is True


@pytest.mark.asyncio
async def test_reset_estop_requires_passive_state(make_config):
    acks = []
    adapter = _StubAdapter(sdk_state="walk")
    safety = SafetyManager(make_config())
    safety.trigger_estop()
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("RESET_ESTOP"))

    assert acks[-1].current_stage == "execution_failed"
    assert safety.estop_active is True


@pytest.mark.asyncio
async def test_reset_estop_succeeds_from_passive(make_config):
    acks = []
    adapter = _StubAdapter(sdk_state="passive")
    safety = SafetyManager(make_config())
    safety.trigger_estop()
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("RESET_ESTOP"))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.set_state_calls == ["balance_stand"]
    assert safety.estop_active is False


@pytest.mark.asyncio
async def test_set_obstacle_avoidance_toggles_adapter(make_config):
    acks = []
    adapter = _StubAdapter(sdk_state="balance_stand")
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("SET_OBSTACLE_AVOIDANCE", params={"enabled": False}))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.obstacle_avoidance_calls == [False]


@pytest.mark.asyncio
async def test_take_control_transitions_quad_to_walk(make_config):
    """Regression test: TAKE_CONTROL used to be a no-op ("backend-only
    concept -- no SDK call"), so the robot stayed at balance_stand even
    though abstract_state flipped to MANUAL/ASSISTED -- every subsequent
    VELOCITY_SEQUENCE drive burst had nothing to move from. commandPolicy.ts
    only allows TAKE_CONTROL from abstract_state STAND (sdk_state
    balance_stand), matching the SDK's own combo-sequence example of calling
    walk() directly after balance_stand() (high_level.md E9)."""
    acks = []
    adapter = _StubAdapter(sdk_state="balance_stand")
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("TAKE_CONTROL"))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.set_state_calls == ["walk"]


@pytest.mark.asyncio
async def test_take_control_transitions_wheel_robot_to_wheel_loco(make_config):
    acks = []
    adapter = _StubAdapter(sdk_state="balance_stand")
    adapter.robot_type = "wheel"
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("TAKE_CONTROL"))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.set_state_calls == ["wheel_loco"]


@pytest.mark.asyncio
async def test_take_control_completes_even_if_sdk_state_query_fails(make_config):
    """TAKE_CONTROL's walk transition depends only on robot_type, not
    sdk_state -- it must still succeed if get_sdk_state() itself fails."""
    acks = []
    adapter = _StubAdapter(raise_on_get_state=True)
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("TAKE_CONTROL"))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.set_state_calls == ["walk"]


@pytest.mark.asyncio
async def test_low_battery_rejects_and_reports_failure_reason(make_config):
    acks = []
    adapter = _StubAdapter(sdk_state="balance_stand")
    safety = SafetyManager(make_config(safety_min_battery_pct=15.0))
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 5.0)

    await sender.handle_command(_command("SET_OBSTACLE_AVOIDANCE"))

    assert acks[-1].current_stage == "execution_failed"
    assert acks[-1].failure_reason == "REJECTED_LOW_BATTERY"


@pytest.mark.asyncio
async def test_unwired_command_type_fails_cleanly_instead_of_no_op(make_config):
    acks = []
    adapter = _StubAdapter(sdk_state="balance_stand")
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("PAUSE"))

    assert acks[-1].current_stage == "execution_failed"
    assert "PAUSE" in acks[-1].failure_reason
    assert adapter.set_state_calls == []
    assert adapter.obstacle_avoidance_calls == []


@pytest.mark.asyncio
async def test_set_state_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter(sdk_state="stand_down")
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("SET_STATE", params={"state": "balance_stand"}))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.set_state_calls == ["balance_stand"]


@pytest.mark.asyncio
async def test_set_gait_command_calls_adapter_set_state(make_config):
    """Regression test: SET_GAIT was previously excluded from
    WIRED_COMMAND_TYPES on the mistaken assumption it needed continuous
    velocity control like DRIVE. Gait names are just SDK target-state names
    (walk/flying_trot/wheel_loco/...), so it reuses set_state()."""
    acks = []
    adapter = _StubAdapter(sdk_state="balance_stand")
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("SET_GAIT", params={"gait": "flying_trot"}))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.set_state_calls == ["flying_trot"]


@pytest.mark.asyncio
async def test_change_mode_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("CHANGE_MODE"))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.change_mode_called is True


@pytest.mark.asyncio
async def test_set_speed_ratio_command_clamps_via_safety(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config(safety_max_speed_ratio=70))
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("SET_SPEED_RATIO", params={"ratio": 95}))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.set_speed_ratio_calls == [70]


@pytest.mark.asyncio
async def test_velocity_sequence_command_calls_adapter_with_clamped_speed(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config(safety_max_speed_ratio=60))
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("VELOCITY_SEQUENCE", params={
        "steps": [[0.5, 0.0, 0.0, 0.25]], "gait": "walk", "speed_ratio": 90,
    }))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.velocity_sequence_calls == [([[0.5, 0.0, 0.0, 0.25]], "walk", 60)]


@pytest.mark.asyncio
async def test_line_walk_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("LINE_WALK", params={"direction": "forward", "distance": 1.5}))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.line_walk_calls == [("forward", 1.5)]


@pytest.mark.asyncio
async def test_rotate_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("ROTATE", params={"direction": "left", "angle": 45.0}))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.rotate_calls == [("left", 45.0)]


@pytest.mark.asyncio
async def test_circle_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("CIRCLE", params={"direction": "right", "turns": 2}))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.circle_calls == [("right", 2)]


@pytest.mark.asyncio
async def test_balance_axis_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter()
    adapter.robot_type = "quad"
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("BALANCE_AXIS", params={
        "axis": "pitch", "value": 10.0, "duration": 0.5, "mode": "dynamic",
    }))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.balance_axis_calls == [("pitch", 10.0, 0.5, "dynamic")]


@pytest.mark.asyncio
async def test_balance_axis_command_rejected_on_wheel_robot(make_config):
    acks = []
    adapter = _StubAdapter()
    adapter.robot_type = "wheel"
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("BALANCE_AXIS", params={
        "axis": "pitch", "value": 10.0, "duration": 0.5, "mode": "dynamic",
    }))

    assert acks[-1].current_stage == "execution_failed"
    assert acks[-1].failure_reason == "REJECTED_UNSUPPORTED_ON_WHEEL"
    assert adapter.balance_axis_calls == []


@pytest.mark.asyncio
async def test_balance_neutral_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("BALANCE_NEUTRAL"))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.balance_neutral_called is True


@pytest.mark.asyncio
async def test_balance_sequence_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)
    steps = [["balance_pitch", 10.0, 0.5, "dynamic"]]

    await sender.handle_command(_command("BALANCE_SEQUENCE", params={"steps": steps}))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.balance_sequence_calls == [steps]


@pytest.mark.asyncio
async def test_dynamic_pose_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("DYNAMIC_POSE", params={
        "duration": 2.0, "roll_deg": 10.0, "pitch_deg": 5.0, "yaw_deg": 0.0, "height_m": -0.05,
    }))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.dynamic_pose_calls == [(2.0, 10.0, 5.0, 0.0, -0.05)]


@pytest.mark.asyncio
async def test_static_pose_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("STATIC_POSE", params={
        "duration": 3.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 5.0, "height_m": 0.0,
    }))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.static_pose_calls == [(3.0, 0.0, 0.0, 5.0, 0.0)]


@pytest.mark.asyncio
async def test_led_signal_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("LED_SIGNAL", params={
        "name": "leg_light1", "r": 255, "g": 0, "b": 0, "brightness": 255, "priority": 0,
    }))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.set_led_calls == [{"name": "leg_light1", "r": 255, "g": 0, "b": 0, "brightness": 255, "priority": 0}]


@pytest.mark.asyncio
async def test_speak_command_calls_adapter(make_config):
    acks = []
    adapter = _StubAdapter()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("SPEAK", params={"file_path": "/tmp/clip.wav"}))

    assert acks[-1].current_stage == "execution_completed"
    assert adapter.speak_calls == ["/tmp/clip.wav"]
