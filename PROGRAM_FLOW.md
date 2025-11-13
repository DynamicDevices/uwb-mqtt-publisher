# UWB MQTT Publisher - Program Flow

This document describes the program flow of the UWB MQTT Publisher application using Mermaid diagrams.

## High-Level Architecture

```mermaid
graph TB
    Start([Program Start]) --> ParseArgs[Parse Command Line Arguments]
    ParseArgs --> LoadModules[Load Optional Modules]
    ParseArgs --> LoadDevEUIMap[Load Dev EUI Mapping<br/>if --dev-eui-mapping]
    LoadDevEUIMap --> InitLoRa[Initialize LoRa Cache<br/>if --enable-lora-cache]
    InitLoRa --> InitUWB[Initialize UWB Network Converter<br/>if --cga-format<br/>Pass LoRa cache]
    InitUWB --> SetupMQTT[Setup MQTT Client<br/>if not --disable-mqtt]
    SetupMQTT --> OpenSerial[Open Serial Port<br/>/dev/ttyUSB0]
    OpenSerial --> MainLoop[Main Processing Loop]
    
    MainLoop --> ReadSerial[Read Data from Serial Port]
    ReadSerial --> ParsePacket[Parse UWB Packet]
    ParsePacket --> ValidateData{Valid Packet?}
    ValidateData -->|No| HandleError[Handle Parsing Error]
    HandleError --> CheckMaxErrors{Max Errors<br/>Reached?}
    CheckMaxErrors -->|Yes| ResetDevice[Reset Device]
    CheckMaxErrors -->|No| MainLoop
    ResetDevice --> MainLoop
    
    ValidateData -->|Yes| ExtractEdges[Extract Edge List<br/>Node pairs + distances]
    ExtractEdges --> FormatData[Format Data]
    FormatData --> CheckCGA{CGA Format<br/>Enabled?}
    
    CheckCGA -->|Yes| ConvertCGA[Convert to CGA Network Format<br/>Add anchor coordinates<br/>Query LoRa cache for GPS/metadata<br/>Add timestamps, battery, triage, etc.]
    CheckCGA -->|No| SimpleFormat[Simple Edge List Format]
    
    ConvertCGA --> RateLimit[Check Rate Limit]
    SimpleFormat --> RateLimit
    RateLimit --> PublishMQTT[Publish to MQTT Broker]
    PublishMQTT --> MainLoop
    
    SetupMQTT -.->|Background Thread| MQTTLoop[MQTT Event Loop<br/>Handle commands]
    InitLoRa -.->|Background Thread| LoRaLoop[LoRa MQTT Subscription<br/>Cache tag data]
    
    MQTTLoop --> HandleCommands[Handle MQTT Commands<br/>e.g., set rate_limit]
    LoRaLoop --> CacheLoRaData[Cache LoRa Tag Data<br/>Map dev_eui to UWB ID]
```

## Detailed Data Flow

