"""Agent: กฎตรวจข้อเสนอต้องกันคำตอบแย่ ๆ ของ LLM ได้ทุกกรณี (ไม่ต้องมีตลาด/LLM จริง)"""
import pytest

import llm
import main
import tools
import validator
from main import decide

BUYERS = [
    {"buyer_id": "B1", "ref_price": 160, "max_defect": 0.12, "moisture_range": [10.0, 12.5]},
    {"buyer_id": "B2", "ref_price": 130, "max_defect": 0.30, "moisture_range": [9.0, 13.5]},
    {"buyer_id": "B3", "ref_price": 90, "max_defect": 1.00, "moisture_range": [0.0, 100.0]},
]
GOOD_LOT = {"lot_id": "L1", "moisture_pct": 11.6, "defect_ratio": 0.10, "image_count": 2}


@pytest.fixture
def ask_all(monkeypatch):
    """ให้ทุกตัวเลือกนับว่าสูสี → LLM ถูกถามทุกครั้ง (ทดสอบ validator)"""
    monkeypatch.setattr(main, "LLM_CHOICE_GAP", 1.0)


def fake_llm(answer, calls=None):
    def ask(situation):
        if calls is not None:
            calls.append(situation)
        return {**answer, "source": "llm"}
    return ask


def run(answer):
    return decide(GOOD_LOT, BUYERS, tools.PriceBook(), [], fake_llm(answer))


def test_eligible_filters_by_quality():
    bad_lot = {**GOOD_LOT, "defect_ratio": 0.5}
    assert [b["buyer_id"] for b in BUYERS if validator.eligible(b, bad_lot)] == ["B3"]
    assert not validator.eligible(BUYERS[0], {"lot_id": "L1", "defect_ratio": 0.1})   # ไม่มีความชื้น


def test_valid_llm_answer_passes_through(ask_all):
    offer, notes = run({"buyer_id": "B2", "price_per_kg": 131})
    assert notes == [] and offer["buyer_id"] == "B2" and offer["price_per_kg"] == 131


def test_unknown_buyer_falls_back_to_rule(ask_all):
    offer, notes = run({"buyer_id": "B9", "price_per_kg": 140})
    assert offer["buyer_id"] == "B1" and offer["price_per_kg"] == 160 and notes


def test_ineligible_buyer_rejected(ask_all):
    lot = {**GOOD_LOT, "defect_ratio": 0.2}     # B1 รับ defect ไม่เกิน 0.12
    offer, _ = decide(lot, BUYERS, tools.PriceBook(), [], fake_llm({"buyer_id": "B1", "price_per_kg": 150}))
    assert offer["buyer_id"] != "B1"


def test_llm_price_limited_to_band_around_rule(ask_all):
    band = validator.LLM_PRICE_BAND
    low, _ = run({"buyer_id": "B1", "price_per_kg": 1})
    high, _ = run({"buyer_id": "B1", "price_per_kg": 99999})
    assert low["price_per_kg"] == round(160 * (1 - band), 2)
    assert high["price_per_kg"] == round(160 * (1 + band), 2)


def test_lot_id_always_from_current_lot(ask_all):
    offer, _ = run({"lot_id": "L99", "buyer_id": "B1", "price_per_kg": 160})
    assert offer["lot_id"] == "L1"


def test_llm_not_asked_when_choice_is_clear():
    calls = []
    offer, _ = decide(GOOD_LOT, BUYERS, tools.PriceBook(), [], fake_llm({"buyer_id": "B3", "price_per_kg": 90}, calls))
    assert calls == [] and offer["buyer_id"] == "B1" and offer["source"] == "rules"


def test_no_eligible_buyer_returns_none():
    offer, notes = decide({**GOOD_LOT, "moisture_pct": 50, "defect_ratio": 0.5},
                          BUYERS[:2], tools.PriceBook(), [], fake_llm({"buyer_id": "B1", "price_per_kg": 150}))
    assert offer is None and notes


def test_pricebook_walks_down_then_up():
    book, b1 = tools.PriceBook(), BUYERS[0]
    book.update(b1, 160.0, False, "ราคาสูงเกินไป")
    assert book.state(b1)["next"] == pytest.approx(160 * tools.DOWN)
    book.update(b1, 148.8, True, "ขายได้")
    # ขึ้นได้ไม่เกินครึ่งทางไปราคาที่เพิ่งโดนปฏิเสธ (160)
    assert book.state(b1)["next"] == pytest.approx((148.8 + 160) / 2)


def test_pricebook_respects_floor():
    book, b1 = tools.PriceBook(), BUYERS[0]
    book.update(b1, 1.0, False, "ราคาสูงเกินไป")
    assert book.state(b1)["next"] == 160 * validator.FLOOR_RATIO


def test_quality_rejection_blocks_buyer():
    book = tools.PriceBook()
    book.update(BUYERS[0], 160.0, False, "เมล็ดเสียเกินเกณฑ์ผู้ซื้อ")
    assert [o["buyer_id"] for o in book.options(BUYERS)] == ["B2", "B3"]


def test_ask_llm_falls_back_when_llm_down(monkeypatch):
    def boom(prompt):
        raise ConnectionError("down")
    monkeypatch.setattr(llm, "call_llm", boom)
    opts = tools.PriceBook().options(BUYERS)
    s = {"lot": GOOD_LOT, "options": opts, "suggested": {"buyer_id": "B1", "price_per_kg": 160.0}}
    assert llm.ask_llm(s)["source"] == "fallback"


def test_parse_json_handles_code_fence():
    assert llm.parse_json('```json\n{"buyer_id":"B1","price_per_kg":150}\n```') == {"buyer_id": "B1", "price_per_kg": 150}
    assert llm.parse_json("no json") is None
