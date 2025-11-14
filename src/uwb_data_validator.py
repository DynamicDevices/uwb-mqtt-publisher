#!/usr/bin/env python3
"""
UWB Data Validator
Validates UWB distance measurements, GPS coordinates, and sensor data for sanity.
"""

from typing import Dict, List, Optional, Any, Tuple, Union
from uwb_logging import UwbLogger
from uwb_constants import MAX_DISTANCE_METERS


class ValidationResult:
    """Result of a validation check."""

    def __init__(self, is_valid: bool, reason: Optional[str] = None):
        self.is_valid = is_valid
        self.reason = reason


class DataValidator:
    """Validates UWB and LoRa data for sanity and correctness."""

    def __init__(
        self,
        logger: UwbLogger,
        min_distance_meters: float = 0.0,
        max_distance_meters: float = MAX_DISTANCE_METERS,
        min_latitude: float = -90.0,
        max_latitude: float = 90.0,
        min_longitude: float = -180.0,
        max_longitude: float = 180.0,
        min_battery_percent: float = 0.0,
        max_battery_percent: float = 100.0,
        min_temperature_celsius: float = -40.0,
        max_temperature_celsius: float = 85.0,
        reject_zero_gps: bool = True,
        verbose: bool = False
    ) -> None:
        """
        Initialize data validator.

        Args:
            logger: Logger instance
            min_distance_meters: Minimum valid distance in meters (default: 0.0)
            max_distance_meters: Maximum valid distance in meters (default: 300.0)
            min_latitude: Minimum valid latitude (default: -90.0)
            max_latitude: Maximum valid latitude (default: 90.0)
            min_longitude: Minimum valid longitude (default: -180.0)
            max_longitude: Maximum valid longitude (default: 180.0)
            min_battery_percent: Minimum valid battery percentage (default: 0.0)
            max_battery_percent: Maximum valid battery percentage (default: 100.0)
            min_temperature_celsius: Minimum valid temperature in Celsius (default: -40.0)
            max_temperature_celsius: Maximum valid temperature in Celsius (default: 85.0)
            reject_zero_gps: Reject GPS coordinates at 0,0 (default: True)
            verbose: Enable verbose logging
        """
        self.logger = logger
        self.min_distance_meters = min_distance_meters
        self.max_distance_meters = max_distance_meters
        self.min_latitude = min_latitude
        self.max_latitude = max_latitude
        self.min_longitude = min_longitude
        self.max_longitude = max_longitude
        self.min_battery_percent = min_battery_percent
        self.max_battery_percent = max_battery_percent
        self.min_temperature_celsius = min_temperature_celsius
        self.max_temperature_celsius = max_temperature_celsius
        self.reject_zero_gps = reject_zero_gps
        self.verbose = verbose

        # Statistics
        self.validation_stats: Dict[str, int] = {
            "total_validated": 0,
            "distance_rejected": 0,
            "gps_rejected": 0,
            "battery_rejected": 0,
            "temperature_rejected": 0
        }

    def validate_distance(self, distance_meters: float, node1: Optional[str] = None, node2: Optional[str] = None) -> ValidationResult:
        """
        Validate UWB distance measurement.

        Args:
            distance_meters: Distance in meters
            node1: First node ID (for logging)
            node2: Second node ID (for logging)

        Returns:
            ValidationResult indicating if distance is valid
        """
        self.validation_stats["total_validated"] += 1

        if distance_meters < self.min_distance_meters:
            reason = f"Distance {distance_meters:.3f}m below minimum {self.min_distance_meters}m"
            if node1 and node2:
                reason += f" (nodes: {node1} -> {node2})"
            self.validation_stats["distance_rejected"] += 1
            return ValidationResult(False, reason)

        if distance_meters > self.max_distance_meters:
            reason = f"Distance {distance_meters:.3f}m exceeds maximum {self.max_distance_meters}m"
            if node1 and node2:
                reason += f" (nodes: {node1} -> {node2})"
            self.validation_stats["distance_rejected"] += 1
            return ValidationResult(False, reason)

        return ValidationResult(True)

    def validate_gps_coordinates(
        self,
        latitude: float,
        longitude: float,
        altitude: Optional[float] = None,
        uwb_id: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate GPS coordinates.

        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            altitude: Altitude in meters (optional, not validated)
            uwb_id: UWB ID (for logging)

        Returns:
            ValidationResult indicating if GPS coordinates are valid
        """
        # Check for zero coordinates (common invalid value)
        if self.reject_zero_gps and latitude == 0.0 and longitude == 0.0:
            reason = "GPS coordinates are 0,0 (invalid)"
            if uwb_id:
                reason += f" (UWB ID: {uwb_id})"
            self.validation_stats["gps_rejected"] += 1
            return ValidationResult(False, reason)

        # Check latitude range
        if latitude < self.min_latitude or latitude > self.max_latitude:
            reason = f"Latitude {latitude:.6f} outside valid range [{self.min_latitude}, {self.max_latitude}]"
            if uwb_id:
                reason += f" (UWB ID: {uwb_id})"
            self.validation_stats["gps_rejected"] += 1
            return ValidationResult(False, reason)

        # Check longitude range
        if longitude < self.min_longitude or longitude > self.max_longitude:
            reason = f"Longitude {longitude:.6f} outside valid range [{self.min_longitude}, {self.max_longitude}]"
            if uwb_id:
                reason += f" (UWB ID: {uwb_id})"
            self.validation_stats["gps_rejected"] += 1
            return ValidationResult(False, reason)

        return ValidationResult(True)

    def validate_battery_level(self, battery_percent: float, uwb_id: Optional[str] = None) -> ValidationResult:
        """
        Validate battery level.

        Args:
            battery_percent: Battery level as percentage (0-100)
            uwb_id: UWB ID (for logging)

        Returns:
            ValidationResult indicating if battery level is valid
        """
        if battery_percent < self.min_battery_percent or battery_percent > self.max_battery_percent:
            reason = f"Battery level {battery_percent:.1f}% outside valid range [{self.min_battery_percent}, {self.max_battery_percent}]"
            if uwb_id:
                reason += f" (UWB ID: {uwb_id})"
            self.validation_stats["battery_rejected"] += 1
            return ValidationResult(False, reason)

        return ValidationResult(True)

    def validate_temperature(self, temperature_celsius: float, uwb_id: Optional[str] = None) -> ValidationResult:
        """
        Validate temperature.

        Args:
            temperature_celsius: Temperature in Celsius
            uwb_id: UWB ID (for logging)

        Returns:
            ValidationResult indicating if temperature is valid
        """
        if temperature_celsius < self.min_temperature_celsius or temperature_celsius > self.max_temperature_celsius:
            reason = f"Temperature {temperature_celsius:.1f}°C outside valid range [{self.min_temperature_celsius}, {self.max_temperature_celsius}]"
            if uwb_id:
                reason += f" (UWB ID: {uwb_id})"
            self.validation_stats["temperature_rejected"] += 1
            return ValidationResult(False, reason)

        return ValidationResult(True)

    def validate_edge_list(
        self,
        edge_list: List[List[Union[str, float]]]
    ) -> Tuple[List[List[Union[str, float]]], List[Dict[str, Any]]]:
        """
        Validate a list of edges and return valid edges plus validation failures.

        Args:
            edge_list: List of edges in format [[node1, node2, distance], ...]

        Returns:
            Tuple of (valid_edges, validation_failures)
        """
        valid_edges = []
        validation_failures = []

        for edge in edge_list:
            if len(edge) < 3:
                validation_failures.append({
                    "type": "invalid_format",
                    "edge": edge,
                    "reason": "Edge must have at least 3 elements [node1, node2, distance]"
                })
                continue

            node1 = str(edge[0])
            node2 = str(edge[1])
            distance = float(edge[2])

            result = self.validate_distance(distance, node1, node2)
            if result.is_valid:
                valid_edges.append(edge)
            else:
                validation_failures.append({
                    "type": "distance_validation",
                    "edge": edge,
                    "reason": result.reason,
                    "node1": node1,
                    "node2": node2,
                    "distance": distance
                })
                if self.verbose:
                    self.logger.warning(f"Validation failed: {result.reason}")

        return valid_edges, validation_failures

    def validate_lora_data(self, lora_data: Dict[str, Any], uwb_id: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Validate LoRa tag data (GPS, battery, temperature).

        Args:
            lora_data: LoRa data dictionary
            uwb_id: UWB ID (for logging)

        Returns:
            Tuple of (is_valid, list_of_failure_reasons)
        """
        failures = []

        # Validate GPS coordinates if present
        location = lora_data.get("location", {})
        if location:
            lat = location.get("latitude")
            lon = location.get("longitude")

            if lat is not None and lon is not None:
                result = self.validate_gps_coordinates(lat, lon, location.get("altitude"), uwb_id)
                if not result.is_valid:
                    failures.append(result.reason or "GPS validation failed")
                    if self.verbose:
                        self.logger.warning(f"GPS validation failed: {result.reason}")

        # Validate battery level if present
        decoded_payload = lora_data.get("decoded_payload", {})
        battery = decoded_payload.get("battery")
        if battery is not None:
            try:
                battery_float = float(battery)
                result = self.validate_battery_level(battery_float, uwb_id)
                if not result.is_valid:
                    failures.append(result.reason or "Battery validation failed")
                    if self.verbose:
                        self.logger.warning(f"Battery validation failed: {result.reason}")
            except (ValueError, TypeError):
                failures.append(f"Invalid battery value: {battery}")

        # Validate temperature if present
        temperature = decoded_payload.get("temperature")
        if temperature is not None:
            try:
                temp_float = float(temperature)
                result = self.validate_temperature(temp_float, uwb_id)
                if not result.is_valid:
                    failures.append(result.reason or "Temperature validation failed")
                    if self.verbose:
                        self.logger.warning(f"Temperature validation failed: {result.reason}")
            except (ValueError, TypeError):
                failures.append(f"Invalid temperature value: {temperature}")

        return len(failures) == 0, failures

    def get_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        total_rejected = (
            self.validation_stats["distance_rejected"]
            + self.validation_stats["gps_rejected"]
            + self.validation_stats["battery_rejected"]
            + self.validation_stats["temperature_rejected"]
        )

        return {
            "total_validated": self.validation_stats["total_validated"],
            "total_rejected": total_rejected,
            "rejection_breakdown": {
                "distance": self.validation_stats["distance_rejected"],
                "gps": self.validation_stats["gps_rejected"],
                "battery": self.validation_stats["battery_rejected"],
                "temperature": self.validation_stats["temperature_rejected"]
            },
            "rejection_rate": (
                total_rejected / self.validation_stats["total_validated"]
                if self.validation_stats["total_validated"] > 0
                else 0.0
            )
        }
