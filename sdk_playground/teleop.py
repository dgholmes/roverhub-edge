"""Real-time keyboard + mouse teleop for the Dobot Quad high-level SDK.

Keyboard (WALK mode, default):
  W/A/S/D   - vx/vy velocity
  Q/E       - yaw rate (turn left/right)
  G         - cycle gait
  [ / ]     - speed ratio -10 / +10
  O         - toggle obstacle avoidance
  Tab       - switch to POSTURE mode
  Space     - immediate soft-stop (passive/emergency, recoverable)
  Esc       - clean shutdown

Mouse (POSTURE mode, entered via Tab):
  Move      - throttled balance_yaw / balance_pitch gestures (not continuous;
              see docs/superpowers/specs/2026-07-05-edge-sdk-playground-design.md
              for why the high-level API can't slave a continuous camera)
  Scroll    - balance_height

Usage:
    python teleop.py --simulate
    python teleop.py --address 192.168.1.6:50051
"""
from __future__ import annotations

import sys
import threading
import time

import grpc

from shared import ConnectionConfig, build_arg_parser, connect, format_state_line

MOVEMENT_KEYS = frozenset({"w", "a", "s", "d", "q", "e"})

GAIT_VELOCITY_LIMITS = {
    "walk": {"vx": (-0.8, 0.8), "vy": (-0.8, 0.8), "vz": (-0.8, 0.8)},
    "flying_trot": {"vx": (0.0, 0.8), "vy": (-0.3, 0.3), "vz": (-0.6, 0.6)},
    "wheel_loco": {"vx": (0.0, 0.8), "vy": (-0.3, 0.3), "vz": (-0.4, 0.4)},
}

MOUSE_SENSITIVITY_YAW = 0.15    # degrees per pixel of accumulated dx
MOUSE_SENSITIVITY_PITCH = 0.15  # degrees per pixel of accumulated dy
MOUSE_DEADZONE_PX = 3


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def compute_velocity(keys: frozenset, gait: str) -> tuple:
    """Pure function: currently-held movement keys -> (vx, vy, vz).

    vy > 0 is left, vy < 0 is right (matches the SDK's own velocity_sequence
    example comments). vz > 0 is left/CCW turn, vz < 0 is right/CW turn
    (matches rotate_walk's angle-sign convention).
    """
    limits = GAIT_VELOCITY_LIMITS[gait]
    vx = 0.0
    vy = 0.0
    vz = 0.0
    if "w" in keys:
        vx += limits["vx"][1]
    if "s" in keys and limits["vx"][0] < 0:
        vx += limits["vx"][0]
    if "a" in keys:
        vy += limits["vy"][1]
    if "d" in keys:
        vy += limits["vy"][0]
    if "q" in keys:
        vz += limits["vz"][1]
    if "e" in keys:
        vz += limits["vz"][0]
    vx = _clamp(vx, *limits["vx"])
    vy = _clamp(vy, *limits["vy"])
    vz = _clamp(vz, *limits["vz"])
    return (vx, vy, vz)


class KeyState:
    """Thread-safe set of currently-held movement keys."""

    def __init__(self):
        self._lock = threading.Lock()
        self._held = set()

    def press(self, key: str) -> None:
        if key not in MOVEMENT_KEYS:
            return
        with self._lock:
            self._held.add(key)

    def release(self, key: str) -> None:
        with self._lock:
            self._held.discard(key)

    def snapshot(self) -> frozenset:
        with self._lock:
            return frozenset(self._held)


class MouseBalanceAccumulator:
    """Accumulates raw mouse deltas and converts them into throttled balance
    gesture magnitudes (degrees) on each flush() call."""

    def __init__(self):
        self._dx = 0.0
        self._dy = 0.0

    def add_delta(self, dx: float, dy: float) -> None:
        self._dx += dx
        self._dy += dy

    def flush(self):
        """Return (yaw_deg, pitch_deg) for motion accumulated since the last
        flush, or None if it's within the deadzone. Always resets the
        accumulator, even when returning None."""
        dx, dy = self._dx, self._dy
        self._dx = 0.0
        self._dy = 0.0
        if abs(dx) < MOUSE_DEADZONE_PX and abs(dy) < MOUSE_DEADZONE_PX:
            return None
        yaw_deg = dx * MOUSE_SENSITIVITY_YAW
        pitch_deg = -dy * MOUSE_SENSITIVITY_PITCH
        return (yaw_deg, pitch_deg)


