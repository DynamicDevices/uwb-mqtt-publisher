#!/usr/bin/env python3
"""
UWB Packet Parser
Parses UWB packets from serial port and extracts distance measurements.
"""

import struct


def twr_value_ok(value):
    """Check if TWR value is valid."""
    return value > 0 and 0.004690384 * value < 300


def parse_final_payload(assignments, final_payload, mode=0, error_handler=None):
    """
    Parse final payload and extract distance measurements.
    
    Args:
        assignments: List of three assignment groups [[group1], [group2], [group3]]
        final_payload: Binary payload data
        mode: Mode flags (bit 0 = group1 internal, bit 1 = group2 internal)
        error_handler: Function to call on parsing errors (optional)
        
    Returns:
        List of edges in format [[node1, node2, distance], ...]
    """
    results = []

    if len(final_payload) == 0:
        return results
    
    try:
        idx = 0

        # Group 1 x Group 2
        for i in range(0, len(assignments[0])):
            for j in range(0, len(assignments[1])):
                if idx + 2 > len(final_payload):
                    raise ValueError("Insufficient payload data for assignments[0] x assignments[1]")
                value = struct.unpack('<H', final_payload[idx:(idx+2)])[0]
                idx += 2
                if twr_value_ok(value):
                    results.append([assignments[0][i], assignments[1][j], 0.004690384 * value])
        
        # Group 1 x Group 3
        for i in range(0, len(assignments[0])):
            for j in range(0, len(assignments[2])):
                if idx + 2 > len(final_payload):
                    raise ValueError("Insufficient payload data for assignments[0] x assignments[2]")
                value = struct.unpack('<H', final_payload[idx:(idx+2)])[0]
                idx += 2
                if twr_value_ok(value):
                    results.append([assignments[0][i], assignments[2][j], 0.004690384 * value])

        # Group 2 x Group 3
        for i in range(0, len(assignments[1])):
            for j in range(0, len(assignments[2])):
                if idx + 2 > len(final_payload):
                    raise ValueError("Insufficient payload data for assignments[1] x assignments[2]")
                value = struct.unpack('<H', final_payload[idx:(idx+2)])[0]
                idx += 2
                if twr_value_ok(value):
                    results.append([assignments[1][i], assignments[2][j], 0.004690384 * value])

        # Group 1 internal (if mode bit 0 set)
        if mode & 1:
            for i in range(0, len(assignments[0])):
                for j in range(i+1, len(assignments[0])):
                    if idx + 2 > len(final_payload):
                        raise ValueError("Insufficient payload data for assignments[0] internal")
                    value = struct.unpack('<H', final_payload[idx:(idx+2)])[0]
                    idx += 2
                    if twr_value_ok(value):
                        results.append([assignments[0][i], assignments[0][j], 0.004690384 * value])
        
        # Group 2 internal (if mode bit 1 set)
        if mode & 2:
            for i in range(0, len(assignments[1])):
                for j in range(i+1, len(assignments[1])):
                    if idx + 2 > len(final_payload):
                        raise ValueError("Insufficient payload data for assignments[1] internal")
                    value = struct.unpack('<H', final_payload[idx:(idx+2)])[0]
                    idx += 2
                    if twr_value_ok(value):
                        results.append([assignments[1][i], assignments[1][j], 0.004690384 * value])
                    
    except (struct.error, ValueError, IndexError) as e:
        if error_handler:
            if error_handler(f"parse_final: {str(e)}"):
                raise Exception("RESET_REQUIRED")
        else:
            raise
        return []
                
    return results

