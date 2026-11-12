"""main.py — AI Agent: วน ดู → คิด → ทำ กับตลาด

ดู : ล็อตล่าสุดจาก MQTT (service/lot) + รายชื่อผู้ซื้อจากตลาด
คิด: tools.suggest() (กฎ) → llm.ask_llm() (LLM ปรับ) → validator.validate_offer() (ตรวจซ้ำทุกครั้ง)
ทำ : market_client.send_offer() แล้ว tools.adapt() ปรับราคารอบถัดไป

ใช้ (จากโฟลเดอร์ agent/):
  python src/main.py                     # 10 รอบ ใช้ LLM
  python src/main.py --rounds 20 --no-llm  # ใช้กฎอย่างเดียว (เทียบผล / LLM ล่ม)

ค่าตั้งอ่านจาก agent/.env (ดู .env.example) — ทุกการตัดสินใจบันทึกที่ agent/logs/decisions.jsonl
"""
import argparse
import json
import logging
import os
import pathlib
import sys
import threading
import time

AGENT_DIR = pathlib.Path(__file__).resolve().parents[1]
ROOT = AGENT_DIR.parent


def load_env(path):
    """อ่าน KEY=VALUE จาก .env (ไม่ทับค่าที่ export ไว้แล้ว) — ต้องทำก่อน import โมดูลที่อ่าน env"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


load_env(AGENT_DIR / ".env")
sys.path.insert(0, str(ROOT / "services" / "mqtt"))   # common.py / config.py

import common          # noqa: E402
import market_client   # noqa: E402
import tools           # noqa: E402
import validator       # noqa: E402

log = logging.getLogger("agent")
DEVICE_ID = "agent-01"
DECISION_LOG = pathlib.Path(os.getenv("AGENT_LOG", AGENT_DIR / "logs" / "decisions.jsonl"))
# ตัวเลือกที่ expected ต่ำกว่าอันดับ 1 ไม่เกินกี่ % ถึงนับว่า "สูสี" และให้ LLM ช่วยเลือก
LLM_CHOICE_GAP = float(os.getenv("LLM_CHOICE_GAP", "0.10"))


# ---------- ดู ----------
class LotWatcher:
    def __init__(self):
        self.lock = threading.Lock()
        self.lot = None

    def on_connected(self, c):
        c.subscribe(common.T_LOT, qos=1)

    def on_message(self, c, userdata, msg):
        if not msg.payload:
            return                      # retained ถูกล้าง
        try:
            lot = json.loads(msg.payload)
        except ValueError:
            log.warning("lot ไม่ใช่ JSON")
            return
        if not isinstance(lot, dict) or "lot_id" not in lot:
            log.warning("lot ไม่มี lot_id — ข้าม")
            return
        with self.lock:
            self.lot = lot

    def get(self):
        with self.lock:
            return dict(self.lot) if self.lot else None


def lot_ready(lot):
    return bool(lot) and lot.get("image_count", 0) > 0 and "moisture_pct" in lot and "defect_ratio" in lot


def wait_for(fn, wait, what):
    """เรียก fn() ซ้ำจนได้ค่าที่ไม่ใช่ None หรือหมดเวลา"""
    t0 = time.time()
    while time.time() - t0 <= wait:
        v = fn()
        if v is not None:
            return v
        time.sleep(1)
    log.error("รอ %s เกิน %ss", what, wait)
    return None


def fetch_buyers():
    try:
        return market_client.get_buyers()
    except market_client.MarketError as e:
        log.warning("%s (ลองใหม่)", e)
        return None


# ---------- คิด ----------
def decide(lot, buyers, price_book, history, ask_llm):
    """คืน (offer, notes) หรือ (None, เหตุผล) ถ้าไม่มีผู้ซื้อรายใดรับล็อตนี้
    price_book = tools.PriceBook() ที่ใช้ต่อเนื่องทุกรอบ"""
    cands = [b for b in buyers if validator.eligible(b, lot)]
    options = price_book.options(cands)
    if not options:
        return None, ["ล็อตไม่ผ่านเกณฑ์ผู้ซื้อรายใดเลย"]
    suggested = {"buyer_id": options[0]["buyer_id"], "price_per_kg": options[0]["rule_price"]}
    # ส่งให้ LLM เฉพาะตัวเลือกที่สูสีกับอันดับ 1 — ถ้าคำตอบชัดอยู่แล้ว ไม่ต้องถาม (เร็วกว่า และ LLM ทำพังไม่ได้)
    close = [o for o in options if o["expected"] >= options[0]["expected"] * (1 - LLM_CHOICE_GAP)]
    if len(close) < 2 and ask_llm is not rules_only:
        choice = {**suggested, "reason": "ตัวเลือกชัดเจน ไม่ต้องถาม LLM", "source": "rules"}
    else:
        choice = ask_llm({"lot": lot, "options": close, "suggested": suggested, "history": history})
    return validator.validate_offer(choice, lot, cands, suggested, close)


def rules_only(situation):
    return {**situation["suggested"], "source": "rules"}


def record(entry):
    try:
        DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DECISION_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        log.warning("เขียน log ไม่ได้: %s", e)


# ---------- ทำ ----------
def run(watcher, rounds, interval, wait, ask_llm):
    lot = wait_for(lambda: watcher.get() if lot_ready(watcher.get()) else None, wait, "ข้อมูลล็อตครบ (ความชื้น + ผลนับเมล็ด)")
    if lot is None:
        log.error("เช็กว่า service_layer / ESP32 / Pi รันอยู่ และ TEAM ตรงกัน")
        return
    buyers = wait_for(fetch_buyers, wait, "รายชื่อผู้ซื้อจากตลาด")
    if buyers is None:
        return

    price_book, history = tools.PriceBook(), []
    for i in range(1, rounds + 1):
        lot = watcher.get()
        if not lot_ready(lot):
            log.warning("รอบ %d: ล็อตยังไม่ครบ (เพิ่งเริ่มล็อตใหม่?) — ข้าม", i)
            time.sleep(interval)
            continue

        offer, notes = decide(lot, buyers, price_book, history, ask_llm)
        if offer is None:
            log.warning("รอบ %d: %s (lot=%s defect=%.3f moist=%s)", i, notes[0],
                        lot["lot_id"], lot["defect_ratio"], lot.get("moisture_pct"))
            time.sleep(interval)
            continue
        for n in notes:
            log.warning("รอบ %d: แก้ข้อเสนอ — %s", i, n)

        try:
            res = market_client.send_offer(lot, offer)
        except market_client.MarketError as e:
            log.error("รอบ %d: %s (จะลองรอบถัดไป)", i, e)
            time.sleep(interval)
            continue

        buyer = next(b for b in buyers if b["buyer_id"] == offer["buyer_id"])
        price_book.update(buyer, offer["price_per_kg"], res["accepted"], res["reason"])
        history.append({"lot_id": offer["lot_id"], "buyer_id": offer["buyer_id"],
                        "price_per_kg": offer["price_per_kg"], "accepted": res["accepted"], "reason": res["reason"]})
        record({"ts": common.now(), "round": i, "lot": {k: lot.get(k) for k in ("lot_id", "moisture_pct", "defect_ratio")},
                **offer, "notes": notes, "accepted": res["accepted"], "result": res["reason"]})
        log.info("รอบ %d: %s → %s @ %.2f บาท/กก. [%s] : %s", i, offer["lot_id"], offer["buyer_id"],
                 offer["price_per_kg"], offer["source"], res["reason"])
        time.sleep(interval)

    try:
        r = market_client.get_results()
        log.info("จบ %d รอบ รายได้รวม (ตลาด) %.2f บาท", r["rounds"], r["revenue_total"])
    except (market_client.MarketError, KeyError, TypeError) as e:
        log.warning("ดึงผลรวมไม่ได้: %s", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--interval", type=float, default=3)
    ap.add_argument("--wait", type=float, default=60, help="รอข้อมูลล็อต/ตลาดสูงสุดกี่วินาที")
    ap.add_argument("--no-llm", action="store_true", help="ใช้กฎในโค้ดอย่างเดียว")
    a = ap.parse_args()

    if a.no_llm:
        ask = rules_only
    else:
        from llm import ask_llm as ask   # import ที่นี่: --no-llm ไม่ต้องมี openai ก็รันได้

    watcher = LotWatcher()
    client = common.make_client(DEVICE_ID, on_connected=watcher.on_connected, on_message=watcher.on_message)
    try:
        run(watcher, a.rounds, a.interval, a.wait, ask)
    except KeyboardInterrupt:
        pass
    common.close(client, DEVICE_ID)


if __name__ == "__main__":
    main()
