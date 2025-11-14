# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-01-XX

### Added
- **Data Quality Management**: Automatic staleness filtering for LoRa tag data
  - `--lora-gps-max-age` parameter to control GPS data staleness (default: 300s)
  - `--lora-sensor-max-age` parameter to control sensor data staleness (default: 600s)
  - Automatic filtering of stale data before use
  - Warnings when data approaches expiration threshold

- **Cache Expiration & Cleanup**: Automatic memory management
  - Background cleanup thread removes expired cache entries
  - Configurable TTL for GPS and sensor data
  - Thread-safe cache cleanup every 60 seconds
  - Prevents unbounded memory growth in long-running deployments

- **Code Quality Improvements**:
  - Replaced dynamic imports with standard Python imports
  - Extracted all magic numbers to `uwb_constants.py`
  - Added comprehensive type hints throughout all modules
  - Created custom `ResetRequiredException` class
  - Improved exception handling with specific exception types

- **New Modules**:
  - `src/uwb_constants.py`: Centralized constants (TWR conversion, packet headers, error thresholds)
  - `src/uwb_exceptions.py`: Custom exception classes

### Changed
- **Breaking Changes**: None (backward compatible)
- Improved error handling: Replaced string-based exception checks with proper exception classes
- Enhanced type safety: All functions now have type hints
- Better code maintainability: Constants extracted from magic numbers

### Fixed
- Improved exception handling robustness
- Better memory management for long-running processes

### Technical Details
- All modules now use standard Python imports instead of `importlib.util`
- Constants extracted: `TWR_TO_METERS`, `MAX_DISTANCE_METERS`, `PACKET_HEADER_BYTE_1/2`, `PACKET_TYPE_*`, `MAX_PARSING_ERRORS`, `MODE_GROUP*_INTERNAL`
- Type hints added to: `mqtt-live-publisher.py`, `uwb_packet_parser.py`, `uwb_serial.py`, `uwb_logging.py`, `uwb_mqtt_client.py`, `uwb_network_converter.py`, `lora_tag_cache.py`
- Custom exception: `ResetRequiredException` replaces string comparison pattern

## [1.0.0] - Previous Release

Initial stable release with core functionality:
- UWB packet reading and parsing
- MQTT publishing
- LoRa tag data integration
- CGA network format conversion

