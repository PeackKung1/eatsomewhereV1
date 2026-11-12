# Agent

เรียก API ตลาด เลือกล็อต ผู้ซื้อ และราคา พร้อมตรวจสอบข้อเสนอก่อนส่ง
วน **ดู → คิด → ทำ**: ล็อตจาก MQTT (`service/lot`) + ผู้ซื้อจากตลาด → กฎ + LLM → ตรวจซ้ำ → ส่งข้อเสนอ

| ไฟล์ | หน้าที่ |
|---|---|
| `src/main.py` | จุดเริ่ม: รับล็อตจาก MQTT, วนรอบ, บันทึก log |
| `src/market_client.py` | คุยกับ API ตลาด (API จริง 17 พ.ย. แก้ไฟล์นี้ที่เดียว) |
| `src/tools.py` | กฎราคา `PriceBook`: เลือกผู้ซื้อราคาสูงสุด, ลด 7% เมื่อโดนปฏิเสธ, ขึ้น 5% (ไม่เกินครึ่งทางไปราคาที่โดนปฏิเสธ) เมื่อขายได้ |
| `src/prompts.py` | system prompt + ข้อมูลที่ส่งให้ LLM (แก้กลยุทธ์ที่นี่) |
| `src/llm.py` | เรียก LLM, แปลง JSON, ล่ม/ตอบผิด → ใช้ค่าจากกฎ |
| `src/validator.py` | ตรวจข้อเสนอทุกครั้ง: ผู้ซื้อผ่านเกณฑ์, ราคา floor/ceiling, LLM แก้ราคาได้ ±2%, lot_id |
| `src/evaluate.py` | เทียบกฎ vs กฎ + LLM บนตลาดจำลองแบบ offline |

## ใช้งาน

```bash
cd agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # แก้ค่า (ห้าม commit .env)
python src/main.py            # ใช้ LLM
python src/main.py --no-llm   # ใช้กฎอย่างเดียว (เทียบผล / LLM ล่ม)
python src/llm.py             # ทดสอบ LLM อย่างเดียว ไม่ต้องมี MQTT/ตลาด
python src/evaluate.py        # เทียบรายได้ rules vs llm (ไม่ต้องมี MQTT/ตลาด)
```

## LLM ทำหน้าที่อะไร

กฎในโค้ดเป็นตัวตัดสินใจหลัก LLM ถูกถามเฉพาะเมื่อมีผู้ซื้อที่ "สูสี" กัน (`LLM_CHOICE_GAP`)
และแก้ราคาได้ไม่เกิน ±`LLM_PRICE_BAND` จากราคาที่กฎคำนวณ — LLM ทำพังได้จำกัด

ผลวัดล่าสุด (ตลาดจำลอง 3 ล็อต × 3 seed × 10 รอบ, `qwen3.5:2b`):

| โหมด | รายได้รวม | ขายได้ |
|---|---|---|
| กฎอย่างเดียว | 365,485 | 31/90 |
| กฎ + LLM | 268,024–295,300 | 23–25/90 |

**ตอนนี้ให้รันด้วย `--no-llm`** — โมเดล 2B ทำให้รายได้ลดลงทุกการตั้งค่าที่ลอง
เมื่อได้ LLM ของผู้จัด (18 พ.ย.) ให้รัน `evaluate.py` ใหม่ ถ้า llm ชนะ rules ค่อยเปิดใช้

ต้องรัน broker, `services/mqtt/service_layer.py`, `services/market/mock_market.py` และ ESP32/Pi (หรือ `tools/mock_*.py`) ก่อน — ดูขั้นตอนเต็มที่ `docs/e2e-rehearsal.md`

ทุกการตัดสินใจบันทึกที่ `agent/logs/decisions.jsonl` (ไม่ commit)

Test: `python -m pytest tests` จาก root ของ repo
