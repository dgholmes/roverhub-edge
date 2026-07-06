"""Menu-driven CLI exercising every RobotClient / SimulatedRobotClient method.

Usage:
    python feature_tester.py --simulate
    python feature_tester.py --address 192.168.1.6:50051
"""
from __future__ import annotations

import grpc

from shared import ConnectionConfig, build_arg_parser, connect, detect_mode, is_success

# ---------------------------------------------------------------------------
# Action functions (testable independent of input()/print())
# ---------------------------------------------------------------------------


def action_get_state_name(client) -> str:
    return client.get_current_state_name()


def action_get_full_state(client) -> str:
    from shared import format_telemetry_block

    return format_telemetry_block(client.get_state())


def action_get_motions(client) -> str:
    res = client.get_motions()
    if not is_success(res):
        return f"Failed: {getattr(res, 'message', 'unknown error')}"
    lines = [f"Available motions ({len(res.motions)}):"]
    for m in res.motions:
        desc = res.descriptions.get(m.motion_id, "")
        lines.append(f"  [{m.motion_id}] {desc}")
    return "\n".join(lines)


def action_set_speed_ratio(client, ratio: int) -> str:
    client.set_speed_ratio(ratio)
    return f"speed_ratio -> {client.get_speed_ratio()}"


def action_set_obstacle_avoidance(client, enabled: bool) -> str:
    client.set_obstacle_avoidance(enabled)
    return f"obstacle_avoidance -> {client.get_obstacle_avoidance()}"


def valid_states_for(client) -> list:
    from dobot_quad.robot_client import VALID_STATES, VALID_WHEEL_STATES

    return sorted(VALID_WHEEL_STATES if client.is_quad_wheel() else VALID_STATES)


def action_set_target_state(client, state_name: str) -> str:
    res = client.set_target_state(state_name)
    return f"-> {client.get_current_state_name()} (success={is_success(res)})"


def action_change_mode(client) -> str:
    client.change_mode()
    return f"-> robot_type={client.get_robot_type()}"


STATE_WRAPPER_NAMES = [
    "passive", "ready", "stand_down", "balance_stand", "walk", "rl",
    "flying_trot", "choreo", "dance", "wave", "jump", "recovery",
]

WHEEL_WRAPPER_NAMES = [
    "passive", "ready", "stand_down", "wheel_loco", "drift", "handstand",
]


def action_call_wrapper(client, wrapper_name: str) -> str:
    method = getattr(client, wrapper_name)
    res = method()
    return f"{wrapper_name} -> {client.get_current_state_name()} (success={is_success(res)})"


DEMO_VELOCITY_STEPS = [
    (0.8, 0.0, 0.0, 2.0),
    (0.0, 0.0, 0.0, 1.0),
    (-0.8, 0.0, 0.0, 2.0),
    (0.0, 0.0, 0.0, 1.0),
]


def action_velocity_sequence_demo(client, gait: str) -> str:
    res = client.velocity_sequence(DEMO_VELOCITY_STEPS, gait=gait, speed_ratio=60)
    return f"velocity_sequence({gait}) -> success={is_success(res)}"


def action_line_walk(client, direction, distance: float) -> str:
    res = client.line_walk(direction, distance)
    return f"line_walk({direction}, {distance}m) -> success={is_success(res)}"


def action_rotate(client, direction: str, angle: float) -> str:
    res = client.rotate(direction, angle)
    return f"rotate({direction}, {angle}deg) -> success={is_success(res)}"


def action_circle(client, direction: str, turns: int) -> str:
    res = client.circle(direction, turns)
    return f"circle({direction}, {turns}) -> success={is_success(res)}"


DEMO_BALANCE_SEQUENCE = [
    ("balance_pitch", 15.0, 0.5, "dynamic"),
    ("balance_yaw", 20.0, 0.5, "dynamic"),
    ("balance_roll", -30.0, 0.5, "dynamic"),
    ("balance_height", -0.12, 0.5, "dynamic"),
    ("balance_neutral", 0.0, 0.5, "dynamic"),
]


