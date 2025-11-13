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

