#!/usr/bin/env python3
"""
UWB Error Recovery
Enhanced error recovery with exponential backoff and different error thresholds.
"""

import time
from typing import Optional, Dict, Any
from enum import Enum
from uwb_logging import UwbLogger
from uwb_constants import MAX_PARSING_ERRORS


class ErrorType(Enum):
    """Types of errors that can occur."""
    PARSING = "parsing"
    CONNECTION = "connection"
    SERIAL = "serial"
    MQTT = "mqtt"


class ErrorRecovery:
    """Manages error recovery with exponential backoff and different thresholds."""
    
    def __init__(
        self,
        logger: UwbLogger,
        parsing_error_threshold: int = MAX_PARSING_ERRORS,
        connection_error_threshold: int = 3,
        initial_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 60.0,
        backoff_multiplier: float = 2.0
    ) -> None:
        """
        Initialize error recovery system.
        
        Args:
            logger: Logger instance
            parsing_error_threshold: Max parsing errors before reset (default: MAX_PARSING_ERRORS)
            connection_error_threshold: Max connection errors before reset (default: 3)
            initial_backoff_seconds: Initial backoff delay (default: 1.0)
            max_backoff_seconds: Maximum backoff delay (default: 60.0)
            backoff_multiplier: Multiplier for exponential backoff (default: 2.0)
        """
        self.logger = logger
        self.parsing_error_threshold = parsing_error_threshold
        self.connection_error_threshold = connection_error_threshold
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.backoff_multiplier = backoff_multiplier
        
        # Error counters per type
        self.error_counts: Dict[ErrorType, int] = {
            ErrorType.PARSING: 0,
            ErrorType.CONNECTION: 0,
            ErrorType.SERIAL: 0,
            ErrorType.MQTT: 0
        }
        
        # Reset tracking
        self.reset_count = 0
        self.last_reset_time: Optional[float] = None
        self.current_backoff_seconds = initial_backoff_seconds
        
    def record_error(self, error_type: ErrorType) -> bool:
        """
        Record an error and determine if reset is needed.
        
        Args:
            error_type: Type of error that occurred
            
        Returns:
            True if reset is required, False otherwise
        """
        self.error_counts[error_type] += 1
        
        # Check threshold based on error type
        threshold = (
            self.parsing_error_threshold if error_type == ErrorType.PARSING
            else self.connection_error_threshold
        )
        
        if self.error_counts[error_type] >= threshold:
            self.logger.warning(
                f"{error_type.value.capitalize()} error threshold reached "
                f"({self.error_counts[error_type]}/{threshold}), reset required"
            )
            return True
        return False
        
    def should_reset_with_backoff(self) -> bool:
        """
        Check if reset should be performed, considering exponential backoff.
        
        Returns:
            True if reset should be performed now, False if still in backoff period
        """
        if self.last_reset_time is None:
            return True
            
        time_since_reset = time.time() - self.last_reset_time
        
        # Calculate current backoff delay
        backoff_delay = min(
            self.initial_backoff_seconds * (self.backoff_multiplier ** self.reset_count),
            self.max_backoff_seconds
        )
        
        if time_since_reset < backoff_delay:
            remaining = backoff_delay - time_since_reset
            self.logger.verbose(
                f"Backoff active: {remaining:.1f}s remaining "
                f"(backoff: {backoff_delay:.1f}s, reset count: {self.reset_count})"
            )
            return False
            
        return True
        
    def reset_error_counts(self, error_type: Optional[ErrorType] = None) -> None:
        """
        Reset error counts, optionally for a specific error type.
        
        Args:
            error_type: Error type to reset, or None to reset all
        """
        if error_type:
            self.error_counts[error_type] = 0
        else:
            for err_type in ErrorType:
                self.error_counts[err_type] = 0
                
    def record_reset(self) -> None:
        """Record that a reset was performed."""
        self.reset_count += 1
        self.last_reset_time = time.time()
        self.current_backoff_seconds = min(
            self.initial_backoff_seconds * (self.backoff_multiplier ** self.reset_count),
            self.max_backoff_seconds
        )
        self.logger.info(
            f"Device reset #{self.reset_count} performed "
            f"(next backoff: {self.current_backoff_seconds:.1f}s)"
        )
        
    def get_stats(self) -> Dict[str, Any]:
        """Get error recovery statistics."""
        return {
            "error_counts": {err_type.value: count for err_type, count in self.error_counts.items()},
            "reset_count": self.reset_count,
            "last_reset_time": self.last_reset_time,
            "current_backoff_seconds": self.current_backoff_seconds,
            "thresholds": {
                "parsing": self.parsing_error_threshold,
                "connection": self.connection_error_threshold
            }
        }

