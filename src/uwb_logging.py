#!/usr/bin/env python3
"""
UWB Logging Utilities
Provides consistent logging functions for the UWB MQTT Publisher.
"""

import sys


class UwbLogger:
    """Logger for UWB MQTT Publisher."""

    def __init__(self, verbose: bool = False, quiet: bool = False) -> None:
        """
        Initialize logger.

        Args:
            verbose: Enable verbose logging
            quiet: Enable quiet mode (minimal logging)
        """
        self._verbose = verbose
        self.quiet = quiet

    def info(self, message: str) -> None:
        """Log info message (always shown unless quiet)."""
        if not self.quiet:
            print(message)

    def verbose(self, message: str) -> None:
        """Log verbose message (only shown if verbose enabled)."""
        if self._verbose:
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
