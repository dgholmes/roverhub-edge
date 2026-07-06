import argparse

import pytest

from shared import (
    DEFAULT_WIFI_ADDRESS,
    ConnectionConfig,
    build_arg_parser,
    connect,
    detect_mode,
    is_success,
    format_state_line,
    format_telemetry_block,
)


def test_default_wifi_address_matches_docs():
    assert DEFAULT_WIFI_ADDRESS == "192.168.1.6:50051"


def test_build_arg_parser_defaults():
    parser = build_arg_parser("test")
    args = parser.parse_args([])
    assert args.address == DEFAULT_WIFI_ADDRESS
    assert args.simulate is False
    assert args.sim_robot_type == "quad"


def test_build_arg_parser_accepts_overrides():
    parser = build_arg_parser("test")
    args = parser.parse_args(["--address", "192.168.5.2:50051", "--simulate", "--sim-robot-type", "wheel"])
    assert args.address == "192.168.5.2:50051"
    assert args.simulate is True
    assert args.sim_robot_type == "wheel"


def test_build_arg_parser_rejects_bad_sim_robot_type():
    parser = build_arg_parser("test")
    with pytest.raises(SystemExit):
        parser.parse_args(["--sim-robot-type", "bogus"])


def test_connect_simulate_returns_working_client():
    config = ConnectionConfig(address="unused", simulate=True, sim_robot_type="quad")
    client = connect(config)
    assert client.get_current_state_name() == "stand_down"


def test_connect_simulate_wheel_type():
    config = ConnectionConfig(address="unused", simulate=True, sim_robot_type="wheel")
    client = connect(config)
    assert client.is_quad_wheel() is True


def test_detect_mode_quad():
    config = ConnectionConfig(address="unused", simulate=True, sim_robot_type="quad")
    client = connect(config)
    assert detect_mode(client) == "quad"


def test_detect_mode_wheel():
    config = ConnectionConfig(address="unused", simulate=True, sim_robot_type="wheel")
    client = connect(config)
    assert detect_mode(client) == "wheel"


class _FakeResult:
    def __init__(self, success):
        self.success = success


def test_is_success_true():
    assert is_success(_FakeResult(True)) is True


def test_is_success_false():
    assert is_success(_FakeResult(False)) is False


def test_is_success_none_is_false():
    # real RobotClient.execute() returns None on Ctrl+C / RPC cancellation
    assert is_success(None) is False


def test_format_state_line_success():
    config = ConnectionConfig(address="unused", simulate=True, sim_robot_type="quad")
    client = connect(config)
    line = format_state_line(client.get_state())
    assert "state=stand_down" in line
    assert "speed_ratio=50" in line


def test_format_telemetry_block_contains_position():
    config = ConnectionConfig(address="unused", simulate=True, sim_robot_type="quad")
    client = connect(config)
    block = format_telemetry_block(client.get_state())
    assert "pos_body" in block
    assert "current_state:" in block
