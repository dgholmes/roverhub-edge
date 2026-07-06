"""Connection and formatting helpers shared by feature_tester.py and teleop.py."""
from __future__ import annotations

import argparse
from dataclasses import dataclass

DEFAULT_WIFI_ADDRESS = "192.168.1.6:50051"


@dataclass
class ConnectionConfig:
    address: str
    simulate: bool
    sim_robot_type: str  # "quad" | "wheel"


def build_arg_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--address",
        default=DEFAULT_WIFI_ADDRESS,
        help=(
            f"Robot gRPC address, host:port (default: {DEFAULT_WIFI_ADDRESS}, WiFi dev). "
            "Use 192.168.5.2:50051 for wired Ethernet."
        ),
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Use an in-memory SimulatedRobotClient instead of connecting to a real robot.",
    )
    parser.add_argument(
        "--sim-robot-type",
        choices=["quad", "wheel"],
        default="quad",
        help="Robot type to simulate when --simulate is set (default: quad).",
    )
    return parser


def connect(config: ConnectionConfig):
    """Create and return a connected client (real or simulated), with safety armed."""
    if config.simulate:
        from sim_robot_client import SimulatedRobotClient

        client = SimulatedRobotClient(robot_type=config.sim_robot_type)
    else:
        from dobot_quad import RobotClient

        client = RobotClient(config.address)
    client.enable_safety_ready()
    return client


def detect_mode(client) -> str:
    """Return 'wheel' or 'quad' based on client.is_quad_wheel()."""
    return "wheel" if client.is_quad_wheel() else "quad"


def is_success(res) -> bool:
    """True if an SDK call result indicates success.

    Handles None: the real RobotClient.execute() returns None when a motion
    is cancelled (Ctrl+C) or the RPC stream errors out, rather than raising.
    """
    return res is not None and bool(getattr(res, "success", False))


def format_state_line(state_resp) -> str:
    """Format a get_state() response into a single human-readable line."""
    if not is_success(state_resp):
        message = getattr(state_resp, "message", "unknown error") if state_resp else "no response"
        return f"state: <unavailable> ({message})"
    oa = "on" if state_resp.obstacle_avoidance_enabled else "off"
    return (
        f"state={state_resp.current_state} "
        f"speed_ratio={state_resp.current_speed_ratio} "
        f"obstacle_avoidance={oa}"
    )


def format_telemetry_block(state_resp) -> str:
    """Format the full robot_state telemetry block (positions, velocities, GRF)."""
    if not is_success(state_resp):
        message = getattr(state_resp, "message", "unknown error") if state_resp else "no response"
        return f"telemetry unavailable: {message}"
    s = state_resp.robot_state
    fmt = lambda arr: [f"{x:.2f}" for x in arr]
    lines = [
        f"current_state:      {state_resp.current_state}",
        f"speed_ratio:        {state_resp.current_speed_ratio}",
        f"obstacle_avoidance: {state_resp.obstacle_avoidance_enabled}",
        f"pos_body [m]:       {fmt(s.pos_body)}",
        f"vel_body [m/s]:     {fmt(s.vel_body)}",
        f"acc_body [m/s^2]:   {fmt(s.acc_body)}",
        f"omega_body [rad/s]: {fmt(s.omega_body)}",
        f"ori_body [rad]:     {fmt(s.ori_body)}",
        f"jpos_leg [rad]:     {fmt(s.jpos_leg)}",
        f"jvel_leg [rad/s]:   {fmt(s.jvel_leg)}",
        f"jtau_leg [Nm]:      {fmt(s.jtau_leg)}",
        f"grf_left [N]:       {fmt(s.grf_left)}",
        f"grf_right [N]:      {fmt(s.grf_right)}",
    ]
    return "\n".join(lines)
