# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.2] - 2025-11-20

### Fixed
- **Logger TypeError**: Fixed `TypeError: 'bool' object is not callable` by renaming internal `_verbose` attribute to `_verbose_flag`
- **Empty Groups Validation**: Allow empty groups in assignments structure (valid when g2=0 or other groups are empty)
- **TOF Count Calculation**: Use actual group lengths from assignments instead of stale g1, g2, g3 variables

### Changed
- **Verbose Logging**: Reduced noise in verbose mode
  - Removed repetitive assignment packet logging (was logging every packet)
  - Only log assignment updates when they actually change
  - Added logging for incoming distance packets (summary)
  - Added logging for published data (CGA network or edge list summaries)
  - Reduced MQTT client verbose noise (summaries instead of full JSON payloads)
- **Default Configuration**: Enabled `--verbose` by default in container config for better debugging

### Added
- **Data Visibility**: Improved logging to show actual data flow
  - Incoming distance measurements summary
  - Published data summaries (UWBs count, edges count)
  - Assignment updates only when changed

## [1.4.1] - 2025-01-14

### Added
- **Enhanced LoRa Cache Logging**: Comprehensive logging for debugging positioning and caching issues
  - GPS position details (lat, lon, alt, accuracy, source)
  - Battery percentage
  - Triage status
  - GPS fix type (no_fix, 2D, 3D) and satellite count
  - Temperature
  - Signal quality metrics (gateway count, average RSSI, average SNR)
  - Frame counter (f_cnt) for message sequence tracking
  - Location extraction logging with source priority
  - Decoded payload field inspection

### Fixed
- **LoRa Data Field Names**: Support for multiple field name formats
  - Battery: `battery` or `battery_percentage`
  - Triage: `triage`, `triageStatus`, or `triage_status`
  - Updated both cache logging and network converter to handle all formats

### Changed
- Cache logging now includes all relevant positioning and quality metrics in a single INFO-level message
- Verbose logging shows decoded payload structure for debugging
- Enhanced location extraction logging shows which source was used (frm-payload, user, gps)

## [1.4.1] - 2025-01-14

### Fixed
- **LoRa Location Extraction**: Fixed location extraction to handle multiple TTN location formats (frm-payload, user, gps, and others)
- **TTN MQTT Configuration**: Updated docker-compose.yml to use correct TTN v3 topic format (`v3/inst-external-tags@ttn/devices/+/up` instead of `#`)
- **MQTT Callback API**: Fixed deprecation warnings by using VERSION1 callback API (VERSION2 has incompatible signatures)
- **SSH Multiplexing**: Added SSH multiplexing to serial forwarding scripts for 12x faster connections
- **Health Monitor**: Fixed missing `serial_connected` parameter in `update_connection_status()` call

### Added
- **Serial Port Forwarding Scripts**: Created scripts to forward UWB serial data from target devices to local machine for testing
  - `scripts/forward-uwb-simple.sh`: Forward serial port from target device using SSH + socat
  - `scripts/test-with-forwarded-serial.sh`: Complete test setup with forwarding
  - Both scripts support SSH multiplexing and automatic container management

### Changed
- **MQTT Options Clarification**: Renamed `--disable-mqtt` to `--disable-publish-mqtt` for clarity (old option still works as alias)
  - `--disable-publish-mqtt`: Disables UWB data publishing (LoRa MQTT is separate)
  - `--disable-mqtt`: Deprecated alias for `--disable-publish-mqtt`
- **UART Port Argument**: Made UART port argument optional when `--disable-serial` is used
- Improved LoRa location extraction priority: frm-payload > user > gps > first available
- Enhanced verbose logging for positioning debugging
- Updated container configuration to use correct TTN topic format

## [1.4.0] - 2025-01-XX

### Added
- **Position Confidence Scoring**: Complete Priority 2 confidence scoring system
  - Calculate confidence scores (0.0-1.0) for position data based on source, age, and quality metrics
  - Anchor points have maximum confidence (1.0, configurable)
  - LoRa GPS data has configurable base confidence (default: 0.7) and minimum confidence (default: 0.3)
  - Confidence decay over time for LoRa data based on TTL
  - GPS accuracy adjustment (better accuracy = higher confidence)
  - Gateway count adjustment (more gateways = higher confidence)
  - RSSI/SNR adjustment (better signal = higher confidence)
  - `positionConfidence` field added to CGA format
  - `--enable-confidence-scoring` flag to enable confidence scoring
  - `--anchor-confidence`, `--lora-gps-base-confidence`, `--lora-gps-min-confidence` parameters
  - `--lora-gps-decay-rate` parameter for time-based decay
  - `--gps-accuracy-weight`, `--gateway-count-weight`, `--rssi-weight` parameters for quality adjustments
  - Integration with network converter for automatic confidence calculation

- **New Module**:
  - `src/uwb_confidence_scorer.py`: Position confidence scoring with configurable algorithms

### Changed
- CGA format now includes `positionConfidence` field when confidence scoring is enabled
- Confidence scores help downstream systems make intelligent decisions about data quality

### Technical Details
- Anchor confidence: Always 1.0 (configurable)
- LoRa GPS confidence: Base 0.7, minimum 0.3, decays over time
- Confidence factors: data age (decay), GPS accuracy, gateway count, RSSI/SNR
- Confidence calculation: `base_confidence - time_decay + accuracy_bonus + gateway_bonus + rssi_bonus`
- Confidence clamped to valid range: `[min_confidence, base_confidence]`

---

## [1.3.0] - 2025-01-XX

### Added
- **Data Validation & Sanity Checks**: Complete Priority 2 data validation system
  - Configurable validation for UWB distances (min/max range)
  - GPS coordinate validation (reject 0,0, validate lat/lon ranges)
  - Battery level validation (configurable min/max percentage)
  - Temperature validation (configurable min/max Celsius)
  - Validation failure logging with detailed reasons
  - Optional MQTT topic for publishing validation failures
  - `--enable-validation` flag to enable validation
  - `--min-distance`, `--max-distance` parameters for distance validation
  - `--reject-zero-gps` flag for GPS validation
  - `--min-battery`, `--max-battery` parameters for battery validation
  - `--min-temperature`, `--max-temperature` parameters for temperature validation
  - `--validation-failures-topic` parameter for validation failure reporting
  - Integration with network converter for GPS/battery/temperature validation
  - Validation statistics tracking

- **New Module**:
  - `src/uwb_data_validator.py`: Data validation with configurable rules

### Changed
- Network converter now validates GPS, battery, and temperature data when validator is enabled
- Invalid data is filtered before publishing to prevent bad data propagation

### Technical Details
- Distance validation checks: `min_distance <= distance <= max_distance`
- GPS validation checks: latitude [-90, 90], longitude [-180, 180], rejects 0,0 by default
- Battery validation checks: `min_battery <= battery <= max_battery` (0-100%)
- Temperature validation checks: `min_temperature <= temp <= max_temperature` (Celsius)
- Validation failures are logged and optionally published to MQTT topic
- Validation statistics tracked: total validated, rejection counts by type, rejection rate

---

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

