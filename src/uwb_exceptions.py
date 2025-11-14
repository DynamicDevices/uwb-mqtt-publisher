#!/usr/bin/env python3
"""
UWB Exceptions
Custom exception classes for the UWB MQTT Publisher application.
"""


class ResetRequiredException(Exception):
    """Exception raised when device reset is required after parsing errors."""
    pass

