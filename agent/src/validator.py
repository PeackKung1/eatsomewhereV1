"""validator.py — กฎตรวจสอบที่ "ห้ามพลาด" (โค้ดล้วน ไม่ใช้ LLM)

- eligible()       ล็อตนี้ผ่านเกณฑ์ผู้ซื้อรายนี้ไหม
- price_bounds()   ช่วงราคาที่ยอมให้เสนอกับผู้ซื้อรายนี้
- validate_offer() ตรวจ/แก้ข้อเสนอที่ LLM ตอบมา ก่อนส่งเข้าตลาดทุกครั้ง
"""
import math
import os

FLOOR_RATIO = 0.55   # ราคาต่ำสุด = ref_price × 0.55 (ห้ามขายต่ำกว่านี้ไม่ว่า LLM จะตอบอะไร)
CEIL_RATIO = 1.3     # ราคาสูงสุด = ref_price × 1.3 (กันเสนอสูงจนเสียรอบเปล่า)
# LLM ปรับราคาได้ไม่เกิน ±2% จาก rule_price ของผู้ซื้อรายนั้น (0 = ใช้ราคาจากกฎเป๊ะ)
LLM_PRICE_BAND = float(os.getenv("LLM_PRICE_BAND", "0.02"))


def eligible(buyer, lot):
    lo, hi = buyer["moisture_range"]
    m = lot.get("moisture_pct")
    dr = lot.get("defect_ratio")
    return dr is not None and dr <= buyer["max_defect"] and m is not None and lo <= m <= hi


def price_bounds(buyer):
    return round(buyer["ref_price"] * FLOOR_RATIO, 2), round(buyer["ref_price"] * CEIL_RATIO, 2)


def validate_offer(choice, lot, candidates, suggested, options=None):
    """คืน (offer, notes)
    offer = {"lot_id","buyer_id","price_per_kg","reason","source"} ที่ปลอดภัยพร้อมส่ง
    notes = รายการสิ่งที่ถูกแก้ (ว่าง = LLM ตอบถูกทุกอย่าง)
    options = ตัวเลือกจาก PriceBook.options() — ถ้าให้มา ผู้ซื้อต้องอยู่ในนั้น และราคาต้องอยู่ใน ±LLM_PRICE_BAND ของ rule_price"""
    notes = []
    by_id = {b["buyer_id"]: b for b in candidates}
    rule_price = {o["buyer_id"]: o["rule_price"] for o in options} if options is not None else None
    allowed = set(rule_price) if rule_price is not None else set(by_id)

    buyer = by_id.get(choice.get("buyer_id")) if choice.get("buyer_id") in allowed else None
    if buyer is None:
        notes.append(f"buyer_id {choice.get('buyer_id')!r} ไม่อยู่ในตัวเลือก → ใช้ {suggested['buyer_id']}")
        buyer = by_id[suggested["buyer_id"]]
        if rule_price is not None:
            choice = {**choice, "price_per_kg": rule_price[buyer["buyer_id"]]}

    try:
        price = float(choice.get("price_per_kg"))
        if not math.isfinite(price):
            raise ValueError
    except (TypeError, ValueError):
        notes.append("ราคาไม่ใช่ตัวเลข → ใช้ราคาจากกฎ")
        price = float(suggested["price_per_kg"])

    lo, hi = price_bounds(buyer)
    if rule_price is not None:
        rp = rule_price[buyer["buyer_id"]]
        lo = max(lo, round(rp * (1 - LLM_PRICE_BAND), 2))
        hi = min(hi, round(rp * (1 + LLM_PRICE_BAND), 2))
    if price < lo:
        notes.append(f"ราคา {price:.2f} ต่ำกว่าช่วงที่อนุญาต → {lo}")
        price = lo
    elif price > hi:
        notes.append(f"ราคา {price:.2f} สูงกว่าช่วงที่อนุญาต → {hi}")
        price = hi

    offer = {
        "lot_id": lot["lot_id"],   # ใช้ล็อตปัจจุบันเสมอ ไม่เชื่อ lot_id จาก LLM
        "buyer_id": buyer["buyer_id"],
        "price_per_kg": round(price, 2),
        "reason": str(choice.get("reason", ""))[:200],
        "source": choice.get("source", "unknown"),
    }
    return offer, notes
