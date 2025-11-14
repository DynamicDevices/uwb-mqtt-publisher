# UWB MQTT Publisher - Program Flow

This document describes the program flow of the UWB MQTT Publisher application using Mermaid diagrams.

## High-Level Architecture

```mermaid
graph TB
    Start([Program Start]) --> ParseArgs[Parse Command Line Arguments]
    ParseArgs --> LoadModules[Load Optional Modules]
    ParseArgs --> LoadDevEUIMap[Load Dev EUI Mapping<br/>if --dev-eui-mapping]
    LoadDevEUIMap --> InitLoRa[Initialize LoRa Cache<br/>if --enable-lora-cache<br/>with TTL and cleanup]
    InitLoRa --> InitErrorRecovery[Initialize Error Recovery<br/>with exponential backoff]
    InitErrorRecovery --> InitHealthMonitor[Initialize Health Monitor<br/>with MQTT reporting]
    InitHealthMonitor --> InitValidator[Initialize Data Validator<br/>if --enable-validation]
    InitValidator --> InitConfidenceScorer[Initialize Confidence Scorer<br/>if --enable-confidence-scoring]
    InitConfidenceScorer --> InitUWB[Initialize UWB Network Converter<br/>if --cga-format<br/>Pass LoRa cache, validator, scorer]
    InitUWB --> SetupMQTT[Setup MQTT Client<br/>if not --disable-mqtt]
    SetupMQTT --> OpenSerial[Open Serial Port<br/>/dev/ttyUSB0]
    OpenSerial --> MainLoop[Main Processing Loop]
    
    MainLoop --> ReadSerial[Read Data from Serial Port]
    ReadSerial --> ParsePacket[Parse UWB Packet]
    ParsePacket --> ValidateData{Valid Packet?}
    ValidateData -->|No| HandleError[Handle Parsing Error<br/>with Error Recovery]
    HandleError --> CheckMaxErrors{Max Errors<br/>with Backoff?}
    CheckMaxErrors -->|Yes| ResetDevice[Reset Device<br/>with Exponential Backoff]
    CheckMaxErrors -->|No| RecordError[Record Error<br/>Update Health Monitor]
    RecordError --> MainLoop
    ResetDevice --> RecordReset[Record Device Reset<br/>Update Health Monitor]
    RecordReset --> MainLoop
    
    ValidateData -->|Yes| ExtractEdges[Extract Edge List<br/>Node pairs + distances]
    ExtractEdges --> ValidateDistances{Data Validation<br/>Enabled?}
    ValidateDistances -->|Yes| CheckDistances[Validate Distances<br/>Filter Invalid Data]
    ValidateDistances -->|No| FormatData[Format Data]
    CheckDistances --> FormatData
    FormatData --> CheckCGA{CGA Format<br/>Enabled?}
    
    CheckCGA -->|Yes| ConvertCGA[Convert to CGA Network Format<br/>Add anchor coordinates<br/>Query LoRa cache for GPS/metadata<br/>Validate GPS/battery/temp<br/>Calculate position confidence<br/>Add timestamps, battery, triage, etc.]
    CheckCGA -->|No| SimpleFormat[Simple Edge List Format]
    
    ConvertCGA --> RateLimit[Check Rate Limit]
    SimpleFormat --> RateLimit
    RateLimit --> PublishMQTT[Publish to MQTT Broker<br/>Record Success/Failure]
    PublishMQTT --> ReportHealth{Health Report<br/>Due?}
    ReportHealth -->|Yes| PublishHealth[Publish Health Report<br/>to MQTT]
    ReportHealth -->|No| MainLoop
    PublishHealth --> MainLoop
    
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
                Converter->>LoRaCache: Query cached LoRa data<br/>for each UWB ID<br/>(with staleness check)
                LoRaCache-->>Converter: Cached data:<br/>GPS, battery, triage,<br/>timestamps, RSSI, SNR, etc.
                alt Data Validation Enabled
                    Converter->>Validator: Validate GPS coordinates<br/>battery, temperature
                    Validator-->>Converter: Validation result
                end
                Converter->>Converter: Add LoRa GPS only if<br/>UWB has no coordinates<br/>(and validated)
                alt Confidence Scoring Enabled
                    Converter->>ConfidenceScorer: Calculate position confidence<br/>based on source, age, quality
                    ConfidenceScorer-->>Converter: Confidence score (0.0-1.0)
                end
                Converter->>Converter: Add LoRa metadata:<br/>timestamps, battery, triage,<br/>gateway count, frame counter
                Converter->>Converter: Set positionSource<br/>positionAccuracy<br/>and positionConfidence
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
        ErrorRecovery[Error Recovery<br/>uwb_error_recovery.py]
        HealthMonitor[Health Monitor<br/>uwb_health_monitor.py]
        Validator[Data Validator<br/>uwb_data_validator.py]
        ConfidenceScorer[Confidence Scorer<br/>uwb_confidence_scorer.py]
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
    Main -->|Validate| Validator
    Validator -->|Valid Data| Main
    Main -->|Convert| Converter
    Converter -->|Read| AnchorConfig
    Converter -->|Query| Cache
    Converter -->|Validate| Validator
    Converter -->|Calculate Confidence| ConfidenceScorer
    Converter -->|Read| DevEUIMap
    LoRaMQTT -->|Subscribe| Cache
    Cache -->|Read| DevEUIMap
    Main -->|Record Errors| ErrorRecovery
    Main -->|Record Metrics| HealthMonitor
    Main -->|Publish| MQTTBroker
    HealthMonitor -->|Publish Health| MQTTBroker
    MQTTBroker -->|Commands| Main
    Main -->|Update Rate Limit| Main
```

