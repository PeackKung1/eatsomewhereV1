"""ตลาดจำลอง (Track 3) สำหรับซ้อม agent loop เท่านั้น

*** ตัวเลข ราคา ผู้ซื้อ และกติกาทั้งหมดในไฟล์นี้ "แต่งขึ้น" ไม่ใช่กติกาจริงของผู้จัด ***
กติกา API และสูตรคะแนนจริงจะแจกวันอบรม 17 พ.ย. — ใช้ไฟล์นี้แค่ฝึกโครง ดู → คิด → ทำ

API (ใช้ได้แค่ไลบรารีมาตรฐาน Python ไม่ต้องติดตั้งอะไร):
  GET  /buyers   รายชื่อผู้ซื้อ + เงื่อนไขที่เปิดเผย + ราคาอ้างอิง
  POST /offer    {"lot_id","buyer_id","price_per_kg","qty_kg","quality":{"moisture_pct","defect_ratio"}}
                 → {"round","accepted","reason"}   (ปิดซอง: ไม่บอกราคาสูงสุดของผู้ซื้อ)
  GET  /results  ประวัติทุกข้อเสนอ + รายได้รวม

ใช้: python mock_market.py [--port 8000] [--seed 1]
"""
import argparse
import json
import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ผู้ซื้อสมมติ (บาท/กก. แต่งขึ้น)
BUYERS = [
    {"buyer_id": "B1", "name": "โรงคั่วพรีเมียม (สมมติ)", "ref_price": 160, "max_defect": 0.12, "moisture_range": [10.0, 12.5]},
    {"buyer_id": "B2", "name": "โรงคั่วทั่วไป (สมมติ)", "ref_price": 130, "max_defect": 0.30, "moisture_range": [9.0, 13.5]},
    {"buyer_id": "B3", "name": "โรงงานกาแฟสำเร็จรูป (สมมติ)", "ref_price": 90, "max_defect": 1.00, "moisture_range": [0.0, 100.0]},
]


class Market:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.lock = threading.Lock()
        self.round = 0
        self.history = []

    def hidden_max(self, buyer, q):
        """ราคาสูงสุดที่ผู้ซื้อยอมจ่าย (ซ่อนจากผู้ขาย) ขึ้นกับคุณภาพ + สุ่ม"""
        dr = q.get("defect_ratio", 1.0)
        m = q.get("moisture_pct")
        lo, hi = buyer["moisture_range"]
        if dr > buyer["max_defect"]:
            return 0, "เมล็ดเสียเกินเกณฑ์ผู้ซื้อ"
        if m is None or not lo <= m <= hi:
            return 0, "ความชื้นไม่อยู่ในช่วงที่ผู้ซื้อรับ"
        factor = max(0.4, 1 - 1.2 * dr - 0.04 * abs(m - 11.5))
        return buyer["ref_price"] * factor * self.rng.uniform(0.9, 1.1), "ok"

    def offer(self, o):
        buyer = next((b for b in BUYERS if b["buyer_id"] == o.get("buyer_id")), None)
        if buyer is None:
            raise ValueError("buyer_id ไม่มีอยู่")
        price = float(o["price_per_kg"])
        qty = float(o.get("qty_kg", 100))
        with self.lock:
            self.round += 1
            mx, why = self.hidden_max(buyer, o.get("quality", {}))
            accepted = mx > 0 and price <= mx
            reason = "ขายได้" if accepted else (why if mx == 0 else "ราคาสูงเกินไป")
            rec = {"round": self.round, "lot_id": o.get("lot_id"), "buyer_id": buyer["buyer_id"],
                   "price_per_kg": price, "qty_kg": qty, "accepted": accepted, "reason": reason,
                   "revenue": round(price * qty, 2) if accepted else 0}
            self.history.append(rec)
            return {"round": self.round, "accepted": accepted, "reason": reason}

    def results(self):
        with self.lock:
            return {"rounds": self.round, "revenue_total": round(sum(r["revenue"] for r in self.history), 2),
                    "history": list(self.history)}


def make_handler(market):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/buyers":
                self._send(200, {"buyers": BUYERS})
            elif self.path == "/results":
                self._send(200, market.results())
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/offer":
                return self._send(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length", 0))
                res = market.offer(json.loads(self.rfile.read(n)))
                print(f"รอบ {res['round']}: {res}")
                self._send(200, res)
            except (ValueError, KeyError, TypeError) as e:
                self._send(400, {"error": str(e)})

        def log_message(self, *args):
            pass
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), make_handler(Market(a.seed)))
    print(f"ตลาดจำลองรันที่ http://127.0.0.1:{a.port}  (Ctrl+C หยุด)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
