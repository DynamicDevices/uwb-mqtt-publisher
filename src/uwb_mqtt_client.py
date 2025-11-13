#!/usr/bin/env python3
"""
UWB MQTT Client
Handles MQTT connection, publishing, and command handling.
"""

import json
import ssl
import time
import threading

try:
    import paho.mqtt.client as mqtt
except ImportError as e:
    print("Error: paho-mqtt library not found. Install with: pip install paho-mqtt")
    raise


class UwbMqttClient:
    """MQTT client for publishing UWB data and receiving commands."""
    
    def __init__(self, broker, port, topic, rate_limit=10.0, command_topic=None, 
                 verbose=False, quiet=False, disable_mqtt=False):
        """
        Initialize MQTT client.
        
        Args:
            broker: MQTT broker hostname
            port: MQTT broker port
            topic: Topic to publish to
            rate_limit: Minimum seconds between publishes
            command_topic: Topic to subscribe to for commands (default: topic/cmd)
            verbose: Enable verbose logging
            quiet: Enable quiet mode
            disable_mqtt: Disable MQTT entirely
        """
        self.broker = broker
        self.port = port
        self.topic = topic
        self.command_topic = command_topic or f"{topic}/cmd"
        self.verbose = verbose
        self.quiet = quiet
        self.disable_mqtt = disable_mqtt
        
        self.client = None
        self.last_publish_time = 0
        self.rate_limit = rate_limit
        self.rate_limit_lock = threading.Lock()
        
    def _log(self, message, level="INFO"):
        """Internal logging."""
        if not self.quiet:
            if level == "VERBOSE" and not self.verbose:
                return
            print(f"[{level}] {message}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback."""
        if rc == 0:
            self._log(f"Connected to MQTT broker {self.broker}:{self.port}", "INFO")
            try:
                client.subscribe(self.command_topic, qos=1)
                self._log(f"Subscribed to command topic: {self.command_topic}", "VERBOSE")
            except Exception as e:
                self._log(f"Failed to subscribe to command topic: {e}", "ERROR")
        else:
            self._log(f"Failed to connect to MQTT broker (rc={rc})", "ERROR")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback."""
        if rc != 0:
            self._log(f"Unexpected disconnection from MQTT broker (rc={rc})", "WARNING")
        else:
            self._log("Disconnected from MQTT broker", "VERBOSE")
    
    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback."""
        self._log(f"Message {mid} published successfully", "VERBOSE")
    
    def _on_log(self, client, userdata, level, buf):
        """MQTT log callback."""
        if self.verbose:
            print(f"[MQTT LOG] {buf}")
    
    def _on_message(self, client, userdata, message):
        """Handle incoming MQTT command messages."""
        try:
            topic = message.topic
            payload = message.payload.decode('utf-8').strip()
            
            self._log(f"Received command on {topic}: {payload}", "VERBOSE")
            
            # Parse rate limit commands
            if payload.startswith('set rate_limit '):
                try:
                    new_rate = float(payload.split(' ')[2])
                    if new_rate > 0:
                        with self.rate_limit_lock:
                            old_rate = self.rate_limit
                            self.rate_limit = new_rate
                        self._log(f"Updated rate limit: {old_rate}s → {new_rate}s", "INFO")
                    else:
                        self._log(f"Invalid rate limit value: {new_rate} (must be > 0)", "WARNING")
                except (IndexError, ValueError) as e:
                    self._log(f"Failed to parse rate limit command: {payload}", "WARNING")
            else:
                self._log(f"Unknown command: {payload}", "VERBOSE")
                
        except Exception as e:
            self._log(f"Error processing MQTT command: {e}", "ERROR")
    
    def setup(self):
        """Setup and connect MQTT client."""
        if self.disable_mqtt:
            self._log("MQTT disabled", "VERBOSE")
            return None
            
        try:
            self._log("Creating MQTT client instance", "VERBOSE")
            self.client = mqtt.Client()
            
            # Set up callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish
            self.client.on_log = self._on_log
            self.client.on_message = self._on_message
            
            self._log(f"Configuring SSL for broker {self.broker}:{self.port}", "VERBOSE")
            
            # Configure SSL
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            self.client.tls_set_context(context)
            self._log("SSL context applied to MQTT client", "VERBOSE")
            
            # Connect to broker
            self._log(f"Attempting to connect to {self.broker}:{self.port}", "VERBOSE")
            connect_result = self.client.connect(self.broker, self.port, 60)
            self._log(f"Connect call returned: {connect_result}", "VERBOSE")
            
            self._log("Starting MQTT client loop", "VERBOSE")
            self.client.loop_start()
            
            # Wait a moment for connection to establish
            time.sleep(2)
            
            if self.client.is_connected():
                self._log("MQTT client reports connected status", "VERBOSE")
            else:
                self._log("MQTT client reports disconnected status after 2 seconds", "VERBOSE")
            
            self._log(f"MQTT client configured for {self.broker}:{self.port}", "INFO")
            return self.client
            
        except Exception as e:
            self._log(f"Failed to setup MQTT: {e}", "ERROR")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return None
    
    def publish(self, data):
        """
        Publish data to MQTT broker with rate limiting.
        
        Args:
            data: Data to publish (will be converted to JSON)
        """
        if self.client is None:
            self._log("MQTT publish skipped - client not available", "INFO")
            return
            
        if self.disable_mqtt:
            self._log("MQTT publish skipped - disabled", "VERBOSE")
            return
            
        current_time = time.time()
        time_since_last = current_time - self.last_publish_time
        
        # Get current rate limit in thread-safe manner
        with self.rate_limit_lock:
            rate_limit = self.rate_limit
        
        if time_since_last < rate_limit:
            return
            
        if not self.client.is_connected():
            self._log("MQTT client not connected, skipping publish", "INFO")
            return
            
        try:
            # Convert data to JSON string
            json_data = json.dumps(data)
            self._log(f"Attempting to publish to topic '{self.topic}': {json_data}", "VERBOSE")
            
            result = self.client.publish(self.topic, json_data, qos=1)
            self._log(f"Publish result: rc={result.rc}, mid={result.mid}", "VERBOSE")
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.last_publish_time = current_time
                self._log(f"Published to MQTT topic '{self.topic}'", "INFO")
            else:
                error_messages = {
                    mqtt.MQTT_ERR_NO_CONN: "No connection to broker",
                    mqtt.MQTT_ERR_QUEUE_SIZE: "Message queue full",
                    mqtt.MQTT_ERR_PAYLOAD_SIZE: "Payload too large"
                }
                error_msg = error_messages.get(result.rc, f"Unknown error {result.rc}")
                self._log(f"Failed to publish to MQTT: {error_msg}", "INFO")
                
        except Exception as e:
            self._log(f"Error publishing to MQTT: {e}", "INFO")
            if self.verbose:
                import traceback
                traceback.print_exc()
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            self._log("Stopping MQTT client loop", "VERBOSE")
            self.client.loop_stop()
            self._log("Disconnecting from MQTT broker", "VERBOSE")
            self.client.disconnect()

