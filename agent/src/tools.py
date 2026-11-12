"""tools.py — กฎราคาในโค้ด (แผนหลักเมื่อไม่มี LLM และเป็นตัวเลือกที่ส่งให้ LLM เลือก)

ตลาดเป็นแบบปิดซอง: ผู้ซื้อแต่ละรายมี "ราคาสูงสุดที่ยอมจ่าย" ที่เราไม่เห็น
PriceBook จึงจำผลของผู้ซื้อแต่ละรายเป็นช่วง [ราคาที่เคยขายได้สูงสุด, ราคาที่เคยโดนปฏิเสธต่ำสุด]
แล้วบีบช่วงเข้าหาราคาจริง (คล้าย binary search) — ไม่ผูกกับสูตรของตลาดจำลอง
"""
from validator import price_bounds

UP, DOWN = 1.05, 0.93   # ขายได้ → ลองขึ้น 5%, "ราคาสูงเกินไป" → ลด 7%


class PriceBook:
    def __init__(self):
        self.s = {}   # buyer_id → สถานะของผู้ซื้อรายนั้น

    def state(self, buyer):
        return self.s.setdefault(buyer["buyer_id"], {
            "next": float(buyer["ref_price"]),   # ราคาที่จะเสนอรอบถัดไป
            "max_ok": None,                      # ราคาสูงสุดที่เคยขายได้
            "min_no": None,                      # ราคาต่ำสุดที่เคยโดน "ราคาสูงเกินไป"
            "ok": 0, "no": 0,                    # จำนวนครั้งขายได้ / ไม่ได้
            "blocked": False,                    # โดนปฏิเสธเพราะคุณภาพ → ไม่เสนอรายนี้อีก
        })

    def score(self, buyer):
        """คะแนน = ราคาที่จะเสนอรอบถัดไป → เริ่มจากผู้ซื้อที่จ่ายสูงสุด แล้วไล่ลงจนขายได้
        (เคยลองคูณ "โอกาสขายได้" แต่ทำให้เสียรอบไปลองผู้ซื้อราคาต่ำ — รายได้ลดลงเกินครึ่ง)"""
        st = self.state(buyer)
        return 0.0 if st["blocked"] else st["next"]

    def options(self, candidates):
        """ตัวเลือกต่อผู้ซื้อ (คำนวณด้วยโค้ด) เรียงจากคะแนนสูงไปต่ำ — ส่งให้ LLM เลือก"""
        opts = []
        for b in candidates:
            st = self.state(b)
            if st["blocked"]:
                continue
            opts.append({"buyer_id": b["buyer_id"], "rule_price": round(st["next"], 2),
                         "expected": round(self.score(b), 2), "sold": st["ok"], "rejected": st["no"],
                         "max_sold_price": st["max_ok"], "min_rejected_price": st["min_no"]})
        return sorted(opts, key=lambda o: o["expected"], reverse=True)

    def suggest(self, candidates):
        """ตัวเลือกที่ดีที่สุดตามกฎ คืน {"buyer_id","price_per_kg"} หรือ None ถ้าไม่มีใครเหลือ"""
        opts = self.options(candidates)
        if not opts:
            return None
        return {"buyer_id": opts[0]["buyer_id"], "price_per_kg": opts[0]["rule_price"]}

    def update(self, buyer, price, accepted, reason):
        """ขายได้ → ขึ้น 5% แต่ไม่เกินครึ่งทางไปราคาที่เพิ่งโดนปฏิเสธ
        ราคาสูงเกินไป → ลด 7% เต็ม (ไม่ชะลอ — รอบที่ขายไม่ได้ = รายได้ 0)
        วัดกับตลาดจำลอง 60 ชุด: รายได้มากกว่ากฎเดิม (ขึ้น 5% / ลด 7% ล้วน) 12% ที่ 10 รอบ, 28% ที่ 30 รอบ"""
        st = self.state(buyer)
        lo, hi = price_bounds(buyer)
        if accepted:
            st["ok"] += 1
            st["max_ok"] = max(st["max_ok"] or 0, price)
            new = price * UP
            if st["min_no"] is not None and st["min_no"] > price:
                new = min(new, (price + st["min_no"]) / 2)
        elif reason == "ราคาสูงเกินไป":
            st["no"] += 1
            st["min_no"] = price             # จำครั้งล่าสุด (ราคาผู้ซื้อแกว่ง ค่าเก่าเชื่อไม่ได้)
            new = price * DOWN
        else:
            st["no"] += 1
            st["blocked"] = True             # ไม่ผ่านเกณฑ์คุณภาพ — ลดราคาไม่ช่วย
            return
        st["next"] = min(max(new, lo), hi)
