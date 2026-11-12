"""ข้อตกลงข้อมูล: ตัวอย่างใน contract ต้องผ่าน validate_* และ schema ต้องตรงกับโค้ด"""
import json
import pathlib

import common

SCHEMAS = pathlib.Path(__file__).resolve().parents[1] / "contracts" / "schemas"

MOISTURE = {"device_id": "esp32-01", "ts": 1763190000, "moisture_pct": 11.8, "raw_adc": 2140}
BEANS = {"device_id": "pi-01", "ts": 1763190000, "image_id": "img_001",
         "counts": {"good": 40, "shell": 2, "full_black": 1, "hull_husk": 0, "broken": 3, "parchment": 1, "immature": 2},
         "total": 49, "defect_ratio": 0.184, "infer_ms": 260}


def test_contract_examples_are_valid():
    assert common.validate_moisture(MOISTURE) == []
    assert common.validate_beans(BEANS) == []


def test_millisecond_ts_rejected():
    assert any("มิลลิวินาที" in e for e in common.validate_moisture({**MOISTURE, "ts": 1763190000000}))


def test_uppercase_class_rejected():
    counts = {("Good" if k == "good" else k): v for k, v in BEANS["counts"].items()}
    assert common.validate_beans({**BEANS, "counts": counts})


def test_wrong_defect_ratio_rejected():
    assert common.validate_beans({**BEANS, "defect_ratio": 0.5})


def test_schema_files_match_code():
    for name in ("moisture", "beans", "lot", "status"):
        s = json.loads((SCHEMAS / f"{name}.schema.json").read_text())
        assert s["type"] == "object" and s["required"]
    beans = json.loads((SCHEMAS / "beans.schema.json").read_text())
    assert beans["properties"]["counts"]["required"] == common.CLASSES
