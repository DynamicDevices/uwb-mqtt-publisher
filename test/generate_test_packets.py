#!/usr/bin/env python3
"""
Generate test UWB packets for local testing.
"""
import struct
import time
import sys

def create_uwb_packet(group1, group2, group3, mode=0, distances=None):
    """
    Create a UWB packet in the expected format.
    
    Args:
        group1: List of node IDs in group 1
        group2: List of node IDs in group 2
        group3: List of node IDs in group 3
        mode: Mode flags
        distances: List of distance values (in TWR units)
    """
    # Packet header: 0xDC 0xAC [length_low] [length_high]
    # Payload: [act_type=2] [act_slot] [timeframe] [tx_pwr] [mode] [g1] [g2] [g3] [group1_ids] [group2_ids] [group3_ids] [distances]
    
    # Assignment packet (act_type=2)
    g1_count = len(group1)
    g2_count = len(group2)
    g3_count = len(group3)
    
    # Calculate expected distance count
    tof_count = g1_count * g2_count + g1_count * g3_count + g2_count * g3_count
    if mode & 1:
        tof_count += g1_count * (g1_count - 1) // 2
    if mode & 2:
        tof_count += g2_count * (g2_count - 1) // 2
    
    # Build assignment payload
    payload = struct.pack('<BbH', 2, 0, 0)  # act_type, act_slot, timeframe
    payload += struct.pack('<BBBBB', 0, mode, g1_count, g2_count, g3_count)  # tx_pwr, mode, g1, g2, g3
    
    # Add group IDs
    for node_id in group1:
        payload += struct.pack('<H', node_id)
    for node_id in group2:
        payload += struct.pack('<H', node_id)
    for node_id in group3:
        payload += struct.pack('<H', node_id)
    
    # Build final packet (act_type=4) with distances
    if distances is None:
        # Generate default distances
        distances = [1000] * int(tof_count)  # Default distance ~4.69m
    
    final_payload = struct.pack('<BbH', 4, 0, 0)  # act_type, act_slot, timeframe
    final_payload += struct.pack('<BBBBB', 0, mode, g1_count, g2_count, g3_count)
    
    # Add group IDs again
    for node_id in group1:
        final_payload += struct.pack('<H', node_id)
    for node_id in group2:
        final_payload += struct.pack('<H', node_id)
    for node_id in group3:
        final_payload += struct.pack('<H', node_id)
    
    # Add distances
    for dist in distances[:int(tof_count)]:
        final_payload += struct.pack('<H', int(dist))
    
    # Create packet with header
    packet = b'\xDC\xAC'
    packet += struct.pack('<H', len(final_payload))
    packet += final_payload
    
    return packet

def main():
    """Generate test packets continuously."""
    # Example: 3 anchors (B4D3=0xB4D3, B98A=0xB98A, B4F1=0xB4F1)
    # Convert hex strings to integers
    group1 = [0xB4D3]
    group2 = [0xB98A]
    group3 = [0xB4F1]
    
    # Generate distances (in TWR units, ~4.69m per 1000 units)
    # Distance between anchors: ~5m = ~1066 units
    distances = [
        1066,  # group1[0] <-> group2[0]
        1066,  # group1[0] <-> group3[0]
        1066,  # group2[0] <-> group3[0]
    ]
    
    while True:
        # Send assignment packet
        assignment = create_uwb_packet(group1, group2, group3, mode=0, distances=None)
        sys.stdout.buffer.write(assignment)
        sys.stdout.buffer.flush()
        time.sleep(0.1)
        
        # Send final packet with distances
        final = create_uwb_packet(group1, group2, group3, mode=0, distances=distances)
        sys.stdout.buffer.write(final)
        sys.stdout.buffer.flush()
        
        time.sleep(1.0)  # Wait 1 second before next packet

if __name__ == '__main__':
    main()

