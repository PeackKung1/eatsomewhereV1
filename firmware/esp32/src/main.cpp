
#include <WiFi.h>
#include <Wire.h>
#include <PubSubClient.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// =====================================
// OLED
// =====================================
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_ADDR 0x3C

#define OLED_SDA 21
#define OLED_SCL 22

Adafruit_SSD1306 display(
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    &Wire,
    -1
);

// =====================================
// WiFi
// =====================================
const char* WIFI_SSID = "EatSomeWhere";
const char* WIFI_PASSWORD = "admin1234";

// =====================================
// MQTT
// =====================================
const char* MQTT_SERVER = "broker.hivemq.com";
const int MQTT_PORT = 1883;

const char* MQTT_CLIENT_ID = "ESP32_Coffee_Moisture_01";

const char* MQTT_TOPIC = "esp32/moisture";
const char* MQTT_STATUS = "esp32/moisture/status";

WiFiClient espClient;
PubSubClient mqtt(espClient);

// =====================================
// OLED STATUS DISPLAY
// =====================================
void showStatus() {

    display.clearDisplay();

    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

    display.setCursor(0, 0);
    display.println("COFFEE MOISTURE");

    display.println("---------------------");

    display.setCursor(0, 20);
    display.print("WiFi : ");

    if (WiFi.status() == WL_CONNECTED) {
        display.println("CONNECTED");
    } else {
        display.println("DISCONNECTED");
    }

    display.setCursor(0, 32);
    display.print("MQTT : ");

    if (mqtt.connected()) {
        display.println("CONNECTED");
    } else {
        display.println("DISCONNECTED");
    }

    display.setCursor(0, 46);

    if (WiFi.status() == WL_CONNECTED) {
        display.print("IP: ");
        display.println(WiFi.localIP());
    } else {
        display.println("Waiting WiFi...");
    }

    display.display();
}

// =====================================
// Connect WiFi
// =====================================
void connectWiFi() {

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    Serial.print("Connecting WiFi...");

    showStatus();

    while (WiFi.status() != WL_CONNECTED) {

        delay(500);

        Serial.print(".");

        showStatus();
    }

    Serial.println("\nWiFi Connected!");

    Serial.println(WiFi.localIP());

    showStatus();
}

// =====================================
// Connect MQTT
// =====================================
void connectMQTT() {

    while (!mqtt.connected()) {

        Serial.print("Connecting MQTT...");

        showStatus();

        if (mqtt.connect(
            MQTT_CLIENT_ID,
            MQTT_TOPIC,
            0,
            true,
            "offline"
        )) {

            Serial.println("Connected!");

            mqtt.publish(MQTT_STATUS, "online", true);

        } else {

            Serial.print("Failed, state = ");
            Serial.println(mqtt.state());

            showStatus();

            delay(2000);
        }
    }

    showStatus();
}

// =====================================
// Setup
// =====================================
void setup() {

    Serial.begin(115200);

    // Initialize I2C
    Wire.begin(OLED_SDA, OLED_SCL);

    // Initialize OLED
    if (!display.begin(
        SSD1306_SWITCHCAPVCC,
        OLED_ADDR
    )) {
        Serial.println("OLED Failed!");
        while (1);
    }

    display.clearDisplay();
    display.display();

    showStatus();

    // MQTT Server
    mqtt.setServer(MQTT_SERVER, MQTT_PORT);

    // WiFi
    connectWiFi();

    // MQTT
    connectMQTT();
}

// =====================================
// Loop
// =====================================
void loop() {

    // WiFi reconnect
    if (WiFi.status() != WL_CONNECTED) {

        showStatus();

        connectWiFi();
    }

    // MQTT reconnect
    if (!mqtt.connected()) {

        showStatus();

        connectMQTT();
    }

    mqtt.loop();

    // Update OLED
    static unsigned long lastDisplay = 0;

    if (millis() - lastDisplay >= 500) {

        lastDisplay = millis();

        showStatus();
    }
}
