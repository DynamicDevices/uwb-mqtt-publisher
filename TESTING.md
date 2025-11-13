# Local Testing Guide

This guide explains how to test the UWB MQTT Publisher locally without requiring physical hardware.

## Prerequisites

Install required Python packages:
```bash
pip3 install pyserial paho-mqtt
```

For serial port simulation, install `socat`:
```bash
# Ubuntu/Debian
sudo apt-get install socat

# macOS
brew install socat
```

## Testing Methods

### Method 1: Simulated Serial Port with Test Data

This method uses `socat` to create a virtual serial port pair and feeds test UWB packet data.

#### Step 1: Create Virtual Serial Ports

In one terminal, create a virtual serial port pair:
```bash
socat -d -d pty,raw,echo=0 pty,raw,echo=0
```

This will output something like:
```
2024/01/01 12:00:00 socat[12345] N PTY is /dev/pts/2
2024/01/01 12:00:01 socat[12345] N PTY is /dev/pts/3
```

Note the two PTY paths (e.g., `/dev/pts/2` and `/dev/pts/3`).

#### Step 2: Generate Test UWB Packets

Create a test script `test/generate_test_packets.py` (see below) to generate UWB packet data.

#### Step 3: Feed Test Data to Serial Port

In one terminal, feed test data to one end of the virtual serial port:
```bash
python3 test/generate_test_packets.py | socat - /dev/pts/2
```

#### Step 4: Run the Application

In another terminal, run the application using the other end of the virtual serial port:
```bash
cd /data_drive/inst/uwb-mqtt-publisher
python3 src/mqtt-live-publisher.py /dev/pts/3 \
    --disable-mqtt \
    --verbose \
    --cga-format \
    --anchor-config config/uwb_anchors_hw_lab.json \
    --dev-eui-mapping config/dev_eui_to_uwb_mappings.json
```

### Method 2: Test Without Serial Port (Mock Mode)

For testing the converter and LoRa cache integration without serial data:

#### Step 1: Create a Test Script

Create `test/test_converter.py` (see below) that directly tests the converter.

#### Step 2: Run Tests

```bash
python3 test/test_converter.py
```

### Method 3: Local MQTT Broker

For full end-to-end testing with MQTT:

#### Step 1: Start Local MQTT Broker

Using Mosquitto:
```bash
# Install mosquitto
sudo apt-get install mosquitto mosquitto-clients

# Start mosquitto (no TLS for local testing)
mosquitto -p 1883 -v
```

#### Step 2: Run Application with Local Broker

```bash
python3 src/mqtt-live-publisher.py /dev/pts/3 \
    --mqtt-broker localhost \
    --mqtt-port 1883 \
    --mqtt-topic test/uwb/positions \
    --verbose \
    --cga-format \
    --anchor-config config/uwb_anchors_hw_lab.json
```

#### Step 3: Subscribe to MQTT Topic

In another terminal:
```bash
mosquitto_sub -h localhost -p 1883 -t test/uwb/positions -v
```

### Method 4: Test LoRa Cache Integration

#### Step 1: Simulate LoRa MQTT Messages

Create `test/simulate_lora_mqtt.py` (see below) to publish test LoRa messages to a local MQTT broker.

#### Step 2: Run Application with LoRa Cache

```bash
python3 src/mqtt-live-publisher.py /dev/pts/3 \
    --disable-mqtt \
    --verbose \
    --cga-format \
    --anchor-config config/uwb_anchors_hw_lab.json \
    --dev-eui-mapping config/dev_eui_to_uwb_mappings.json \
    --enable-lora-cache \
    --lora-broker localhost \
    --lora-port 1883 \
    --lora-topic "v3/+/devices/+/up"
```

## Test Scripts

### Test Packet Generator

Create `test/generate_test_packets.py`:

```python
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
```

### Converter Test Script

Create `test/test_converter.py`:

```python
#!/usr/bin/env python3
"""
Test the UWB Network Converter directly.
"""
import sys
import os
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from uwb_network_converter import UwbNetworkConverter

def test_basic_conversion():
    """Test basic edge list to CGA conversion."""
    print("Testing basic conversion...")
    
    # Create converter with test anchor config
    anchor_config = os.path.join(os.path.dirname(__file__), '..', 'config', 'uwb_anchors_hw_lab.json')
    converter = UwbNetworkConverter(anchor_config_path=anchor_config)
    
    # Test edge list
    edge_list = [
        ["B4D3", "B98A", 5.0],
        ["B4D3", "B4F1", 5.0],
        ["B98A", "B4F1", 5.0],
    ]
    
    network = converter.convert_edges_to_network(edge_list)
    
    print("Network JSON:")
    print(json.dumps(network, indent=2))
    
    assert len(network['uwbs']) == 3, "Should have 3 UWBs"
    assert network['uwbs'][0]['positionKnown'] == True, "Anchors should have known positions"
    
    print("✓ Basic conversion test passed!")

def test_lora_integration():
    """Test LoRa cache integration."""
    print("\nTesting LoRa cache integration...")
    
    # This would require a mock LoRa cache
    # For now, just test that converter accepts lora_cache parameter
    anchor_config = os.path.join(os.path.dirname(__file__), '..', 'config', 'uwb_anchors_hw_lab.json')
    converter = UwbNetworkConverter(anchor_config_path=anchor_config, lora_cache=None)
    
    edge_list = [
        ["B4D3", "B98A", 5.0],
    ]
    
    network = converter.convert_edges_to_network(edge_list)
    print("✓ LoRa integration test passed (with None cache)!")

if __name__ == '__main__':
    test_basic_conversion()
    test_lora_integration()
    print("\nAll tests passed!")
```