def action_balance_axis(client, axis: str, value: float, duration: float, mode: str) -> str:
    method = getattr(client, f"balance_{axis}")
    res = method(value, duration=duration, mode=mode)
    return f"balance_{axis}({value}, {duration}s, {mode}) -> success={is_success(res)}"


def action_balance_sequence_demo(client) -> str:
    res = client.balance_sequence(DEMO_BALANCE_SEQUENCE)
    return f"balance_sequence(demo) -> success={is_success(res)}"


def action_dynamic_pose_demo(client) -> str:
    res = client.dynamic_pose(2.0, roll_deg=20.0, pitch_deg=10.0, yaw_deg=15.0, height_m=-0.08)
    return f"dynamic_pose(demo) -> success={is_success(res)}"


def action_static_pose_demo(client) -> str:
    res = client.static_pose(3.0, roll_deg=-20.0, pitch_deg=-10.0, yaw_deg=-15.0, height_m=-0.08)
    return f"static_pose(demo) -> success={is_success(res)}"


def action_kill_robot(client, confirmation: str) -> str:
    """Engineering-only. Requires the exact confirmation text 'KILL'.

    kill_robot terminates the robot controller entirely — not recoverable
    like the soft E-stop (docs/03-sdk-integration.md §9.2). Never bind this
    to a single key or menu shortcut.
    """
    if confirmation != "KILL":
        return "Aborted: kill_robot requires typing KILL exactly to confirm."
    res = client.execute("kill_robot")
    return f"kill_robot -> success={is_success(res)}"


# ---------------------------------------------------------------------------
# Interactive menu (manually verified, not unit tested)
# ---------------------------------------------------------------------------


def _print_menu() -> None:
    print(
        """
==================== RoverHub SDK Playground - Feature Tester ====================
 1) Connection & Info
 2) State Machine
 3) Motion Enumeration
 4) Configuration
 5) Velocity Sequence
 6) Line Walk / Rotation
 7) Balance & Pose
 8) Engineering (dangerous)
 0) Quit
"""
    )


def _menu_connection_info(client) -> None:
    print("a) get_current_state_name  b) get_state (full telemetry)")
    print("c) get_robot_type/is_quad/is_quad_wheel  d) get_speed_ratio  e) get_obstacle_avoidance")
    choice = input("> ").strip().lower()
    if choice == "a":
        print(action_get_state_name(client))
    elif choice == "b":
        print(action_get_full_state(client))
    elif choice == "c":
        print(
            f"robot_type={client.get_robot_type()} is_quad={client.is_quad()} "
            f"is_quad_wheel={client.is_quad_wheel()}"
        )
    elif choice == "d":
        print(client.get_speed_ratio())
    elif choice == "e":
        print(client.get_obstacle_avoidance())


def _menu_state_machine(client) -> None:
    states = valid_states_for(client)
    wrappers = WHEEL_WRAPPER_NAMES if client.is_quad_wheel() else STATE_WRAPPER_NAMES
    print("Convenience wrappers:", ", ".join(wrappers))
    print("Or type any valid state name:", ", ".join(states))
    print("Or 'change_mode'")
    choice = input("> ").strip().lower()
    if choice == "change_mode":
        print(action_change_mode(client))
    elif choice in wrappers:
        print(action_call_wrapper(client, choice))
    else:
        print(action_set_target_state(client, choice))


def _menu_motions(client) -> None:
    print(action_get_motions(client))


def _menu_configuration(client) -> None:
    print("a) set_speed_ratio  b) set_obstacle_avoidance")
    choice = input("> ").strip().lower()
    if choice == "a":
        ratio = int(input("ratio [10-100]: "))
        print(action_set_speed_ratio(client, ratio))
    elif choice == "b":
        enabled = input("on/off: ").strip().lower() == "on"
        print(action_set_obstacle_avoidance(client, enabled))


