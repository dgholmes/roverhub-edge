from __future__ import annotations

from typing import Optional

FAULT_SDK_STATES = {"recovery"}
WALK_SDK_STATES = {"walk", "flying_trot", "wheel_loco"}


def compute_abstract_state(
    sdk_state: str,
    estop_active: bool,
    obstacle_avoidance_enabled: bool,
    mission_active: bool = False,
    mission_phase: Optional[str] = None,
) -> str:
    """Maps SDK state + bridge-local context onto the 9-state RoverHub
    abstract state machine (docs/04-edge-bridge.md SS4)."""

    if estop_active:
        return "E_STOP"
    if sdk_state in FAULT_SDK_STATES:
        return "FAULT"
    if sdk_state == "stand_down":
        return "PASSIVE"
    if sdk_state in ("balance_stand", "ready"):
        return "STAND"
    if sdk_state in WALK_SDK_STATES:
        if mission_active and mission_phase == "returning":
            return "RETURNING"
        if mission_active and mission_phase == "docking":
            return "DOCKING"
        if mission_active:
            return "AUTO_MISSION"
        if obstacle_avoidance_enabled:
            return "ASSISTED"
        return "MANUAL"
    return "FAULT"
