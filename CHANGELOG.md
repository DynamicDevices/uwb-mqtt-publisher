# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-01-XX

### Added
- **Enhanced Error Recovery**: Complete Priority 1 error recovery system
  - Exponential backoff for device resets (configurable initial, max, multiplier)
  - Different error thresholds for parsing vs connection errors
  - Automatic retry with backoff delays to prevent rapid reset loops
  - `--parsing-error-threshold`, `--connection-error-threshold` parameters
  - `--backoff-initial`, `--backoff-max`, `--backoff-multiplier` parameters

- **Health Monitoring & Reporting**: Comprehensive system health tracking
  - MQTT-based health status reporting (default: `{mqtt_topic}/health`)
  - Tracks parsing errors, connection errors, device resets, packet success rates
  - Connection status monitoring (serial, MQTT, LoRa cache)
  - Configurable health report interval (`--health-interval`)
  - Health status: healthy, degraded, or unhealthy
  - `--health-topic` parameter for custom health reporting topic

- **Graceful Degradation**: Continue operation with partial data
  - `--graceful-degradation` flag to continue with partial data when possible
  - Prevents complete shutdown on minor errors
  - Better uptime and reliability

- **New Modules**:
  - `src/uwb_error_recovery.py`: Error recovery with exponential backoff
  - `src/uwb_health_monitor.py`: Health monitoring and MQTT reporting

### Changed
- Error handling now uses exponential backoff instead of immediate resets
- Different thresholds for parsing errors vs connection errors
- Health metrics automatically tracked and reported
- Improved error recovery reduces downtime

### Technical Details
- Error recovery uses exponential backoff: `initial * (multiplier ^ reset_count)`
- Health reports include: uptime, connection status, error counts, success rates
- Connection health tracked for serial, MQTT, and LoRa cache
- Graceful degradation allows continued operation with partial data

---

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

