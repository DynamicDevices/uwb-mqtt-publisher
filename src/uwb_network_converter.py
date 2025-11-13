#!/usr/bin/env python3
"""
UWB Network Converter - Converts edge list format to CGA network format

This module provides functionality to convert UWB distance measurements
from edge list format to the network format required by CGA systems.

Author: Dynamic Devices Ltd. 2025
Reviewer: Jen
"""

import json
import time
import os


class UwbNetworkConverter:
    """
    Converts UWB edge list data to CGA network format.
    
    This class handles the conversion of UWB distance measurements from
    a simple edge list format to a structured network format with anchor
    point positioning support.
    
    Example usage:
        converter = UwbNetworkConverter(anchor_config_path="anchors.json")
        network_json = converter.convert_edges_to_network(edge_list)
    """
    
    def __init__(self, anchor_config_path=None, dev_eui_mapping_path=None, lora_cache=None):
        """
        Initialize the converter with anchor point configuration.
        
        Args:
            anchor_config_path (str, optional): Path to JSON config file with anchor points.
                Format: {"anchors": [{"id": "B5A4", "lat": 53.48..., "lon": -2.19..., "alt": 0}, ...]}
                If None, no anchor points will be configured.
            dev_eui_mapping_path (str, optional): Path to JSON config file with dev_eui to UWB ID mappings.
                Format: {"dev_eui_to_uwb_id": {"F4CE36E6CD722E97": "8FA4", ...}}
                If None, no dev_eui mappings will be configured.
            lora_cache (LoraTagDataCache, optional): LoRa tag data cache instance.
                If provided, LoRa data (battery, GPS, temperature, etc.) will be included in CGA format.
        """
        self.anchor_config_path = anchor_config_path
        self.dev_eui_mapping_path = dev_eui_mapping_path
        self.lora_cache = lora_cache
        self.anchor_map = {}  # Maps anchor ID to [lat, lon, alt]
        self.dev_eui_to_uwb_id_map = {}  # Maps dev_eui (hex string) to UWB ID (hex string)
        
        if anchor_config_path and os.path.exists(anchor_config_path):
            self._load_anchor_config()
        elif anchor_config_path:
            print(f"[WARNING] Anchor config file not found: {anchor_config_path}")
        
        if dev_eui_mapping_path and os.path.exists(dev_eui_mapping_path):
            self._load_dev_eui_mapping()
        elif dev_eui_mapping_path:
            print(f"[WARNING] Dev EUI mapping file not found: {dev_eui_mapping_path}")
    
    def _load_anchor_config(self):
        """Load anchor point configuration from JSON file."""
        try:
            with open(self.anchor_config_path, 'r') as f:
                config = json.load(f)
            
            if 'anchors' not in config:
                print(f"[WARNING] No 'anchors' key found in config file")
                return
            
            for anchor in config['anchors']:
                if 'id' not in anchor or 'lat' not in anchor or 'lon' not in anchor:
                    print(f"[WARNING] Invalid anchor entry: {anchor}")
                    continue
                
                anchor_id = anchor['id']
                lat = float(anchor['lat'])
                lon = float(anchor['lon'])
                alt = float(anchor.get('alt', 0.0))
                
                self.anchor_map[anchor_id] = [lat, lon, alt]
            
            print(f"[INFO] Loaded {len(self.anchor_map)} anchor points from config")
        
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse anchor config JSON: {e}")
        except Exception as e:
            print(f"[ERROR] Failed to load anchor config: {e}")
    
    def _load_dev_eui_mapping(self):
        """Load dev_eui to UWB ID mapping from separate JSON file."""
        try:
            with open(self.dev_eui_mapping_path, 'r') as f:
                config = json.load(f)
            
            if 'dev_eui_to_uwb_id' not in config:
                print(f"[WARNING] No 'dev_eui_to_uwb_id' key found in mapping file")
                return
            
            self.dev_eui_to_uwb_id_map = config['dev_eui_to_uwb_id']
            # Normalize keys to uppercase
            self.dev_eui_to_uwb_id_map = {k.upper(): v.upper() for k, v in self.dev_eui_to_uwb_id_map.items()}
            print(f"[INFO] Loaded {len(self.dev_eui_to_uwb_id_map)} dev_eui to UWB ID mappings")
        
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse dev_eui mapping JSON: {e}")
        except Exception as e:
            print(f"[ERROR] Failed to load dev_eui mapping: {e}")
    
    def convert_edges_to_network(self, edge_list, timestamp=None):
        """
        Convert edge list to CGA network format.
        
        Args:
            edge_list (list): List of edges in format [["B5A4", "B57A", 1.726], ...]
            timestamp (float, optional): Unix timestamp for lastPositionUpdateTime.
                If None, uses current time.
        
        Returns:
            dict: Network object with "uwbs" array in CGA format
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Extract unique UWB IDs from edges
        uwb_ids = set()
        for edge in edge_list:
            if len(edge) >= 2:
                uwb_ids.add(edge[0])
                uwb_ids.add(edge[1])
        
        # Create UWB objects with default values
        uwbs = []
        sorted_ids = sorted(uwb_ids)
        
        for idx, uwb_id in enumerate(sorted_ids):
            # Check if this UWB is an anchor (has known position)
            is_anchor = uwb_id in self.anchor_map
            anchor_position = self.anchor_map.get(uwb_id, [0.0, 0.0, 0.0])
            
            # Determine position - use anchor position if available, otherwise try LoRa GPS
            position_known = is_anchor
            lat_lon_alt = anchor_position if is_anchor else [0.0, 0.0, 0.0]
            
            # Only add LoRa GPS coordinates if UWB doesn't already have coordinates (not an anchor)
            if not is_anchor:
                # Try to get LoRa data for this UWB ID
                lora_data = None
                if self.lora_cache:
                    try:
                        lora_data = self.lora_cache.get_by_uwb_id(uwb_id)
                    except Exception as e:
                        # Silently fail if cache lookup fails
                        pass
                
                # Add LoRa GPS coordinates if available
                if lora_data and lora_data.get("location"):
                    loc = lora_data["location"]
                    if loc.get("latitude") and loc.get("longitude"):
                        lat_lon_alt = [
                            loc.get("latitude", 0.0),
                            loc.get("longitude", 0.0),
                            loc.get("altitude", 0.0)
                        ]
                        position_known = True
            else:
                # For anchors, still check LoRa cache for metadata (battery, etc.) but don't override position
                lora_data = None
                if self.lora_cache:
                    try:
                        lora_data = self.lora_cache.get_by_uwb_id(uwb_id)
                    except Exception as e:
                        # Silently fail if cache lookup fails
                        pass
            
            uwb = {
                "id": uwb_id,
                "triageStatus": 0,  # unknown/not triaged
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "latLonAlt": lat_lon_alt,
                "positionKnown": position_known,
                "lastPositionUpdateTime": timestamp,
                "edges": [],
                "positionAccuracy": 0.0
            }
            
            # Add LoRa metadata if available
            if lora_data:
                # Add decoded payload fields (battery, temperature, etc.)
                decoded = lora_data.get("decoded_payload", {})
                if decoded:
                    # Add common fields that might be in decoded payload
                    if "battery" in decoded:
                        uwb["battery"] = decoded["battery"]
                    if "temperature" in decoded:
                        uwb["temperature"] = decoded["temperature"]
                    if "humidity" in decoded:
                        uwb["humidity"] = decoded["humidity"]
                    # Add any other decoded fields
                    for key, value in decoded.items():
                        if key not in ["battery", "temperature", "humidity"]:
                            uwb[f"lora_{key}"] = value
                
                # Add location accuracy if available
                if lora_data.get("location", {}).get("accuracy"):
                    uwb["positionAccuracy"] = lora_data["location"]["accuracy"]
                
                # Add RX metadata (gateway info, RSSI, SNR)
                rx_metadata = lora_data.get("rx_metadata", [])
                if rx_metadata:
                    # Use the best RSSI/SNR from all gateways
                    best_rssi = None
                    best_snr = None
                    for rx in rx_metadata:
                        if rx.get("rssi") is not None:
                            if best_rssi is None or rx["rssi"] > best_rssi:
                                best_rssi = rx["rssi"]
                        if rx.get("snr") is not None:
                            if best_snr is None or rx["snr"] > best_snr:
                                best_snr = rx["snr"]
                    
                    if best_rssi is not None:
                        uwb["rssi"] = best_rssi
                    if best_snr is not None:
                        uwb["snr"] = best_snr
            
            uwbs.append(uwb)
        
        # Create a map for quick lookup
        uwb_map = {uwb["id"]: uwb for uwb in uwbs}
        
        # Populate edges (bidirectional - add to both nodes)
        for edge in edge_list:
            if len(edge) < 3:
                continue
            
            end0_id = edge[0]
            end1_id = edge[1]
            distance = float(edge[2])
            
            edge_obj = {
                "end0": end0_id,
                "end1": end1_id,
                "distance": distance
            }
            
            # Add edge to both UWBs (bidirectional)
            if end0_id in uwb_map:
                uwb_map[end0_id]["edges"].append(edge_obj)
            if end1_id in uwb_map:
                uwb_map[end1_id]["edges"].append(edge_obj)
        
        # Create Network object
        network = {
            "uwbs": uwbs
        }
        
        return network
    
    def convert_edges_to_network_json(self, edge_list, timestamp=None):
        """
        Convert edge list to CGA network format and return as JSON string.
        
        Args:
            edge_list (list): List of edges in format [["B5A4", "B57A", 1.726], ...]
            timestamp (float, optional): Unix timestamp for lastPositionUpdateTime.
                If None, uses current time.
        
        Returns:
            str: JSON string representation of network object
        """
        network = self.convert_edges_to_network(edge_list, timestamp)
        return json.dumps(network)

