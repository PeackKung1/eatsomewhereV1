// =====================================
// ESP32 วัดแสง + อุณหภูมิ -> MQTT  (บอร์ด ESP32 CAN R01)
// ส่วนที่มีป้าย [ใหม่] = ส่วนที่เพิ่มเข้ามา
// ส่วนที่มีป้าย [แก้]  = แก้จากโค้ดเดิม
// =====================================
#include <Arduino.h>            // [ใหม่] PlatformIO ต้องมี
#include <WiFi.h>
#include <Wire.h>
#include <time.h>               // [ใหม่] เวลา ts (NTP)
#include <PubSubClient.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <OneWire.h>            // [ใหม่] DS18B20
#include <DallasTemperature.h>  // [ใหม่] DS18B20

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

const char* MQTT_CLIENT_ID = "ESP32_LightTemp_01";         // [แก้] ชื่อตามโจทย์ใหม่

const char* MQTT_TOPIC = "esp32/lighttemp";                // [แก้]
const char* MQTT_STATUS = "esp32/lighttemp/status";        // [แก้]

const char* DEVICE_ID = "esp32-01";                        // [ใหม่] ใส่ใน JSON
const unsigned long PUBLISH_MS = 2000;                     // [ใหม่] ส่งทุก 2 วินาที

WiFiClient espClient;
PubSubClient mqtt(espClient);

// =====================================
// [ใหม่] ขาเซนเซอร์บนบอร์ด
// =====================================
#define PIN_LDR  35   // LDR (R7) + R8 4.7k -> IO35 (ADC1 ใช้ได้แม้เปิด WiFi)
#define PIN_DS18 13   // DS18B20
#define PIN_SW2  32   // กด = LOW -> เก็บจุด calibrate

const float R_FIXED = 4700.0;   // R8
const float VCC_MV  = 3300.0;

// =====================================
// [ใหม่] ค่าจากการ calibrate (ได้จาก fit_light.py)
//   log10(lux) = C0 + C1*x + C2*x^2   โดย x = log10(R_LDR)
//   อุณหภูมิจริง = ค่าที่อ่านได้ + TEMP_OFFSET
// =====================================
float LUX_C0 = 6.71;    // ค่าเริ่มต้นคร่าว ๆ ของ LDR ทั่วไป -> ต้อง calibrate ใหม่
float LUX_C1 = -1.43;
float LUX_C2 = 0.0;
float TEMP_OFFSET = 0.0;

// =====================================
// [ใหม่] ตัวแปรเซนเซอร์
// =====================================
OneWire oneWire(PIN_DS18);
DallasTemperature ds(&oneWire);

float ldrMv   = NAN;   // แรงดันที่ IO35 (mV)
float ldrOhm  = NAN;   // ความต้านทาน LDR (โอห์ม)
float luxVal  = NAN;   // ความสว่าง (lux) หลังแปลงด้วยสูตร
float tempRaw = NAN;   // อุณหภูมิดิบจาก DS18B20
float tempC   = NAN;   // อุณหภูมิหลังชดเชย
int   calCount = 0;
char  clientId[48];

// =====================================
// [ใหม่] อ่านแสง
// =====================================
// อ่าน 64 ครั้ง ตัดค่าสูงสุด/ต่ำสุดทิ้ง แล้วเฉลี่ย -> ลดสัญญาณรบกวนตอน WiFi ส่งข้อมูล
float readLdrMv() {
    uint32_t sum = 0, mn = UINT32_MAX, mx = 0;
    for (int i = 0; i < 64; i++) {
        uint32_t v = analogReadMilliVolts(PIN_LDR);
        sum += v;
        if (v < mn) mn = v;
        if (v > mx) mx = v;
        delayMicroseconds(150);
    }
    return (sum - mn - mx) / 62.0;
}

// LDR อยู่ด้านบน (ต่อ 3V3), R8 อยู่ด้านล่าง (ลง GND)
// V = Vcc * R8 / (R8 + R_LDR)  ->  R_LDR = R8 * (Vcc / V - 1)
float mvToOhm(float mv) {
    if (mv < 5) return INFINITY;          // มืดสนิท
    if (mv > VCC_MV - 5) return 0;        // สว่างจัดเกินช่วงวัด
    return R_FIXED * (VCC_MV / mv - 1.0);
}

