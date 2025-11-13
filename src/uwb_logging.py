#!/usr/bin/env python3
"""
UWB Logging Utilities
Provides consistent logging functions for the UWB MQTT Publisher.
"""

import sys


class UwbLogger:
    """Logger for UWB MQTT Publisher."""
    
    def __init__(self, verbose=False, quiet=False):
        """
        Initialize logger.
        
        Args:
            verbose: Enable verbose logging
            quiet: Enable quiet mode (minimal logging)
        """
        self.verbose = verbose
        self.quiet = quiet
    
    def info(self, message):
        """Log info message (always shown unless quiet)."""
        if not self.quiet:
            print(message)
    
    def verbose(self, message):
        """Log verbose message (only shown if verbose enabled)."""
        if self.verbose:
            print(message)
    
    def warning(self, message):
        """Log warning message (always shown)."""
        print(f"[WARNING] {message}")
    
    def error(self, message):
        """Log error message (always shown)."""
        print(f"[ERROR] {message}", file=sys.stderr)
    
    def start(self, message):
        """Log startup message (always shown unless quiet)."""
        if not self.quiet:
            print(f"[START] {message}")

