#!/usr/bin/env python3
"""
UWB Health Monitor
Tracks system health metrics and provides health reporting via MQTT.
"""

import time
from typing import Dict, Optional, Any
from datetime import datetime
from uwb_logging import UwbLogger


class HealthMonitor:
    """Monitors and reports system health metrics."""

    def __init__(
        self,
        logger: UwbLogger,
        mqtt_client: Optional[Any] = None,
        health_topic: Optional[str] = None,
        report_interval: float = 60.0,
        uwb_data_timeout_seconds: float = 300.0,
        mqtt_connection_timeout_seconds: float = 60.0
    ) -> None:
        """
        Initialize health monitor.

        Args:
            logger: Logger instance
            mqtt_client: MQTT client for health reporting (optional)
            health_topic: MQTT topic for health reports (default: {mqtt_topic}/health)
            report_interval: Interval between health reports in seconds (default: 60)
            uwb_data_timeout_seconds: Seconds without UWB data before unhealthy (default: 300)
            mqtt_connection_timeout_seconds: Seconds without MQTT connection before unhealthy (default: 60)
        """
        self.logger = logger
        self.mqtt_client = mqtt_client
        self.health_topic = health_topic
        self.report_interval = report_interval
        self.last_report_time = 0.0
        self.uwb_data_timeout_seconds = uwb_data_timeout_seconds
        self.mqtt_connection_timeout_seconds = mqtt_connection_timeout_seconds

        # Health metrics
        self.metrics: Dict[str, Any] = {
            "start_time": time.time(),
            "parsing_errors": 0,
            "connection_errors": 0,
            "device_resets": 0,
            "successful_packets": 0,
            "failed_packets": 0,
            "mqtt_publishes": 0,
            "mqtt_failures": 0,
            "last_reset_time": None,
            "last_error_time": None,
            "last_uwb_data_time": None,  # Track when we last received UWB data
            "last_mqtt_connected_time": None,  # Track when MQTT was last connected
            "consecutive_errors": 0,
            "uptime_seconds": 0.0
        }

        # Connection health
        self.serial_connected = False
        self.mqtt_connected = False
        self.lora_cache_connected = False

        # Health thresholds (configurable)
        self.uwb_data_timeout_seconds = uwb_data_timeout_seconds  # Default: 5 minutes without UWB data = unhealthy
        self.mqtt_connection_timeout_seconds = mqtt_connection_timeout_seconds  # Default: 1 minute without MQTT connection = unhealthy

    def record_parsing_error(self) -> None:
        """Record a parsing error."""
        self.metrics["parsing_errors"] += 1
        self.metrics["failed_packets"] += 1
        self.metrics["last_error_time"] = time.time()
        self.metrics["consecutive_errors"] += 1

    def record_connection_error(self) -> None:
        """Record a connection error."""
        self.metrics["connection_errors"] += 1
        self.metrics["last_error_time"] = time.time()
        self.metrics["consecutive_errors"] += 1

    def record_device_reset(self) -> None:
        """Record a device reset."""
        self.metrics["device_resets"] += 1
        self.metrics["last_reset_time"] = time.time()
        self.metrics["consecutive_errors"] = 0

    def record_successful_packet(self) -> None:
        """Record a successfully processed packet."""
        self.metrics["successful_packets"] += 1
        self.metrics["consecutive_errors"] = 0
        self.metrics["last_uwb_data_time"] = time.time()  # Update last UWB data time

    def record_mqtt_publish(self, success: bool = True) -> None:
        """Record an MQTT publish attempt."""
        if success:
            self.metrics["mqtt_publishes"] += 1
        else:
            self.metrics["mqtt_failures"] += 1

    def update_connection_status(
        self,
        serial_connected: bool,
        mqtt_connected: Optional[bool] = None,
        lora_cache_connected: Optional[bool] = None
    ) -> None:
        """Update connection status."""
        self.serial_connected = serial_connected
        if mqtt_connected is not None:
            self.mqtt_connected = mqtt_connected
            # Track when MQTT was last connected
            if mqtt_connected:
                self.metrics["last_mqtt_connected_time"] = time.time()
        if lora_cache_connected is not None:
            self.lora_cache_connected = lora_cache_connected

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        current_time = time.time()
        self.metrics["uptime_seconds"] = current_time - self.metrics["start_time"]

        # Calculate success rate
        total_packets = self.metrics["successful_packets"] + self.metrics["failed_packets"]
        success_rate = (
            self.metrics["successful_packets"] / total_packets
            if total_packets > 0 else 1.0
        )

        # Calculate MQTT success rate
        total_mqtt = self.metrics["mqtt_publishes"] + self.metrics["mqtt_failures"]
        mqtt_success_rate = (
            self.metrics["mqtt_publishes"] / total_mqtt
            if total_mqtt > 0 else 1.0
        )

        # Check MQTT connection status
        mqtt_connected_now = False
        if self.mqtt_client and self.mqtt_client.client:
            mqtt_connected_now = self.mqtt_client.client.is_connected()
            # Update last connected time if currently connected
            if mqtt_connected_now:
                self.metrics["last_mqtt_connected_time"] = current_time

        # Check if MQTT connection has been down too long
        last_mqtt_time = self.metrics.get("last_mqtt_connected_time")
        mqtt_connection_ok = True  # Assume OK if we've never tracked it
        if mqtt_connected_now:
            mqtt_connection_ok = True
        elif last_mqtt_time is not None:
            # Check if MQTT has been disconnected for too long
            time_since_mqtt = current_time - last_mqtt_time
            if time_since_mqtt > self.mqtt_connection_timeout_seconds:
                mqtt_connection_ok = False
        elif not mqtt_connected_now:
            # If we're not connected and have never been connected, mark as unhealthy after startup period
            startup_period = 30.0  # Allow 30 seconds for initial connection
            if current_time - self.metrics["start_time"] > startup_period:
                mqtt_connection_ok = False

        # Check if we've received UWB data recently
        last_uwb_time = self.metrics.get("last_uwb_data_time")
        uwb_data_recent = True
        if last_uwb_time is not None:
            time_since_uwb = current_time - last_uwb_time
            if time_since_uwb > self.uwb_data_timeout_seconds:
                uwb_data_recent = False

        # Determine overall health status
        health_status = "healthy"
        if not self.serial_connected:
            health_status = "degraded"
        elif not mqtt_connection_ok:
            # MQTT connection is down
            health_status = "unhealthy"
        elif not uwb_data_recent:
            # Haven't received UWB data for too long
            health_status = "unhealthy"
        elif self.metrics["consecutive_errors"] >= 5:
            health_status = "unhealthy"
        elif self.metrics["parsing_errors"] > 0 and success_rate < 0.8:
            # If we have parsing errors and low success rate, mark as unhealthy
            health_status = "unhealthy"
        elif success_rate < 0.8:
            health_status = "degraded"
        elif self.metrics["parsing_errors"] >= 10:
            # If we have many parsing errors, mark as unhealthy even if success rate is OK
            health_status = "unhealthy"

        return {
            "status": health_status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": self.metrics["uptime_seconds"],
            "connections": {
                "serial": self.serial_connected,
                "mqtt": mqtt_connected_now,
                "lora_cache": self.lora_cache_connected
            },
            "data_reception": {
                "last_uwb_data_time": self.metrics.get("last_uwb_data_time"),
                "uwb_data_recent": uwb_data_recent,
                "time_since_last_uwb": current_time - last_uwb_time if last_uwb_time else None
            },
            "mqtt_connection": {
                "connected": mqtt_connected_now,
                "last_connected_time": last_mqtt_time,
                "time_since_last_connected": current_time - last_mqtt_time if last_mqtt_time else None,
                "connection_ok": mqtt_connection_ok
            },
            "metrics": {
                "packets": {
                    "successful": self.metrics["successful_packets"],
                    "failed": self.metrics["failed_packets"],
                    "success_rate": round(success_rate, 3)
                },
                "errors": {
                    "parsing": self.metrics["parsing_errors"],
                    "connection": self.metrics["connection_errors"],
                    "consecutive": self.metrics["consecutive_errors"]
                },
                "device": {
                    "resets": self.metrics["device_resets"],
                    "last_reset": self.metrics["last_reset_time"]
                },
                "mqtt": {
                    "publishes": self.metrics["mqtt_publishes"],
                    "failures": self.metrics["mqtt_failures"],
                    "success_rate": round(mqtt_success_rate, 3)
                }
            }
        }

    def report_health(self, force: bool = False) -> None:
        """Report health status via MQTT if interval has passed."""
        current_time = time.time()

        # Always write health status to file for Docker health check
        try:
            health_status = self.get_health_status()
            import json
            health_json = json.dumps(health_status)

            # Write health status to file for Docker health check
            try:
                with open("/tmp/uwb-health-status.json", "w") as f:
                    f.write(health_json)
            except Exception:
                pass  # Silently fail if we can't write to /tmp

        except Exception as e:
            self.logger.warning(f"Failed to get health status: {e}")
            return

        if not force and (current_time - self.last_report_time) < self.report_interval:
            return

        if not self.mqtt_client or not self.health_topic:
            return

        try:
            if self.mqtt_client.client and self.mqtt_client.client.is_connected():
                result = self.mqtt_client.client.publish(self.health_topic, health_json, qos=1)
                if result.rc == 0:
                    self.last_report_time = current_time
                    self.logger.verbose(f"Health status reported: {health_status['status']}")
        except Exception as e:
            self.logger.warning(f"Failed to report health status: {e}")
