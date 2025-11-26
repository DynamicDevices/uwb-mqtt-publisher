#!/usr/bin/env python3
"""
Generate a simple HTML map visualization of UWB anchor positions using Leaflet.
Supports real-time updates via MQTT subscription.
"""

import json
import sys
from typing import Dict, List


def parse_mqtt_data(mqtt_json_str: str) -> Dict:
    """Parse MQTT JSON data."""
    # Remove topic prefix if present
    if " " in mqtt_json_str:
        topic, json_data = mqtt_json_str.split(" ", 1)
    else:
        json_data = mqtt_json_str

    return json.loads(json_data)


def create_anchor_map_html(
        uwbs: List[Dict],
        output_file: str = "anchor_map.html",
        mqtt_broker: str = "mqtt.dynamicdevices.co.uk",
        mqtt_port: int = 8883,
        mqtt_topic: str = "DotnetMQTT/Test/out",
        enable_realtime: bool = True) -> None:
    """Create an HTML map showing anchor positions and connections with real-time MQTT updates."""

    # Calculate center point (use default if no anchors)
    if uwbs:
        lats = [uwb["latLonAlt"][0] for uwb in uwbs]
        lons = [uwb["latLonAlt"][1] for uwb in uwbs]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
    else:
        # Default center (Manchester area)
        center_lat = 53.41531994922044
        center_lon = -2.3372524742526837

    # Anchor color mapping
    colors = {
        'B4F1': '#FF0000',  # Red
        'B5A4': '#00FF00',  # Green
        'B98A': '#0000FF',  # Blue
    }

    # Generate HTML with MQTT real-time updates
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>UWB Anchor Map - Real-time</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/mqtt/dist/mqtt.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
        }}
        #map {{
            width: 100%;
            height: 100vh;
        }}
        .info {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            z-index: 1000;
            max-width: 300px;
            font-size: 12px;
        }}
        .info h3 {{
            margin-top: 0;
            margin-bottom: 5px;
        }}
        .info ul {{
            margin: 5px 0;
            padding-left: 20px;
        }}
        .status {{
            margin-top: 10px;
            padding: 5px;
            border-radius: 3px;
            font-size: 11px;
        }}
        .status.connected {{
            background: #d4edda;
            color: #155724;
        }}
        .status.disconnected {{
            background: #f8d7da;
            color: #721c24;
        }}
        .status.connecting {{
            background: #fff3cd;
            color: #856404;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info">
        <h3>UWB Anchors</h3>
        <ul id="anchor-list">
            <li>Waiting for data...</li>
        </ul>
        <div id="status" class="status connecting">Connecting to MQTT...</div>
        <div style="margin-top: 5px; font-size: 10px; color: #666;">
            Topic: {mqtt_topic}<br>
            Broker: {mqtt_broker}:{mqtt_port}
        </div>
    </div>

    <script>
        // Map and data storage
        var map = L.map('map').setView([{center_lat}, {center_lon}], 19);
        var anchorMarkers = {{}};
        var edgeLines = {{}};
        var distanceLabels = {{}};
        var colors = {json.dumps(colors)};

        // Add OpenStreetMap tiles
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            maxZoom: 22
        }}).addTo(map);

        // Update anchor list in info panel
        function updateAnchorList(anchors) {{
            var list = document.getElementById('anchor-list');
            if (anchors.length === 0) {{
                list.innerHTML = '<li>Waiting for data...</li>';
                return;
            }}
            list.innerHTML = anchors.map(function(a) {{
                return '<li><strong>' + a.id + '</strong>: ' +
                       a.lat.toFixed(6) + ', ' + a.lon.toFixed(6) + '</li>';
            }}).join('');
        }}

        // Update status
        function updateStatus(status, message) {{
            var statusEl = document.getElementById('status');
            statusEl.className = 'status ' + status;
            statusEl.textContent = message;
        }}

        // Remove old edges
        function clearEdges() {{
            Object.keys(edgeLines).forEach(function(key) {{
                map.removeLayer(edgeLines[key]);
            }});
            Object.keys(distanceLabels).forEach(function(key) {{
                map.removeLayer(distanceLabels[key]);
            }});
            edgeLines = {{}};
            distanceLabels = {{}};
        }}

        // Update map with new anchor data
        function updateMap(uwbs) {{
            if (!uwbs || uwbs.length === 0) return;

            // Remove old edges
            clearEdges();

            // Update or create markers
            var anchorPositions = {{}};
            uwbs.forEach(function(uwb) {{
                var anchorId = uwb.id;
                var latLonAlt = uwb.latLonAlt;
                var lat = latLonAlt[0];
                var lon = latLonAlt[1];
                var alt = latLonAlt[2];

                anchorPositions[anchorId] = {{lat: lat, lon: lon, alt: alt}};

                // Update or create marker
                if (anchorMarkers[anchorId]) {{
                    anchorMarkers[anchorId].setLatLng([lat, lon]);
                }} else {{
                    var color = colors[anchorId] || '#808080';
                    anchorMarkers[anchorId] = L.circleMarker([lat, lon], {{
                        radius: 10,
                        fillColor: color,
                        color: '#000',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.8
                    }}).addTo(map);
                }}

                // Update popup
                var edges = uwb.edges || [];
                var edgeInfo = edges.map(function(e) {{
                    return '→ ' + e.end1 + ': ' + e.distance.toFixed(2) + 'm';
                }}).join('<br>');

                var popupContent = '<div style="font-family: monospace; min-width: 200px;">' +
                    '<h3 style="margin-top: 0;">Anchor: ' + anchorId + '</h3>' +
                    '<p><strong>Coordinates:</strong><br>' +
                    'Lat: ' + lat.toFixed(8) + '<br>' +
                    'Lon: ' + lon.toFixed(8) + '<br>' +
                    'Alt: ' + alt.toFixed(2) + 'm</p>' +
                    '<p><strong>Connections:</strong><br>' + (edgeInfo || 'None') + '</p>' +
                    '</div>';

                anchorMarkers[anchorId].bindPopup(popupContent);
            }});

            // Draw edges
            uwbs.forEach(function(uwb) {{
                var anchorId = uwb.id;
                var edges = uwb.edges || [];

                edges.forEach(function(edge) {{
                    var end0 = edge.end0;
                    var end1 = edge.end1;
                    var distance = edge.distance || 0;

                    if (end0 === anchorId && anchorPositions[end1]) {{
                        var from = anchorPositions[end0];
                        var to = anchorPositions[end1];
                        var edgeKey = end0 + '-' + end1;

                        // Draw line
                        var line = L.polyline(
                            [[from.lat, from.lon], [to.lat, to.lon]],
                            {{
                                color: '#0066FF',
                                weight: 3,
                                opacity: 0.7
                            }}
                        ).addTo(map);
                        edgeLines[edgeKey] = line;

                        // Add distance label
                        var midLat = (from.lat + to.lat) / 2;
                        var midLon = (from.lon + to.lon) / 2;
                        var label = L.marker([midLat, midLon], {{
                            icon: L.divIcon({{
                                className: 'distance-label',
                                html: '<div style="background: white; padding: 2px 5px; border-radius: 3px; font-size: 11px; font-weight: bold; border: 1px solid #0066FF;">' + distance.toFixed(2) + 'm</div>',
                                iconSize: [60, 20],
                                iconAnchor: [30, 10]
                            }})
                        }}).addTo(map);
                        distanceLabels[edgeKey] = label;
                    }}
                }});
            }});

            // Update anchor list
            updateAnchorList(uwbs.map(function(u) {{
                return {{
                    id: u.id,
                    lat: u.latLonAlt[0],
                    lon: u.latLonAlt[1]
                }};
            }}));
        }}

        // MQTT connection
        var mqttBroker = '{mqtt_broker}';
        var mqttPort = {mqtt_port};
        var mqttTopic = '{mqtt_topic}';

        // Use WebSocket for browser MQTT connection
        // Common WebSocket ports: 9001 (ws), 9443/8884 (wss), or same port with /ws path
        var wsProtocol = mqttPort === 8883 ? 'wss' : 'ws';
        // Try common WebSocket ports: 9443, 8884, 9001, or same port
        var wsPorts = mqttPort === 8883 ? [9443, 8884, 9001] : [9001, 8083];
        var wsPaths = ['/mqtt', '/ws', '/'];

        // Try multiple WebSocket configurations
        var mqttUrl = null;
        var currentWsIndex = 0;
        var wsConfigs = [];
        wsPorts.forEach(function(port) {{
            wsPaths.forEach(function(path) {{
                wsConfigs.push(wsProtocol + '://' + mqttBroker + ':' + port + path);
            }});
        }});

        // Start with first configuration
        mqttUrl = wsConfigs[0];

        console.log('Connecting to MQTT via WebSocket:', mqttUrl);
        console.log('Available WebSocket configs:', wsConfigs);
        updateStatus('connecting', 'Connecting to MQTT...');

        function tryConnect(configIndex) {{
            if (configIndex >= wsConfigs.length) {{
                console.error('All WebSocket configurations failed');
                updateStatus('disconnected', 'Failed to connect - WebSocket not available');
                return null;
            }}

            var url = wsConfigs[configIndex];
            console.log('Trying WebSocket:', url);

            var client = mqtt.connect(url, {{
                clientId: 'uwb-map-' + Math.random().toString(16).substr(2, 8),
                reconnectPeriod: 5000,
                connectTimeout: 10000,
                // For secure connections, disable certificate validation (development only)
                rejectUnauthorized: false
            }});

            var connectTimeout = setTimeout(function() {{
                if (client && !client.connected) {{
                    console.log('Connection timeout, trying next config...');
                    client.end();
                    tryConnect(configIndex + 1);
                }}
            }}, 10000);

            client.on('connect', function() {{
                clearTimeout(connectTimeout);
                console.log('Successfully connected via:', url);
            }});

            client.on('error', function(err) {{
                clearTimeout(connectTimeout);
                console.error('Connection error with', url, ':', err);
                if (configIndex < wsConfigs.length - 1) {{
                    console.log('Trying next WebSocket configuration...');
                    client.end();
                    tryConnect(configIndex + 1);
                }}
            }});

            return client;
        }}

        var client = tryConnect(0);

        client.on('connect', function() {{
            console.log('Connected to MQTT broker');
            updateStatus('connected', 'Connected - Listening for updates');
            client.subscribe(mqttTopic, function(err) {{
                if (err) {{
                    console.error('Failed to subscribe:', err);
                    updateStatus('disconnected', 'Failed to subscribe: ' + err.message);
                }} else {{
                    console.log('Subscribed to topic:', mqttTopic);
                }}
            }});
        }});

        client.on('message', function(topic, message) {{
            try {{
                var data = JSON.parse(message.toString());
                console.log('Received MQTT message:', data);

                // Extract UWBs array
                var uwbs = data.uwbs || [];
                if (uwbs.length > 0) {{
                    updateMap(uwbs);
                }}
            }} catch (e) {{
                console.error('Error parsing MQTT message:', e);
                console.log('Raw message:', message.toString());
            }}
        }});

        client.on('error', function(err) {{
            console.error('MQTT error:', err);
            updateStatus('disconnected', 'MQTT Error: ' + err.message);
        }});

        client.on('close', function() {{
            console.log('MQTT connection closed');
            updateStatus('disconnected', 'Disconnected - Reconnecting...');
        }});

        client.on('offline', function() {{
            console.log('MQTT client offline');
            updateStatus('disconnected', 'Offline');
        }});

        // Initial data (if provided)
        var initialData = {json.dumps(uwbs) if uwbs else '[]'};
        if (initialData.length > 0) {{
            updateMap(initialData);
        }}
    </script>
