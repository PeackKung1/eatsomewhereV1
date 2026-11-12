# ชุดซ้อม End-to-End รอบแรก — TESA Top Gun #20

> ย้ายมาจากชุดซ้อม tesa-e2e — path ปรับตามโครง repo แล้ว (รันทุกคำสั่งจาก root ของ repo)

เป้าหมายรอบนี้: **หาจุดที่ต่อกันไม่ติด** ไม่ใช่ทำให้ทุกอย่างแม่น
เส้นทางข้อมูล: `ESP32 + Pi → Broker → Service Layer → Agent → ตลาด` และ `Broker → Monitor`

## ไฟล์ในชุด

| ไฟล์ | ทำอะไร | ใครรัน |
|---|---|---|
| `config.py` | host/port/รหัส/ชื่อทีม — **แก้ที่นี่ที่เดียว** | ทุกคน |
| `common.py` | ชื่อ topic, การเชื่อมต่อ (LWT + reconnect), ตรวจ schema | (ไลบรารี) |
| `mock_esp32.py` | จำลอง ESP32 ส่งความชื้น | Integration |
| `mock_pi.py` | จำลอง Pi ส่งผลนับเมล็ด | Integration |
| `service_layer.py` | รวมข้อมูลเป็นล็อต → `service/lot` | Integration |
| `mock_market.py` | ตลาดจำลอง (ตัวเลขแต่งขึ้น ไม่ใช่กติกาจริง) | LLM/Agent |
| `agent/src/` | Agent วน ดู → คิด → ทำ (ดู agent/README.md) | LLM/Agent |
| `monitor.py` | Dashboard แบบ terminal + เตือนข้อความผิด schema | PM / ใครก็ได้ |
| `tools.py` | `new-lot` / `clear` / `bad` | Integration |

ใช้แค่ `paho-mqtt` ตัวเดียว ที่เหลือเป็นไลบรารีมาตรฐาน Python

## เตรียมเครื่อง (ทำก่อนวันซ้อม)

```bash
cd eatsomewhereV1
python3 -m venv .venv && source .venv/bin/activate
pip install -r agent/requirements.txt
```

แก้ `TEAM` ใน `config.py` เป็นชื่อทีมที่ตกลงกัน (ทุกเครื่องต้องตรงกัน) หรือใช้ env: `export TESA_TEAM=ชื่อทีม`

ทุกเครื่อง (ESP32, Pi) ต้องใช้ prefix เดียวกัน: `tesa/<TEAM>/...` และ client ID ขึ้นต้นด้วย `<TEAM>-`

## เปิด terminal 6 หน้าต่าง (เครื่อง Integration)

| # | คำสั่ง | ดูอะไร |
|---|---|---|
| 1 | `python tools/monitor.py` | เปิดค้างตลอด ดูทุกอย่าง |
| 2 | `python services/mqtt/service_layer.py` | log การรวมล็อต |
| 3 | `python tools/mock_esp32.py` | (ปิดเมื่อใช้ ESP32 จริง) |
| 4 | `python tools/mock_pi.py` | (ปิดเมื่อใช้ Pi จริง) |
| 5 | `python services/market/mock_market.py` | log ข้อเสนอ |
| 6 | `python agent/src/main.py` | log การตั้งราคา |

**ก่อนเริ่มทุกขั้น:** `python tools/tools.py clear` (ล้าง retained ค้าง)

---

## ขั้นที่ 1 — ทุกส่วนเป็น mock (~20 นาที)

รัน 1 → 2 → 3 → 4 → 5 แล้วรอ 10 วินาที ค่อยรัน 6

ผ่านเมื่อ:
- [ ] Monitor เห็น `esp32-01`, `pi-01`, `service-01` เป็น online
- [ ] Monitor แสดงล็อต L1 มีความชื้น, จำนวนภาพเพิ่มขึ้นเรื่อย ๆ
- [ ] ช่อง "ข้อความผิด schema" ว่าง
- [ ] Agent วนครบ 10 รอบ มีขายได้อย่างน้อย 1 รอบ
- [ ] `python tools/tools.py new-lot` → Monitor เปลี่ยนเป็น L2 และนับใหม่จาก 0

## ขั้นที่ 2 — เปลี่ยนเป็น ESP32 จริง (~30 นาที)

ปิด terminal 3 (Ctrl+C) แล้วเสียบ ESP32 จริง ส่งไปที่ `tesa/<TEAM>/esp32/moisture`

ผ่านเมื่อ:
- [ ] Monitor ไม่มีเตือน schema จาก moisture
- [ ] "อายุ" ของค่าความชื้นใน Monitor ไม่เกิน 2–3 เท่าของรอบส่ง (ถ้าหลักล้านวินาที = ESP32 ยังไม่ได้ตั้ง NTP)
- [ ] `moisture_samples` ในล็อตเพิ่มขึ้น
- [ ] `esp32-01` แสดง online (ESP32 ต้องตั้ง LWT + ส่ง online เอง)

## ขั้นที่ 3 — เปลี่ยนเป็น Pi จริง (~30 นาที)

