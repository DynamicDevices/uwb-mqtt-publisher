#!/usr/bin/env python3
"""
UWB Position Confidence Scorer
Calculates confidence scores for position data based on source, age, and quality metrics.
"""

import time
from typing import Dict, Optional, Any
from uwb_logging import UwbLogger


class ConfidenceScorer:
    """Calculates position confidence scores for UWB and LoRa data."""

    def __init__(
        self,
        logger: UwbLogger,
        anchor_confidence: float = 1.0,
        lora_gps_base_confidence: float = 0.7,
        lora_gps_min_confidence: float = 0.3,
        lora_gps_decay_rate: float = 0.1,  # Confidence decay per TTL period
        gps_accuracy_weight: float = 0.2,  # Weight for GPS accuracy in confidence
        gateway_count_weight: float = 0.1,  # Weight for number of gateways
        rssi_weight: float = 0.1,  # Weight for RSSI/SNR
        verbose: bool = False
    ) -> None:
        """
        Initialize confidence scorer.

        Args:
            logger: Logger instance
            anchor_confidence: Confidence score for anchor points (default: 1.0)
            lora_gps_base_confidence: Base confidence for LoRa GPS data (default: 0.7)
            lora_gps_min_confidence: Minimum confidence for LoRa GPS data (default: 0.3)
            lora_gps_decay_rate: Rate of confidence decay per TTL period (default: 0.1)
            gps_accuracy_weight: Weight for GPS accuracy in confidence calculation (default: 0.2)
            gateway_count_weight: Weight for gateway count in confidence calculation (default: 0.1)
            rssi_weight: Weight for RSSI/SNR in confidence calculation (default: 0.1)
            verbose: Enable verbose logging
        """
        self.logger = logger
        self.anchor_confidence = anchor_confidence
        self.lora_gps_base_confidence = lora_gps_base_confidence
        self.lora_gps_min_confidence = lora_gps_min_confidence
        self.lora_gps_decay_rate = lora_gps_decay_rate
        self.gps_accuracy_weight = gps_accuracy_weight
        self.gateway_count_weight = gateway_count_weight
        self.rssi_weight = rssi_weight
        self.verbose = verbose

    def calculate_anchor_confidence(self) -> float:
        """
        Calculate confidence for anchor points.

        Returns:
            Confidence score (always 1.0 for anchors)
        """
        return self.anchor_confidence

    def calculate_lora_gps_confidence(
        self,
        lora_data: Dict[str, Any],
        gps_ttl_seconds: float = 300.0,
        current_time: Optional[float] = None
    ) -> float:
        """
        Calculate confidence for LoRa GPS data based on age and quality metrics.

        Args:
            lora_data: LoRa data dictionary containing location, metadata, etc.
            gps_ttl_seconds: GPS TTL in seconds (default: 300.0)
            current_time: Current timestamp (default: time.time())

        Returns:
            Confidence score between min_confidence and base_confidence
        """
        if current_time is None:
            current_time = time.time()

        # Start with base confidence
        confidence = self.lora_gps_base_confidence

        # Calculate data age
        data_timestamp = lora_data.get("timestamp", 0)
        if not data_timestamp:
            # Try to parse received_at if timestamp not available
            received_at = lora_data.get("received_at")
            if received_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(received_at.replace('Z', '+00:00'))
                    data_timestamp = dt.timestamp()
                except (ValueError, TypeError):
                    # If we can't determine age, use minimum confidence
                    return self.lora_gps_min_confidence

        data_age = current_time - data_timestamp

        # Apply time-based decay
        # Decay is proportional to how much of the TTL has elapsed
        ttl_ratio = data_age / gps_ttl_seconds if gps_ttl_seconds > 0 else 1.0
        time_decay = self.lora_gps_decay_rate * ttl_ratio
        confidence -= time_decay

        # Apply GPS accuracy adjustment if available
        location = lora_data.get("location", {})
        if location:
            # GPS accuracy in meters (lower is better)
            accuracy = location.get("accuracy")
            if accuracy is not None:
                # Normalize accuracy: 0-50m = full confidence, 50-100m = reduced, >100m = more reduced
                if accuracy <= 10:
                    accuracy_bonus = self.gps_accuracy_weight * 0.5  # High accuracy bonus
                elif accuracy <= 50:
                    accuracy_bonus = self.gps_accuracy_weight * 0.2  # Medium accuracy bonus
                elif accuracy <= 100:
                    accuracy_bonus = 0.0  # No bonus
                else:
                    accuracy_bonus = -self.gps_accuracy_weight * 0.3  # Penalty for poor accuracy

                confidence += accuracy_bonus

        # Apply gateway count adjustment if available
        # More gateways = better signal quality
        metadata = lora_data.get("metadata", {})
        if metadata:
            gateway_count = len(metadata.get("gateways", []))
            if gateway_count > 0:
                # More gateways = higher confidence (up to a point)
                if gateway_count >= 3:
                    gateway_bonus = self.gateway_count_weight * 0.5  # 3+ gateways = bonus
                elif gateway_count >= 2:
                    gateway_bonus = self.gateway_count_weight * 0.2  # 2 gateways = small bonus
                else:
                    gateway_bonus = 0.0  # 1 gateway = no bonus

                confidence += gateway_bonus

                # Apply RSSI/SNR adjustment if available
                # Use the best RSSI/SNR from all gateways
                best_rssi = None
                best_snr = None
                for gateway in metadata.get("gateways", []):
                    rssi = gateway.get("rssi")
                    snr = gateway.get("snr")
                    if rssi is not None and (best_rssi is None or rssi > best_rssi):
                        best_rssi = rssi
                    if snr is not None and (best_snr is None or snr > best_snr):
                        best_snr = snr

                # RSSI: higher is better (typically -120 to -50 dBm)
                if best_rssi is not None:
                    # Normalize RSSI: -50 to -80 = good, -80 to -100 = medium, < -100 = poor
                    if best_rssi >= -80:
                        rssi_bonus = self.rssi_weight * 0.3  # Good signal
                    elif best_rssi >= -100:
                        rssi_bonus = 0.0  # Medium signal
                    else:
                        rssi_bonus = -self.rssi_weight * 0.2  # Poor signal

                    confidence += rssi_bonus

                # SNR: higher is better (typically -20 to +20 dB)
                if best_snr is not None:
                    # Normalize SNR: > 5 = good, 0-5 = medium, < 0 = poor
                    if best_snr >= 5:
                        snr_bonus = self.rssi_weight * 0.2  # Good SNR
                    elif best_snr >= 0:
                        snr_bonus = 0.0  # Medium SNR
                    else:
                        snr_bonus = -self.rssi_weight * 0.1  # Poor SNR

                    confidence += snr_bonus

        # Clamp confidence to valid range
        confidence = max(self.lora_gps_min_confidence, min(self.lora_gps_base_confidence, confidence))

        if self.verbose:
            self.logger.verbose(
                f"Calculated LoRa GPS confidence: {confidence:.3f} "
                f"(age: {data_age:.1f}s, TTL: {gps_ttl_seconds}s)"
            )

        return round(confidence, 3)

    def calculate_confidence(
        self,
        is_anchor: bool,
        lora_data: Optional[Dict[str, Any]] = None,
        gps_ttl_seconds: float = 300.0,
        current_time: Optional[float] = None
    ) -> float:
        """
        Calculate position confidence based on source type and quality metrics.

        Args:
            is_anchor: Whether this is an anchor point
            lora_data: LoRa data dictionary (optional, for non-anchor points)
            gps_ttl_seconds: GPS TTL in seconds (default: 300.0)
            current_time: Current timestamp (default: time.time())

        Returns:
            Confidence score between 0.0 and 1.0
        """
        if is_anchor:
            return self.calculate_anchor_confidence()

        if lora_data and lora_data.get("location"):
            return self.calculate_lora_gps_confidence(lora_data, gps_ttl_seconds, current_time)

        # No position data available - return minimum confidence
        return 0.0