</body>
</html>"""

    # Save HTML file
    with open(output_file, 'w') as f:
        f.write(html_content)

    print(f"Map saved to: {output_file}")
    print(f"Open {output_file} in a web browser to view the map")
    if enable_realtime:
        print("Real-time MQTT updates enabled:")
        print(f"  Broker: {mqtt_broker}:{mqtt_port}")
        print(f"  Topic: {mqtt_topic}")
    if uwbs:
        print(f"\nInitial anchors found: {len(uwbs)}")
        for u in uwbs:
            anchor_id = u["id"]
            lat, lon, alt = u["latLonAlt"]
            print(f"  - {anchor_id}: ({lat:.8f}, {lon:.8f}, {alt:.2f}m)")


def main():
    """Main function."""
    mqtt_broker = "mqtt.dynamicdevices.co.uk"
    mqtt_port = 8883
    mqtt_topic = "DotnetMQTT/Test/out"
    enable_realtime = True

    if len(sys.argv) > 1:
        # Read from file
        with open(sys.argv[1], 'r') as f:
            data = f.read()
    else:
        # Read from stdin
        print("Paste MQTT JSON data (or provide file as argument):")
        data = sys.stdin.read()

    # Parse data (if provided)
    uwbs = []
    if data.strip():
        try:
            if data.strip().startswith('{'):
                # Direct JSON
                parsed = json.loads(data)
            else:
                # MQTT format with topic
                parsed = parse_mqtt_data(data)

            # Extract UWBs
            if "uwbs" in parsed:
                uwbs = parsed["uwbs"]
            elif isinstance(parsed, list):
                uwbs = parsed
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse initial data: {e}")
            print("Map will start empty and populate via MQTT")

    # Generate map
    output_file = sys.argv[2] if len(sys.argv) > 2 else "anchor_map.html"
    create_anchor_map_html(
        uwbs,
        output_file,
        mqtt_broker,
        mqtt_port,
        mqtt_topic,
        enable_realtime)


if __name__ == "__main__":
    main()
