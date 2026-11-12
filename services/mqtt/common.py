"""ของที่ทุกส่วนใช้ร่วมกัน: ชื่อ topic, ชื่อคลาส, การเชื่อมต่อ MQTT (LWT + reconnect), ตรวจ schema"""
import json
import logging
import time

import paho.mqtt.client as mqtt

import config

CLASSES = ["good", "shell", "full_black", "hull_husk", "broken", "parchment", "immature"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s | %(message)s", datefmt="%H:%M:%S")


def topic(*parts):
    return "/".join([config.PREFIX, *parts])


T_MOISTURE = topic("esp32", "moisture")
T_BEANS = topic("pi", "beans")
T_LOT = topic("service", "lot")
T_CMD = topic("service", "cmd")


def now():
    return int(time.time())


def make_client(device_id, on_connected=None, on_message=None):
    """สร้าง client ที่มี LWT, ส่ง status online, reconnect เอง และเรียก on_connected ทุกครั้งที่ต่อติด
    (subscribe ใน on_connected เพื่อให้ subscribe ใหม่หลัง reconnect)"""
    log = logging.getLogger(device_id)
    client_id = f"{config.TEAM}-{device_id}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if config.USERNAME:
        client.username_pw_set(config.USERNAME, config.PASSWORD)
    if config.USE_TLS:
        client.tls_set()

    status_topic = topic("status", device_id)
    client.will_set(status_topic, json.dumps({"device_id": device_id, "state": "offline"}), qos=1, retain=True)
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def _on_connect(c, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.warning("ต่อ broker ไม่สำเร็จ: %s", reason_code)
            return
        log.info("ต่อ %s:%s แล้ว (client_id=%s)", config.HOST, config.PORT, client_id)
        c.publish(status_topic, json.dumps({"device_id": device_id, "state": "online", "ts": now()}), qos=1, retain=True)
        if on_connected:
            on_connected(c)

    def _on_disconnect(c, userdata, flags, reason_code, properties):
        log.warning("หลุดจาก broker (%s) กำลังต่อใหม่...", reason_code)

    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    if on_message:
        client.on_message = on_message
    client.connect_async(config.HOST, config.PORT, keepalive=30)
    client.loop_start()
    return client


def close(client, device_id):
    """ปิดแบบสุภาพ: ประกาศ offline เอง (LWT จะไม่ทำงานเมื่อปิดปกติ)"""
    info = client.publish(topic("status", device_id), json.dumps({"device_id": device_id, "state": "offline"}), qos=1, retain=True)
    try:
        info.wait_for_publish(timeout=3)
    except Exception:
        pass
    client.disconnect()
    client.loop_stop()


# ---------- ตรวจ schema ----------

def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_moisture(m):
    errs = []
    if not isinstance(m, dict):
        return ["ไม่ใช่ JSON object"]
    if not isinstance(m.get("device_id"), str):
        errs.append("device_id หาย/ไม่ใช่ string")
    if not _is_int(m.get("ts")):
        errs.append("ts หาย/ไม่ใช่จำนวนเต็ม")
    elif m["ts"] > 10_000_000_000:
        errs.append("ts ดูเป็นมิลลิวินาที ต้องเป็นวินาที")
    v = m.get("moisture_pct")
    if not _is_num(v):
        errs.append("moisture_pct หาย/ไม่ใช่ตัวเลข")
    elif not 0 <= v <= 100:
        errs.append("moisture_pct ต้องอยู่ 0–100")
    if "raw_adc" in m and not (_is_int(m["raw_adc"]) and 0 <= m["raw_adc"] <= 4095):
        errs.append("raw_adc ต้องเป็นจำนวนเต็ม 0–4095")
    return errs


def validate_beans(m):
    errs = []
    if not isinstance(m, dict):
        return ["ไม่ใช่ JSON object"]
    for k in ("device_id", "image_id"):
        if not isinstance(m.get(k), str):
            errs.append(f"{k} หาย/ไม่ใช่ string")
    if not _is_int(m.get("ts")):
        errs.append("ts หาย/ไม่ใช่จำนวนเต็ม")
    elif m["ts"] > 10_000_000_000:
        errs.append("ts ดูเป็นมิลลิวินาที ต้องเป็นวินาที")
    counts = m.get("counts")
    if not isinstance(counts, dict):
        return errs + ["counts หาย/ไม่ใช่ object"]
    missing = [c for c in CLASSES if c not in counts]
    extra = [c for c in counts if c not in CLASSES]
    if missing:
        errs.append(f"counts ขาดคลาส: {missing}")
    if extra:
        errs.append(f"counts มีคลาสชื่อผิด: {extra}")
    if any(not (_is_int(v) and v >= 0) for v in counts.values()):
        errs.append("counts ต้องเป็นจำนวนเต็ม >= 0")
    if not errs:
        total = sum(counts.values())
        if m.get("total") != total:
            errs.append(f"total={m.get('total')} ไม่ตรงผลรวม counts={total}")
        dr = m.get("defect_ratio")
        expect = round((total - counts["good"]) / total, 3) if total else 0
        if not _is_num(dr) or abs(dr - expect) > 0.002:
            errs.append(f"defect_ratio={dr} ควรเป็น {expect}")
    return errs
