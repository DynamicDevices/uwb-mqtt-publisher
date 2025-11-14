#!/usr/bin/env python3
"""
UWB MQTT Publisher - Main Entry Point
Refactored version using modular components.

Version: 1.2.0
"""

import struct
import argparse
import time
import json
import sys
import os
from typing import Optional, Any, List, Union

# Import modular components using standard Python imports
from uwb_serial import connect_serial, reset_device, read_serial, disconnect_serial
from uwb_packet_parser import parse_final_payload
from uwb_mqtt_client import UwbMqttClient
from uwb_logging import UwbLogger
from uwb_constants import (
    MAX_PARSING_ERRORS,
    MAX_DISTANCE_METERS,
    PACKET_HEADER_BYTE_1,
    PACKET_HEADER_BYTE_2,
    PACKET_TYPE_ASSIGNMENT,
    PACKET_TYPE_DISTANCE,
    MODE_GROUP1_INTERNAL,
    MODE_GROUP2_INTERNAL,
    DEFAULT_CONNECTION_ERROR_THRESHOLD,
    DEFAULT_INITIAL_BACKOFF_SECONDS,
    DEFAULT_MAX_BACKOFF_SECONDS,
    DEFAULT_BACKOFF_MULTIPLIER,
    DEFAULT_HEALTH_REPORT_INTERVAL
)
from uwb_exceptions import ResetRequiredException
from uwb_error_recovery import ErrorRecovery, ErrorType
from uwb_health_monitor import HealthMonitor
from uwb_data_validator import DataValidator

# Import optional components
try:
    from uwb_network_converter import UwbNetworkConverter
except ImportError:
    UwbNetworkConverter = None

try:
    from lora_tag_cache import LoraTagDataCache