```mermaid
sequenceDiagram
    participant Serial as Serial Port<br/>(/dev/ttyUSB0)
    participant Main as Main Script
    participant Parser as Packet Parser
    participant Converter as UWB Network Converter
    participant LoRaCache as LoRa Tag Cache
    participant MQTT as MQTT Broker
    
    Note over Main: Initialization Phase
    Main->>Main: Load dev_eui mapping file<br/>if --dev-eui-mapping
    Main->>LoRaCache: Initialize LoRa cache<br/>Pass dev_eui mappings<br/>if --enable-lora-cache
    LoRaCache->>MQTT: Subscribe to TTN topics<br/>(background thread)
    LoRaCache-->>Main: Cache initialized
    Main->>Converter: Initialize converter<br/>Load anchor config<br/>Pass LoRa cache reference<br/>if --cga-format
    Converter-->>Main: Converter ready
    Main->>MQTT: Connect & subscribe to command topic<br/>if not --disable-mqtt
    MQTT-->>Main: Connected
    
    Note over Main: Main Processing Loop
    loop Continuous Processing
        Serial->>Main: Raw UWB packet bytes
        Main->>Parser: Parse packet structure
        Parser->>Parser: Validate packet format
        Parser->>Parser: Extract assignments<br/>(node groups)
        Parser->>Parser: Extract final payload<br/>(distance measurements)
        Parser->>Parser: Parse final payload<br/>into edge list
        
        alt Parsing Error
            Parser-->>Main: Error signal
            Main->>Main: Increment error count
            alt Max Errors Reached
                Main->>Serial: Reset device
            end
        else Valid Data
            Parser-->>Main: Edge list<br/>[[node1, node2, distance], ...]
            
            alt CGA Format Enabled
                Main->>Converter: convert_edges_to_network(edge_list)
                Converter->>Converter: Map UWB IDs to anchors<br/>Set anchor coordinates
                Converter->>LoRaCache: Query cached LoRa data<br/>for each UWB ID
                LoRaCache-->>Converter: Cached data:<br/>GPS, battery, triage,<br/>timestamps, RSSI, SNR, etc.
                Converter->>Converter: Add LoRa GPS only if<br/>UWB has no coordinates
                Converter->>Converter: Add LoRa metadata:<br/>timestamps, battery, triage,<br/>gateway count, frame counter
                Converter->>Converter: Set positionSource<br/>(anchor_config or lora source)
                Converter->>Converter: Build network JSON<br/>with all metadata
                Converter-->>Main: CGA network format JSON
            else Simple Format
                Main->>Main: Format as simple edge list
            end
            
            Main->>Main: Check rate limit
            alt Rate Limit OK
                Main->>MQTT: Publish formatted data
                MQTT-->>Main: Publish confirmation
            else Rate Limited
                Main->>Main: Skip publish
            end
        end
    end
    
    Note over LoRaCache,MQTT: Background Threads
    loop LoRa MQTT Subscription
        MQTT->>LoRaCache: LoRa tag uplink message
        LoRaCache->>LoRaCache: Extract dev_eui
        LoRaCache->>LoRaCache: Map dev_eui to UWB ID
        LoRaCache->>LoRaCache: Cache tag data<br/>(battery, GPS, temp, etc.)
    end
    
    loop MQTT Command Handling
        MQTT->>Main: Command message<br/>(e.g., set rate_limit 5.0)
        Main->>Main: Parse command
        Main->>Main: Update rate limit
    end
```

## Component Interaction Diagram

```mermaid
graph LR
    subgraph "Input Sources"
        Serial[Serial Port<br/>UWB Device]
        LoRaMQTT[LoRa MQTT<br/>TTN Broker]
    end
    
    subgraph "Core Components"
        Main[mqtt-live-publisher.py<br/>Main Script]
        Parser[Packet Parser<br/>parse_final]
        Converter[UWB Network Converter<br/>uwb_network_converter.py]
        Cache[LoRa Tag Cache<br/>lora_tag_cache.py]
    end
    
    subgraph "Output"
        MQTTBroker[MQTT Broker<br/>Publish Data]
        MQTTCommands[MQTT Commands<br/>Receive Control]
    end
    
    subgraph "Configuration"
        AnchorConfig[Anchor Config<br/>uwb_anchors*.json]
        DevEUIMap[Dev EUI Mappings<br/>dev_eui_to_uwb_mappings.json]
    end
    
    Serial -->|Raw Packets| Main
    Main -->|Parse| Parser
    Parser -->|Edge List| Main
    Main -->|Convert| Converter
    Converter -->|Read| AnchorConfig
    Converter -->|Query| Cache
    Converter -->|Read| DevEUIMap
    LoRaMQTT -->|Subscribe| Cache
    Cache -->|Read| DevEUIMap
    Main -->|Publish| MQTTBroker
    MQTTBroker -->|Commands| Main
    Main -->|Update Rate Limit| Main
```

## Error Handling Flow

