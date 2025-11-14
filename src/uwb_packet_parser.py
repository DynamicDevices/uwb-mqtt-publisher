#!/usr/bin/env python3
"""
UWB Packet Parser
Parses UWB packets from serial port and extracts distance measurements.
"""

import struct
from typing import List, Optional, Callable, Union
from uwb_constants import (
    TWR_TO_METERS, 
    MAX_DISTANCE_METERS,
    MODE_GROUP1_INTERNAL,
    MODE_GROUP2_INTERNAL
)
from uwb_exceptions import ResetRequiredException


def twr_value_ok(value: int) -> bool:
    """
    Check if TWR value is valid.
    
    Args:
        value: TWR value to validate
        
    Returns:
        True if value is valid (positive and within max distance)
    """
    return value > 0 and TWR_TO_METERS * value < MAX_DISTANCE_METERS


def parse_final_payload(
    assignments: List[List[int]], 
    final_payload: bytes, 
    mode: int = 0, 
    error_handler: Optional[Callable[[str], bool]] = None
) -> List[List[Union[int, float]]]:
    """
    Parse final payload and extract distance measurements.

    Args:
        assignments: List of three assignment groups [[group1], [group2], [group3]]
        final_payload: Binary payload data
        mode: Mode flags (bit 0 = group1 internal, bit 1 = group2 internal)
        error_handler: Function to call on parsing errors (optional). 
                      Should return True if reset is required.

    Returns:
        List of edges in format [[node1, node2, distance], ...]
    """
    results = []

    if len(final_payload) == 0:
        return results

    # Validate assignments structure
    if not isinstance(assignments, list) or len(assignments) != 3:
        error_msg = f"Invalid assignments structure: expected list of 3 groups, got {type(assignments)} with length {len(assignments) if isinstance(assignments, list) else 'N/A'}"
        if error_handler:
            error_handler(error_msg)
        return results

    # Check if any assignment group is empty or invalid
    for i, group in enumerate(assignments):
        if not isinstance(group, list):
            error_msg = f"Assignment group {i} is not a list: {type(group)}"
            if error_handler:
                error_handler(error_msg)
            return results
        if len(group) == 0:
            error_msg = f"Assignment group {i} is empty"
            if error_handler:
                error_handler(error_msg)
            return results

    try:
        idx = 0

        # Group 1 x Group 2
        for i in range(0, len(assignments[0])):
            for j in range(0, len(assignments[1])):
                if idx + 2 > len(final_payload):
                    raise ValueError("Insufficient payload data for assignments[0] x assignments[1]")
                value = struct.unpack('<H', final_payload[idx:(idx + 2)])[0]
                idx += 2
                if twr_value_ok(value):
                    results.append([assignments[0][i], assignments[1][j], TWR_TO_METERS * value])

        # Group 1 x Group 3
        for i in range(0, len(assignments[0])):
            for j in range(0, len(assignments[2])):
                if idx + 2 > len(final_payload):
                    raise ValueError("Insufficient payload data for assignments[0] x assignments[2]")
                value = struct.unpack('<H', final_payload[idx:(idx + 2)])[0]
                idx += 2
                if twr_value_ok(value):
                    results.append([assignments[0][i], assignments[2][j], TWR_TO_METERS * value])

        # Group 2 x Group 3
        for i in range(0, len(assignments[1])):
            for j in range(0, len(assignments[2])):
                if idx + 2 > len(final_payload):
                    raise ValueError("Insufficient payload data for assignments[1] x assignments[2]")
                value = struct.unpack('<H', final_payload[idx:(idx + 2)])[0]
                idx += 2
                if twr_value_ok(value):
                    results.append([assignments[1][i], assignments[2][j], TWR_TO_METERS * value])

        # Group 1 internal (if mode bit 0 set)
        if mode & MODE_GROUP1_INTERNAL:
            for i in range(0, len(assignments[0])):
                for j in range(i + 1, len(assignments[0])):
                    if idx + 2 > len(final_payload):
                        raise ValueError("Insufficient payload data for assignments[0] internal")
                    value = struct.unpack('<H', final_payload[idx:(idx + 2)])[0]
                    idx += 2
                    if twr_value_ok(value):
                        results.append([assignments[0][i], assignments[0][j], TWR_TO_METERS * value])

        # Group 2 internal (if mode bit 1 set)
        if mode & MODE_GROUP2_INTERNAL:
            for i in range(0, len(assignments[1])):
                for j in range(i + 1, len(assignments[1])):
                    if idx + 2 > len(final_payload):
                        raise ValueError("Insufficient payload data for assignments[1] internal")
                    value = struct.unpack('<H', final_payload[idx:(idx + 2)])[0]
                    idx += 2
                    if twr_value_ok(value):
                        results.append([assignments[1][i], assignments[1][j], TWR_TO_METERS * value])

    except (struct.error, ValueError, IndexError) as e:
        if error_handler:
            if error_handler(f"parse_final: {str(e)}"):
                raise ResetRequiredException("Maximum parsing errors reached, reset required")
        else:
            raise
        return []

    return results
