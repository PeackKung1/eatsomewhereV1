"""evaluate.py — เทียบ "กฎอย่างเดียว" กับ "กฎ + LLM" บนตลาดจำลองแบบ offline (ไม่ต้องมี MQTT / ไม่ต้องเปิด mock_market)

ใช้ (จากโฟลเดอร์ agent/):
  python src/evaluate.py                    # 3 ล็อต × 3 seed × 10 รอบ ทั้งสองโหมด
  python src/evaluate.py --seeds 20 --no-llm  # วัดเฉพาะกฎ (เร็ว ใช้ตอนจูน UP/DOWN)

ใช้ตอนเปลี่ยน LLM (เช่น LLM ของผู้จัดวันที่ 18) หรือแก้ prompt / กฎ: ถ้า llm ได้น้อยกว่า rules → รันจริงด้วย --no-llm
*** ตลาดจำลองแต่งขึ้น ผลที่นี่ใช้เทียบกันเองเท่านั้น ไม่ใช่คะแนนจริง ***
"""
import argparse
import logging
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "market"))

import main                         # noqa: E402  (โหลด .env + path ของ services/mqtt)
import tools                        # noqa: E402
from mock_market import BUYERS, Market   # noqa: E402

LOTS = [
    {"lot_id": "L1", "moisture_pct": 11.6, "defect_ratio": 0.169, "image_count": 2},   # กลาง ๆ
    {"lot_id": "L2", "moisture_pct": 11.2, "defect_ratio": 0.08, "image_count": 2},    # ดี
    {"lot_id": "L3", "moisture_pct": 12.8, "defect_ratio": 0.25, "image_count": 2},    # แย่
]


def play(ask, lot, seed, rounds):
    market, book, history = Market(seed), tools.PriceBook(), []
    for _ in range(rounds):
        offer, _ = main.decide(lot, BUYERS, book, history, ask)
        if offer is None:
            break
        res = market.offer({**offer, "qty_kg": 100,
                            "quality": {k: lot[k] for k in ("moisture_pct", "defect_ratio")}})
        buyer = next(b for b in BUYERS if b["buyer_id"] == offer["buyer_id"])
        book.update(buyer, offer["price_per_kg"], res["accepted"], res["reason"])
        history.append({"buyer_id": offer["buyer_id"], "price_per_kg": offer["price_per_kg"],
                        "accepted": res["accepted"], "reason": res["reason"]})
    r = market.results()
    return r["revenue_total"], sum(h["accepted"] for h in r["history"])


def main_():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    logging.getLogger().setLevel(logging.ERROR)   # ปิด log รายรอบ

    modes = [("rules", main.rules_only)]
    if not a.no_llm:
        from llm import ask_llm
        modes.append(("llm", ask_llm))

    runs = len(LOTS) * a.seeds
    for name, ask in modes:
        t0, rev, sales = time.time(), 0, 0
        for lot in LOTS:
            for seed in range(1, a.seeds + 1):
                r, s = play(ask, lot, seed, a.rounds)
                rev += r
                sales += s
        print(f"{name:6s} รายได้รวม {rev:>11,.0f}  เฉลี่ย/ชุด {rev / runs:>9,.0f}  "
              f"ขายได้ {sales}/{runs * a.rounds} รอบ  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main_()
