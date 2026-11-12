"""Dashboard แบบ terminal: ดูทุก topic ของทีมสด ๆ + เตือนข้อความผิด schema

ใช้: python monitor.py
"""
import json
import os
import threading
import time

import pathlib
import sys

# common.py / config.py อยู่ที่ services/mqtt/
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services" / "mqtt"))
import common  # noqa: E402

state = {"status": {}, "moisture": None, "beans": None, "lot": None, "errors": [], "count": 0}
lock = threading.Lock()


def on_connected(c):
    c.subscribe(common.topic("#"), qos=1)


def on_message(c, userdata, msg):
    t = msg.topic
    with lock:
        state["count"] += 1
        if not msg.payload:
            return
        try:
            data = json.loads(msg.payload)
        except ValueError:
            state["errors"].append(f"{time.strftime('%H:%M:%S')} {t}: ไม่ใช่ JSON")
            return
        if t.startswith(common.topic("status")):
            state["status"][t.rsplit("/", 1)[-1]] = data.get("state", "?")
        elif t == common.T_MOISTURE:
            state["moisture"] = (data, msg.retain)
            errs = common.validate_moisture(data)
            if errs:
                state["errors"].append(f"{time.strftime('%H:%M:%S')} moisture: {'; '.join(errs)}")
        elif t == common.T_BEANS:
            state["beans"] = data
            errs = common.validate_beans(data)
            if errs:
                state["errors"].append(f"{time.strftime('%H:%M:%S')} beans: {'; '.join(errs)}")
        elif t == common.T_LOT:
            state["lot"] = data
        state["errors"] = state["errors"][-6:]


def render():
    with lock:
        s = json.loads(json.dumps(state))
    out = [f"=== TESA monitor  {common.config.HOST}  prefix={common.config.PREFIX}  ข้อความ {s['count']} ===", ""]
    out.append("สถานะอุปกรณ์: " + ("  ".join(f"{k}={v}" for k, v in sorted(s["status"].items())) or "-"))
    if s["moisture"]:
        m, r = s["moisture"]
        age = common.now() - m.get("ts", 0) if isinstance(m.get("ts"), int) else "?"
        out.append(f"ความชื้นล่าสุด: {m.get('moisture_pct')} %  raw={m.get('raw_adc', '-')}  อายุ {age}s"
                   + ("  (retained)" if r else ""))
    if s["beans"]:
        b = s["beans"]
        out.append(f"ภาพล่าสุด: {b.get('image_id')}  total={b.get('total')}  defect={b.get('defect_ratio')}  "
                   f"infer={b.get('infer_ms', '-')}ms")
        out.append("   " + "  ".join(f"{k}={v}" for k, v in (b.get("counts") or {}).items()))
    if s["lot"]:
        l = s["lot"]
        out += ["", f"ล็อต {l.get('lot_id')}: ความชื้น {l.get('moisture_pct', '-')}% ({l.get('moisture_samples')} ค่า)  "
                    f"ภาพ {l.get('image_count')}  เมล็ด {l.get('total')}  เสีย {l.get('defect_ratio')}"]
    out += ["", "ข้อความผิด schema ล่าสุด:"] + (s["errors"] or ["  (ไม่มี)"])
    print("\033[2J\033[H" + "\n".join(out), flush=True)


def main():
    client = common.make_client("monitor-01", on_connected=on_connected, on_message=on_message)
    try:
        while True:
            render()
            time.sleep(1)
    except KeyboardInterrupt:
        common.close(client, "monitor-01")


if __name__ == "__main__":
    main()
