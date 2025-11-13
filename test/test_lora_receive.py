#!/usr/bin/env python3
"""
Test receiving real LoRa data from TTN MQTT broker.
This script subscribes to LoRa messages and displays what's being received and cached.
"""
import sys
import os
import json
import time
import argparse

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lora_tag_cache import LoraTagDataCache

def load_dev_eui_mapping(mapping_path):
    """Load dev_eui to UWB ID mapping."""
    if not mapping_path or not os.path.exists(mapping_path):
        return {}
    
    try:
        with open(mapping_path, 'r') as f:
            config = json.load(f)
        if 'dev_eui_to_uwb_id' in config:
            mapping = config['dev_eui_to_uwb_id']
            # Normalize keys to uppercase
            return {k.upper(): v.upper() for k, v in mapping.items()}
    except Exception as e:
        print(f"Error loading dev_eui mapping: {e}")
    
    return {}

def main():
    parser = argparse.ArgumentParser(description='Test receiving real LoRa data from TTN')
    parser.add_argument("--lora-broker", help="LoRa MQTT broker hostname", type=str, default="eu1.cloud.thethings.network")
    parser.add_argument("--lora-port", help="LoRa MQTT broker port", type=int, default=8883)
    parser.add_argument("--lora-username", help="LoRa MQTT username", type=str, required=True)
    parser.add_argument("--lora-password", help="LoRa MQTT password", type=str, required=True)
    parser.add_argument("--lora-topic", help="LoRa MQTT topic pattern", type=str, default="#")
    parser.add_argument("--dev-eui-mapping", help="Path to dev_eui mapping file", type=str, 
                       default=os.path.join(os.path.dirname(__file__), '..', 'config', 'dev_eui_to_uwb_mappings.json'))
    parser.add_argument("--verbose", help="Enable verbose logging", action="store_true")
    parser.add_argument("--duration", help="Run for N seconds (0 = forever)", type=int, default=0)
    
    args = parser.parse_args()
    
    # Load dev_eui mapping
    dev_eui_map = load_dev_eui_mapping(args.dev_eui_mapping)
    print(f"Loaded {len(dev_eui_map)} dev_eui to UWB ID mappings")
    if args.verbose:
        for dev_eui, uwb_id in dev_eui_map.items():
            print(f"  {dev_eui} -> {uwb_id}")
    
    # Create LoRa cache
    print(f"\nConnecting to LoRa broker: {args.lora_broker}:{args.lora_port}")
    print(f"Topic pattern: {args.lora_topic}")
    print(f"Username: {args.lora_username}")
    print("\nWaiting for LoRa messages... (Press Ctrl+C to stop)\n")
    
    cache = LoraTagDataCache(
        broker=args.lora_broker,
        port=args.lora_port,
        username=args.lora_username,
        password=args.lora_password,
        topic_pattern=args.lora_topic,
        dev_eui_to_uwb_id_map=dev_eui_map,
        verbose=args.verbose
    )
    
    cache.start()
    
    # Give it a moment to connect
    time.sleep(2)
    
    start_time = time.time()
    last_stats_time = start_time
    
    try:
        while True:
            time.sleep(1)
            
            # Print stats every 5 seconds
            current_time = time.time()
            if current_time - last_stats_time >= 5:
                stats = cache.get_cache_stats()
                print(f"\n[Stats] Dev EUIs: {stats['dev_eui_count']}, UWB IDs: {stats['uwb_id_count']}, Mappings: {stats['mapping_count']}")
                
                # Show cached UWB IDs
                if stats['uwb_ids']:
                    print(f"  Cached UWB IDs: {', '.join(stats['uwb_ids'])}")
                
                # Show sample cached data
                if stats['uwb_ids']:
                    sample_uwb_id = stats['uwb_ids'][0]
                    sample_data = cache.get_by_uwb_id(sample_uwb_id)
                    if sample_data:
                        print(f"\n  Sample data for UWB ID {sample_uwb_id}:")
                        if sample_data.get('location'):
                            loc = sample_data['location']
                            print(f"    GPS: ({loc.get('latitude')}, {loc.get('longitude')}, {loc.get('altitude')})")
                            print(f"    Accuracy: {loc.get('accuracy')}m")
                        if sample_data.get('decoded_payload'):
                            decoded = sample_data['decoded_payload']
                            print(f"    Decoded payload: {json.dumps(decoded, indent=6)}")
                        if sample_data.get('timestamp'):
                            age = current_time - sample_data['timestamp']
                            print(f"    Data age: {age:.1f} seconds")
                        if sample_data.get('rx_metadata'):
                            rx = sample_data['rx_metadata'][0] if sample_data['rx_metadata'] else {}
                            print(f"    RSSI: {rx.get('rssi')}, SNR: {rx.get('snr')}")
                
                last_stats_time = current_time
            
            # Check duration
            if args.duration > 0 and (current_time - start_time) >= args.duration:
                print(f"\nDuration of {args.duration} seconds reached. Stopping...")
                break
                
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        cache.stop()
        
        # Final stats
        stats = cache.get_cache_stats()
        print(f"\nFinal stats:")
        print(f"  Dev EUIs cached: {stats['dev_eui_count']}")
        print(f"  UWB IDs cached: {stats['uwb_id_count']}")
        
        if stats['uwb_ids']:
            print(f"\nAll cached UWB data:")
            for uwb_id in stats['uwb_ids']:
                data = cache.get_by_uwb_id(uwb_id)
                if data:
                    print(f"\n  UWB ID: {uwb_id}")
                    print(f"    Dev EUI: {data.get('dev_eui')}")
                    if data.get('location'):
                        loc = data['location']
                        print(f"    GPS: ({loc.get('latitude')}, {loc.get('longitude')}, {loc.get('altitude')})")
                    if data.get('decoded_payload'):
                        print(f"    Payload: {json.dumps(data['decoded_payload'], indent=4)}")
                    if data.get('timestamp'):
                        age = time.time() - data['timestamp']
                        print(f"    Age: {age:.1f} seconds")

if __name__ == '__main__':
    main()

