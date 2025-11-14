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
        report_interval: float = 60.0
    ) -> None:
        """
        Initialize health monitor.
        
        Args:
            logger: Logger instance
            mqtt_client: MQTT client for health reporting (optional)
            health_topic: MQTT topic for health reports (default: {mqtt_topic}/health)
            report_interval: Interval between health reports in seconds (default: 60)
        """
        self.logger = logger
        self.mqtt_client = mqtt_client
        self.health_topic = health_topic
        self.report_interval = report_interval
        self.last_report_time = 0.0
        
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
            "consecutive_errors": 0,
            "uptime_seconds": 0.0
        }
        
        # Connection health
        self.serial_connected = False
        self.mqtt_connected = False
        self.lora_cache_connected = False
        
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
        
        # Determine overall health status
        health_status = "healthy"
        if not self.serial_connected:
            health_status = "degraded"
        elif self.metrics["consecutive_errors"] >= 5:
            health_status = "unhealthy"
        elif success_rate < 0.8:
            health_status = "degraded"
            
        return {
            "status": health_status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": self.metrics["uptime_seconds"],
            "connections": {
                "serial": self.serial_connected,
                "mqtt": self.metrics["mqtt_publishes"] > 0,  # Assume connected if we've published
                "lora_cache": self.lora_cache_connected
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
        
        if not force and (current_time - self.last_report_time) < self.report_interval:
            return
            
        if not self.mqtt_client or not self.health_topic:
            return
            
        try:
            health_status = self.get_health_status()
            import json
            health_json = json.dumps(health_status)
            
            if self.mqtt_client.client and self.mqtt_client.client.is_connected():
                result = self.mqtt_client.client.publish(self.health_topic, health_json, qos=1)
                if result.rc == 0:
                    self.last_report_time = current_time
                    self.logger.verbose(f"Health status reported: {health_status['status']}")
        except Exception as e:
            self.logger.warning(f"Failed to report health status: {e}")

