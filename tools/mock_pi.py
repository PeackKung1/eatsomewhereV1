"""จำลอง Raspberry Pi: ส่งผลนับเมล็ด 7 คลาส 1 ข้อความต่อ 1 ภาพ (QoS 1, ไม่ retain)

ใช้: python mock_pi.py [--interval 5] [--defect 0.18] [--images 0] [--device pi-01]
     --images 0 = ส่งไปเรื่อย ๆ, ใส่ตัวเลข = ส่งครบแล้วหยุด
"""
import argparse
import json
import random
import time

import pathlib
import sys

# common.py / config.py อยู่ที่ services/mqtt/
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services" / "mqtt"))
import common  # noqa: E402

DEFECT_CLASSES = common.CLASSES[1:]


def make_msg(device_id, image_no, defect):
    n = random.randint(35, 60)
    bad = sum(random.random() < defect for _ in range(n))
    counts = {c: 0 for c in common.CLASSES}
    counts["good"] = n - bad
    for _ in range(bad):
        counts[random.choice(DEFECT_CLASSES)] += 1
    total = sum(counts.values())
    return {
        "device_id": device_id,
        "ts": common.now(),
        "image_id": f"img_{image_no:03d}",
        "counts": counts,
        "total": total,
        "defect_ratio": round((total - counts["good"]) / total, 3) if total else 0,
        "infer_ms": random.randint(220, 300),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--defect", type=float, default=0.18, help="สัดส่วนเมล็ดเสียโดยประมาณ 0–1")
    ap.add_argument("--images", type=int, default=0)
    ap.add_argument("--device", default="pi-01")
    a = ap.parse_args()

    client = common.make_client(a.device)
    i = 1
    try:
        while a.images == 0 or i <= a.images:
            msg = make_msg(a.device, i, a.defect)
            client.publish(common.T_BEANS, json.dumps(msg), qos=1, retain=False)
            print("→", common.T_BEANS, msg["image_id"], msg["counts"], "defect", msg["defect_ratio"])
            i += 1
            time.sleep(a.interval)
    except KeyboardInterrupt:
        pass
    common.close(client, a.device)


if __name__ == "__main__":
    main()
