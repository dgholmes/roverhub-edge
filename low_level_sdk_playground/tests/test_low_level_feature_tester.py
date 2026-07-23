import low_level_feature_tester as lft


def test_raw_motor_command_aborts_without_confirmation(monkeypatch):
    """Safety-critical test: anything other than the exact 'MOTORCMD'
    confirmation string must abort before touching the DDS middleware at
    all -- no writer creation, no subscription, no publish. The real E9
    behavior sends conflicting commands to live motors if the robot's main
    controller wasn't already killed, so this gate is the only thing
    standing between a typo and a real safety hazard."""
    monkeypatch.setattr("builtins.input", lambda *_args: "yes please")

    class _ExplodingMiddleware:
        def __getattr__(self, name):
            raise AssertionError(f"middleware.{name} must not be called when confirmation is refused")

    lft.menu_raw_motor_command(_ExplodingMiddleware())


def test_raw_motor_command_proceeds_only_on_exact_confirmation(monkeypatch):
    """Confirms the gate actually opens on the correct string (and then
    aborts cleanly when the robot never sends enough lower_state messages,
    which is the only path reachable without a real DDS connection)."""
    inputs = iter(["MOTORCMD"])
    monkeypatch.setattr("builtins.input", lambda *_args: next(inputs))
    monkeypatch.setattr("time.sleep", lambda *_args: None)

    created_writers = []

    class _StubMiddleware:
        def createLowerCmdWriter(self, topic, qos_config):
            created_writers.append(topic)

        def subscribeLowerState(self, topic, callback):
            pass  # never fires -- simulates no robot connected

    import sys
    import types
    fake_dds = types.ModuleType("dds_middleware_python")
    sys.modules["dds_middleware_python"] = fake_dds

    try:
        lft.menu_raw_motor_command(_StubMiddleware())
    finally:
        del sys.modules["dds_middleware_python"]

    assert created_writers == ["rt/lower/cmd"]


def test_run_quits_on_zero(monkeypatch):
    monkeypatch.setattr(lft, "connect", lambda config: object())
    inputs = iter(["0"])
    monkeypatch.setattr("builtins.input", lambda *_args: next(inputs))
    lft.run(config=object())


def test_run_reports_unknown_option_then_quits(monkeypatch):
    monkeypatch.setattr(lft, "connect", lambda config: object())
    inputs = iter(["99", "0"])
    monkeypatch.setattr("builtins.input", lambda *_args: next(inputs))
    lft.run(config=object())


def test_run_dispatches_to_the_matching_handler(monkeypatch):
    monkeypatch.setattr(lft, "connect", lambda config: "the-middleware")
    calls = []
    monkeypatch.setitem(lft.MENU_HANDLERS, "1", lambda middleware: calls.append(middleware))
    inputs = iter(["1", "0"])
    monkeypatch.setattr("builtins.input", lambda *_args: next(inputs))

    lft.run(config=object())

    assert calls == ["the-middleware"]