```mermaid
graph TD
    Start[Read Serial Data] --> Parse[Parse Packet]
    Parse --> CheckValid{Valid Packet?}
    
    CheckValid -->|Yes| Process[Process Data]
    CheckValid -->|No| IncrementError[Increment Error Count]
    
    IncrementError --> CheckMax{Error Count<br/>>= MAX?}
    CheckMax -->|No| LogWarning[Log Warning<br/>Continue Processing]
    CheckMax -->|Yes| LogCritical[Log Critical Error]
    
    LogCritical --> ResetSerial[Reset Serial Port]
    ResetSerial --> Reopen[Reopen Serial Port]
    Reopen --> ClearErrors[Clear Error Count]
    ClearErrors --> Start
    
    LogWarning --> Start
    Process --> Publish[Publish to MQTT]
    Publish --> CheckMQTT{MQTT<br/>Connected?}
    CheckMQTT -->|No| LogMQTTError[Log MQTT Error]
    CheckMQTT -->|Yes| Success[Success]
    LogMQTTError --> Start
    Success --> Start
```

## Configuration Loading Flow

```mermaid
graph TD
    Start([Program Start]) --> ParseArgs[Parse Arguments]
    ParseArgs --> CheckCGA{--cga-format<br/>specified?}
    
    CheckCGA -->|Yes| LoadAnchorConfig[Load Anchor Config<br/>uwb_anchors*.json]
    CheckCGA -->|No| SkipAnchor[Skip Anchor Config]
    
    LoadAnchorConfig --> ParseAnchorJSON[Parse JSON<br/>Extract anchors]
    ParseAnchorJSON --> BuildAnchorMap[Build Anchor Map<br/>id -> lat, lon, alt]
    
    CheckCGA -->|Yes| LoadDevEUIMap[Load Dev EUI Mapping<br/>dev_eui_to_uwb_mappings.json]
    CheckCGA -->|No| SkipDevEUI[Skip Dev EUI Mapping]
    
    LoadDevEUIMap --> ParseDevEUIJSON[Parse JSON<br/>Extract mappings]
    ParseDevEUIJSON --> BuildDevEUIMap[Build Dev EUI Map<br/>dev_eui -> uwb_id]
    
    BuildAnchorMap --> InitConverter[Initialize Converter<br/>with configs]
    BuildDevEUIMap --> InitConverter
    
    InitConverter --> CheckLoRa{--enable-lora-cache<br/>specified?}
    CheckLoRa -->|Yes| PassDevEUIToLoRa[Pass Dev EUI Map<br/>to LoRa Cache]
    CheckLoRa -->|No| SkipLoRa[Skip LoRa Cache]
    
    PassDevEUIToLoRa --> InitLoRaCache[Initialize LoRa Cache<br/>with mappings]
    InitLoRaCache --> StartLoRaThread[Start LoRa MQTT<br/>Subscription Thread]
    
    SkipAnchor --> SkipLoRa
    SkipDevEUI --> SkipLoRa
    SkipLoRa --> Ready[Ready for Processing]
    StartLoRaThread --> Ready
```

## Rate Limiting Flow

```mermaid
graph TD
    DataReady[Data Ready to Publish] --> GetTime[Get Current Time]
    GetTime --> CheckLastPublish{Time Since<br/>Last Publish<br/>>= Rate Limit?}
    
    CheckLastPublish -->|Yes| Publish[Publish to MQTT]
    CheckLastPublish -->|No| Skip[Skip Publish<br/>Rate Limited]
    
    Publish --> UpdateLastTime[Update Last Publish Time]
    UpdateLastTime --> Done[Done]
    Skip --> Done
    
    MQTTCommand[Receive MQTT Command<br/>set rate_limit X] --> ParseCommand[Parse Command]
    ParseCommand --> ValidateRate{Rate > 0?}
    ValidateRate -->|Yes| UpdateRateLimit[Update Rate Limit<br/>Thread-Safe Lock]
    ValidateRate -->|No| LogError[Log Error<br/>Invalid Rate]
    UpdateRateLimit --> Done
    LogError --> Done
```

## Data Format Conversion

