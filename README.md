# UWB MQTT Publisher

This application reads UWB positioning data from a serial port and publishes it to an MQTT broker.

## Features

- Reads UWB distance measurements from serial port
- Publishes data to MQTT broker in simple edge list or CGA network format
- Integrates LoRa tag data (GPS, battery, triage status) from TTN
- Configurable anchor points and dev_eui mappings
- Rate limiting for MQTT publishing
- **Data quality management**: Automatic staleness filtering for LoRa data
- **Cache expiration**: Automatic cleanup of expired cache entries
- **Type-safe codebase**: Full type hints throughout
- Modular architecture for maintainability

## Installation

### Requirements

- Python 3.x
- `pyserial` - for serial port communication
- `paho-mqtt` - for MQTT publishing

Install dependencies:
```bash
pip install pyserial paho-mqtt
```

## Usage

See [TESTING.md](TESTING.md) for local testing instructions.

Basic usage:
```bash
python3 src/mqtt-live-publisher.py /dev/ttyUSB0 \
    --mqtt-broker mqtt.dynamicdevices.co.uk \
    --mqtt-port 8883 \
    --mqtt-topic uwb/positions \
    --cga-format \
    --anchor-config config/uwb_anchors_hw_lab.json \
    --dev-eui-mapping config/dev_eui_to_uwb_mappings.json \
    --enable-lora-cache \
    --lora-broker eu1.cloud.thethings.network \
    --lora-port 8883 \
    --lora-username inst-external-tags@ttn \
    --lora-password <password> \
    --lora-topic "#" \
    --lora-gps-max-age 300 \
    --lora-sensor-max-age 600
```

### New Options

- `--lora-gps-max-age SECONDS`: Maximum age for LoRa GPS data in seconds (default: 300 = 5 minutes)
- `--lora-sensor-max-age SECONDS`: Maximum age for LoRa sensor data in seconds (default: 600 = 10 minutes)

These options control data staleness filtering. GPS data older than the specified age will be automatically filtered out to prevent using outdated location information.

## Development

### Code Quality

This project uses `flake8` for linting. A git pre-commit hook automatically runs linting on staged Python files.

To install the pre-commit hook:
```bash
# The hook is already installed in .git/hooks/pre-commit
# It will run automatically on git commit
```

To manually run linting:
```bash
flake8 --max-line-length=120 --ignore=E501,W503 src/
```

### Pre-commit Framework (Optional)

For additional checks (trailing whitespace, YAML/JSON validation, etc.), use the pre-commit framework:

```bash
pip install pre-commit
pre-commit install
```

See `.pre-commit-config.yaml` for configuration.

## Documentation

- [PROGRAM_FLOW.md](PROGRAM_FLOW.md) - Program flow and architecture diagrams
- [FUTURE_ENHANCEMENTS.md](FUTURE_ENHANCEMENTS.md) - Prioritized list of future enhancements
- [TESTING.md](TESTING.md) - Local testing guide

## Project Structure

```
uwb-mqtt-publisher/
├── src/
│   ├── mqtt-live-publisher.py    # Main application
│   ├── uwb_serial.py              # Serial port handling
│   ├── uwb_packet_parser.py       # Packet parsing
│   ├── uwb_mqtt_client.py         # MQTT client
│   ├── uwb_logging.py             # Logging utilities
│   ├── uwb_network_converter.py   # CGA format conversion
│   ├── lora_tag_cache.py          # LoRa data caching with expiration
│   ├── uwb_constants.py           # Centralized constants
│   └── uwb_exceptions.py          # Custom exception classes
├── config/
│   ├── uwb_anchors.json           # Anchor configuration
│   ├── uwb_anchors_hw_lab.json   # Hardware lab anchors
│   └── dev_eui_to_uwb_mappings.json  # Dev EUI mappings
└── test/                          # Test scripts
```

## License

Copyright (c) Dynamic Devices Ltd. 2025. All rights reserved.
