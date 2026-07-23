"""Connection and formatting helpers shared by low_level_feature_tester.py.

Standalone low-level (DDS) SDK-discovery tool -- separate from robot_bridge/,
same relationship sdk_playground/ has to it (see CLAUDE.md's SDK Isolation
section). Talks to dds_middleware_python directly, exactly as the vendored
SDK's own low_level/python/e1-e9_*.py examples do -- every field name, topic,
and unit here is taken from those examples and docs/docs/api/low_level.md,
not guessed.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

DEFAULT_CONFIG_PATH = "config/dds_config.yaml"
DEFAULT_DOMAIN_ID = 0

RGB_TOPICS = {"front": "rt/camera/camera2/image_compressed", "back": "rt/camera/camera3/image_compressed"}
DEPTH_TOPICS = {"front": "rt/camera/camera2/image_depth", "back": "rt/camera/camera3/image_depth"}
LOWER_STATE_TOPIC = "rt/lower/state"
LEDS_CMD_TOPIC = "rt/leds/cmd"
VOICE_CMD_TOPIC = "rt/voice/cmd"
VOICE_STATE_TOPIC = "rt/voice/state"
LOWER_CMD_TOPIC = "rt/lower/cmd"

NUM_LOWER_MOTORS = 16

# E9's motor offset table -- see low_level.md's "Motor Offset" section.
# Maps the 12 actuated joints onto the 16-motor hardware index space.
NUM_ACTUATED_MOTORS = 12
ABS2HW = [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14]
MOTOR_OFFSET = [
    -0.05, -0.5, 1.17, 0.0, 0.05, -0.5, 1.17, 0.0,
    -0.05, 0.5, -1.17, 0.0, 0.05, 0.5, -1.17, 0.0,
]

LED_NAMES = ["leg_light1", "leg_light2", "leg_light3", "leg_light4", "fill_light1", "fill_light3"]


@dataclass
class ConnectionConfig:
    config_path: str
    domain_id: int
    use_config_file: bool


def build_arg_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config", default=DEFAULT_CONFIG_PATH,
        help=f"Path to a dds_config.yaml (default: {DEFAULT_CONFIG_PATH}).",
    )
    parser.add_argument(
        "--domain-id", type=int, default=None,
        help="Use a bare DDS domain ID instead of a config file (e.g. --domain-id 0).",
    )
    return parser


def config_from_args(args) -> ConnectionConfig:
    if args.domain_id is not None:
        return ConnectionConfig(config_path="", domain_id=args.domain_id, use_config_file=False)
    return ConnectionConfig(config_path=args.config, domain_id=DEFAULT_DOMAIN_ID, use_config_file=True)


def connect(config: ConnectionConfig):
    """Create a real dds_middleware_python.PyDDSMiddleware. Only reachable
    when actually run on a host with the DDS middleware installed (Jetson or
    Raspberry Pi wired to the robot's DDS network via Ethernet --
    docs/09-low-level-sdk.md) -- never importable on a plain dev machine,
    same constraint as robot_bridge/dobot_adapter.py's real_dds_middleware_factory."""
    import dds_middleware_python as dds

    if config.use_config_file:
        return dds.PyDDSMiddleware(config.config_path)
    return dds.PyDDSMiddleware(config.domain_id)


def format_imu(imu) -> str:
    return (
        f"Quaternion (w,x,y,z): {[round(v, 4) for v in imu.quaternion()]}\n"
        f"Gyroscope (rad/s):    {[round(v, 4) for v in imu.gyroscope()]}\n"
        f"Accelerometer (m/s^2):{[round(v, 4) for v in imu.accelerometer()]}\n"
        f"RPY (rad):            {[round(v, 4) for v in imu.rpy()]}"
    )


def format_motor(index: int, motor) -> str:
    return (
        f"Motor[{index:2d}]: mode={motor.mode()} q={motor.q():.4f} rad dq={motor.dq():.4f} rad/s "
        f"tau_est={motor.tau_est():.4f} N*m temp={motor.motor_temp()} degC"
    )


def format_all_motors(motor_states) -> str:
    return "\n".join(format_motor(i, motor_states[i]) for i in range(NUM_LOWER_MOTORS))


def format_bms(bms) -> str:
    return f"Battery Level: {bms.battery_level()}"


def format_lower_state(state) -> str:
    return (
        format_imu(state.imu_state())
        + "\n"
        + format_all_motors(state.motor_state())
        + "\n"
        + format_bms(state.bms_state())
    )


def format_compressed_image_meta(data) -> str:
    return (
        f"Frame ID: {data.header().frame_id()}  Format: {data.format()}  "
        f"Size: {len(data.data())} bytes  "
        f"Timestamp: {data.header().stamp().sec()}.{data.header().stamp().nanosec():09d}"
    )


def format_depth_image_meta(depth_msg) -> str:
    return (
        f"{depth_msg.width()}x{depth_msg.height()} encoding={depth_msg.encoding()} "
        f"step={depth_msg.step()} bigendian={depth_msg.is_bigendian()} "
        f"size={len(depth_msg.data())} bytes"
    )


def format_voice_state_meta(voice_state_msg) -> str:
    return f"Data size: {len(voice_state_msg.data_())} bytes  Angle: {voice_state_msg.angle_():.2f} deg"


def hw_to_logical(motor_states, hw: int) -> float:
    """Read side of E9's motor-offset conversion: hardware angle -> logical joint angle."""
    return motor_states[hw].q() - MOTOR_OFFSET[hw]


def logical_to_hw(q_logical: float, hw: int) -> float:
    """Command side of E9's motor-offset conversion: logical joint angle -> hardware angle."""
    return q_logical + MOTOR_OFFSET[hw]
