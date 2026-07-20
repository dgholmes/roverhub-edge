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

    async def get_sdk_state(self):
        if self._raise_on_get_state:
            raise RuntimeError("not connected")
        return self._sdk_state

    async def set_state(self, target):
        self.set_state_calls.append(target)
        self._sdk_state = target

    async def enable_obstacle_avoidance(self, enabled):
        self.obstacle_avoidance_calls.append(enabled)


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
async def test_take_control_completes_without_sdk_call(make_config):
    acks = []
    adapter = _StubAdapter(raise_on_get_state=True)
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("TAKE_CONTROL"))

    assert acks[-1].current_stage == "execution_completed"


@pytest.mark.asyncio
async def test_low_battery_rejects_and_reports_failure_reason(make_config):
    acks = []
    adapter = _StubAdapter(sdk_state="balance_stand")
    safety = SafetyManager(make_config(safety_min_battery_pct=15.0))
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 5.0)

    await sender.handle_command(_command("SET_OBSTACLE_AVOIDANCE"))

    assert acks[-1].current_stage == "execution_failed"
    assert acks[-1].failure_reason == "REJECTED_LOW_BATTERY"
