from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config import BridgeConfig


@dataclass
class SafetyCheckResult:
    approved: bool
    rejection_code: Optional[str] = None


class SafetyManager:
    """Pre-flight gate for commands, and owner of the E-Stop flag. Only the
    five command types this build wires are evaluated -- see
    shared.schemas.commands.WIRED_COMMAND_TYPES."""

    def __init__(self, config: BridgeConfig):
        self._config = config
        self._estop_active = False

    @property
    def estop_active(self) -> bool:
        return self._estop_active

    def trigger_estop(self) -> None:
        self._estop_active = True

    def clear_estop(self) -> None:
        self._estop_active = False

    def check(self, command_type: str, sdk_connected: bool, battery_percent: float) -> SafetyCheckResult:
        if command_type == "ESTOP":
            return SafetyCheckResult(approved=True)

        if self._estop_active and command_type != "RESET_ESTOP":
            return SafetyCheckResult(approved=False, rejection_code="REJECTED_ESTOP")

        if command_type in ("TAKE_CONTROL", "RELEASE_CONTROL"):
            return SafetyCheckResult(approved=True)

        if not sdk_connected:
            return SafetyCheckResult(approved=False, rejection_code="REJECTED_NO_CONNECTION")

        if battery_percent < self._config.safety_min_battery_pct:
            return SafetyCheckResult(approved=False, rejection_code="REJECTED_LOW_BATTERY")

        return SafetyCheckResult(approved=True)