except ImportError:
    LoraTagDataCache = None


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='UWB MQTT Publisher')
    parser.add_argument("uart", help="uart port to use", type=str, default="/dev/ttyUSB0", nargs='?')
    parser.add_argument("nodes", help="node lists", type=str, default="[]", nargs='?')
    parser.add_argument("--mqtt-broker", help="MQTT broker hostname", type=str, default="mqtt.dynamicdevices.co.uk")
    parser.add_argument("--mqtt-port", help="MQTT broker port", type=int, default=8883)
    parser.add_argument("--mqtt-topic", help="MQTT topic to publish to", type=str, default="uwb/positions")
    parser.add_argument("--mqtt-rate-limit", help="Minimum seconds between MQTT publishes", type=float, default=10.0)
    parser.add_argument("--disable-mqtt", help="Disable MQTT publishing", action="store_true")
    parser.add_argument("--verbose", help="Enable verbose logging", action="store_true")
    parser.add_argument("--quiet", help="Enable quiet mode (minimal logging)", action="store_true")
    parser.add_argument("--cga-format", help="Publish in CGA network format", action="store_true")
    parser.add_argument("--anchor-config", help="Path to anchor config JSON", type=str, default=None)
    parser.add_argument("--dev-eui-mapping", help="Path to dev_eui mapping JSON", type=str, default=None)
    parser.add_argument("--lora-broker", help="LoRa MQTT broker hostname", type=str, default="eu1.cloud.thethings.network")
    parser.add_argument("--lora-port", help="LoRa MQTT broker port", type=int, default=8883)
    parser.add_argument("--lora-username", help="LoRa MQTT username", type=str, default=None)
    parser.add_argument("--lora-password", help="LoRa MQTT password", type=str, default=None)
    parser.add_argument("--lora-topic", help="LoRa MQTT topic pattern", type=str, default="#")
    parser.add_argument("--enable-lora-cache", help="Enable LoRa tag data caching", action="store_true")
    parser.add_argument("--lora-gps-max-age", help="Maximum age for LoRa GPS data in seconds (default: 300)", type=float, default=300.0)
    parser.add_argument("--lora-sensor-max-age", help="Maximum age for LoRa sensor data in seconds (default: 600)", type=float, default=600.0)
    parser.add_argument("--disable-serial", help="Disable serial port reading", action="store_true")
    parser.add_argument("--parsing-error-threshold", help="Max parsing errors before reset (default: 3)", type=int, default=MAX_PARSING_ERRORS)
    parser.add_argument("--connection-error-threshold", help="Max connection errors before reset (default: 3)", type=int, default=DEFAULT_CONNECTION_ERROR_THRESHOLD)
    parser.add_argument("--backoff-initial", help="Initial backoff delay in seconds (default: 1.0)", type=float, default=DEFAULT_INITIAL_BACKOFF_SECONDS)
    parser.add_argument("--backoff-max", help="Maximum backoff delay in seconds (default: 60.0)", type=float, default=DEFAULT_MAX_BACKOFF_SECONDS)
    parser.add_argument("--backoff-multiplier", help="Exponential backoff multiplier (default: 2.0)", type=float, default=DEFAULT_BACKOFF_MULTIPLIER)
    parser.add_argument("--health-topic", help="MQTT topic for health reports (default: {mqtt_topic}/health)", type=str, default=None)
    parser.add_argument("--health-interval", help="Health report interval in seconds (default: 60)", type=float, default=DEFAULT_HEALTH_REPORT_INTERVAL)
    parser.add_argument("--graceful-degradation", help="Continue with partial data when possible", action="store_true")
    parser.add_argument("--enable-validation", help="Enable data validation and sanity checks", action="store_true")
    parser.add_argument("--min-distance", help="Minimum valid distance in meters (default: 0.0)", type=float, default=0.0)
    parser.add_argument("--max-distance", help="Maximum valid distance in meters (default: 300.0)", type=float, default=MAX_DISTANCE_METERS)
    parser.add_argument("--reject-zero-gps", help="Reject GPS coordinates at 0,0 (default: True)", action="store_true", default=True)
    parser.add_argument("--min-battery", help="Minimum valid battery percentage (default: 0.0)", type=float, default=0.0)
    parser.add_argument("--max-battery", help="Maximum valid battery percentage (default: 100.0)", type=float, default=100.0)
    parser.add_argument("--min-temperature", help="Minimum valid temperature in Celsius (default: -40.0)", type=float, default=-40.0)
    parser.add_argument("--max-temperature", help="Maximum valid temperature in Celsius (default: 85.0)", type=float, default=85.0)
    parser.add_argument("--validation-failures-topic", help="MQTT topic for validation failures (default: {mqtt_topic}/validation_failures)", type=str, default=None)
    return parser.parse_args()