def _menu_velocity_sequence(client) -> None:
    gaits = ["wheel_loco"] if client.is_quad_wheel() else ["walk", "flying_trot"]
    gait = input(f"gait {gaits} (enter={gaits[0]}): ").strip().lower() or gaits[0]
    print(action_velocity_sequence_demo(client, gait))


def _menu_line_walk_rotation(client) -> None:
    print("a) walk_forward  b) walk_backward  c) move_left  d) move_right")
    print("e) rotate_left  f) rotate_right  g) circle")
    choice = input("> ").strip().lower()
    if choice == "a":
        print(action_line_walk(client, "forward", float(input("distance m: ") or "1.0")))
    elif choice == "b":
        print(action_line_walk(client, "backward", float(input("distance m: ") or "1.0")))
    elif choice == "c":
        print(action_line_walk(client, "left", float(input("distance m: ") or "1.0")))
    elif choice == "d":
        print(action_line_walk(client, "right", float(input("distance m: ") or "1.0")))
    elif choice == "e":
        print(action_rotate(client, "left", float(input("angle deg: ") or "90")))
    elif choice == "f":
        print(action_rotate(client, "right", float(input("angle deg: ") or "90")))
    elif choice == "g":
        direction = input("direction (left/right): ").strip().lower() or "left"
        turns = int(input("turns: ") or "1")
        print(action_circle(client, direction, turns))


def _menu_balance_pose(client) -> None:
    if client.is_quad_wheel():
        print("Not supported on MINI_QUAD_WHEEL.")
        return
    client.balance_stand()
    print("a) balance_pitch  b) balance_yaw  c) balance_roll  d) balance_height")
    print("e) balance_neutral  f) balance_sequence demo  g) dynamic_pose demo  h) static_pose demo")
    choice = input("> ").strip().lower()
    axis_map = {"a": "pitch", "b": "yaw", "c": "roll", "d": "height"}
    if choice in axis_map:
        value = float(input("value: "))
        duration = float(input("duration s: ") or "2.0")
        mode = input("mode (dynamic/static): ").strip().lower() or "dynamic"
        print(action_balance_axis(client, axis_map[choice], value, duration, mode))
    elif choice == "e":
        client.balance_neutral()
        print("balance_neutral -> done")
    elif choice == "f":
        print(action_balance_sequence_demo(client))
    elif choice == "g":
        print(action_dynamic_pose_demo(client))
    elif choice == "h":
        print(action_static_pose_demo(client))


def _menu_engineering(client) -> None:
    print("!!! kill_robot terminates the robot controller. NOT recoverable like E-stop. !!!")
    confirmation = input("Type KILL to confirm, anything else to abort: ").strip()
    print(action_kill_robot(client, confirmation))


MENU_HANDLERS = {
    "1": _menu_connection_info,
    "2": _menu_state_machine,
    "3": _menu_motions,
    "4": _menu_configuration,
    "5": _menu_velocity_sequence,
    "6": _menu_line_walk_rotation,
    "7": _menu_balance_pose,
    "8": _menu_engineering,
}


def run(config: ConnectionConfig) -> None:
    client = connect(config)
    label = "SIMULATED" if config.simulate else config.address
    print(f"Connected ({label}). Mode: {detect_mode(client)}")
    try:
        while True:
            _print_menu()
            choice = input("> ").strip()
            if choice == "0":
                break
            handler = MENU_HANDLERS.get(choice)
            if handler is None:
                print("Unknown option.")
                continue
            try:
                handler(client)
            except ValueError as exc:
                print(f"Invalid input: {exc}")
            except grpc.RpcError as exc:
                print(f"Connection error: {exc}")
    finally:
        print("Shutting down: stand_down -> passive")
        try:
            client.stand_down(show_progress=False)
            client.passive(show_progress=False)
        except Exception:
            pass
        client.close()


def main() -> None:
    parser = build_arg_parser("RoverHub SDK Playground - menu-driven feature tester")
    args = parser.parse_args()
    config = ConnectionConfig(
        address=args.address, simulate=args.simulate, sim_robot_type=args.sim_robot_type
    )
    run(config)


if __name__ == "__main__":
    main()
