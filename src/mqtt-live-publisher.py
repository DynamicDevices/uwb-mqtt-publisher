#!/usr/bin/env python3
"""
UWB MQTT Publisher - Main Entry Point
Refactored version using modular components.

Version: 1.1.0
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
    PACKET_HEADER_BYTE_1,
    PACKET_HEADER_BYTE_2,
    PACKET_TYPE_ASSIGNMENT,
    PACKET_TYPE_DISTANCE,
    MODE_GROUP1_INTERNAL,
    MODE_GROUP2_INTERNAL
)
from uwb_exceptions import ResetRequiredException

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
    return parser.parse_args()


class PacketProcessor:
    """Processes UWB packets from serial port."""
    
    def __init__(
        self, 
        logger: UwbLogger, 
        mqtt_client: Optional[UwbMqttClient], 
        uwb_converter: Optional[Any] = None
    ) -> None:
        self.logger = logger
        self.mqtt_client = mqtt_client
        self.uwb_converter = uwb_converter
        self.parsing_error_count = 0
        
    def handle_parsing_error(self, error_msg: str) -> bool:
        """Handle packet parsing errors."""
        self.parsing_error_count += 1
        self.logger.warning(f"Packet parsing error ({self.parsing_error_count}/{MAX_PARSING_ERRORS}): {error_msg}")
        
        if self.parsing_error_count >= MAX_PARSING_ERRORS:
            self.logger.warning(f"Maximum parsing errors reached ({MAX_PARSING_ERRORS}), resetting device...")
            return True
        return False
    
    def process_results(
        self, 
        results: List[List[Union[int, float]]], 
        assignments: Optional[List[List[int]]] = None
    ) -> None:
        """Process and publish results."""
        if len(results) == 0:
            return
        
        current_timestamp = time.time()
        formatted_data = []
        
        for item in results:
            mqtt_entry = ["{:04X}".format(item[0]), "{:04X}".format(item[1]), round(item[2], 3)]
            formatted_data.append(mqtt_entry)
        
        # Convert to CGA format if requested
        if self.uwb_converter is not None:
            try:
                network_data = self.uwb_converter.convert_edges_to_network(formatted_data, timestamp=current_timestamp)
                # Don't log every conversion (too verbose) - only log on errors
                if self.mqtt_client:
                    self.mqtt_client.publish(network_data)
            except Exception as e:
                self.logger.error(f"Failed to convert to CGA format: {e}")
                self.logger.info("Falling back to simple edge list format")
                if self.mqtt_client:
                    self.mqtt_client.publish(formatted_data)
        else:
            # Publish in simple edge list format
            if self.mqtt_client:
                self.mqtt_client.publish(formatted_data)


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
    
    # Initialize packet processor
    processor = PacketProcessor(logger, mqtt_client, uwb_converter)
    
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
            sys.exit(1)
        
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
                                
                                [act_type, act_slot, timeframe] = struct.unpack('<BbH', bytes(payload[idx:(idx+4)]))
                                # Only log act_type for assignment packets (type 2) to reduce noise
                                if payload[0] == PACKET_TYPE_ASSIGNMENT:
                                    logger.verbose(f"Assignment packet: act_type={hex(act_type)}, slot={act_slot}, timeframe={timeframe}")
                                idx = idx + 4
                                
                                if payload[0] == PACKET_TYPE_ASSIGNMENT:
                                    # Assignment packet
                                    assignments = []
                                    if len(payload) < idx + 5:
                                        raise ValueError("Assignment payload too short")
                                    
                                    [tx_pwr, mode, g1, g2, g3] = struct.unpack('<BBBBB', bytes(payload[idx:(idx+5)]))
                                    # Only log mode details if groups changed significantly
                                    logger.verbose(f"Assignment: mode={hex(mode)}, groups=[{g1}, {g2}, {g3}]")
                                    idx = idx + 5
                                    
                                    group1 = []
                                    for i in range(0, g1):
                                        if idx + 2 > len(payload):
                                            raise ValueError("Group1 data incomplete")
                                        group1.append(struct.unpack('<H', bytes(payload[idx:(idx+2)]))[0])
                                        idx = idx + 2
                                    
                                    group2 = []
                                    for i in range(0, g2):
                                        if idx + 2 > len(payload):
                                            raise ValueError("Group2 data incomplete")
                                        group2.append(struct.unpack('<H', bytes(payload[idx:(idx+2)]))[0])
                                        idx = idx + 2
                                    
                                    group3 = []
                                    unassigned_count = 0
                                    for i in range(0, g3):
                                        if idx + 2 > len(payload):
                                            raise ValueError("Group3 data incomplete")
                                        id = struct.unpack('<H', bytes(payload[idx:(idx+2)]))[0]
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
                                        tof_count = tof_count + g1 * (g1-1) / 2
                                    if mode & MODE_GROUP2_INTERNAL:
                                        tof_count = tof_count + g2 * (g2-1) / 2
                                    
                                    tof_count = int(tof_count)
                                    # Don't log tof_count every time (too verbose)
                                    
                                    ii = (idx + tof_count * 2)
                                    
                                    for i in range(0, unassigned_count):
                                        if ii + 2 > len(payload):
                                            raise ValueError("New assignments data incomplete")
                                        id = struct.unpack('<H', bytes(payload[ii:(ii+2)]))[0]
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
                            reset_device(ser, verbose=args.verbose)
                            ser.reset_input_buffer()
                            s = []
                            assignments = []
                            processor.parsing_error_count = 0
                            continue
                        except (struct.error, ValueError, IndexError, OSError) as e:
                            if processor.handle_parsing_error(f"Packet processing: {str(e)}"):
                                reset_device(ser, verbose=args.verbose)
                                ser.reset_input_buffer()
                                s = []
                                assignments = []
                                processor.parsing_error_count = 0
                                continue
        
        except KeyboardInterrupt:
            logger.start("\nShutting down...")
        finally:
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

