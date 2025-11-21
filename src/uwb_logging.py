#!/usr/bin/env python3
"""
UWB Logging Utilities
Provides consistent logging functions for the UWB MQTT Publisher.
"""

import sys


class UwbLogger:
    """Logger for UWB MQTT Publisher."""

    def __init__(
        self,
        verbose: bool = False,
        quiet: bool = False,
        log_received_data: bool = False,
        log_published_data: bool = False
    ) -> None:
        """
        Initialize logger.

        Args:
            verbose: Enable verbose logging
            quiet: Enable quiet mode (minimal logging)
            log_received_data: Enable logging of received UWB data from serial port
            log_published_data: Enable logging of published UWB data to MQTT broker
        """
        self._verbose_flag = verbose
        self.quiet = quiet
        self._log_received_data = log_received_data
        self._log_published_data = log_published_data

    def info(self, message: str) -> None:
        """Log info message (always shown unless quiet)."""
        if not self.quiet:
            print(message)

    def verbose(self, message: str) -> None:
        """Log verbose message (only shown if verbose enabled)."""
        if self._verbose_flag:
            print(message)

    def warning(self, message: str) -> None:
        """Log warning message (always shown)."""
        print(f"[WARNING] {message}")

    def error(self, message: str) -> None:
        """Log error message (always shown)."""
        print(f"[ERROR] {message}", file=sys.stderr)

    def start(self, message: str) -> None:
        """Log startup message (always shown unless quiet)."""
        if not self.quiet:
            print(f"[START] {message}")

    def log_received_data(self, message: str) -> None:
        """Log received UWB data from serial port (only if enabled)."""
        if self._log_received_data:
            print(f"[RECEIVED] {message}")

    def log_published_data(self, message: str) -> None:
        """Log published UWB data to MQTT broker (only if enabled)."""
        if self._log_published_data:
            print(f"[PUBLISHED] {message}")