float ohmToLux(float ohm) {
    if (isinf(ohm)) return 0;
    if (!(ohm > 0)) return NAN;
    float x = log10(ohm);
    return pow(10, LUX_C0 + LUX_C1 * x + LUX_C2 * x * x);
}

void readLight() {
    ldrMv  = readLdrMv();
    ldrOhm = mvToOhm(ldrMv);
    luxVal = ohmToLux(ldrOhm);
}

// =====================================
// [ใหม่] อ่านอุณหภูมิแบบไม่ค้าง loop
// สั่งวัด -> ไปทำอย่างอื่น -> ครบ 800 ms ค่อยกลับมาอ่าน
// =====================================
void tempTick() {
    static bool pending = false;
    static unsigned long t0 = 0;

    if (!pending) {
        ds.requestTemperatures();
        pending = true;
        t0 = millis();
        return;
    }
    if (millis() - t0 < 800) return;

    float t = ds.getTempCByIndex(0);
    pending = false;

    // -127 = ไม่เจอเซนเซอร์, 85 = ค่าเริ่มต้นตอนเพิ่งเปิดเครื่อง
    if (t == DEVICE_DISCONNECTED_C || t == 85.0) {
        tempRaw = tempC = NAN;
    } else {
        tempRaw = t;
        tempC = t + TEMP_OFFSET;
    }
}

// =====================================
// OLED STATUS DISPLAY   [แก้] เพิ่มค่าแสง/อุณหภูมิ
// =====================================
void showStatus() {

    display.clearDisplay();

    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

    display.setCursor(0, 0);
    display.println("LIGHT + TEMP");

    display.setCursor(0, 10);
    display.print("WiFi:");
    display.print(WiFi.status() == WL_CONNECTED ? "OK " : "-- ");
    display.print(" MQTT:");
    display.println(mqtt.connected() ? "OK" : "--");

    display.setTextSize(2);
    display.setCursor(0, 22);
    if (isnan(luxVal)) display.println("-- lx");
    else               display.printf("%.0f lx\n", luxVal);

    display.setCursor(0, 40);
    if (isnan(tempC)) display.println("-- C");
    else              display.printf("%.1f C\n", tempC);

    display.setTextSize(1);
    display.setCursor(0, 57);
    if (WiFi.status() == WL_CONNECTED) {
        display.print(WiFi.localIP());
    } else {
        display.print("Waiting WiFi...");
    }

    display.display();
}

// =====================================
// Connect WiFi
// =====================================
void connectWiFi() {

    WiFi.mode(WIFI_STA);
    WiFi.setTxPower(WIFI_POWER_15dBm);   // [ใหม่] ลดกำลังส่ง -> กระแสพุ่งน้อยลง กัน brownout
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

    configTime(0, 0, "pool.ntp.org", "time.google.com");   // [ใหม่] ซิงก์เวลาสำหรับ ts

    showStatus();
}

