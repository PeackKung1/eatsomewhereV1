"""Service Layer: รับ esp32/moisture + pi/beans → รวมเป็นล็อต → ส่ง service/lot (QoS 1, retained)

- ข้ามค่า moisture ที่มาแบบ retained (อาจเป็นค่าค้างจากรอบก่อน)
- ข้อความผิด schema → log แล้วข้าม ไม่ล้ม
- ภาพ image_id ซ้ำในล็อตเดียว (QoS 1 อาจส่งซ้ำ) → ไม่นับซ้ำ
- เริ่มล็อตใหม่: ส่ง {"cmd":"new_lot"} ไปที่ service/cmd (หรือรัน new_lot.py)
- ตอนเริ่มโปรแกรม ล้าง retained เก่าของ service/lot

ใช้: python service_layer.py
"""
import json
import logging
import statistics
import threading
import time

import common

log = logging.getLogger("service")
DEVICE_ID = "service-01"


class Lot:
    def __init__(self, lot_no):
        self.lot_id = f"L{lot_no}"
        self.moisture = []
        self.counts = {c: 0 for c in common.CLASSES}
        self.images = set()

    def add_moisture(self, pct):
        self.moisture.append(pct)

    def add_beans(self, image_id, counts):
        if image_id in self.images:
            return False
        self.images.add(image_id)
        for c in common.CLASSES:
            self.counts[c] += counts[c]
        return True

    def to_msg(self):
        total = sum(self.counts.values())
        msg = {"lot_id": self.lot_id, "ts": common.now()}
        if self.moisture:
            msg["moisture_pct"] = round(statistics.median(self.moisture), 1)
        msg.update({
            "moisture_samples": len(self.moisture),
            "image_count": len(self.images),
            "counts": dict(self.counts),
            "total": total,
            "defect_ratio": round((total - self.counts["good"]) / total, 3) if total else 0,
        })
        return msg


class Service:
    def __init__(self):
        self.lock = threading.Lock()
        self.lot_no = 1
        self.lot = Lot(self.lot_no)
        self.dirty = True
        self.cleared = False
        self.stats = {"moisture": 0, "beans": 0, "rejected": 0, "retained_skipped": 0, "duplicate": 0}

    # ---- MQTT callbacks ----
    def on_connected(self, c):
        if not self.cleared:
            c.publish(common.T_LOT, payload=None, qos=1, retain=True)   # ล้างล็อตค้างจากรอบก่อน
            self.cleared = True
        c.subscribe([(common.T_MOISTURE, 0), (common.T_BEANS, 1), (common.T_CMD, 1)])
        log.info("subscribe: moisture, beans, cmd")

    def on_message(self, c, userdata, msg):
        try:
            self.handle(msg.topic, msg.payload, msg.retain)
        except Exception as e:                      # อะไรก็ตามห้ามทำให้ service ล้ม
            self.stats["rejected"] += 1
            log.exception("error ตอนจัดการ %s: %s", msg.topic, e)

    # ---- logic (เทสได้โดยไม่ต้องมี broker) ----
    def handle(self, t, payload, retained=False):
        if t == common.T_MOISTURE and retained:
            self.stats["retained_skipped"] += 1
            log.info("ข้าม moisture แบบ retained (ค่าเก่าจาก broker)")
            return
        try:
            data = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            self.stats["rejected"] += 1
            log.warning("ทิ้ง %s: ไม่ใช่ JSON: %r", t, payload[:80])
            return

        if t == common.T_CMD:
            if isinstance(data, dict) and data.get("cmd") == "new_lot":
                self.new_lot()
            return

        if t == common.T_MOISTURE:
            errs = common.validate_moisture(data)
            if errs:
                self.stats["rejected"] += 1
                log.warning("ทิ้ง moisture: %s", "; ".join(errs))
                return
            with self.lock:
                self.lot.add_moisture(data["moisture_pct"])
                self.dirty = True
            self.stats["moisture"] += 1

        elif t == common.T_BEANS:
            errs = common.validate_beans(data)
            if errs:
                self.stats["rejected"] += 1
                log.warning("ทิ้ง beans: %s", "; ".join(errs))
                return
            with self.lock:
                added = self.lot.add_beans(data["image_id"], data["counts"])
                self.dirty = self.dirty or added
            if added:
                self.stats["beans"] += 1
            else:
                self.stats["duplicate"] += 1
                log.info("ข้ามภาพซ้ำ %s", data["image_id"])

    def new_lot(self):
        with self.lock:
            self.lot_no += 1
            self.lot = Lot(self.lot_no)
            self.dirty = True
        log.info("=== เริ่มล็อตใหม่ %s ===", self.lot.lot_id)

    def take_update(self):
        """คืนข้อความล็อตถ้ามีการเปลี่ยนแปลง (เรียกไม่เกิน 1 ครั้ง/วินาที)"""
        with self.lock:
            if not self.dirty:
                return None
            self.dirty = False
            return self.lot.to_msg()


def main():
    svc = Service()
    client = common.make_client(DEVICE_ID, on_connected=svc.on_connected, on_message=svc.on_message)
    last_stats = 0
    try:
        while True:
            time.sleep(1)
            if not client.is_connected():
                continue
            msg = svc.take_update()
            if msg:
                client.publish(common.T_LOT, json.dumps(msg), qos=1, retain=True)
                log.info("→ lot %s moist=%s (%d) imgs=%d total=%d defect=%.3f", msg["lot_id"],
                         msg.get("moisture_pct", "-"), msg["moisture_samples"], msg["image_count"],
                         msg["total"], msg["defect_ratio"])
            if time.time() - last_stats > 30:
                log.info("สถิติ: %s", svc.stats)
                last_stats = time.time()
    except KeyboardInterrupt:
        log.info("สถิติสุดท้าย: %s", svc.stats)
        common.close(client, DEVICE_ID)


if __name__ == "__main__":
    main()