class PacketProcessor:
    """Processes UWB packets from serial port."""

    def __init__(
        self,
        logger: UwbLogger,
        mqtt_client: Optional[UwbMqttClient],
        uwb_converter: Optional[Any] = None,
        error_recovery: Optional[ErrorRecovery] = None,
        health_monitor: Optional[HealthMonitor] = None,
        data_validator: Optional[DataValidator] = None,
        graceful_degradation: bool = False
    ) -> None:
        self.logger = logger
        self.mqtt_client = mqtt_client
        self.uwb_converter = uwb_converter
        self.error_recovery = error_recovery
        self.health_monitor = health_monitor
        self.data_validator = data_validator
        self.graceful_degradation = graceful_degradation

    def handle_parsing_error(self, error_msg: str) -> bool:
        """Handle packet parsing errors."""
        if self.error_recovery:
            if self.health_monitor:
                self.health_monitor.record_parsing_error()
            return self.error_recovery.record_error(ErrorType.PARSING)
        else:
            # Fallback to simple counting if error recovery not available
            return False

    def process_results(
        self,
        results: List[List[Union[int, float]]],
        assignments: Optional[List[List[int]]] = None
    ) -> None:
        """Process and publish results."""
        # Graceful degradation: continue with partial data if enabled
        if len(results) == 0:
            if self.graceful_degradation:
                self.logger.verbose("No results to publish (graceful degradation: continuing)")
            return

        # Record successful packet processing
        if self.health_monitor:
            self.health_monitor.record_successful_packet()

        current_timestamp = time.time()
        formatted_data = []
        validation_failures = []

        # Format data and validate if validator is enabled
        for item in results:
            mqtt_entry = ["{:04X}".format(item[0]), "{:04X}".format(item[1]), round(item[2], 3)]

            # Validate distance if validator is enabled
            if self.data_validator:
                distance = float(item[2])
                node1 = mqtt_entry[0]
                node2 = mqtt_entry[1]
                validation_result = self.data_validator.validate_distance(distance, node1, node2)

                if validation_result.is_valid:
                    formatted_data.append(mqtt_entry)
                else:
                    # Log validation failure
                    self.logger.warning(f"Validation failed: {validation_result.reason}")
                    validation_failures.append({
                        "type": "distance",
                        "edge": mqtt_entry,
                        "reason": validation_result.reason,
                        "timestamp": current_timestamp
                    })
            else:
                formatted_data.append(mqtt_entry)

        # Publish validation failures if validator is enabled and failures occurred
        if self.data_validator and validation_failures and self.mqtt_client:
            # Try to get validation failures topic from validator or use default
            failures_topic = getattr(self.data_validator, 'validation_failures_topic', None)
            if failures_topic:
                try:
                    import json
                    failures_json = json.dumps({
                        "timestamp": current_timestamp,
                        "failures": validation_failures,
                        "total_failures": len(validation_failures)
                    })
                    if self.mqtt_client.client and self.mqtt_client.client.is_connected():
                        self.mqtt_client.client.publish(failures_topic, failures_json, qos=1)
                        self.logger.verbose(f"Published {len(validation_failures)} validation failures to {failures_topic}")
                except Exception as e:
                    self.logger.warning(f"Failed to publish validation failures: {e}")

        # If all data was rejected, log warning
        if self.data_validator and len(formatted_data) == 0 and len(results) > 0:
            self.logger.warning(f"All {len(results)} distance measurements were rejected by validation")
            if not self.graceful_degradation:
                return

        # Convert to CGA format if requested
        if self.uwb_converter is not None:
            try:
                network_data = self.uwb_converter.convert_edges_to_network(formatted_data, timestamp=current_timestamp)
                # Don't log every conversion (too verbose) - only log on errors
                if self.mqtt_client:
                    try:
                        self.mqtt_client.publish(network_data)
                        if self.health_monitor:
                            self.health_monitor.record_mqtt_publish(success=True)
                    except Exception as e:
                        if self.health_monitor:
                            self.health_monitor.record_mqtt_publish(success=False)
                        self.logger.warning(f"MQTT publish failed: {e}")
            except Exception as e:
                self.logger.error(f"Failed to convert to CGA format: {e}")
                self.logger.info("Falling back to simple edge list format")
                if self.mqtt_client:
                    self.mqtt_client.publish(formatted_data)
        else:
            # Publish in simple edge list format
            if self.mqtt_client:
                try:
                    self.mqtt_client.publish(formatted_data)
                    if self.health_monitor:
                        self.health_monitor.record_mqtt_publish(success=True)
                except Exception as e:
                    if self.health_monitor:
                        self.health_monitor.record_mqtt_publish(success=False)
                    self.logger.warning(f"MQTT publish failed: {e}")