class TeleopController:
    """Owns teleop mode/gait/speed state and issues one client call per tick.

    Pure with respect to I/O: no pynput or threading lives here. teleop.run()
    wires up listeners/timers and calls tick_walk()/tick_posture() on them.
    """

    GAITS_QUAD = ["walk", "flying_trot"]
    GAITS_WHEEL = ["wheel_loco"]

    def __init__(self, client, tick_seconds: float = 0.25):
        self.client = client
        self.tick_seconds = tick_seconds
        self.mode = "WALK"
        self.gaits = self.GAITS_WHEEL if client.is_quad_wheel() else self.GAITS_QUAD
        self.gait_index = 0
        self.key_state = KeyState()
        self.mouse_acc = MouseBalanceAccumulator()

    @property
    def gait(self) -> str:
        return self.gaits[self.gait_index]

    def cycle_gait(self) -> str:
        self.gait_index = (self.gait_index + 1) % len(self.gaits)
        return self.gait

    def adjust_speed(self, delta: int) -> int:
        current = self.client.get_speed_ratio()
        self.client.set_speed_ratio(current + delta)
        return self.client.get_speed_ratio()

    def toggle_obstacle_avoidance(self) -> bool:
        current = self.client.get_obstacle_avoidance()
        self.client.set_obstacle_avoidance(not current)
        return self.client.get_obstacle_avoidance()

    def enter_walk_mode(self) -> None:
        self.mode = "WALK"
        if self.client.get_current_state_name() not in ("walk", "flying_trot", "wheel_loco"):
            self.client.ready(show_progress=False)
            self.client.balance_stand(show_progress=False)
            self.client.set_target_state(self.gait, show_progress=False)

    def enter_posture_mode(self) -> None:
        self.mode = "POSTURE"
        if self.client.get_current_state_name() != "balance_stand":
            self.client.ready(show_progress=False)
            self.client.balance_stand(show_progress=False)

    def toggle_mode(self) -> str:
        if self.mode == "WALK":
            self.enter_posture_mode()
        else:
            self.enter_walk_mode()
        return self.mode

    def emergency_stop(self):
        return self.client.passive(show_progress=False)

    def tick_walk(self):
        """Compute velocity from currently-held keys and issue one tick's
        velocity_sequence call. Returns the (vx, vy, vz) issued."""
        keys = self.key_state.snapshot()
        vx, vy, vz = compute_velocity(keys, self.gait)
        self.client.velocity_sequence(
            [(vx, vy, vz, self.tick_seconds)],
            gait=self.gait,
            stand_down_after=False,
            show_progress=False,
        )
        return (vx, vy, vz)

    def tick_posture(self, dx: float = 0.0, dy: float = 0.0):
        """Feed one sample of mouse delta; on flush, issue a balance gesture.
        Returns the (yaw_deg, pitch_deg) issued, or None if below deadzone."""
        self.mouse_acc.add_delta(dx, dy)
        result = self.mouse_acc.flush()
        if result is None:
            return None
        yaw_deg, pitch_deg = result
        if yaw_deg:
            self.client.balance_yaw(yaw_deg, duration=0.5, mode="dynamic", show_progress=False)
        if pitch_deg:
            self.client.balance_pitch(pitch_deg, duration=0.5, mode="dynamic", show_progress=False)
        return (yaw_deg, pitch_deg)

    def adjust_height(self, delta_m: float):
        return self.client.balance_height(delta_m, duration=0.5, mode="dynamic", show_progress=False)


# ---------------------------------------------------------------------------
# Interactive wiring (manually verified, not unit tested)
# ---------------------------------------------------------------------------


def run(config: ConnectionConfig) -> None:
    from pynput import keyboard, mouse

    client = connect(config)
    controller = TeleopController(client)
    controller.enter_walk_mode()

    stop_event = threading.Event()
    last_mouse = {"x": None, "y": None}

    def on_press(key):
        char = getattr(key, "char", None)
        char = char.lower() if char else None
        if char in MOVEMENT_KEYS:
            controller.key_state.press(char)
        elif char == "g":
            controller.cycle_gait()
        elif char == "o":
            controller.toggle_obstacle_avoidance()
        elif char == "[":
            controller.adjust_speed(-10)
        elif char == "]":
            controller.adjust_speed(10)
        if key == keyboard.Key.space:
            controller.emergency_stop()
        elif key == keyboard.Key.tab:
            controller.toggle_mode()
        elif key == keyboard.Key.esc:
            stop_event.set()
            return False
        return None

    def on_release(key):
        char = getattr(key, "char", None)
        char = char.lower() if char else None
        if char in MOVEMENT_KEYS:
            controller.key_state.release(char)

    def on_move(x, y):
        if controller.mode != "POSTURE":
            last_mouse["x"], last_mouse["y"] = x, y
            return
        if last_mouse["x"] is None:
            last_mouse["x"], last_mouse["y"] = x, y
            return
        dx = x - last_mouse["x"]
        dy = y - last_mouse["y"]
        last_mouse["x"], last_mouse["y"] = x, y
        try:
            controller.tick_posture(dx=dx, dy=dy)
        except (grpc.RpcError, ValueError) as exc:
            print(f"\n[posture error] {exc}")

    def on_scroll(x, y, dx, dy):
        if controller.mode == "POSTURE":
            try:
                controller.adjust_height(dy * -0.01)
            except (grpc.RpcError, ValueError) as exc:
                print(f"\n[height error] {exc}")

    def control_loop():
        while not stop_event.is_set():
            if controller.mode == "WALK":
                try:
                    controller.tick_walk()
                except grpc.RpcError as exc:
                    print(f"\n[connection error] {exc}")
                except ValueError as exc:
                    print(f"\n[invalid command] {exc}")
            time.sleep(controller.tick_seconds)

    def status_loop():
        while not stop_event.is_set():
            try:
                state = client.get_state()
                line = format_state_line(state)
            except grpc.RpcError as exc:
                line = f"connection error: {exc}"
            keys = ",".join(sorted(controller.key_state.snapshot())) or "-"
            sys.stdout.write(f"\r[{controller.mode}] {line} gait={controller.gait} keys={keys}      ")
            sys.stdout.flush()
            time.sleep(0.5)

    print(__doc__)
    kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    mouse_listener = mouse.Listener(on_move=on_move, on_scroll=on_scroll)
    kb_listener.start()
    mouse_listener.start()
    threading.Thread(target=control_loop, daemon=True).start()
    threading.Thread(target=status_loop, daemon=True).start()

    try:
        kb_listener.join()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        print("\nShutting down: stand_down -> passive")
        try:
            client.stand_down(show_progress=False)
            client.passive(show_progress=False)
        except Exception:
            pass
        client.close()


def main() -> None:
    parser = build_arg_parser("RoverHub SDK Playground - real-time keyboard/mouse teleop")
    args = parser.parse_args()
    config = ConnectionConfig(
        address=args.address, simulate=args.simulate, sim_robot_type=args.sim_robot_type
    )
    run(config)


if __name__ == "__main__":
    main()