```mermaid
graph LR
    RawPacket["Raw UWB Packet<br/>Binary Data"] --> Parse["Parse Packet"]
    Parse --> EdgeList["Edge List Format<br/>node1, node2, distance"]
    
    EdgeList --> CheckFormat{Format Type?}
    
    CheckFormat -->|Simple| SimpleJSON["Simple JSON<br/>Array of edges"]
    CheckFormat -->|CGA| CGAConversion["CGA Conversion"]
    
    CGAConversion --> AddAnchors["Add Anchor Coordinates<br/>from config<br/>Set positionSource=anchor_config"]
    AddAnchors --> QueryLoRa["Query LoRa Cache<br/>for each UWB ID"]
    QueryLoRa --> CheckCoords{UWB has<br/>coordinates?}
    CheckCoords -->|No| AddLoRaGPS["Add LoRa GPS Coordinates<br/>Update lastPositionUpdateTime"]
    CheckCoords -->|Yes| KeepAnchorCoords["Keep Anchor Coordinates<br/>Don't override"]
    AddLoRaGPS --> AddLoRaMetadata["Add LoRa Metadata:<br/>timestamps, battery, triage,<br/>RSSI, SNR, gateway count, etc."]
    KeepAnchorCoords --> AddLoRaMetadata
    AddLoRaMetadata --> SetPositionSource["Set positionSource<br/>and positionAccuracy"]
    SetPositionSource --> CGANetwork["CGA Network Format<br/>Structured JSON<br/>with all metadata"]
    
    SimpleJSON --> MQTT["MQTT Publish"]
    CGANetwork --> MQTT
```

## Future Enhancements

This section documents potential future improvements to the UWB MQTT Publisher system, along with the rationale for each enhancement.

### Data Quality & Staleness Management

**Enhancement**: Add configurable data staleness thresholds and automatic filtering
- **Why**: Currently, LoRa cached data has timestamps but no automatic filtering based on age. Old GPS coordinates or sensor data could be misleading.
- **Implementation**: 
  - Add `--lora-max-age` parameter (seconds) to filter out stale LoRa data
  - Add `--lora-gps-max-age` parameter specifically for GPS coordinates
  - Log warnings when using stale data
  - Optionally exclude stale data from CGA format output
- **Benefits**: Prevents using outdated location data, improves data quality, reduces false positioning

### Cache Expiration & Cleanup

**Enhancement**: Implement automatic cache expiration for LoRa data
- **Why**: Currently, LoRa cache stores data indefinitely. Old entries could consume memory and provide stale information.
- **Implementation**:
  - Add TTL (Time To Live) for cached entries
  - Periodic cleanup thread to remove expired entries
  - Configurable expiration times per data type (GPS vs sensor data)
- **Benefits**: Memory efficiency, ensures only recent data is used, prevents stale data issues

### Position Confidence Scoring

**Enhancement**: Add confidence scores for position data
- **Why**: Different position sources (anchor config, LoRa GPS) have different reliability. A confidence score would help downstream systems make decisions.
- **Implementation**:
  - Calculate confidence based on: data age, GPS accuracy, number of gateways, RSSI/SNR
  - Add `positionConfidence` field (0.0-1.0) to CGA format
  - Higher confidence for anchors, lower for old/stale LoRa GPS
- **Benefits**: Enables intelligent decision-making in positioning systems, improves reliability assessment

### Multi-Source Position Fusion

**Enhancement**: Combine multiple position sources (anchor config + LoRa GPS) with weighted averaging
- **Why**: Currently, anchor positions take precedence. In some cases, combining anchor and LoRa GPS could provide better accuracy.
- **Implementation**:
  - Weighted average of anchor and LoRa GPS positions
  - Weights based on confidence, accuracy, and data age
  - Configurable fusion strategy (prefer anchor, prefer LoRa, or weighted)
- **Benefits**: Improved positioning accuracy, better use of available data sources

### Enhanced Error Recovery

**Enhancement**: Improve error handling and recovery mechanisms
- **Why**: Current error handling resets device after max errors, but could be more sophisticated.
- **Implementation**:
  - Exponential backoff for device resets
  - Different error thresholds for different error types
  - Automatic retry with different serial port settings
  - Health monitoring and reporting
