from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

# State names from docs/03-sdk-integration.md section 7.1 (quad) and 7.2 (wheel).
# Hand-rolled rather than imported from dobot_quad so this test fixture never
# touches the vendored SDK (see Global Constraints: only dobot_adapter.py
# imports it, and edge/sdk_playground/ is a separate tool, not a dependency).
VALID_STATES = {
    "emergency", "passive", "ready", "stand_down", "balance_stand", "walk",
    "rl", "flying_trot", "choreo", "wave", "dance0", "jump", "recovery",
    "change_mode", "wheel_loco", "drift", "handstand",
}


@dataclass
class FakeRobotState:
    pos_body: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    vel_body: Tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class FakeStateResponse:
    success: bool
    current_state: str
    current_speed_ratio: int
    obstacle_avoidance_enabled: bool
    robot_state: FakeRobotState = field(default_factory=FakeRobotState)
    message: str = ""


@dataclass
class FakeExecResponse:
    success: bool
    current_state: str = ""
    message: str = ""


class FakeRobotClient:
    """Test-only stand-in for dobot_quad.RobotClient's method surface used by
    dobot_adapter.py. Battery has no real SDK/DDS source this round (no BMS/
    DDS simulation exists) -- battery_percent is a static fixture value, not
    a simulated drain."""

    def __init__(self, robot_type: str = "quad", battery_percent: float = 87.5):
        if robot_type not in ("quad", "wheel"):
            raise ValueError("robot_type must be 'quad' or 'wheel'")
        self.robot_type = robot_type
        self.battery_percent = battery_percent
        self._state = "stand_down"
        self._speed_ratio = 50
        self._obstacle_avoidance = True
        self._pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._vel: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.safety_ready_called = False
        self.speed_ratio = 50
        self.last_velocity_sequence = None
        self.last_line_walk = None
        self.last_rotate = None
        self.last_circle = None

    def enable_safety_ready(self) -> None:
        self.safety_ready_called = True

    def is_quad_wheel(self) -> bool:
        return self.robot_type == "wheel"

    def get_current_state_name(self) -> str:
        return self._state

    def set_target_state(self, target_state: str) -> FakeExecResponse:
        if target_state not in VALID_STATES:
            raise ValueError(f"unknown state: {target_state}")
        self._state = target_state
        return FakeExecResponse(success=True, current_state=self._state)

    def get_obstacle_avoidance(self) -> bool:
        return self._obstacle_avoidance

    def set_obstacle_avoidance(self, enable: bool) -> FakeExecResponse:
        self._obstacle_avoidance = bool(enable)
        return FakeExecResponse(success=True, current_state=self._state)

    def change_mode(self):
        self.robot_type = "wheel" if self.robot_type == "quad" else "quad"
        return FakeExecResponse(success=True, current_state=self._state)

    def set_speed_ratio(self, ratio: int):
        self.speed_ratio = ratio
        return FakeExecResponse(success=True, current_state=self._state)

    def velocity_sequence(self, steps, gait="walk", speed_ratio=None, stand_down_after=True):
        self.last_velocity_sequence = {"steps": steps, "gait": gait, "speed_ratio": speed_ratio}
        return FakeExecResponse(success=True, current_state=self._state)

    def line_walk(self, direction, distance=3.0):
        self.last_line_walk = {"direction": direction, "distance": distance}
        return FakeExecResponse(success=True, current_state=self._state)

    def rotate(self, direction="left", angle=90.0):
        self.last_rotate = {"direction": direction, "angle": angle}
        return FakeExecResponse(success=True, current_state=self._state)

    def circle(self, direction="left", turns=1):
        self.last_circle = {"direction": direction, "turns": turns}
        return FakeExecResponse(success=True, current_state=self._state)

    def get_state(self) -> FakeStateResponse:
        return FakeStateResponse(
            success=True,
            current_state=self._state,
            current_speed_ratio=self._speed_ratio,
            obstacle_avoidance_enabled=self._obstacle_avoidance,
            robot_state=FakeRobotState(pos_body=self._pos, vel_body=self._vel),
        )

    def close(self) -> None:
        pass
