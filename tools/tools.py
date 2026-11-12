"""คำสั่งช่วยระหว่างทดสอบ

python tools.py new-lot   เริ่มล็อตใหม่ (ส่งคำสั่งให้ Service Layer)
python tools.py clear     ล้าง retained ทั้งหมดของทีม (moisture, lot, status) — ทำก่อนเริ่มซ้อมทุกครั้ง
python tools.py bad       ส่งข้อความผิดรูปแบบ 6 แบบ (ทดสอบว่า Service Layer ไม่ล้ม)
"""
import json
import sys
import time

import pathlib

# common.py / config.py อยู่ที่ services/mqtt/
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services" / "mqtt"))
import common  # noqa: E402

BAD = [
    (common.T_BEANS, b"not json at all"),
    (common.T_BEANS, json.dumps({"device_id": "pi-01", "ts": common.now(), "image_id": "bad1",
                                 "counts": {"Good": 40}, "total": 40, "defect_ratio": 0}).encode()),
    (common.T_BEANS, json.dumps({"device_id": "pi-01", "ts": common.now(), "image_id": "bad2",
                                 "counts": {c: 1 for c in common.CLASSES}, "total": 99, "defect_ratio": 0.857}).encode()),
    (common.T_BEANS, json.dumps({"device_id": "pi-01", "ts": common.now() * 1000, "image_id": "bad3",
                                 "counts": {c: 1 for c in common.CLASSES}, "total": 7, "defect_ratio": 0.857}).encode()),
    (common.T_MOISTURE, json.dumps({"device_id": "esp32-01", "ts": common.now(), "moisture_pct": 18.4 * 100}).encode()),
    (common.T_MOISTURE, json.dumps({"device_id": "esp32-01", "ts": common.now(), "moisture_pct": None}).encode()),
]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd not in ("new-lot", "clear", "bad"):
        print(__doc__)
        return
    c = common.make_client("tools-01")
    for _ in range(50):
        if c.is_connected():
            break
        time.sleep(0.1)
    if cmd == "new-lot":
        c.publish(common.T_CMD, json.dumps({"cmd": "new_lot"}), qos=1).wait_for_publish(5)
        print("ส่งคำสั่งเริ่มล็อตใหม่แล้ว")
    elif cmd == "clear":
        topics = [common.T_MOISTURE, common.T_LOT] + [common.topic("status", d) for d in
                  ("esp32-01", "pi-01", "service-01", "agent-01", "monitor-01")]
        for t in topics:
            c.publish(t, payload=None, qos=1, retain=True).wait_for_publish(5)
            print("ล้าง", t)
    elif cmd == "bad":
        for t, p in BAD:
            c.publish(t, p, qos=1).wait_for_publish(5)
            print("ส่งของผิด →", t, p[:70])
    c.disconnect()
    c.loop_stop()


if __name__ == "__main__":
    main()
