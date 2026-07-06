"""In-memory stand-in for dobot_quad.RobotClient — no gRPC, no hardware.

Reuses the real SDK's validation helpers and constants (from
dobot_quad.robot_client) so simulated runs reject the same bad inputs the
real robot would, and stay correct if the SDK's limits change.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from dobot_quad.robot_client import (
    validate_state,
    validate_gait,
    validate_balance_motion,
    resolve_direction,
    resolve_rotate_direction,
    clamp_speed_ratio,
    clamp_distance,
    clamp_angle,
    clamp_angle_signed,
    clamp_balance_value,
    clamp_balance_duration,
    clamp_pose_duration,
    clamp_turns,
)


@dataclass
class FakeRobotState:
    jpos_leg: list = field(default_factory=lambda: [0.0] * 12)
    jpos_leg_des: list = field(default_factory=lambda: [0.0] * 12)
    jvel_leg: list = field(default_factory=lambda: [0.0] * 12)
    jvel_leg_des: list = field(default_factory=lambda: [0.0] * 12)
    jtau_leg: list = field(default_factory=lambda: [0.0] * 12)
    jtau_leg_des: list = field(default_factory=lambda: [0.0] * 12)
    pos_body: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    vel_body: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    acc_body: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    omega_body: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    ori_body: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    grf_left: list = field(default_factory=lambda: [0.0, 0.0])
    grf_right: list = field(default_factory=lambda: [0.0, 0.0])
    grf_vertical_filtered: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])


@dataclass
class FakeStateResponse:
    success: bool
    current_state: str
    current_speed_ratio: int
    obstacle_avoidance_enabled: bool
    robot_type: str
    robot_state: FakeRobotState
    message: str = ""


@dataclass
class FakeMotion:
    motion_id: str


@dataclass
class FakeMotionsResponse:
    success: bool
    motions: list
    descriptions: dict
    message: str = ""


@dataclass
class FakeExecResponse:
    success: bool
    current_state: str = ""
    message: str = ""


QUAD_MOTIONS = {
    "passive": "Emergency halt / passive mode",
    "ready": "Controller active, not standing",
    "stand_down": "Sit / crouch, low power",
    "balance_stand": "Standing, balanced, awaiting commands",
    "walk": "Standard walking gait",
    "rl": "Reinforcement learning gait",
    "flying_trot": "Fast trot gait",
    "choreo": "Scripted choreography",
    "wave": "Wave gesture",
    "dance0": "Dance routine 0",
    "jump": "Jump motion",
    "recovery": "Fault recovery",
    "change_mode": "Switch quad/wheel configuration",
}

WHEEL_MOTIONS = {
    "passive": "Emergency halt / passive mode",
    "ready": "Controller active, wheels down",
    "stand_down": "Low, wheels stationary",
    "wheel_loco": "Wheel locomotion",
    "drift": "Controlled wheel drift",
    "climb": "Climb mode",
    "handstand": "Handstand posture",
    "change_mode": "Switch to quad configuration",
}


class SimulatedRobotClient:
    """Drop-in stand-in for RobotClient. Same public method surface, no network I/O."""

    def __init__(self, robot_type: str = "quad", verbose: bool = True):
        if robot_type not in ("quad", "wheel"):
            raise ValueError("robot_type must be 'quad' or 'wheel'")
        self._robot_type = "miniQuadW" if robot_type == "wheel" else "miniQuad"
        self._state = "stand_down"
        self._speed_ratio = 50
        self._obstacle_avoidance = True
        self._pos = [0.0, 0.0, 0.0]
        self._ori = [0.0, 0.0, 0.0]  # roll, pitch, yaw (degrees)
        self._verbose = verbose
        self._safety_triggered = False

    # ---- Query ----

    def get_motions(self):
        table = WHEEL_MOTIONS if self.is_quad_wheel() else QUAD_MOTIONS
        motions = [FakeMotion(motion_id=k) for k in table]
        return FakeMotionsResponse(success=True, motions=motions, descriptions=dict(table))

    def get_state(self):
        return FakeStateResponse(
            success=True,
            current_state=self._state,
            current_speed_ratio=self._speed_ratio,
            obstacle_avoidance_enabled=self._obstacle_avoidance,
            robot_type=self._robot_type,
            robot_state=FakeRobotState(pos_body=list(self._pos), ori_body=list(self._ori)),
        )

    def get_current_state_name(self) -> str:
        return self._state

    def get_speed_ratio(self) -> int:
        return self._speed_ratio

    def get_obstacle_avoidance(self) -> bool:
        return self._obstacle_avoidance

    def get_robot_type(self) -> str:
        return self._robot_type

    def is_quad(self) -> bool:
        return self._robot_type == "miniQuad"

    def is_quad_wheel(self) -> bool:
        return self._robot_type == "miniQuadW"

    # ---- Configuration ----

    def set_speed_ratio(self, ratio: int):
        self._speed_ratio = clamp_speed_ratio(ratio)
        return FakeExecResponse(success=True, current_state=self._state)

    def set_obstacle_avoidance(self, enable):
        if isinstance(enable, str):
            norm = enable.strip().lower()
            if norm not in ("on", "off"):
                raise ValueError("set_obstacle_avoidance only accepts bool or 'on'/'off'")
            enable = norm == "on"
        self._obstacle_avoidance = bool(enable)
        return FakeExecResponse(success=True, current_state=self._state)

    # ---- State switching ----

    def set_target_state(self, target_state: str, show_progress=True):
        norm = validate_state(target_state)
        self._state = norm
        if self._verbose and show_progress:
            print(f"  [sim] -> state: {self._state}")
        return FakeExecResponse(success=True, current_state=self._state)

    def passive(self, show_progress=True):
        return self.set_target_state("passive", show_progress)

    def emergency(self, show_progress=True):
        return self.passive(show_progress)

    def ready(self, show_progress=True):
        return self.set_target_state("ready", show_progress)

    def stand_down(self, show_progress=True):
        return self.set_target_state("stand_down", show_progress)

    def balance_stand(self, show_progress=True):
        return self.set_target_state("balance_stand", show_progress)

    def walk(self, show_progress=True):
        return self.set_target_state("walk", show_progress)

    def rl(self, show_progress=True):
        return self.set_target_state("rl", show_progress)

    def flying_trot(self, show_progress=True):
        return self.set_target_state("flying_trot", show_progress)

    def choreo(self, show_progress=True):
        return self.set_target_state("choreo", show_progress)

    def dance0(self, show_progress=True, duration=126.5):
        return self.set_target_state("dance0", show_progress)

    def dance(self, duration=126.5, show_progress=True):
        return self.dance0(show_progress=show_progress, duration=duration)

    def wave(self, duration=5.0, show_progress=True):
        return self.set_target_state("wave", show_progress)

    def wave_hand(self, duration=5.0, show_progress=True):
        return self.wave(duration=duration, show_progress=show_progress)

    def jump(self, show_progress=True):
        return self.set_target_state("jump", show_progress)

    def recovery(self, show_progress=True):
        return self.set_target_state("recovery", show_progress)

    def change_mode(self, show_progress=True):
        self._robot_type = "miniQuad" if self.is_quad_wheel() else "miniQuadW"
        self._state = "change_mode"
        if self._verbose and show_progress:
            print(f"  [sim] change_mode -> robot_type: {self._robot_type}")
        return FakeExecResponse(success=True, current_state=self._state)

    def wheel_loco(self, show_progress=True):
        return self.set_target_state("wheel_loco", show_progress)

    def drift(self, show_progress=True):
        return self.set_target_state("drift", show_progress)

    def climb(self, show_progress=True):
        return self.set_target_state("climb", show_progress)

    def handstand(self, show_progress=True):
        return self.set_target_state("handstand", show_progress)

    # ---- Velocity sequence ----

    def velocity_sequence(
        self, vel_seq, gait="walk", speed_ratio=None, stand_down_after=True, show_progress=True
    ):
        norm_gait = validate_gait(gait)
        if speed_ratio is not None:
            self.set_speed_ratio(speed_ratio)

        steps = vel_seq if isinstance(vel_seq, (list, tuple)) else self._parse_velocity_string(vel_seq)
        for vx, vy, vyaw, dur in steps:
            self._pos[0] += vx * dur
            self._pos[1] += vy * dur
            self._ori[2] += vyaw * dur

        self._state = norm_gait
        if self._verbose and show_progress:
            print(f"  [sim] velocity_sequence gait={norm_gait} steps={list(steps)}")
        if stand_down_after:
            self.stand_down(show_progress=False)
        return FakeExecResponse(success=True, current_state=self._state)

    @staticmethod
    def _parse_velocity_string(vel_seq: str):
        steps = []
        for chunk in vel_seq.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            vx, vy, vyaw, dur = (float(x) for x in chunk.split(","))
            steps.append((vx, vy, vyaw, dur))
        return steps

    # ---- Balance motions ----

    def _balance_motion(self, motion_id, value, duration, mode, show_progress):
        validate_balance_motion(motion_id)
        axis = motion_id.replace("balance_", "")
        value = clamp_balance_value(value, axis)
        duration = clamp_balance_duration(duration)
        if axis == "pitch":
            self._ori[1] = value
        elif axis == "roll":
            self._ori[0] = value
        elif axis == "yaw":
            self._ori[2] = -value
        elif axis == "neutral":
            self._ori = [0.0, 0.0, 0.0]
        if self._verbose and show_progress:
            print(f"  [sim] {motion_id}={value} duration={duration} mode={mode}")
        return FakeExecResponse(success=True, current_state=self._state)

    def balance_pitch(self, value, duration=2.0, mode="dynamic", show_progress=True):
        return self._balance_motion("balance_pitch", value, duration, mode, show_progress)

    def balance_yaw(self, value, duration=2.0, mode="dynamic", show_progress=True):
        return self._balance_motion("balance_yaw", value, duration, mode, show_progress)

    def balance_roll(self, value, duration=2.0, mode="dynamic", show_progress=True):
        return self._balance_motion("balance_roll", value, duration, mode, show_progress)

    def balance_height(self, value, duration=2.0, mode="dynamic", show_progress=True):
        return self._balance_motion("balance_height", value, duration, mode, show_progress)

    def balance_neutral(self, duration=0.5, show_progress=True):
        return self._balance_motion("balance_neutral", 0.0, duration, "dynamic", show_progress)

    def balance_sequence(self, motions, show_progress=True):
        last = None
        for motion_id, value, duration, mode in motions:
            last = self._balance_motion(motion_id, value, duration, mode, show_progress)
        return last or FakeExecResponse(success=True, current_state=self._state)

    # ---- Line walk / rotation ----

    def line_walk(self, direction=0, distance=3.0, speed_ratio=None, show_progress=True):
        direction = resolve_direction(direction)
        distance = clamp_distance(distance)
        if speed_ratio is not None:
            self.set_speed_ratio(speed_ratio)
        dx = {0: distance, 1: -distance, 2: 0.0, 3: 0.0}[direction]
        dy = {0: 0.0, 1: 0.0, 2: distance, 3: -distance}[direction]
        self._pos[0] += dx
        self._pos[1] += dy
        if self._verbose and show_progress:
            print(f"  [sim] line_walk direction={direction} distance={distance}")
        return FakeExecResponse(success=True, current_state=self._state)

    def walk_forward(self, distance=3.0, speed_ratio=None, show_progress=True):
        return self.line_walk(0, distance, speed_ratio, show_progress)

    def walk_backward(self, distance=3.0, speed_ratio=None, show_progress=True):
        return self.line_walk(1, distance, speed_ratio, show_progress)

    def move_left(self, distance=3.0, speed_ratio=None, show_progress=True):
        return self.line_walk(2, distance, speed_ratio, show_progress)

    def move_right(self, distance=3.0, speed_ratio=None, show_progress=True):
        return self.line_walk(3, distance, speed_ratio, show_progress)

    def rotate(self, direction="left", angle=90.0, show_progress=True):
        direction = resolve_rotate_direction(direction)
        angle = clamp_angle(angle)
        sign = -1 if direction == 0 else 1
        self._ori[2] += sign * angle
        if self._verbose and show_progress:
            print(f"  [sim] rotate direction={direction} angle={angle}")
        return FakeExecResponse(success=True, current_state=self._state)

    def rotate_left(self, angle=90.0, show_progress=True):
        return self.rotate("left", angle, show_progress)

    def rotate_right(self, angle=90.0, show_progress=True):
        return self.rotate("right", angle, show_progress)

    def circle(self, direction="left", turns=1, show_progress=True):
        turns = clamp_turns(turns)
        return self.rotate(direction, angle=turns * 360.0, show_progress=show_progress)

    def rotate_walk(self, angle=0.0, distance=0.0, speed_ratio=None, show_progress=True):
        angle = clamp_angle_signed(angle)
        distance = clamp_distance(distance)
        if angle >= 0:
            self.rotate("right", angle, show_progress)
        else:
            self.rotate("left", -angle, show_progress)
        return self.walk_forward(distance, speed_ratio, show_progress)

    # ---- Pose blocks ----

    def dynamic_pose(
        self, duration=2.0, roll_deg=0.0, pitch_deg=0.0, yaw_deg=0.0, height_m=0.0, show_progress=True
    ):
        return self._pose_motion(duration, roll_deg, pitch_deg, yaw_deg, height_m, show_progress)

    def static_pose(
        self, duration=2.0, roll_deg=0.0, pitch_deg=0.0, yaw_deg=0.0, height_m=0.0, show_progress=True
    ):
        return self._pose_motion(duration, roll_deg, pitch_deg, yaw_deg, height_m, show_progress)

    def _pose_motion(self, duration, roll_deg, pitch_deg, yaw_deg, height_m, show_progress):
        duration = clamp_pose_duration(duration)
        self._ori[0] = clamp_balance_value(roll_deg, "roll")
        self._ori[1] = clamp_balance_value(pitch_deg, "pitch")
        self._ori[2] = -clamp_balance_value(yaw_deg, "yaw")
        if self._verbose and show_progress:
            print(
                f"  [sim] pose roll={roll_deg} pitch={pitch_deg} yaw={yaw_deg} "
                f"height={height_m} duration={duration}"
            )
        return FakeExecResponse(success=True, current_state=self._state)

    # ---- Engineering / generic execute ----

    def execute(self, *motions, loop=False, show_progress=True):
        """Generic execute passthrough — used for kill_robot-style raw calls."""
        for item in motions:
            motion_id = item if isinstance(item, str) else item[0]
            if motion_id == "kill_robot":
                self._state = "passive"
                if self._verbose:
                    print("  [sim] kill_robot: controller terminated (simulated).")
                return FakeExecResponse(success=True, current_state="passive")
        return FakeExecResponse(success=True, current_state=self._state)

    # ---- Lifecycle ----

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def enable_safety_ready(self):
        self._safety_triggered = False
