from __future__ import annotations

import json
from typing import Callable, Tuple

from config import BridgeConfig
from shared.schemas.bridge_status import HeartbeatPayload, StateUpdate
from shared.schemas.commands import Command
from shared.schemas.low_level_telemetry import LowerStateFrame
from shared.schemas.telemetry import TelemetryFrame

MqttClientFactory = Callable[[], object]


def real_mqtt_client_factory():
    import paho.mqtt.client as mqtt

    return mqtt.Client()


class ConnectionManager:
    """Wraps the outbound MQTT connection from the bridge to the cloud
    broker. The bridge always connects outbound -- the cloud never dials
    in (see docs/02-system-architecture.md)."""

    def __init__(self, config: BridgeConfig, mqtt_client_factory: MqttClientFactory):
        self._config = config
        self._client = mqtt_client_factory()

    def connect(self) -> None:
        host, port = self._parse_broker_url(self._config.cloud_mqtt_url)
        self._client.connect(host, port)
        self._client.loop_start()

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def publish_registration(self, robot_type: str) -> None:
        # Retained so a backend that starts (or restarts) after this
        # bridge already sent its registration still receives it -- the
        # in-memory RobotRegistry only ever *creates* a record from this
        # message (mark_seen()/update_state() only update an existing
        # one), so a non-retained, one-shot registration was silently
        # invisible to any late subscriber even while telemetry/heartbeat
        # kept flowing normally. main.py also re-publishes this on every
        # heartbeat tick as a second, retain-independent self-heal in case
        # the broker itself doesn't persist retained messages across a
        # restart (this project's mosquitto.conf sets persistence false).
        topic = f"roverhub/admin/{self._config.bridge_id}/register"
        payload = {
            "bridge_id": self._config.bridge_id,
            "site_id": self._config.site_id,
            "robot_id": self._config.robot_id,
            "robot_type": robot_type,
        }
        self._client.publish(topic, json.dumps(payload), qos=1, retain=True)

    def publish_telemetry(self, frame: TelemetryFrame) -> None:
        topic = f"roverhub/{self._config.site_id}/{self._config.robot_id}/telemetry"
        self._client.publish(topic, frame.model_dump_json(), qos=0)

    def publish_state(self, update: StateUpdate) -> None:
        # Retained for the same reason as publish_registration above:
        # this is only published on change (telemetry_reader.py's
        # compute_abstract_state comparison), so a frontend that connects
        # or reloads while the robot's state hasn't changed recently would
        # otherwise never learn the real current state and would sit on
        # its own hardcoded 'STAND' default indefinitely -- live-reported
        # as "UI shows Standing even though the robot is at stand_down/
        # passive."
        topic = f"roverhub/{self._config.site_id}/{self._config.robot_id}/state"
        self._client.publish(topic, update.model_dump_json(), qos=1, retain=True)

    def publish_heartbeat(self, payload: HeartbeatPayload) -> None:
        topic = f"roverhub/{self._config.site_id}/{self._config.robot_id}/heartbeat"
        self._client.publish(topic, payload.model_dump_json(), qos=0)

    def publish_lower_state(self, frame: LowerStateFrame) -> None:
        # Only ever published when low_level_enabled is on (DDS wired up on
        # a Jetson/Raspberry Pi) -- see low_level_reader.py. qos=0 like
        # telemetry: this is decimated but still relatively high-frequency
        # (IMU/motor state), not worth guaranteed delivery.
        topic = f"roverhub/{self._config.site_id}/{self._config.robot_id}/lower_state"
        self._client.publish(topic, frame.model_dump_json(), qos=0)

    def subscribe_commands(self, on_command: Callable[[bytes], None]) -> None:
        topic = f"roverhub/{self._config.site_id}/{self._config.robot_id}/commands"
        self._client.on_message = lambda client, userdata, message: on_command(message.payload)
        self._client.subscribe(topic, qos=1)

    def publish_ack(self, command: Command) -> None:
        topic = f"roverhub/{self._config.site_id}/{self._config.robot_id}/ack"
        self._client.publish(topic, command.model_dump_json(), qos=1)

    @staticmethod
    def _parse_broker_url(url: str) -> Tuple[str, int]:
        without_scheme = url.split("://", 1)[-1]
        host, _, port = without_scheme.partition(":")
        return host, int(port) if port else 1883