## Error Handling Flow

```mermaid
graph TD
    Start[Read Serial Data] --> Parse[Parse Packet]
    Parse --> CheckValid{Valid Packet?}
    
    CheckValid -->|Yes| Process[Process Data]
    CheckValid -->|No| RecordError[Record Error<br/>Error Recovery System]
    
    RecordError --> CheckErrorType{Error Type?}
    CheckErrorType -->|Parsing| CheckParsingThreshold{Parsing Errors<br/>>= Threshold?}
    CheckErrorType -->|Connection| CheckConnThreshold{Connection Errors<br/>>= Threshold?}
    
    CheckParsingThreshold -->|No| LogWarning[Log Warning<br/>Update Health Monitor]
    CheckParsingThreshold -->|Yes| CheckBackoff{Should Reset<br/>with Backoff?}
    CheckConnThreshold -->|No| LogWarning
    CheckConnThreshold -->|Yes| CheckBackoff
    
    CheckBackoff -->|Yes| CalculateBackoff[Calculate Exponential Backoff<br/>initial * multiplier^reset_count]
    CalculateBackoff --> WaitBackoff[Wait for Backoff Period]
    WaitBackoff --> ResetSerial[Reset Device]
    CheckBackoff -->|No| LogWarning
    
    ResetSerial --> RecordReset[Record Device Reset<br/>Update Health Monitor]
    RecordReset --> ClearErrors[Clear Error Count<br/>for Error Type]
    ClearErrors --> Start
    
    LogWarning --> Start
    Process --> ValidateData{Data Validation<br/>Enabled?}
    ValidateData -->|Yes| CheckValidation{Data Valid?}
    ValidateData -->|No| Publish[Publish to MQTT]
    CheckValidation -->|No| LogValidationFailure[Log Validation Failure<br/>Publish to validation_failures topic]
    CheckValidation -->|Yes| Publish
    LogValidationFailure --> Start
    
    Publish --> CheckMQTT{MQTT<br/>Connected?}
    CheckMQTT -->|No| RecordMQTTError[Record MQTT Error<br/>Update Health Monitor]
    CheckMQTT -->|Yes| RecordMQTTSuccess[Record MQTT Success<br/>Update Health Monitor]
    RecordMQTTError --> Start
    RecordMQTTSuccess --> Success[Success]
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
    AddAnchors --> QueryLoRa["Query LoRa Cache<br/>for each UWB ID<br/>(with staleness check)"]
    QueryLoRa --> CheckCoords{UWB has<br/>coordinates?}
    CheckCoords -->|No| ValidateLoRaGPS["Validate LoRa GPS<br/>if validator enabled<br/>(reject 0,0, check ranges)"]
    CheckCoords -->|Yes| KeepAnchorCoords["Keep Anchor Coordinates<br/>Don't override"]
    ValidateLoRaGPS --> ValidateLoRaData["Validate LoRa Data<br/>battery, temperature<br/>if validator enabled"]
    ValidateLoRaData --> AddLoRaGPS["Add LoRa GPS Coordinates<br/>Update lastPositionUpdateTime"]
    AddLoRaGPS --> CalculateConfidence["Calculate Position Confidence<br/>if scorer enabled<br/>(anchor: 1.0, LoRa: 0.3-0.7)"]
    KeepAnchorCoords --> CalculateConfidence
    CalculateConfidence --> AddLoRaMetadata["Add LoRa Metadata:<br/>timestamps, battery, triage,<br/>RSSI, SNR, gateway count, etc."]
    AddLoRaMetadata --> SetPositionSource["Set positionSource<br/>positionAccuracy<br/>and positionConfidence"]
    SetPositionSource --> CGANetwork["CGA Network Format<br/>Structured JSON<br/>with all metadata"]
    
    SimpleJSON --> MQTT["MQTT Publish"]
    CGANetwork --> MQTT
```

## Future Enhancements

For detailed information about planned future enhancements, prioritized by importance and impact, see [FUTURE_ENHANCEMENTS.md](FUTURE_ENHANCEMENTS.md).

The enhancements are organized into 5 priority levels:
1. **Priority 1**: Critical for Production Reliability (Data staleness, cache expiration, error recovery)
2. **Priority 2**: Important for Data Quality (Data validation, confidence scoring)
3. **Priority 3**: Useful Features (Statistics, data filtering)
4. **Priority 4**: Advanced Features (Position fusion, historical tracking)
5. **Priority 5**: Nice to Have (Dynamic config, multi-broker, binary formats)

An implementation roadmap is provided in the FUTURE_ENHANCEMENTS.md file.

