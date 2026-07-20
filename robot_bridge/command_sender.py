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
    """Executes the five in-scope command types against dobot_adapter,
    gated by safety_manager, emitting ACK stage updates via on_ack. Only
    one command executes at a time (docs/04-edge-bridge.md SS3.5 -- this
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

        check = self._safety.check(
            command_type=command.type,
            sdk_connected=sdk_connected,
            battery_percent=self._battery_percent_provider(),
        )
        if not check.approved:
            command.failure_reason = check.rejection_code
            self._advance(command, "execution_failed")
            return

        self._advance(command, "bridge_received")
        self._advance(command, "local_safety_check")

        try:
            await self._execute(command, sdk_state)
        except Exception as exc:
            command.failure_reason = str(exc)
            self._advance(command, "execution_failed")
            return

        self._advance(command, "sdk_sent")
        self._advance(command, "robot_acknowledged")
        self._advance(command, "execution_started")
        self._advance(command, "execution_completed")

    async def _execute(self, command: Command, sdk_state: Optional[str]) -> None:
        if command.type == "ESTOP":
            self._safety.trigger_estop()
            await self._adapter.set_state(ESTOP_TARGET_STATE)
        elif command.type == "RESET_ESTOP":
            if sdk_state != "passive":
                raise RuntimeError("robot is not in passive state; cannot clear E-Stop")
            self._safety.clear_estop()
            await self._adapter.set_state(RECOVERY_TARGET_STATE)
        elif command.type == "SET_OBSTACLE_AVOIDANCE":
            enabled = bool((command.params or {}).get("enabled", True))
            await self._adapter.enable_obstacle_avoidance(enabled)
        elif command.type in ("TAKE_CONTROL", "RELEASE_CONTROL"):
            pass  # backend-only concept -- no SDK call
        else:
            raise RuntimeError(f"unsupported command type for this build: {command.type}")

    def _advance(self, command: Command, stage: str) -> None:
        command.current_stage = stage
        command.stages.append(CommandStageEvent(stage=stage, at=datetime.now(timezone.utc).isoformat()))
        self._on_ack(command)
