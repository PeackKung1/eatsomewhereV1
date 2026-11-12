"""Service Layer: รวมข้อมูลเป็นล็อตถูกต้อง และไม่ล้มเมื่อเจอข้อความผิด (ไม่ต้องมี broker)"""
import json

import common
from service_layer import Service
from test_contracts import BEANS, MOISTURE


def send(svc, topic, msg, retained=False):
    svc.handle(topic, msg if isinstance(msg, bytes) else json.dumps(msg).encode(), retained)


def test_lot_combines_moisture_and_beans():
    svc = Service()
    send(svc, common.T_MOISTURE, MOISTURE)
    send(svc, common.T_BEANS, BEANS)
    lot = svc.take_update()
    assert lot["lot_id"] == "L1"
    assert lot["moisture_pct"] == 11.8 and lot["image_count"] == 1
    assert lot["total"] == 49 and lot["defect_ratio"] == 0.184


def test_retained_moisture_skipped():
    svc = Service()
    send(svc, common.T_MOISTURE, MOISTURE, retained=True)
    assert "moisture_pct" not in svc.take_update()
    assert svc.stats["retained_skipped"] == 1


def test_duplicate_image_counted_once():
    svc = Service()
    send(svc, common.T_BEANS, BEANS)
    send(svc, common.T_BEANS, BEANS)
    assert svc.take_update()["image_count"] == 1


def test_bad_messages_rejected_without_crash():
    svc = Service()
    send(svc, common.T_BEANS, b"not json")
    send(svc, common.T_MOISTURE, {**MOISTURE, "moisture_pct": None})
    assert svc.stats["rejected"] == 2


def test_new_lot_resets_counts():
    svc = Service()
    send(svc, common.T_BEANS, BEANS)
    send(svc, common.T_CMD, {"cmd": "new_lot"})
    lot = svc.take_update()
    assert lot["lot_id"] == "L2" and lot["total"] == 0