- **Benefits**: More robust operation, reduced downtime, better diagnostics

### Data Validation & Sanity Checks

**Enhancement**: Add validation for UWB distance measurements and LoRa data
- **Why**: Invalid or impossible measurements (e.g., negative distances, GPS coordinates outside valid range) should be filtered.
- **Implementation**:
  - Validate UWB distances are within expected range
  - Validate GPS coordinates are reasonable (not 0,0 or extreme values)
  - Validate battery levels, temperatures are within expected ranges
  - Configurable validation rules
- **Benefits**: Prevents bad data from propagating, improves system reliability

### Statistics & Monitoring

**Enhancement**: Add comprehensive statistics and monitoring
- **Why**: Understanding system performance, data quality, and issues requires visibility.
- **Implementation**:
  - Track packet parsing success rate
  - Track LoRa cache hit/miss rates
  - Track data staleness statistics
  - Track MQTT publish success/failure rates
  - Periodic statistics reporting via MQTT or log
- **Benefits**: Better observability, easier troubleshooting, performance optimization

### Configurable Data Filtering

**Enhancement**: Allow filtering of UWB edges based on distance, quality, or other criteria
- **Why**: Some distance measurements may be unreliable (too long, too short, poor signal quality).
- **Implementation**:
  - Add `--max-distance` and `--min-distance` filters
  - Filter based on signal quality if available
  - Filter based on measurement confidence
- **Benefits**: Improved data quality, reduced noise in positioning calculations

### Historical Data Tracking

**Enhancement**: Maintain historical position and sensor data for trend analysis
- **Why**: Tracking position changes over time could enable velocity calculation, path prediction, and anomaly detection.
- **Implementation**:
  - Maintain sliding window of recent positions
  - Calculate velocity and acceleration
  - Detect sudden position jumps (potential errors)
  - Optional historical data export
- **Benefits**: Enables advanced features like velocity tracking, path prediction, anomaly detection

### Multi-Broker Support

**Enhancement**: Support publishing to multiple MQTT brokers simultaneously
- **Why**: Some deployments may need to publish to multiple systems (monitoring, analytics, control systems).
- **Implementation**:
  - Allow multiple `--mqtt-broker` arguments
  - Separate configuration per broker (topic, credentials, etc.)
  - Independent rate limiting per broker
- **Benefits**: Flexibility in deployment, supports multiple downstream systems

### Protocol Buffers or MessagePack Support

**Enhancement**: Add binary serialization formats as alternatives to JSON
- **Why**: JSON is human-readable but verbose. Binary formats reduce bandwidth and improve performance.
- **Implementation**:
  - Add `--format` option (json, protobuf, msgpack)
  - Define protobuf schema for CGA network format
  - Maintain JSON as default for compatibility
- **Benefits**: Reduced bandwidth, improved performance, smaller message sizes

### WebSocket Support for MQTT

**Enhancement**: Add WebSocket transport option for MQTT
- **Why**: Some network environments may require WebSocket instead of raw TCP for MQTT.
- **Implementation**:
  - Add `--mqtt-transport` option (tcp, websockets)
  - Support WebSocket URL format
- **Benefits**: Better compatibility with firewalls and proxies, supports web-based deployments

### Dynamic Anchor Configuration

**Enhancement**: Support updating anchor configuration at runtime via MQTT commands
- **Why**: Anchor positions may need to be updated without restarting the service.
- **Implementation**:
  - MQTT command: `update_anchor_config <json>`
  - Reload anchor configuration from file or MQTT payload
  - Validate new configuration before applying
- **Benefits**: Operational flexibility, no downtime for config changes

### Device Health Monitoring

**Enhancement**: Monitor and report device health metrics
- **Why**: Proactive monitoring can detect issues before they cause failures.
- **Implementation**:
  - Track serial port errors, connection status
  - Monitor LoRa cache connectivity
  - Track MQTT connection stability
  - Periodic health status reports
- **Benefits**: Early problem detection, improved reliability, easier maintenance


