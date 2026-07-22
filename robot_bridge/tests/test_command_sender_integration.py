"""Integration tests driving CommandSender through the REAL DobotAdapter
(wired to FakeRobotClient / FakePyDDSMiddleware), not the hand-rolled
_StubAdapter used in test_command_sender.py. test_command_sender.py proves
command_sender.py's own dispatch/ACK/safety-wiring logic in isolation, but
never proves the CommandSender -> DobotAdapter -> FakeRobotClient chain
actually lines up end-to-end -- if DobotAdapter's method signatures ever
drifted from what _StubAdapter re-declares, that suite would stay green.
These tests close that gap by exercising the real adapter + real
SafetyManager together."""

import pytest

from command_sender import CommandSender
from dobot_adapter import DobotAdapter
from fake_robot_client import FakeRobotClient
from safety_manager import SafetyManager
from shared.schemas.commands import Command


class _FakeDdsMessages:
    """Mirrors dobot_adapter.py's _RealDdsMessages, but returns the fake
    DDS message stand-ins from fake_dds_middleware.py instead of importing
    dds_middleware_python (unavailable on this dev machine). Duplicated
    from test_dobot_adapter.py's identical helper rather than imported
    across test modules, matching that file's own precedent."""

    @staticmethod
    def led_control():
        from fake_dds_middleware import FakeLEDControl
        return FakeLEDControl()

    @staticmethod
    def leds_cmd():
        from fake_dds_middleware import FakeLedsCmd
        return FakeLedsCmd()

    @staticmethod
    def header():
        from fake_dds_middleware import FakeHeader
        return FakeHeader()

    @staticmethod
    def time():
        from fake_dds_middleware import FakeTime
        return FakeTime()

    @staticmethod
    def voice_cmd():
        from fake_dds_middleware import FakeVoiceCmd
        return FakeVoiceCmd()

    @staticmethod
    def voice_priority_normal():
        return 0


def _command(command_type, params=None):
    return Command(
        command_id="cmd-1", robot_id="robot-dev-01", type=command_type,
        label=command_type, params=params, initiated_by="operator-1",
    )


@pytest.mark.asyncio
async def test_line_walk_reaches_fake_robot_client_end_to_end(make_config):
    """A representative movement command flows CommandSender -> real
    DobotAdapter -> FakeRobotClient, and the fake actually records the
    call with the exact args command_sender passed through."""
    acks = []
    client = FakeRobotClient()
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("LINE_WALK", params={"direction": "forward", "distance": 1.5}))

    assert acks[-1].current_stage == "execution_completed"
    assert client.last_line_walk == {"direction": "forward", "distance": 1.5}


@pytest.mark.asyncio
async def test_balance_axis_rejected_on_wheel_robot_end_to_end(make_config):
    """A wheel-gated balance command is rejected end-to-end: the real
    DobotAdapter.get_robot_config() reports "wheel" (derived from
    FakeRobotClient.is_quad_wheel() at connect time), the real
    SafetyManager sees that robot_type and rejects, and the SDK-level
    call never reaches the fake robot client."""
    acks = []
    client = FakeRobotClient(robot_type="wheel")
    adapter = DobotAdapter(lambda: client)
    await adapter.connect()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("BALANCE_AXIS", params={
        "axis": "pitch", "value": 10.0, "duration": 0.5, "mode": "dynamic",
    }))

    assert acks[-1].current_stage == "execution_failed"
    assert acks[-1].failure_reason == "REJECTED_UNSUPPORTED_ON_WHEEL"
    assert client.last_balance_call is None


@pytest.mark.asyncio
async def test_led_signal_reaches_fake_dds_middleware_end_to_end(make_config):
    """An LED command flows CommandSender -> real DobotAdapter.set_led ->
    the fake DDS middleware's publishLedsCmd, landing in its published
    dict -- not just a stub recording that set_led was called."""
    from fake_dds_middleware import FakePyDDSMiddleware

    acks = []
    middleware = FakePyDDSMiddleware(0)
    adapter = DobotAdapter(
        lambda: FakeRobotClient(),
        dds_middleware_factory=lambda: middleware,
        dds_messages=_FakeDdsMessages,
    )
    await adapter.connect()
    safety = SafetyManager(make_config())
    sender = CommandSender(adapter, safety, acks.append, battery_percent_provider=lambda: 80.0)

    await sender.handle_command(_command("LED_SIGNAL", params={
        "name": "leg_light1", "r": 255, "g": 0, "b": 0, "brightness": 255, "priority": 0,
    }))

    assert acks[-1].current_stage == "execution_completed"
    assert "rt/leds/cmd" in middleware.created_writers
    published = middleware.published["rt/leds/cmd"]
    assert len(published) == 1
    assert published[0].leds()[0].name() == "leg_light1"
    assert published[0].leds()[0].r() == 255
