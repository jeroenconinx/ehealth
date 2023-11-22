#if defined(ESP32)
  #include <WiFiMulti.h>
  WiFiMulti wifiMulti;
  #define DEVICE "ESP32"
  #elif defined(ESP8266)
  #include <ESP8266WiFiMulti.h>
  ESP8266WiFiMulti wifiMulti;
  #define DEVICE "ESP8266"
  #endif

  #include <Arduino.h>
  #include "Preferences.h"
  #include "ECG_Demo.h"

  uint16_t Sample_TimeUS = 1000*1000/sample_rate; //Sample time in microseconds
  uint16_t ECG_ARRAY_size = 0;

  unsigned long PrevMicros = 0;
  uint16_t ArrayCounter = 0;
  
  #include <InfluxDbClient.h>
  #include <InfluxDbCloud.h>
  
  // WiFi AP SSID
  #define WIFI_SSID SSID_4G
  // WiFi password
  #define WIFI_PASSWORD Password_4G
  
  #define INFLUXDB_URL url_4G
  #define INFLUXDB_TOKEN "S1St6xMc4hEz8NU2A6-tEoaGtvzDSUMNJBkIL7W4PE8dfwAQvjaabkE7FZvZtrvoUFwc195CVV7pf4necsxgQw=="
  #define INFLUXDB_ORG "uh"
  #define INFLUXDB_BUCKET "ehealth"
  
  // Time zone info
  #define TZ_INFO "UTC-1"
  
  // Declare InfluxDB client instance with preconfigured InfluxCloud certificate
  InfluxDBClient client(INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET, INFLUXDB_TOKEN, InfluxDbCloud2CACert);
  
  // Declare Data point
  Point sensor("wifi_status");
  Point sensorNetworks("network_status");

  void setup() {
    delay(10000);
    Serial.begin(115200);
    ECG_ARRAY_size = sizeof(ECG_ARRAY)/sizeof(ECG_ARRAY[0]);

    // Setup wifi
    WiFi.mode(WIFI_STA);
    wifiMulti.addAP(WIFI_SSID, WIFI_PASSWORD);
  
    Serial.print("Connecting to wifi");
    while (wifiMulti.run() != WL_CONNECTED) {
      Serial.print(".");
      delay(100);
    }
    Serial.println();
  
    // Accurate time is necessary for certificate validation and writing in batches
    // We use the NTP servers in your area as provided by: https://www.pool.ntp.org/zone/
    // Syncing progress and the time will be printed to Serial.
    timeSync(TZ_INFO, "pool.ntp.org", "time.nis.gov");
  
    // Check server connection
    if (client.validateConnection()) {
      Serial.print("Connected to InfluxDB: ");
      Serial.println(client.getServerUrl());
    } else {
      Serial.print("InfluxDB connection failed: ");
      Serial.println(client.getLastErrorMessage());
    }
    Serial.println("\tAvailable RAM memory: " + String(esp_get_free_heap_size()) + " bytes");
    // Warning, leave enough headroom for other tasks!

    // Set write options for batching and precision
    client.setWriteOptions(
        WriteOptions()
            .writePrecision(WritePrecision::MS)
            .batchSize(240)
            .bufferSize(1000)
            .flushInterval(100)
    );

    // Set HTTP options for the client
    client.setHTTPOptions(
        HTTPOptions().connectionReuse(true)
    );

  }

  void sendDataToInfluxDB(float ecgValue) {
    if (client.isBufferEmpty()) {
      Serial.print("Buffer is empty\n");
      // Additional actions or logic after successful data transmission
      // Add data to sensorNetworks point and write it to the buffer
      sensorNetworks.addField("ECG", ecgValue); // Add new field to point (Field != indexed datapoint, used for raw data)
      //Serial.print("Writing: ");
      //Serial.println(client.pointToLineProtocol(sensorNetworks));
      client.writePoint(sensorNetworks); // Write point into buffer
    }
    else{
    // Add fields to the point
    sensor.addField("ecg_value", ecgValue);

    // Write the point to InfluxDB
    if (client.writePoint(sensor)) {
      //Serial.println("Data sent to InfluxDB successfully!");
      Serial.println("\tAvailable RAM memory: " + String(esp_get_free_heap_size()) + " bytes");
    } else {
      Serial.print("InfluxDB write failed: ");
      Serial.println(client.getLastErrorMessage());
    }
    // Clear previous data from the point
    sensor.clearFields();
    }
  }

 void loop() {
  if (micros() >= PrevMicros + Sample_TimeUS) {
    PrevMicros = micros();
    float ecgValue = ECG_ARRAY[ArrayCounter] / 1000.0;
    sendDataToInfluxDB(ecgValue);
    ArrayCounter++;
  }
  if (ArrayCounter >= ECG_ARRAY_size) {
    ArrayCounter = 0;
  }
}