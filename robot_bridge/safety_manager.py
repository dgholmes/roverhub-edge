from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config import BridgeConfig
from shared.schemas.commands import QUAD_ONLY_COMMAND_TYPES


@dataclass
class SafetyCheckResult:
    approved: bool
    rejection_code: Optional[str] = None
    clamped_speed_ratio: Optional[int] = None


class SafetyManager:
    """Pre-flight gate for commands, and owner of the E-Stop flag. Covers
    the full wired command surface -- see
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

    def check(
        self,
        command_type: str,
        sdk_connected: bool,
        battery_percent: float,
        robot_type: Optional[str] = None,
        speed_ratio: Optional[int] = None,
    ) -> SafetyCheckResult:
        if command_type == "ESTOP":
            return SafetyCheckResult(approved=True)

        if self._estop_active and command_type != "RESET_ESTOP":
            return SafetyCheckResult(approved=False, rejection_code="REJECTED_ESTOP")

        if command_type in ("TAKE_CONTROL", "RELEASE_CONTROL"):
            return SafetyCheckResult(approved=True)

        if command_type in QUAD_ONLY_COMMAND_TYPES and robot_type == "wheel":
            return SafetyCheckResult(approved=False, rejection_code="REJECTED_UNSUPPORTED_ON_WHEEL")

        if not sdk_connected:
            return SafetyCheckResult(approved=False, rejection_code="REJECTED_NO_CONNECTION")

        if battery_percent < self._config.safety_min_battery_pct:
            return SafetyCheckResult(approved=False, rejection_code="REJECTED_LOW_BATTERY")

        clamped = None
        if speed_ratio is not None:
            clamped = min(speed_ratio, self._config.safety_max_speed_ratio)

        return SafetyCheckResult(approved=True, clamped_speed_ratio=clamped)
