# UWB MQTT Publisher

A service that reads Ultra-Wideband (UWB) positioning data from a serial port and publishes it to an MQTT broker in CGA network format.

## Features

- **UWB Data Processing**: Reads distance measurements from UWB sensor gateway via serial port
- **MQTT Publishing**: Publishes UWB network data to MQTT broker with configurable rate limiting
- **CGA Network Format**: Converts edge list data to CGA network JSON format with anchor point support
- **LoRa Tag Integration**: Optional integration with LoRa tag data from TTN MQTT broker
- **Systemd Service**: Runs as a systemd service with automatic restart and logging

## Components

### Main Scripts

- **`src/mqtt-live-publisher.py`**: Main application that reads UWB data and publishes to MQTT
- **`src/uwb_network_converter.py`**: Converts edge list format to CGA network format
- **`src/lora_tag_cache.py`**: Subscribes to TTN MQTT and caches LoRa tag data

### Configuration Files

- **`config/uwb_anchors.json`**: Anchor point coordinates and dev_eui to UWB ID mappings
- **`config/uwb_anchors_hw_lab.json`**: Hardware lab test anchor configuration
- **`config/uwb-mqtt-publisher.default`**: Default environment variables
- **`config/uwb-mqtt-publisher.conf`**: Configuration documentation

### Systemd Service

- **`systemd/uwb-mqtt-publisher.service`**: Systemd service file

## Installation

### For Yocto/BitBake Builds

Add this repository to your `SRC_URI`:

```bitbake
SRC_URI = "git://github.com/DynamicDevices/uwb-mqtt-publisher.git;protocol=https;branch=main"
SRCREV = "${AUTOREV}"
```

The recipe will automatically:
- Clone the repository
- Install Python scripts to `/usr/bin/`
- Install anchor configuration to `/etc/uwb_anchors.json`
- Install systemd service and configuration files

### Manual Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/DynamicDevices/uwb-mqtt-publisher.git
   cd uwb-mqtt-publisher
   ```

2. Install Python scripts:
   ```bash
   sudo install -m 0755 src/mqtt-live-publisher.py /usr/bin/uwb-mqtt-publisher
   sudo install -m 0644 src/uwb_network_converter.py /usr/bin/
   sudo install -m 0644 src/lora_tag_cache.py /usr/bin/
   ```

3. Install configuration:
   ```bash
   sudo install -m 0644 config/uwb_anchors.json /etc/
   sudo install -m 0644 systemd/uwb-mqtt-publisher.service /etc/systemd/system/
   sudo install -m 0644 config/uwb-mqtt-publisher.default /etc/default/
   ```

4. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable uwb-mqtt-publisher.service
   sudo systemctl start uwb-mqtt-publisher.service
   ```

## Configuration

### Environment Variables

Edit `/etc/default/uwb-mqtt-publisher`:

```bash
# Serial port
UART_PORT="/dev/ttyUSB0"

# MQTT broker
MQTT_BROKER="mqtt.dynamicdevices.co.uk"
MQTT_PORT="8883"
MQTT_TOPIC="DotnetMQTT/Test/in"

# Rate limiting (seconds)
MQTT_RATE_LIMIT="10.0"

# Additional arguments
EXTRA_ARGS="--verbose --cga-format --anchor-config /etc/uwb_anchors.json"
```

### Anchor Configuration

Edit `/etc/uwb_anchors.json`:

```json
{
  "anchors": [
    {
      "id": "B5A4",
      "lat": 53.48514639104522,
      "lon": -2.191785053920114,
      "alt": 0.0
    }
  ],
  "dev_eui_to_uwb_id": {
    "F4CE36E6CD722E97": "0000"
  }
}
```

## Usage

### Command Line

```bash
# Basic usage
/usr/bin/uwb-mqtt-publisher /dev/ttyUSB0

# With CGA format
/usr/bin/uwb-mqtt-publisher /dev/ttyUSB0 \
    --cga-format \
    --anchor-config /etc/uwb_anchors.json

# With LoRa tag cache
/usr/bin/uwb-mqtt-publisher /dev/ttyUSB0 \
    --cga-format \
    --anchor-config /etc/uwb_anchors.json \
    --enable-lora-cache \
    --lora-broker eu1.cloud.thethings.network \
    --lora-username inst-external-tags@ttn \
    --lora-password <password>
```

