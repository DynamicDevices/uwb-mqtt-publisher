# UWB MQTT Publisher - Program Flow

This document describes the program flow of the UWB MQTT Publisher application using Mermaid diagrams.

## High-Level Architecture

```mermaid
graph TB
    Start([Program Start]) --> ParseArgs[Parse Command Line Arguments]
    ParseArgs --> LoadModules[Load Optional Modules]
    LoadModules --> InitUWB[Initialize UWB Network Converter<br/>if --cga-format]
    InitUWB --> InitLoRa[Initialize LoRa Cache<br/>if --enable-lora-cache]
    InitLoRa --> SetupMQTT[Setup MQTT Client<br/>if not --disable-mqtt]
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
    
    CheckCGA -->|Yes| ConvertCGA[Convert to CGA Network Format<br/>Add anchor coordinates<br/>Add LoRa tag data]
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
    Main->>Converter: Load anchor config<br/>Load dev_eui mappings
    Converter-->>Main: Anchor map loaded
    Main->>LoRaCache: Start LoRa MQTT subscription<br/>Pass dev_eui mappings
    LoRaCache->>MQTT: Subscribe to TTN topics
    LoRaCache-->>Main: Cache initialized
    Main->>MQTT: Connect & subscribe to command topic
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
                Converter->>Converter: Map UWB IDs to anchors
                Converter->>LoRaCache: Get cached LoRa data<br/>for UWB IDs
                LoRaCache-->>Converter: Battery, GPS, temp, etc.
                Converter->>Converter: Build network JSON<br/>with coordinates & metadata
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
    RawPacket[Raw UWB Packet<br/>Binary Data] --> Parse[Parse Packet]
    Parse --> EdgeList[Edge List Format<br/>[node1, node2, distance]]
    
    EdgeList --> CheckFormat{Format Type?}
    
    CheckFormat -->|Simple| SimpleJSON[Simple JSON<br/>Array of edges]
    CheckFormat -->|CGA| CGAConversion[CGA Conversion]
    
    CGAConversion --> AddAnchors[Add Anchor Coordinates<br/>from config]
    AddAnchors --> AddLoRaData[Add LoRa Tag Data<br/>from cache]
    AddLoRaData --> AddMetadata[Add Metadata<br/>timestamp, etc.]
    AddMetadata --> CGANetwork[CGA Network Format<br/>Structured JSON]
    
    SimpleJSON --> MQTT[MQTT Publish]
    CGANetwork --> MQTT
```

