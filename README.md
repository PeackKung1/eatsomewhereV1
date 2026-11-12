# eatsomewhereV1

โปรเจกต์นี้ใช้โครงสร้างแบบ monorepo เพื่อรวมโค้ดของ ESP32, ระบบวิเคราะห์ภาพบน Raspberry Pi, AI Agent และ Service Layer ไว้ใน repository เดียว ทำให้แต่ละส่วนใช้ข้อตกลงข้อมูลร่วมกันและทดสอบการเชื่อมต่อได้สะดวก

```text
.
├── README.md
├── .gitignore
├── .env.example
├── docs/
│   ├── architecture.md
│   ├── mqtt-contract.md
│   ├── setup.md
│   └── decisions/
├── contracts/
│   ├── mqtt-topics.yaml
│   └── schemas/
│       ├── moisture.schema.json
│       ├── beans.schema.json
│       ├── lot.schema.json
│       └── status.schema.json
├── firmware/
│   └── esp32/
│       ├── README.md
│       ├── src/
│       └── platformio.ini
├── vision/
│   ├── README.md
│   ├── src/
│   ├── training/
│   ├── configs/
│   └── models/
├── agent/
│   ├── README.md
│   ├── src/
│   ├── requirements.txt
│   └── .env.example
├── services/
│   ├── mqtt/
│   │   ├── common.py
│   │   ├── config.py
│   │   └── service_layer.py
│   ├── market/
│   │   └── mock_market.py
│   └── dashboard/
├── tools/
│   ├── mock_esp32.py
│   ├── mock_pi.py
│   ├── monitor.py
│   └── tools.py
└── tests/
    ├── test_contracts.py
    └── test_service_layer.py
```

### หน้าที่ของแต่ละส่วน

| โฟลเดอร์ | หน้าที่ |
|---|---|
| `docs/` | เอกสารภาพรวมสถาปัตยกรรม วิธีติดตั้ง และบันทึกการตัดสินใจ |
| `contracts/` | ข้อตกลง MQTT topics และรูปแบบ JSON ที่ทุกส่วนของระบบใช้ร่วมกัน |
| `firmware/esp32/` | อ่านค่าความชื้นจากเซนเซอร์ แปลงเป็นเปอร์เซ็นต์ และส่งข้อมูลผ่าน MQTT |
| `vision/` | เตรียมข้อมูล ฝึกโมเดล และทำ inference เพื่อนับเมล็ดกาแฟบน Raspberry Pi |
| `agent/` | เรียก API ตลาด เลือกล็อต ผู้ซื้อ และราคา พร้อมตรวจสอบข้อเสนอก่อนส่ง |
| `services/mqtt/` | ตั้งค่า MQTT client, การเชื่อมต่อและ reconnect, LWT และ Service Layer |
| `services/market/` | ตลาดจำลองสำหรับการพัฒนาและซ้อมระบบ โดยข้อมูลไม่ใช่กติกาจริง |
| `services/dashboard/` | ส่วนแสดงสถานะและข้อมูลของระบบ |
| `tools/` | โปรแกรมจำลองอุปกรณ์ เครื่องมือตรวจข้อความ และคำสั่งช่วยซ้อม |
| `tests/` | ตรวจสอบรูปแบบข้อมูลและการทำงานร่วมกันของ service |

### แนวทางการพัฒนา

1. ตกลง MQTT topics และ JSON schema ใน `contracts/` ก่อนเริ่มเชื่อมระบบ
2. พัฒนาและทดสอบแต่ละส่วนแยกกัน โดยใช้ mock ใน `tools/` เมื่ออุปกรณ์จริงยังไม่พร้อม
3. เชื่อม ESP32 และ Raspberry Pi เข้ากับ MQTT แล้วตรวจสอบข้อมูลที่ Service Layer ได้รับ
4. เชื่อม Agent กับข้อมูลล็อตและ API ตลาด
5. ทดสอบการทำงานแบบ end-to-end ก่อนเตรียม demo

ตั้งค่า broker และค่าการเชื่อมต่อผ่านไฟล์ config เพื่อให้เปลี่ยนจาก broker สำหรับซ้อมไปเป็น broker ของผู้จัดได้จากจุดเดียว โดยรายละเอียด broker วันแข่งยังต้องรอข้อมูลจากผู้จัด

### การจัดการข้อมูลและความลับ

- ห้าม commit รหัสผ่าน, API token หรือไฟล์ `.env` จริง ให้เพิ่มไฟล์เหล่านี้ใน `.gitignore`
- เก็บเฉพาะตัวอย่างค่าที่ไม่มีความลับไว้ใน `.env.example`
- ตรวจสอบขนาดและเงื่อนไขการใช้ก่อนเพิ่มชุดภาพฝึกหรือ model weights ลง Git
- ข้อมูลตลาดจำลองใช้สำหรับซ้อมเท่านั้น ไม่ถือเป็นกติกาหรือสูตรคะแนนจริง