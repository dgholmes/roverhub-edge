from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from dobot_adapter import DobotAdapter
from safety_manager import SafetyManager
from shared.schemas.commands import Command, CommandStageEvent

AckHandler = Callable[[Command], None]
BatteryProvider = Callable[[], float]

ESTOP_TARGET_STATE = "emergency"
RECOVERY_TARGET_STATE = "balance_stand"


class CommandSender:
    """Executes commands against dobot_adapter, gated by safety_manager,
    emitting ACK stage updates via on_ack. Covers the full wired command
    surface -- see shared.schemas.commands.WIRED_COMMAND_TYPES. Only one
    command executes at a time (docs/04-edge-bridge.md SS3.5 -- this
    build has no queueing since nothing yet issues overlapping commands)."""

    def __init__(
        self,
        adapter: DobotAdapter,
        safety: SafetyManager,
        on_ack: AckHandler,
        battery_percent_provider: BatteryProvider,
    ):
        self._adapter = adapter
        self._safety = safety
        self._on_ack = on_ack
        self._battery_percent_provider = battery_percent_provider

    async def handle_command(self, command: Command) -> None:
        self._advance(command, "cloud_received")
        self._advance(command, "cloud_validated")

        try:
            sdk_state: Optional[str] = await self._adapter.get_sdk_state()
            sdk_connected = True
        except Exception:
            sdk_state = None
            sdk_connected = False

        try:
            robot_type = await self._adapter.get_robot_config()
        except Exception:
            robot_type = None

        command_params = command.params or {}
        # SET_SPEED_RATIO carries its value under "ratio"; VELOCITY_SEQUENCE
        # under "speed_ratio". Check both so safety clamping applies to either.
        requested_speed_ratio = command_params.get("speed_ratio", command_params.get("ratio"))

        check = self._safety.check(
            command_type=command.type,
            sdk_connected=sdk_connected,
            battery_percent=self._battery_percent_provider(),
            robot_type=robot_type,
            speed_ratio=requested_speed_ratio,
        )
        if not check.approved:
            command.failure_reason = check.rejection_code
            self._advance(command, "execution_failed")
            return

        self._advance(command, "bridge_received")
        self._advance(command, "local_safety_check")

        try:
            await self._execute(command, sdk_state, check.clamped_speed_ratio)
        except Exception as exc:
            command.failure_reason = str(exc)
            self._advance(command, "execution_failed")
            return

        self._advance(command, "sdk_sent")
        self._advance(command, "robot_acknowledged")
        self._advance(command, "execution_started")
        self._advance(command, "execution_completed")

    async def _execute(self, command: Command, sdk_state: Optional[str], clamped_speed_ratio: Optional[int]) -> None:
        params = command.params or {}
        if command.type == "ESTOP":
            self._safety.trigger_estop()
            await self._adapter.set_state(ESTOP_TARGET_STATE)
        elif command.type == "RESET_ESTOP":
            if sdk_state != "passive":
                raise RuntimeError("robot is not in passive state; cannot clear E-Stop")
            await self._adapter.set_state(RECOVERY_TARGET_STATE)
            self._safety.clear_estop()
        elif command.type == "SET_OBSTACLE_AVOIDANCE":
            enabled = bool(params.get("enabled", True))
            await self._adapter.enable_obstacle_avoidance(enabled)
        elif command.type in ("TAKE_CONTROL", "RELEASE_CONTROL"):
            pass  # backend-only concept -- no SDK call
        elif command.type == "SET_STATE":
            await self._adapter.set_state(params["state"])
        elif command.type == "SET_GAIT":
            # Gait names are SDK target-state names (walk/flying_trot/rl on
            # quad, wheel_loco/drift on wheel) -- set_target_state() handles
            # the actual FSM transition; an unsupported gait for the current
            # robot type raises ValueError, caught by handle_command() same
            # as any other execution failure.
            await self._adapter.set_state(params["gait"])
        elif command.type == "CHANGE_MODE":
            await self._adapter.change_mode()
        elif command.type == "SET_SPEED_RATIO":
            await self._adapter.set_speed_ratio(clamped_speed_ratio if clamped_speed_ratio is not None else params["ratio"])
        elif command.type == "VELOCITY_SEQUENCE":
            speed_ratio = clamped_speed_ratio if clamped_speed_ratio is not None else params.get("speed_ratio")
            await self._adapter.send_velocity_sequence(params["steps"], params.get("gait", "walk"), speed_ratio)
        elif command.type == "LINE_WALK":
            await self._adapter.line_walk(params["direction"], params.get("distance", 1.0))
        elif command.type == "ROTATE":
            await self._adapter.rotate(params["direction"], params.get("angle", 90.0))
        elif command.type == "CIRCLE":
            await self._adapter.circle(params.get("direction", "left"), params.get("turns", 1))
        elif command.type == "BALANCE_AXIS":
            await self._adapter.balance_axis(params["axis"], params["value"], params.get("duration", 2.0), params.get("mode", "dynamic"))
        elif command.type == "BALANCE_NEUTRAL":
            await self._adapter.balance_neutral()
        elif command.type == "BALANCE_SEQUENCE":
            await self._adapter.balance_sequence(params["steps"])
        elif command.type == "DYNAMIC_POSE":
            await self._adapter.dynamic_pose(
                params.get("duration", 2.0), params.get("roll_deg", 0.0),
                params.get("pitch_deg", 0.0), params.get("yaw_deg", 0.0), params.get("height_m", 0.0),
            )
        elif command.type == "STATIC_POSE":
            await self._adapter.static_pose(
                params.get("duration", 2.0), params.get("roll_deg", 0.0),
                params.get("pitch_deg", 0.0), params.get("yaw_deg", 0.0), params.get("height_m", 0.0),
            )
        elif command.type == "LED_SIGNAL":
            await self._adapter.set_led(params)
        elif command.type == "SPEAK":
            await self._adapter.speak(params["file_path"])
        else:
            raise RuntimeError(f"unsupported command type for this build: {command.type}")

    def _advance(self, command: Command, stage: str) -> None:
        command.current_stage = stage
        command.stages.append(CommandStageEvent(stage=stage, at=datetime.now(timezone.utc).isoformat()))
        self._on_ack(command)
