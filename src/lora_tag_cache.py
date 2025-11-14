#!/usr/bin/env python3
"""
LoRa Tag Data Cache
Subscribes to TTN MQTT broker and caches LoRa tag data (battery, temperature, GPS, etc.)
Maps dev_eui to UWB IDs using configuration file

Copyright (c) Dynamic Devices Ltd. 2025. All rights reserved.
"""

import json
import ssl
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Any

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: paho-mqtt library not found. Install with: pip install paho-mqtt")
    raise


class LoraTagDataCache:
    """
    Subscribes to TTN MQTT broker and caches LoRa tag data.
    Provides thread-safe access to cached data mapped by UWB ID.
    """

    def __init__(self,
                 broker: str = "eu1.cloud.thethings.network",
                 port: int = 8883,
                 username: str = None,
                 password: str = None,
                 topic_pattern: str = "#",
                 dev_eui_to_uwb_id_map: Dict[str, str] = None,
                 verbose: bool = False,
                 gps_ttl_seconds: float = 300.0,  # 5 minutes default for GPS
                 sensor_ttl_seconds: float = 600.0,  # 10 minutes default for sensor data
                 cleanup_interval_seconds: float = 60.0):  # Cleanup every minute
        """
        Initialize the LoRa tag data cache.

        Args:
            broker: MQTT broker hostname
            port: MQTT broker port
            username: MQTT username
            password: MQTT password
            topic_pattern: MQTT topic pattern to subscribe to (default: "#" for all topics)
            dev_eui_to_uwb_id_map: Dictionary mapping dev_eui (hex string) to UWB ID (hex string)
            verbose: Enable verbose logging
            gps_ttl_seconds: Time-to-live for GPS data in seconds (default: 300 = 5 minutes)
            sensor_ttl_seconds: Time-to-live for sensor data in seconds (default: 600 = 10 minutes)
            cleanup_interval_seconds: Interval for cache cleanup thread in seconds (default: 60)
        """
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.topic_pattern = topic_pattern
        self.dev_eui_to_uwb_id_map = dev_eui_to_uwb_id_map or {}
        self.verbose = verbose
        self.gps_ttl_seconds = gps_ttl_seconds
        self.sensor_ttl_seconds = sensor_ttl_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds

        # Cache: dev_eui -> latest data
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = threading.RLock()

        # Cache: UWB ID -> latest data (derived from dev_eui mapping)
        self._uwb_cache: Dict[str, Dict[str, Any]] = {}

        # MQTT client
        self.mqtt_client: Optional[mqtt.Client] = None
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None

        # Cleanup thread for expired entries
        self._cleanup_thread: Optional[threading.Thread] = None
        self._cleanup_running: bool = False

    def _log(self, message: str, level: str = "INFO"):
        """Internal logging method"""
        if self.verbose or level in ["ERROR", "WARNING"]:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [LoRaCache {level}] {message}")

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: Any
    ) -> None:
        """MQTT connection callback"""
        if rc == 0:
            self._log(f"Connected to TTN MQTT broker {self.broker}:{self.port}")
            try:
                client.subscribe(self.topic_pattern, qos=0)
                self._log(f"Subscribed to topic pattern: {self.topic_pattern}")
            except Exception as e:
                self._log(f"Failed to subscribe: {e}", "ERROR")
        else:
            self._log(f"Failed to connect to MQTT broker (rc={rc})", "ERROR")

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        rc: Any
    ) -> None:
        """MQTT disconnection callback"""
        if rc != 0:
            self._log(f"Unexpected disconnection from MQTT broker (rc={rc})", "WARNING")
        else:
            self._log("Disconnected from MQTT broker")

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        message: mqtt.MQTTMessage
    ) -> None:
        """MQTT message callback - processes LoRa tag data"""
        try:
            topic = message.topic
            payload = message.payload.decode('utf-8')

            self._log(f"Received message on topic: {topic}", "INFO")
            self._log(f"Message payload (first 500 chars): {payload[:500]}", "VERBOSE")

            # Parse JSON payload
            data = json.loads(payload)

            # Extract dev_eui
            dev_eui = None
            try:
                dev_eui = data.get("end_device_ids", {}).get("dev_eui", "").upper()
            except (AttributeError, KeyError):
                self._log("Could not extract dev_eui from message", "WARNING")
                return

            if not dev_eui:
                self._log("No dev_eui found in message", "WARNING")
                return

            # Extract decoded payload
            decoded_payload = {}
            try:
                uplink_msg = data.get("uplink_message", {})
                decoded_payload = uplink_msg.get("decoded_payload", {})
                if decoded_payload:
                    self._log(f"Decoded payload keys: {list(decoded_payload.keys())}", "VERBOSE")
                    self._log(f"Decoded payload: {json.dumps(decoded_payload)}", "VERBOSE")
                else:
                    self._log("No decoded_payload in uplink_message", "VERBOSE")
            except (AttributeError, KeyError) as e:
                self._log(f"Error extracting decoded_payload: {e}", "VERBOSE")

            # Extract location data
            # TTN provides locations in multiple formats: "frm-payload", "user", "gps", etc.
            # Priority: frm-payload > user > gps > first available
            location_data = {}
            try:
                locations = uplink_msg.get("locations", {})
                loc = None
                location_source = None

                # Try different location sources in priority order
                for source in ["frm-payload", "user", "gps"]:
                    if source in locations:
                        loc = locations[source]
                        location_source = source
                        break

                # If no standard source found, use first available location
                if loc is None and locations:
                    location_source = list(locations.keys())[0]
                    loc = locations[location_source]

                if loc:
                    location_data = {
                        "latitude": loc.get("latitude"),
                        "longitude": loc.get("longitude"),
                        "altitude": loc.get("altitude"),
                        "accuracy": loc.get("accuracy"),
                        "source": loc.get("source") or location_source
                    }
                    self._log(
                        f"Extracted location from {location_source}: "
                        f"lat={location_data['latitude']:.6f}, "
                        f"lon={location_data['longitude']:.6f}, "
                        f"alt={location_data.get('altitude', 'N/A')}, "
                        f"accuracy={location_data.get('accuracy', 'N/A')}m",
                        "VERBOSE"
                    )
                elif locations:
                    self._log(f"No valid location found in {list(locations.keys())}", "VERBOSE")
                else:
                    self._log("No location data in message", "VERBOSE")
            except (AttributeError, KeyError) as e:
                self._log(f"Error extracting location: {e}", "VERBOSE")

            # Extract metadata
            metadata = {
                "received_at": data.get("received_at"),
                "device_id": data.get("end_device_ids", {}).get("device_id"),
                "application_id": data.get("end_device_ids", {}).get("application_ids", {}).get("application_id"),
                "f_port": uplink_msg.get("f_port"),
                "f_cnt": uplink_msg.get("f_cnt"),
            }

            # Extract RX metadata (gateway info, RSSI, SNR)
            rx_metadata = []
            try:
                rx_list = uplink_msg.get("rx_metadata", [])
                for rx in rx_list:
                    rx_metadata.append({
                        "gateway_id": rx.get("gateway_ids", {}).get("gateway_id"),
                        "gateway_eui": rx.get("gateway_ids", {}).get("eui"),
                        "rssi": rx.get("rssi"),
                        "snr": rx.get("snr"),
                        "timestamp": rx.get("timestamp"),
                        "time": rx.get("time")
                    })
            except (AttributeError, KeyError):
                pass

            # Build cached data structure
            cached_data = {
                "dev_eui": dev_eui,
                "timestamp": time.time(),
                "received_at": metadata.get("received_at"),
                "decoded_payload": decoded_payload,
                "location": location_data,
                "metadata": metadata,
                "rx_metadata": rx_metadata
            }

            # Update cache
            with self._cache_lock:
                self._cache[dev_eui] = cached_data

                # Update UWB cache if mapping exists
                uwb_id = self.dev_eui_to_uwb_id_map.get(dev_eui)
                if uwb_id:
                    # Normalize UWB ID to uppercase hex string
                    uwb_id = uwb_id.upper()
                    self._uwb_cache[uwb_id] = cached_data

                    # Build detailed log message with GPS, battery, and triage status
                    log_parts = [f"Cached data for dev_eui={dev_eui} -> UWB ID={uwb_id}"]

                    # Add GPS position/status
                    # Note: Location source can be from device GPS (frm-payload) or TTN location service (gps, user)
                    if location_data and location_data.get("latitude") and location_data.get("longitude"):
                        lat = location_data.get("latitude")
                        lon = location_data.get("longitude")
                        alt = location_data.get("altitude", "N/A")
                        accuracy = location_data.get("accuracy", "N/A")
                        source = location_data.get("source", "unknown")
                        # Clarify if source is from device or TTN service
                        if source == "SOURCE_GPS" or source == "gps":
                            source_label = f"{source}(TTN_service)"
                        elif source == "frm-payload":
                            source_label = f"{source}(device)"
                        else:
                            source_label = source
                        log_parts.append(f"location: ({lat:.6f}, {lon:.6f}, alt={alt}) accuracy={accuracy}m source={source_label}")
                    else:
                        log_parts.append("location: no position")

                    # Add battery status (check multiple possible field names)
                    battery = None
                    if decoded_payload:
                        battery = decoded_payload.get("battery") or decoded_payload.get("battery_percentage")
                    if battery is not None:
                        log_parts.append(f"battery={battery}%")
                    else:
                        log_parts.append("battery=N/A")

                    # Add triage status (check multiple possible field names)
                    triage = None
                    if decoded_payload:
                        triage = decoded_payload.get("triage") or decoded_payload.get("triageStatus") or decoded_payload.get("triage_status")
                    if triage is not None:
                        log_parts.append(f"triage={triage}")
                    else:
                        log_parts.append("triage=N/A")

                    # Add device GPS quality indicators (fix_type, satellites)
                    # Note: This is the device's own GPS module status, which may differ from
                    # the location source (which could be from TTN's location service)
                    if decoded_payload:
                        fix_type = decoded_payload.get("fix_type")
                        satellites = decoded_payload.get("satellites")
                        if fix_type is not None:
                            fix_names = {0: "no_fix", 1: "2D", 2: "3D"}
                            fix_name = fix_names.get(fix_type, f"unknown({fix_type})")
                            log_parts.append(f"device_GPS_fix={fix_name}")
                        if satellites is not None:
                            log_parts.append(f"device_satellites={satellites}")

                    # Add temperature if available
                    if decoded_payload and "temperature" in decoded_payload:
                        temp = decoded_payload["temperature"]
                        log_parts.append(f"temp={temp}°C")

                    # Add signal quality (gateway count, RSSI, SNR)
                    if rx_metadata:
                        gateway_count = len(rx_metadata)
                        log_parts.append(f"gateways={gateway_count}")
                        # Calculate average RSSI and SNR
                        rssi_values = [rx.get("rssi") for rx in rx_metadata if rx.get("rssi") is not None]
                        snr_values = [rx.get("snr") for rx in rx_metadata if rx.get("snr") is not None]
                        if rssi_values:
                            avg_rssi = sum(rssi_values) / len(rssi_values)
                            log_parts.append(f"RSSI={avg_rssi:.1f}dBm")
                        if snr_values:
                            avg_snr = sum(snr_values) / len(snr_values)
                            log_parts.append(f"SNR={avg_snr:.1f}dB")

                    # Add frame counter for message sequence tracking
                    if metadata.get("f_cnt") is not None:
                        log_parts.append(f"f_cnt={metadata['f_cnt']}")

                    self._log(" | ".join(log_parts), "INFO")
                else:
                    self._log(f"No UWB mapping for dev_eui={dev_eui}", "VERBOSE")

        except json.JSONDecodeError as e:
            self._log(f"Failed to parse JSON payload: {e}", "ERROR")
        except Exception as e:
            self._log(f"Error processing message: {e}", "ERROR")
            if self.verbose:
                import traceback
                traceback.print_exc()

    def start(self) -> None:
        """Start the MQTT subscriber and cleanup thread in background threads"""
        if self._running:
            self._log("Cache already running", "WARNING")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        # Start cleanup thread
        self._cleanup_running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

        self._log(f"LoRa tag cache started (GPS TTL: {self.gps_ttl_seconds}s, Sensor TTL: {self.sensor_ttl_seconds}s)")

    def stop(self) -> None:
        """Stop the MQTT subscriber and cleanup thread"""
        self._running = False
        self._cleanup_running = False

        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        if self._thread:
            self._thread.join(timeout=5)
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        self._log("LoRa tag cache stopped")

    def _run(self) -> None:
        """Run the MQTT client loop"""
        try:
            # Use VERSION1 callback API (VERSION2 has different signatures)
            # VERSION1 is still supported and works correctly
            try:
                self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            except AttributeError:
                # Fallback for older paho-mqtt versions
                self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_message = self._on_message

            # Set credentials if provided
            if self.username and self.password:
                self.mqtt_client.username_pw_set(self.username, self.password)

            # Configure TLS
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self.mqtt_client.tls_set_context(context)

            # Connect
            self.mqtt_client.connect(self.broker, self.port, 60)

            # Run loop
            self.mqtt_client.loop_start()

            # Keep thread alive
            while self._running:
                time.sleep(1)

        except Exception as e:
            self._log(f"Error in MQTT loop: {e}", "ERROR")
            if self.verbose:
                import traceback
                traceback.print_exc()
        finally:
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()

    def get_by_dev_eui(self, dev_eui: str) -> Optional[Dict[str, Any]]:
        """
        Get cached data by dev_eui.

        Args:
            dev_eui: Device EUI (hex string, case-insensitive)

        Returns:
            Cached data dictionary or None if not found
        """
        dev_eui = dev_eui.upper()
        with self._cache_lock:
            return self._cache.get(dev_eui)

    def get_by_uwb_id(
        self,
        uwb_id: str,
        max_age_seconds: Optional[float] = None,
        check_gps_staleness: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached data by UWB ID (using dev_eui mapping).

        Args:
            uwb_id: UWB ID (hex string, case-insensitive)
            max_age_seconds: Maximum age in seconds for data to be considered valid.
                           If None, uses configured TTL values.
            check_gps_staleness: If True, checks GPS data staleness separately using GPS TTL

        Returns:
            Cached data dictionary or None if not found or stale
        """
        uwb_id = uwb_id.upper()
        with self._cache_lock:
            data = self._uwb_cache.get(uwb_id)
            if data is None:
                return None

            # Check if data is stale
            if not self._is_data_valid(data, max_age_seconds, check_gps_staleness):
                return None

            return data

    def _is_data_valid(
        self,
        data: Dict[str, Any],
        max_age_seconds: Optional[float] = None,
        check_gps_staleness: bool = True
    ) -> bool:
        """
        Check if cached data is still valid (not expired).

        Args:
            data: Cached data dictionary
            max_age_seconds: Override max age (uses configured TTL if None)
            check_gps_staleness: If True, checks GPS data separately

        Returns:
            True if data is valid, False if expired
        """
        if not data or "timestamp" not in data:
            return False

        current_time = time.time()
        data_age = current_time - data.get("timestamp", 0)

        # Check GPS staleness if location data exists
        if check_gps_staleness and data.get("location"):
            location = data["location"]
            if location.get("latitude") and location.get("longitude"):
                # GPS data has stricter TTL
                gps_max_age = max_age_seconds if max_age_seconds is not None else self.gps_ttl_seconds
                if data_age > gps_max_age:
                    return False

        # Check general data staleness
        sensor_max_age = max_age_seconds if max_age_seconds is not None else self.sensor_ttl_seconds
        return data_age <= sensor_max_age

    def _cleanup_loop(self) -> None:
        """Background thread to periodically clean up expired entries."""
        while self._cleanup_running:
            try:
                time.sleep(self.cleanup_interval_seconds)
                self._cleanup_expired_entries()
            except Exception as e:
                self._log(f"Error in cleanup loop: {e}", "ERROR")

    def _cleanup_expired_entries(self) -> None:
        """Remove expired entries from cache."""
        expired_dev_euis = []
        expired_uwb_ids = []

        with self._cache_lock:
            # Check dev_eui cache
            for dev_eui, data in list(self._cache.items()):
                if not self._is_data_valid(data, check_gps_staleness=True):
                    expired_dev_euis.append(dev_eui)

            # Check UWB cache
            for uwb_id, data in list(self._uwb_cache.items()):
                if not self._is_data_valid(data, check_gps_staleness=True):
                    expired_uwb_ids.append(uwb_id)

            # Remove expired entries
            for dev_eui in expired_dev_euis:
                del self._cache[dev_eui]

            for uwb_id in expired_uwb_ids:
                del self._uwb_cache[uwb_id]

            if expired_dev_euis or expired_uwb_ids:
                self._log(
                    f"Cleaned up {len(expired_dev_euis)} dev_eui entries and "
                    f"{len(expired_uwb_ids)} UWB ID entries",
                    "VERBOSE"
                )

    def get_all_cached(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all cached data by UWB ID.

        Returns:
            Dictionary mapping UWB ID to cached data
        """
        with self._cache_lock:
            return self._uwb_cache.copy()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._cache_lock:
            return {
                "dev_eui_count": len(self._cache),
                "uwb_id_count": len(self._uwb_cache),
                "mapping_count": len(self.dev_eui_to_uwb_id_map),
                "dev_euis": list(self._cache.keys()),
                "uwb_ids": list(self._uwb_cache.keys())
            }