### Systemd Service

```bash
# Start service
sudo systemctl start uwb-mqtt-publisher.service

# Enable on boot
sudo systemctl enable uwb-mqtt-publisher.service

# Check status
sudo systemctl status uwb-mqtt-publisher.service

# View logs
sudo journalctl -u uwb-mqtt-publisher.service -f
```

## Data Format

### Input Format (Serial)

The service expects UWB distance measurements in binary format from the serial port.

### Output Format (MQTT)

#### Simple Edge List Format (Default)
```json
[
  ["B5A4", "B57A", 1.726],
  ["B5A4", "B98A", 2.341]
]
```

#### CGA Network Format (`--cga-format`)
```json
{
  "uwbs": [
    {
      "id": "B5A4",
      "triageStatus": 0,
      "position": {"x": 0.0, "y": 0.0, "z": 0.0},
      "latLonAlt": [53.48514639104522, -2.191785053920114, 0.0],
      "positionKnown": true,
      "lastPositionUpdateTime": 1699876543.21,
      "edges": [
        {
          "end0": "B5A4",
          "end1": "B57A",
          "distance": 1.726
        }
      ],
      "positionAccuracy": 0.0
    }
  ]
}
```

## Command-Line Options

### Main Options

- `uart` - Serial port device (e.g., `/dev/ttyUSB0`)
- `--mqtt-broker` - MQTT broker hostname (default: `mqtt.dynamicdevices.co.uk`)
- `--mqtt-port` - MQTT broker port (default: `8883`)
- `--mqtt-topic` - MQTT topic to publish to (default: `uwb/positions`)
- `--mqtt-rate-limit` - Minimum seconds between publishes (default: `10.0`)

### Format Options

- `--cga-format` - Publish in CGA network format instead of simple edge list
- `--anchor-config` - Path to JSON config file with anchor point coordinates

### LoRa Integration Options

- `--enable-lora-cache` - Enable LoRa tag data caching
- `--lora-broker` - LoRa MQTT broker hostname (default: `eu1.cloud.thethings.network`)
- `--lora-port` - LoRa MQTT broker port (default: `8883`)
- `--lora-username` - LoRa MQTT username
- `--lora-password` - LoRa MQTT password
- `--lora-topic` - LoRa MQTT topic pattern (default: `#`)

### Logging Options

- `--verbose` - Enable verbose logging
- `--quiet` - Enable quiet mode (minimal logging)
- `--disable-mqtt` - Disable MQTT publishing entirely

## Dependencies

- Python 3.x
- pyserial
- paho-mqtt

## Development

### Project Structure

```
uwb-mqtt-publisher/
├── src/
│   ├── mqtt-live-publisher.py      # Main application
│   ├── uwb_network_converter.py    # CGA format converter
│   └── lora_tag_cache.py           # LoRa tag cache
├── config/
│   ├── uwb_anchors.json            # Anchor configuration
│   ├── uwb_anchors_hw_lab.json    # Hardware lab test configuration
│   ├── uwb-mqtt-publisher.default  # Default environment variables
│   └── uwb-mqtt-publisher.conf     # Configuration documentation
├── systemd/
│   └── uwb-mqtt-publisher.service  # Systemd service file
├── .gitignore                      # Git ignore rules
├── LICENSE                         # License file
├── CONTRIBUTING.md                 # Contributing guidelines
└── README.md                       # This file
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings to classes and functions
- Keep functions focused and small

## Troubleshooting

### Service Not Starting

Check service status:
```bash
sudo systemctl status uwb-mqtt-publisher.service
```

View logs:
```bash
sudo journalctl -u uwb-mqtt-publisher.service -n 50
```

### Serial Port Issues

Verify serial port exists:
```bash
ls -l /dev/ttyUSB*
```

Check permissions:
```bash
sudo chmod 666 /dev/ttyUSB0
```

### MQTT Connection Issues

Test MQTT connection:
```bash
mosquitto_pub -h mqtt.dynamicdevices.co.uk -p 8883 --cafile /etc/ssl/certs/ca-certificates.crt -t test/topic -m "test"
```

## License

Copyright (c) Dynamic Devices Ltd. 2025. All rights reserved.

## Authors

- Dynamic Devices Ltd.
- Reviewer: Jen

## Support

For issues and questions, please open an issue on GitHub.

