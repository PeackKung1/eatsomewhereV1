"""จำลอง ESP32: ส่งค่าความชื้นตาม schema ทุก N วินาที (QoS 0, retained)

ใช้: python mock_esp32.py [--interval 2] [--base 11.5] [--device esp32-01]
หยุด: Ctrl+C (จะประกาศ offline ให้เอง)
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


def make_msg(device_id, base):
    pct = round(random.gauss(base, 0.3), 1)
    raw = max(0, min(4095, int(4095 - pct * 120 + random.randint(-15, 15))))
    return {"device_id": device_id, "ts": common.now(), "moisture_pct": pct, "raw_adc": raw}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--base", type=float, default=11.5, help="ค่าความชื้นเฉลี่ย (%%)")   # %% เพราะ argparse ใช้ % จัดรูปแบบ (Python 3.14 crash)
    ap.add_argument("--device", default="esp32-01")
    a = ap.parse_args()

    client = common.make_client(a.device)
    try:
        while True:
            msg = make_msg(a.device, a.base)
            client.publish(common.T_MOISTURE, json.dumps(msg), qos=0, retain=True)
            print("→", common.T_MOISTURE, msg)
            time.sleep(a.interval)
    except KeyboardInterrupt:
        common.close(client, a.device)


if __name__ == "__main__":
    main()