def main() -> None:
    """Main entry point."""
    args = parse_arguments()

    # Initialize logger
    logger = UwbLogger(verbose=args.verbose, quiet=args.quiet)

    # Load dev_eui mapping
    dev_eui_map = {}
    if args.dev_eui_mapping and os.path.exists(args.dev_eui_mapping):
        try:
            with open(args.dev_eui_mapping, 'r') as f:
                config = json.load(f)
            if 'dev_eui_to_uwb_id' in config:
                dev_eui_map = config['dev_eui_to_uwb_id']
                dev_eui_map = {k.upper(): v.upper() for k, v in dev_eui_map.items()}
                logger.verbose(f"Loaded {len(dev_eui_map)} dev_eui to UWB ID mappings")
        except Exception as e:
            logger.warning(f"Failed to load dev_eui mapping: {e}")

    # Initialize LoRa cache
    lora_cache = None
    if args.enable_lora_cache:
        if LoraTagDataCache is None:
            logger.warning("--enable-lora-cache requires lora_tag_cache.py module - LoRa caching disabled")
        else:
            lora_cache = LoraTagDataCache(
                broker=args.lora_broker,
                port=args.lora_port,
                username=args.lora_username,
                password=args.lora_password,
                topic_pattern=args.lora_topic,
                dev_eui_to_uwb_id_map=dev_eui_map,
                verbose=args.verbose,
                gps_ttl_seconds=args.lora_gps_max_age,
                sensor_ttl_seconds=args.lora_sensor_max_age
            )
            lora_cache.start()
            logger.info("LoRa tag data cache enabled and started")

    # Initialize UWB converter
    uwb_converter = None
    if args.cga_format:
        if UwbNetworkConverter is None:
            logger.error("--cga-format requires uwb_network_converter.py module")
            sys.exit(1)
        uwb_converter = UwbNetworkConverter(
            anchor_config_path=args.anchor_config,
            dev_eui_mapping_path=args.dev_eui_mapping,
            lora_cache=lora_cache
        )

    # Initialize error recovery system
    error_recovery = ErrorRecovery(
        logger=logger,
        parsing_error_threshold=args.parsing_error_threshold,
        connection_error_threshold=args.connection_error_threshold,
        initial_backoff_seconds=args.backoff_initial,
        max_backoff_seconds=args.backoff_max,
        backoff_multiplier=args.backoff_multiplier
    )

    # Initialize MQTT client
    mqtt_client = None
    if not args.disable_mqtt:
        mqtt_client = UwbMqttClient(
            broker=args.mqtt_broker,
            port=args.mqtt_port,
            topic=args.mqtt_topic,
            rate_limit=args.mqtt_rate_limit,
            verbose=args.verbose,
            quiet=args.quiet,
            disable_mqtt=args.disable_mqtt
        )
        mqtt_client.setup()

    # Initialize health monitor
    health_topic = args.health_topic or f"{args.mqtt_topic}/health"
    health_monitor = HealthMonitor(
        logger=logger,
        mqtt_client=mqtt_client,
        health_topic=health_topic,
        report_interval=args.health_interval
    )

    # Update health monitor with LoRa cache status
    if lora_cache:
        health_monitor.update_connection_status(lora_cache_connected=True)

    # Initialize data validator if enabled
    data_validator = None
    if args.enable_validation:
        validation_failures_topic = args.validation_failures_topic or f"{args.mqtt_topic}/validation_failures"
        data_validator = DataValidator(
            logger=logger,
            min_distance_meters=args.min_distance,
            max_distance_meters=args.max_distance,
            min_battery_percent=args.min_battery,
            max_battery_percent=args.max_battery,
            min_temperature_celsius=args.min_temperature,
            max_temperature_celsius=args.max_temperature,
            reject_zero_gps=args.reject_zero_gps,
            verbose=args.verbose
        )
        # Store validation failures topic for later use
        data_validator.validation_failures_topic = validation_failures_topic
        logger.info(f"Data validation enabled (distance: {args.min_distance}-{args.max_distance}m, GPS: reject_zero={args.reject_zero_gps})")

        # Pass validator to network converter if it exists
        if uwb_converter:
            uwb_converter.data_validator = data_validator

    # Initialize packet processor with error recovery, health monitoring, and validation
    processor = PacketProcessor(
        logger,
        mqtt_client,
        uwb_converter,
        error_recovery=error_recovery,
        health_monitor=health_monitor,
        data_validator=data_validator,
        graceful_degradation=args.graceful_degradation
    )

    # Print startup info
    logger.start("UWB MQTT Publisher Starting...")
    if args.disable_serial:
        logger.start("Serial port: DISABLED (testing mode)")
    else:
        logger.start(f"Serial port: {args.uart}")
    logger.start(f"MQTT broker: {args.mqtt_broker}:{args.mqtt_port}")

    # Initialize serial port
    ser = None
    if not args.disable_serial:
        logger.verbose(f"Connecting to serial port {args.uart}")
        ser = connect_serial(args.uart, verbose=args.verbose)

        if not ser:
            logger.error("Failed to connect to serial port")
            health_monitor.update_connection_status(serial_connected=False)
            error_recovery.record_error(ErrorType.SERIAL)
            sys.exit(1)

        health_monitor.update_connection_status(serial_connected=True)
        reset_device(ser, verbose=args.verbose)
        time.sleep(0.5)
        ser.reset_input_buffer()
        ser.write([PACKET_HEADER_BYTE_1, PACKET_HEADER_BYTE_2, 1, 0, ord('s')])
    else:
        logger.info("Serial port disabled - running in test mode")

    # Main processing loop
    if args.disable_serial:
        logger.start("Running in test mode (no serial data processing)")
        logger.info("Press Ctrl+C to exit")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.start("\nShutting down...")
    else:
        logger.start("Data processing started...")

        s = []
        assignments = []
        mode = 0
        g1 = 0
        g2 = 0
        g3 = 0
        unassigned_count = 0

        try:
            while True:
                # Report health status periodically
                health_monitor.report_health()

                cnt = ser.in_waiting
                if cnt > 0:
                    newS = read_serial(ser, 1)
                    s = s + newS

                    while len(s) >= 4:
                        try:
                            if s[0] == PACKET_HEADER_BYTE_1 and s[1] == PACKET_HEADER_BYTE_2:
                                payload_len = struct.unpack('<H', bytes(s[2:4]))[0]
                                payload = read_serial(ser, payload_len)
                                s = []
                                idx = 0

                                if len(payload) < 4:
                                    raise ValueError("Payload too short")

                                [act_type, act_slot, timeframe] = struct.unpack('<BbH', bytes(payload[idx:(idx + 4)]))
                                # Only log act_type for assignment packets (type 2) to reduce noise
                                if payload[0] == PACKET_TYPE_ASSIGNMENT:
                                    logger.verbose(f"Assignment packet: act_type={hex(act_type)}, slot={act_slot}, timeframe={timeframe}")
                                idx = idx + 4

                                if payload[0] == PACKET_TYPE_ASSIGNMENT:
                                    # Assignment packet
                                    assignments = []
                                    if len(payload) < idx + 5:
                                        raise ValueError("Assignment payload too short")

                                    [tx_pwr, mode, g1, g2, g3] = struct.unpack('<BBBBB', bytes(payload[idx:(idx + 5)]))
                                    # Only log mode details if groups changed significantly
                                    logger.verbose(f"Assignment: mode={hex(mode)}, groups=[{g1}, {g2}, {g3}]")
                                    idx = idx + 5

                                    group1 = []
                                    for i in range(0, g1):
                                        if idx + 2 > len(payload):
                                            raise ValueError("Group1 data incomplete")
                                        group1.append(struct.unpack('<H', bytes(payload[idx:(idx + 2)]))[0])
                                        idx = idx + 2

                                    group2 = []
                                    for i in range(0, g2):
                                        if idx + 2 > len(payload):
                                            raise ValueError("Group2 data incomplete")
                                        group2.append(struct.unpack('<H', bytes(payload[idx:(idx + 2)]))[0])
                                        idx = idx + 2

                                    group3 = []
                                    unassigned_count = 0
                                    for i in range(0, g3):
                                        if idx + 2 > len(payload):
                                            raise ValueError("Group3 data incomplete")
                                        id = struct.unpack('<H', bytes(payload[idx:(idx + 2)]))[0]
                                        if id == 0:
                                            unassigned_count = unassigned_count + 1
                                        group3.append(id)
                                        idx = idx + 2

                                    assignments = [group1, group2, group3]
                                    # Only log assignments if they changed (reduce noise)
                                    if not hasattr(processor, '_last_assignments') or processor._last_assignments != assignments:
                                        logger.verbose(f"New assignments: group1={len(group1)}, group2={len(group2)}, group3={len(group3)}")
                                        processor._last_assignments = assignments

                                if payload[0] == PACKET_TYPE_DISTANCE:
                                    # Distance measurement packet
                                    # Check if we have valid assignments from a previous type 2 packet
                                    if not assignments or len(assignments) != 3:
                                        logger.warning(f"Distance packet received but no valid assignments (assignments={assignments}), skipping")
                                        continue

                                    # Verify assignments structure
                                    if not all(isinstance(g, list) and len(g) > 0 for g in assignments):
                                        logger.warning(f"Invalid assignments structure: {assignments}, skipping distance packet")
                                        continue

                                    tof_count = g1 * g2 + g1 * g3 + g2 * g3
                                    if mode & MODE_GROUP1_INTERNAL:
                                        tof_count = tof_count + g1 * (g1 - 1) / 2
                                    if mode & MODE_GROUP2_INTERNAL:
                                        tof_count = tof_count + g2 * (g2 - 1) / 2

                                    tof_count = int(tof_count)
                                    # Don't log tof_count every time (too verbose)

                                    ii = (idx + tof_count * 2)

                                    for i in range(0, unassigned_count):
                                        if ii + 2 > len(payload):
                                            raise ValueError("New assignments data incomplete")
                                        id = struct.unpack('<H', bytes(payload[ii:(ii + 2)]))[0]
                                        ii = ii + 2
                                        assignments[2][g3 - unassigned_count + i] = id

                                    # Parse final payload
                                    # Only log parsing details if verbose and first time or on error
                                    results = parse_final_payload(
                                        assignments,
                                        bytes(payload[idx:]),
                                        mode,
                                        error_handler=processor.handle_parsing_error
                                    )

                                    # Process and publish results
                                    processor.process_results(results, assignments)

                            else:
                                # Not a start of packet, realign
                                logger.verbose(f'Realigning: thrash {hex(s[0])}: {chr((s[0])) if 32 <= s[0] <= 126 else "?"}')
                                s = s[1:]

                        except ResetRequiredException:
                            # Check if we should reset with backoff
                            if error_recovery.should_reset_with_backoff():
                                if health_monitor:
                                    health_monitor.record_device_reset()
                                error_recovery.record_reset()
                                reset_device(ser, verbose=args.verbose)
                                ser.reset_input_buffer()
                                s = []
                                assignments = []
                                error_recovery.reset_error_counts(ErrorType.PARSING)
                            continue
                        except OSError as e:
                            # Connection errors
                            if health_monitor:
                                health_monitor.record_connection_error()
                            if error_recovery.record_error(ErrorType.CONNECTION):
                                logger.error(f"Connection error threshold reached: {e}")
                                if error_recovery.should_reset_with_backoff():
                                    if health_monitor:
                                        health_monitor.record_device_reset()
                                    error_recovery.record_reset()
                                    reset_device(ser, verbose=args.verbose)
                                    ser.reset_input_buffer()
                                    s = []
                                    assignments = []
                                    error_recovery.reset_error_counts(ErrorType.CONNECTION)
                            continue
                        except (struct.error, ValueError, IndexError) as e:
                            if processor.handle_parsing_error(f"Packet processing: {str(e)}"):
                                # Check if we should reset with backoff
                                if error_recovery.should_reset_with_backoff():
                                    if health_monitor:
                                        health_monitor.record_device_reset()
                                    error_recovery.record_reset()
                                    reset_device(ser, verbose=args.verbose)
                                    ser.reset_input_buffer()
                                    s = []
                                    assignments = []
                                    error_recovery.reset_error_counts(ErrorType.PARSING)
                            continue

        except KeyboardInterrupt:
            logger.start("\nShutting down...")
        finally:
            # Final health report
            if health_monitor:
                health_monitor.report_health(force=True)
                health_monitor.update_connection_status(
                    serial_connected=False,
                    mqtt_connected=False,
                    lora_cache_connected=False
                )

            # Cleanup
            if lora_cache:
                logger.verbose("Stopping LoRa tag cache...")
                lora_cache.stop()
            if mqtt_client:
                mqtt_client.disconnect()
            if ser:
                logger.verbose("Disconnecting from serial port...")
                disconnect_serial(ser)
            logger.verbose("Cleanup complete, exiting...")
            sys.exit(0)


if __name__ == '__main__':
    main()
