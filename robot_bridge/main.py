from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from command_sender import CommandSender
from config import BridgeConfig
from connection_manager import ConnectionManager, real_mqtt_client_factory
from dobot_adapter import DobotAdapter, real_client_factory
from heartbeat import HeartbeatSender
from safety_manager import SafetyManager
from shared.schemas.bridge_status import StateUpdate
from shared.schemas.commands import Command
from telemetry_reader import TelemetryReader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("robot_bridge.main")


class _LatestBattery:
    """Shared holder so command_sender's safety check can read the most
    recently observed battery level without polling the adapter again."""

    def __init__(self) -> None:
        self.percent = 100.0

    def update(self, percent: float) -> None:
        self.percent = percent

    def read(self) -> float:
        return self.percent


class _LatestState:
    """Shared holder so on_heartbeat can re-publish the current state on
    every tick without waiting for another actual transition -- see
    connection_manager.py's publish_state docstring for why this self-heal
    matters (a frontend connecting/reloading while state hasn't changed
    recently would otherwise see a stale default forever)."""

    def __init__(self) -> None:
        self.sdk_state: str | None = None
        self.abstract_state: str | None = None

    def update(self, sdk_state: str, abstract_state: str) -> None:
        self.sdk_state = sdk_state
        self.abstract_state = abstract_state


async def run(config: BridgeConfig | None = None, client_factory=None, mqtt_client_factory=real_mqtt_client_factory) -> None:
    config = config or BridgeConfig.from_env()
    if client_factory is None:
        client_factory = lambda: real_client_factory(config)

    adapter = DobotAdapter(client_factory)
    connection = ConnectionManager(config, mqtt_client_factory)
    safety = SafetyManager(config)
    latest_battery = _LatestBattery()
    latest_state = _LatestState()

    await adapter.connect()
    robot_type = await adapter.get_robot_config()
    connection.connect()
    connection.publish_registration(robot_type)

    async def on_frame(frame):
        connection.publish_telemetry(frame)
        latest_battery.update(frame.battery_percent)

    async def on_state_change(sdk_state, abstract_state):
        latest_state.update(sdk_state, abstract_state)
        connection.publish_state(StateUpdate(
            robot_id=config.robot_id, site_id=config.site_id,
            abstract_state=abstract_state, sdk_state=sdk_state,
            updated_at=datetime.now(timezone.utc).isoformat(),
        ))

    async def on_heartbeat(payload):
        # Re-broadcast registration alongside every heartbeat, not just
        # once at startup -- self-heals a backend that started (or
        # restarted) after the one-shot startup registration, independent
        # of whether the broker's retained-message support survives a
        # broker restart (this project's mosquitto.conf sets persistence
        # false, so a retained message alone wouldn't survive that case).
        connection.publish_registration(robot_type)
        # Same self-heal for state -- re-publish the last known state on
        # every heartbeat tick, not just on an actual transition. Guarded
        # on latest_state.abstract_state being set at all, since the very
        # first heartbeat tick could in principle fire before the first
        # telemetry poll has ever computed a state.
        if latest_state.abstract_state is not None:
            connection.publish_state(StateUpdate(
                robot_id=config.robot_id, site_id=config.site_id,
                abstract_state=latest_state.abstract_state, sdk_state=latest_state.sdk_state,
                updated_at=datetime.now(timezone.utc).isoformat(),
            ))
        connection.publish_heartbeat(payload)

    sender = CommandSender(adapter, safety, on_ack=connection.publish_ack, battery_percent_provider=latest_battery.read)

    loop = asyncio.get_running_loop()

    def _log_command_failure(future: "asyncio.Future") -> None:
        exc = future.exception()
        if exc is not None:
            logger.error("unhandled error while executing command: %r", exc)

    def on_command_bytes(payload: bytes) -> None:
        try:
            data = json.loads(payload)
            command = Command(
                command_id=data.get("command_id", str(uuid.uuid4())),
                robot_id=config.robot_id,
                type=data["type"],
                label=data.get("label", data["type"]),
                params=data.get("params"),
                initiated_by=data.get("initiated_by", "unknown"),
            )
        except Exception:
            logger.warning("dropping unparseable command payload: %r", payload)
            return
        future = asyncio.run_coroutine_threadsafe(sender.handle_command(command), loop)
        future.add_done_callback(_log_command_failure)

    connection.subscribe_commands(on_command_bytes)

    reader = TelemetryReader(
        adapter, config, on_frame, on_state_change=on_state_change,
        estop_active_provider=lambda: safety.estop_active,
    )
    heartbeat = HeartbeatSender(adapter, config, on_heartbeat)

    logger.info("robot_bridge started: robot_type=%s bridge_id=%s", robot_type, config.bridge_id)
    await asyncio.gather(reader.run_forever(), heartbeat.run_forever())


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()  # loads .env in this directory, if present; real env vars still win
    asyncio.run(run())
