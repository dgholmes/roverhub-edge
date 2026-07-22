from __future__ import annotations

from typing import Optional

FAULT_SDK_STATES = {"recovery"}
WALK_SDK_STATES = {"walk", "flying_trot", "wheel_loco"}

# Every other real SDK state that means "the robot is actively carrying out
# an operator-commanded motion" -- canned gestures (quick actions), fine
# movement (line_walk/rotate/circle -> "rotation"), balance-axis nudges,
# pose commands, and quad/wheel mode-switching. Sourced from
# dobot_adapter.get_motions()'s real response (confirmed via a live
# heartbeat's available_motions list), not guessed -- this list must stay
# in sync with whatever the SDK's get_motions() reports. Treated identically
# to WALK_SDK_STATES below: MANUAL/ASSISTED (or AUTO_MISSION/RETURNING/
# DOCKING if a mission is driving it), never FAULT. `recovery`/`kill_robot`
# are deliberately NOT included: `recovery` is a genuine fault state (see
# FAULT_SDK_STATES); `kill_robot` is never dispatched by this build at all
# (see shared.schemas.commands.WIRED_COMMAND_TYPES) and reaching it would
# indicate the controller terminated, which is correctly still FAULT.
ACTIVE_MOTION_SDK_STATES = {
    "backflip", "balance_height", "balance_neutral", "balance_pitch", "balance_roll",
    "balance_yaw", "change_mode", "choreo", "dance0", "dynamic_pose",
    "flying_trot_velocity_seq", "jump", "line_walk", "rl", "rl_velocity_seq",
    "rotation", "static_pose", "walk_velocity_seq", "wave",
}


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
    if sdk_state in WALK_SDK_STATES or sdk_state in ACTIVE_MOTION_SDK_STATES:
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