// =====================================
// Connect MQTT
// =====================================
void connectMQTT() {

    while (!mqtt.connected()) {

        Serial.print("Connecting MQTT...");

        showStatus();

        // [แก้] LWT ต้องชี้ไปที่ MQTT_STATUS ไม่ใช่ MQTT_TOPIC
        //       (เดิมถ้าบอร์ดหลุด broker จะเขียน "offline" ทับข้อมูลเซนเซอร์ใน topic หลัก)
        // [แก้] ใช้ clientId ที่ต่อท้ายเลขชิป กันชื่อซ้ำกับเครื่องอื่นแล้วเตะกันหลุด
        if (mqtt.connect(
            clientId,
            MQTT_STATUS,
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
// [ใหม่] ส่งข้อมูลขึ้น MQTT (QoS 0, retained)
// =====================================
void numOrNull(char* buf, size_t n, float v, int digits) {   // NAN -> null ใน JSON
    if (isnan(v) || isinf(v)) snprintf(buf, n, "null");
    else snprintf(buf, n, "%.*f", digits, v);
}

void publishData() {
    time_t now = time(nullptr);
    long ts = (now > 1700000000) ? (long)now : 0;   // 0 = ยังซิงก์ NTP ไม่ได้

    char sLux[16], sMv[12], sOhm[16], sT[12], sTr[12];
    numOrNull(sLux, sizeof sLux, luxVal, 1);
    numOrNull(sMv,  sizeof sMv,  ldrMv, 0);
    numOrNull(sOhm, sizeof sOhm, ldrOhm, 0);
    numOrNull(sT,   sizeof sT,   tempC, 2);
    numOrNull(sTr,  sizeof sTr,  tempRaw, 2);

    char payload[256];
    snprintf(payload, sizeof payload,
        "{\"device_id\":\"%s\",\"ts\":%ld,\"lux\":%s,\"light_mv\":%s,"
        "\"ldr_ohm\":%s,\"temp_c\":%s,\"temp_raw_c\":%s}",
        DEVICE_ID, ts, sLux, sMv, sOhm, sT, sTr);

    bool ok = mqtt.publish(MQTT_TOPIC, payload, true);   // retained
    Serial.print(ok ? "[PUB] " : "[PUB FAIL] ");
    Serial.println(payload);
}

// =====================================
// [ใหม่] เก็บจุด calibrate: กด SW2
// เฉลี่ย 5 วินาที แล้วพิมพ์บรรทัด CSV ออก Serial -> คัดลอกไปใส่ calibration.csv
// =====================================
void capturePoint() {
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("CALIBRATE...");
    display.println("hold still 5 s");
    display.display();

    float sum = 0;
    int n = 0;
    unsigned long t0 = millis();
    while (millis() - t0 < 5000) {
        sum += readLdrMv();
        n++;
        mqtt.loop();          // กัน MQTT หลุดระหว่างรอ
        delay(50);
    }
    float mv = sum / n;
    float ohm = mvToOhm(mv);
    calCount++;

    Serial.printf("CALPOINT,%d,%.1f,%.0f,%.2f\n", calCount, mv, ohm, tempRaw);
    Serial.println("  -> (จุด, mV, R_ohm, temp_raw)  ใส่ค่า lux จากแอปวัดแสงคู่กัน");

    display.clearDisplay();
    display.setCursor(0, 0);
    display.printf("CAL point #%d\n\n", calCount);
    display.printf("mV   %.1f\n", mv);
    display.printf("R    %.0f ohm\n", ohm);
    display.printf("Traw %.2f C\n", tempRaw);
    display.display();
    delay(2500);
}

bool sw2Pressed() {
    static bool prev = HIGH;
    static unsigned long lastPress = 0;
    bool now = digitalRead(PIN_SW2);
    bool ev = (prev == HIGH && now == LOW && millis() - lastPress > 250);
    if (ev) lastPress = millis();
    prev = now;
    return ev;
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

    // [ใหม่] เซนเซอร์
    pinMode(PIN_SW2, INPUT);                       // บนบอร์ดมี pull-up แล้ว
    analogSetPinAttenuation(PIN_LDR, ADC_11db);    // วัดได้ถึง ~3.1 V
    ds.begin();
    ds.setWaitForConversion(false);
    Serial.printf("DS18B20 found: %d\n", ds.getDeviceCount());
    readLight();                                   // อ่านครั้งแรกก่อนเปิด WiFi

    // [ใหม่] client ID ไม่ซ้ำใคร
    snprintf(clientId, sizeof clientId, "%s-%04X",
             MQTT_CLIENT_ID, (unsigned)(ESP.getEfuseMac() & 0xFFFF));

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

    // [ใหม่] อุณหภูมิ
    tempTick();

    // [ใหม่] ปุ่ม calibrate
    if (sw2Pressed()) capturePoint();

    // Update OLED   [แก้] อ่านแสงก่อนวาดจอ
    static unsigned long lastDisplay = 0;

    if (millis() - lastDisplay >= 500) {

        lastDisplay = millis();

        readLight();

        showStatus();
    }

    // [ใหม่] ส่งข้อมูลทุก PUBLISH_MS
    static unsigned long lastPublish = 0;

    if (millis() - lastPublish >= PUBLISH_MS) {

        lastPublish = millis();

        publishData();
    }
}