### LoRa MQTT Simulator

Create `test/simulate_lora_mqtt.py`:

```python
#!/usr/bin/env python3
"""
Simulate LoRa tag uplink messages for testing.
"""
import json
import time
import paho.mqtt.client as mqtt
import sys

def create_lora_message(dev_eui, uwb_id, battery=85, temperature=22.5, lat=51.5238, lon=-0.7514, alt=50.8):
    """Create a test LoRa uplink message."""
    return {
        "end_device_ids": {
            "device_id": f"tag-{uwb_id.lower()}",
            "dev_eui": dev_eui,
            "application_ids": {
                "application_id": "test-app"
            }
        },
        "received_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
        "uplink_message": {
            "f_port": 1,
            "f_cnt": 1234,
            "decoded_payload": {
                "battery": battery,
                "temperature": temperature,
                "triage": 0
            },
            "locations": {
                "frm-payload": {
                    "latitude": lat,
                    "longitude": lon,
                    "altitude": alt,
                    "accuracy": 5.0,
                    "source": "frm-payload"
                }
            },
            "rx_metadata": [
                {
                    "gateway_ids": {
                        "gateway_id": "test-gateway",
                        "eui": "B827EBFFFE123456"
                    },
                    "rssi": -85,
                    "snr": 8.5,
                    "timestamp": int(time.time() * 1000000)
                }
            ]
        }
    }

def main():
    """Publish test LoRa messages."""
    if len(sys.argv) < 3:
        print("Usage: python3 simulate_lora_mqtt.py <broker> <port>")
        print("Example: python3 simulate_lora_mqtt.py localhost 1883")
        sys.exit(1)
    
    broker = sys.argv[1]
    port = int(sys.argv[2])
    
    # Test mappings from dev_eui_to_uwb_mappings.json
    test_tags = [
        ("F4CE366381C3C7BD", "90A2", 51.523792, -0.751437, 50.8),
        ("F4CE368DA5BB9FC6", "90A6", 51.523810, -0.751475, 50.8),
        ("F4CE360BA8B8A1D4", "909B", 51.523815, -0.751407, 50.8),
    ]
    
    client = mqtt.Client()
    client.connect(broker, port, 60)
    client.loop_start()
    
    print(f"Publishing test LoRa messages to {broker}:{port}")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            for dev_eui, uwb_id, lat, lon, alt in test_tags:
                topic = f"v3/test-app/devices/tag-{uwb_id.lower()}/up"
                message = create_lora_message(dev_eui, uwb_id, lat=lat, lon=lon, alt=alt)
                payload = json.dumps(message)
                
                client.publish(topic, payload)
                print(f"Published to {topic}: {uwb_id} @ ({lat}, {lon})")
                
                time.sleep(2)
            
            time.sleep(5)  # Wait before next round
    except KeyboardInterrupt:
        print("\nStopping...")
        client.loop_stop()
        client.disconnect()

if __name__ == '__main__':
    main()
```

## Quick Start Testing

### Minimal Test (No MQTT, No Serial)

Test just the converter:
```bash
cd /data_drive/inst/uwb-mqtt-publisher
python3 test/test_converter.py
```

### Full Test with Simulated Serial Port

1. Terminal 1 - Create virtual serial ports:
```bash
socat -d -d pty,raw,echo=0 pty,raw,echo=0
# Note the two PTY paths
```

2. Terminal 2 - Generate test packets:
```bash
python3 test/generate_test_packets.py | socat - /dev/pts/X
# Replace X with first PTY number
```

3. Terminal 3 - Run application:
```bash
python3 src/mqtt-live-publisher.py /dev/pts/Y \
    --disable-mqtt \
    --verbose \
    --cga-format \
    --anchor-config config/uwb_anchors_hw_lab.json
# Replace Y with second PTY number
```

## Troubleshooting

### Serial Port Permission Denied

If you get permission errors:
```bash
sudo chmod 666 /dev/pts/X
```

### Module Not Found

Make sure you're in the repository directory:
```bash
cd /data_drive/inst/uwb-mqtt-publisher
```

### MQTT Connection Failed

For local testing, use `--disable-mqtt` or start a local Mosquitto broker without TLS:
```bash
mosquitto -p 1883 -v
```

## Expected Output

When running with `--verbose`, you should see:
- Packet parsing messages
- Edge list extraction
- CGA format conversion (if enabled)
- LoRa cache queries (if enabled)
- MQTT publish confirmations (if MQTT enabled)

With `--disable-mqtt`, the output will show what would be published without actually sending to MQTT.

