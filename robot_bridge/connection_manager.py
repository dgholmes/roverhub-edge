from __future__ import annotations

import json
from typing import Callable, Tuple

from config import BridgeConfig
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
        topic = f"roverhub/admin/{self._config.bridge_id}/register"
        payload = {
            "bridge_id": self._config.bridge_id,
            "site_id": self._config.site_id,
            "robot_id": self._config.robot_id,
            "robot_type": robot_type,
        }
        self._client.publish(topic, json.dumps(payload), qos=1)

    def publish_telemetry(self, frame: TelemetryFrame) -> None:
        topic = f"roverhub/{self._config.site_id}/{self._config.robot_id}/telemetry"
        self._client.publish(topic, frame.model_dump_json(), qos=0)

    @staticmethod
    def _parse_broker_url(url: str) -> Tuple[str, int]:
        without_scheme = url.split("://", 1)[-1]
        host, _, port = without_scheme.partition(":")
        return host, int(port) if port else 1883