ปิด terminal 4 แล้วให้ Pi ถ่ายภาพ รันโมเดล และส่งไปที่ `tesa/<TEAM>/pi/beans`

ผ่านเมื่อ:
- [ ] ไม่มีเตือน schema จาก beans (ชื่อคลาสตัวเล็กครบ 7, total ตรง, defect_ratio ตรง)
- [ ] 1 ภาพ = 1 ข้อความ, `image_count` เพิ่มทีละ 1
- [ ] จดเวลาจากกดถ่ายจนล็อตอัปเดตใน Monitor: ____ วินาที

## ขั้นที่ 4 — ของจริงทั้งหมด (~30 นาที)

ซ้อมเหมือนวันแข่ง: `tools/tools.py clear` → `tools/tools.py new-lot` → ใส่เมล็ดชุดที่ 1 → วัดความชื้น + ถ่ายภาพ 3 ภาพ → รัน `agent/src/main.py` → ล็อตใหม่ → ทำซ้ำ 3 ล็อต

ผ่านเมื่อ:
- [ ] 3 ล็อตไม่ปนกัน (ค่าแต่ละล็อตเริ่มจาก 0)
- [ ] Agent ได้ค่าความชื้น + defect ของล็อตปัจจุบันจริง
- [ ] จดเวลาต่อล็อตตั้งแต่ใส่เมล็ดถึง Agent เสนอราคาครั้งแรก: ____ นาที

## ขั้นที่ 5 — ทดสอบกรณีพัง (~20 นาที)

| ทดสอบ | วิธี | ผ่านเมื่อ |
|---|---|---|
| ไฟดับ | ถอดปลั๊ก ESP32 | ภายใน ~45 วิ Monitor แสดง `esp32-01=offline` |
| เน็ตหลุด | ปิด Wi-Fi โน้ตบุ๊ก 30 วิ แล้วเปิด | ทุกโปรแกรมต่อใหม่เอง ไม่ต้องรันใหม่ |
| ข้อความผิด | `python tools/tools.py bad` | Service ทิ้ง 6 ข้อความ ไม่ล้ม ล็อตไม่เปลี่ยน |
| ค่าค้าง | ปิด Service → รอ ESP32 ส่ง 1 ค่า → เปิดใหม่ | log "ข้าม moisture แบบ retained" และล็อตไม่นับค่านั้น |
| ตลาดล่ม | ปิด `mock_market.py` ระหว่าง agent รัน | Agent log error แล้ววนต่อ ไม่ crash |
| client ID ซ้ำ | รัน `mock_pi.py` 2 หน้าต่างพร้อมกัน | สังเกตว่าหลุดสลับกัน → นี่คือเหตุผลที่ห้ามซ้ำ |

---

## บันทึกผล (PM จด)

| ขั้น | ผ่าน? | ปัญหาที่เจอ | ใครแก้ | แก้แล้ว? |
|---|---|---|---|---|
| 1 mock ทั้งหมด | | | | |
| 2 ESP32 จริง | | | | |
| 3 Pi จริง | | | | |
| 4 ของจริงทั้งหมด | | | | |
| 5 กรณีพัง | | | | |

## ปัญหาที่เจอบ่อย

| อาการ | สาเหตุที่น่าจะเป็น |
|---|---|
| Monitor ไม่เห็นอะไรเลย | `TEAM` ไม่ตรงกัน หรือ host ผิด |
| อุปกรณ์หลุด/ต่อสลับไปมา | client ID ซ้ำ (บน public broker อาจซ้ำกับคนอื่นถ้าชื่อทีมไม่เฉพาะพอ) |
| เตือน `ts ดูเป็นมิลลิวินาที` | ใช้ `millis()` หรือ `time.time()*1000` ต้องเป็นวินาที |
| เตือน `counts ขาดคลาส` | ชื่อคลาสตัวพิมพ์ใหญ่ หรือไม่ได้ส่งคลาสที่เป็น 0 |
| ล็อตมีค่าแปลกตั้งแต่เริ่ม | ลืม `tools/tools.py clear` |
| Agent บอกไม่มีข้อมูลล็อตครบ | ล็อตยังไม่มีทั้งความชื้นและภาพ หรือ Service ไม่ได้รัน |
| broker.hivemq.com ต่อไม่ได้ | public broker ล่มชั่วคราว → ใช้ Mosquitto ในเครื่อง: `export MQTT_HOST=<IP โน้ตบุ๊ก>` ทุกเครื่อง |

## หมายเหตุ

- `mock_market.py` ตัวเลข ผู้ซื้อ และกติกาแต่งขึ้นทั้งหมด ใช้ซ้อมโครง agent เท่านั้น API จริงได้วันที่ 17 พ.ย.
- LLM อยู่ที่ `agent/src/llm.py` — วันอบรมเปลี่ยน `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` ใน `agent/.env` เป็นของผู้จัด
- วันแข่งเปลี่ยน broker: แก้ `config.py` หรือ `export MQTT_HOST=... MQTT_PORT=... MQTT_USER=... MQTT_PASS=... MQTT_TLS=1`
