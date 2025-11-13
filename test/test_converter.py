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

