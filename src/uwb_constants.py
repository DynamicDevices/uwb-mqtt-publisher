#!/usr/bin/env python3
"""
UWB Constants
Centralized constants for the UWB MQTT Publisher application.
"""

# TWR (Time-of-Flight) conversion factor
# Converts TWR units to meters: distance_meters = twr_value * TWR_TO_METERS
TWR_TO_METERS = 0.004690384

# Maximum valid distance in meters (used for TWR value validation)
MAX_DISTANCE_METERS = 300.0

# Packet header bytes
PACKET_HEADER_BYTE_1 = 0xDC
PACKET_HEADER_BYTE_2 = 0xAC

# Packet type constants
PACKET_TYPE_ASSIGNMENT = 2  # Assignment packet (act_type=2)
PACKET_TYPE_DISTANCE = 4    # Distance measurement packet (act_type=4)

# Error handling
MAX_PARSING_ERRORS = 3  # Maximum parsing errors before device reset

# Mode flags for packet parsing
MODE_GROUP1_INTERNAL = 1  # Bit 0: Group 1 internal measurements
MODE_GROUP2_INTERNAL = 2  # Bit 1: Group 2 internal measurements

# Error recovery defaults
DEFAULT_CONNECTION_ERROR_THRESHOLD = 3  # Connection errors before reset
DEFAULT_INITIAL_BACKOFF_SECONDS = 1.0  # Initial backoff delay
DEFAULT_MAX_BACKOFF_SECONDS = 60.0  # Maximum backoff delay
DEFAULT_BACKOFF_MULTIPLIER = 2.0  # Exponential backoff multiplier
DEFAULT_HEALTH_REPORT_INTERVAL = 60.0  # Health report interval in seconds

