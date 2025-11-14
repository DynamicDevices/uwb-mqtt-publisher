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
- **Enhanced error recovery**: Exponential backoff, different error thresholds, health monitoring
- **Health monitoring**: MQTT-based health reporting with connection metrics
- **Graceful degradation**: Continue with partial data when possible
- **Data validation**: Configurable sanity checks for distances, GPS, battery, and temperature
- **Position confidence scoring**: Confidence scores (0.0-1.0) for position data based on source, age, and quality
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
    --lora-topic "v3/inst-external-tags/devices/+/up" \
    --lora-gps-max-age 300 \
    --lora-sensor-max-age 600
```

**Note**: There are two separate MQTT connections:
- **UWB MQTT** (`--mqtt-broker`): For publishing UWB position data (can be disabled with `--disable-publish-mqtt`)
- **LoRa MQTT** (`--lora-broker`): For receiving LoRa tag data from TTN (separate connection)

If serial port is disabled (`--disable-serial`), the UART port argument is optional:
```bash
python3 src/mqtt-live-publisher.py \
    --disable-serial \
    --enable-lora-cache \
    --lora-broker eu1.cloud.thethings.network \
    --lora-port 8883 \
    --lora-username inst-external-tags@ttn \
    --lora-password <password> \
    --lora-topic "v3/inst-external-tags/devices/+/up"
```

### New Options

**Data Quality:**
- `--lora-gps-max-age SECONDS`: Maximum age for LoRa GPS data in seconds (default: 300 = 5 minutes)
- `--lora-sensor-max-age SECONDS`: Maximum age for LoRa sensor data in seconds (default: 600 = 10 minutes)

**Error Recovery:**
- `--parsing-error-threshold COUNT`: Max parsing errors before reset (default: 3)
- `--connection-error-threshold COUNT`: Max connection errors before reset (default: 3)
- `--backoff-initial SECONDS`: Initial backoff delay for resets (default: 1.0)
- `--backoff-max SECONDS`: Maximum backoff delay (default: 60.0)
- `--backoff-multiplier FLOAT`: Exponential backoff multiplier (default: 2.0)

**Health Monitoring:**
- `--health-topic TOPIC`: MQTT topic for health reports (default: {mqtt_topic}/health)
- `--health-interval SECONDS`: Health report interval in seconds (default: 60)
- `--graceful-degradation`: Continue with partial data when possible

**Data Validation:**
- `--enable-validation`: Enable data validation and sanity checks
- `--min-distance METERS`: Minimum valid distance in meters (default: 0.0)
- `--max-distance METERS`: Maximum valid distance in meters (default: 300.0)
- `--reject-zero-gps`: Reject GPS coordinates at 0,0 (default: True)
- `--min-battery PERCENT`: Minimum valid battery percentage (default: 0.0)
- `--max-battery PERCENT`: Maximum valid battery percentage (default: 100.0)
- `--min-temperature CELSIUS`: Minimum valid temperature in Celsius (default: -40.0)
- `--max-temperature CELSIUS`: Maximum valid temperature in Celsius (default: 85.0)
- `--validation-failures-topic TOPIC`: MQTT topic for validation failures (default: {mqtt_topic}/validation_failures)

**Position Confidence Scoring:**
- `--enable-confidence-scoring`: Enable position confidence scoring
- `--anchor-confidence FLOAT`: Confidence score for anchor points (default: 1.0)
- `--lora-gps-base-confidence FLOAT`: Base confidence for LoRa GPS data (default: 0.7)
- `--lora-gps-min-confidence FLOAT`: Minimum confidence for LoRa GPS data (default: 0.3)
- `--lora-gps-decay-rate FLOAT`: Confidence decay rate per TTL period (default: 0.1)
- `--gps-accuracy-weight FLOAT`: Weight for GPS accuracy in confidence (default: 0.2)
- `--gateway-count-weight FLOAT`: Weight for gateway count in confidence (default: 0.1)
- `--rssi-weight FLOAT`: Weight for RSSI/SNR in confidence (default: 0.1)

These options control data staleness filtering, error recovery behavior, health monitoring, data validation, and position confidence scoring. GPS data older than the specified age will be automatically filtered out to prevent using outdated location information.

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
