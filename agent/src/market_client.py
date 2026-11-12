"""market_client.py — คุยกับ API ตลาด (ที่เดียวในระบบ)

วันที่ 17 พ.ย. ได้ API จริง: แก้ path / ชื่อ field ในไฟล์นี้ไฟล์เดียว
ตอนนี้ตรงกับ services/market/mock_market.py:
  GET  /buyers  → {"buyers": [...]}
  POST /offer   → {"round","accepted","reason"}
  GET  /results → {"rounds","revenue_total","history"}

ทุก error (ต่อไม่ได้ / timeout / HTTP 4xx-5xx / ตอบผิดรูปแบบ) ถูกแปลงเป็น MarketError
ให้ main.py จับที่เดียวแล้ววนต่อ
"""
import json
import os
import urllib.error
import urllib.request

MARKET_URL = os.getenv("MARKET_URL", "http://127.0.0.1:8000")
MARKET_TOKEN = os.getenv("MARKET_API_TOKEN", "")
TIMEOUT = float(os.getenv("MARKET_TIMEOUT", "10"))


class MarketError(Exception):
    pass


def _http(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if MARKET_TOKEN:
        headers["Authorization"] = f"Bearer {MARKET_TOKEN}"
    req = urllib.request.Request(MARKET_URL + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:200]
        raise MarketError(f"{method} {path} → HTTP {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise MarketError(f"{method} {path} → ต่อตลาดไม่ได้: {e}") from e
    except ValueError as e:
        raise MarketError(f"{method} {path} → คำตอบไม่ใช่ JSON") from e


def get_buyers():
    res = _http("GET", "/buyers")
    buyers = res.get("buyers") if isinstance(res, dict) else None
    if not isinstance(buyers, list):
        raise MarketError("GET /buyers → ไม่มี key 'buyers'")
    return buyers


def send_offer(lot, offer, qty_kg=100):
    body = {
        "lot_id": offer["lot_id"],
        "buyer_id": offer["buyer_id"],
        "price_per_kg": offer["price_per_kg"],
        "qty_kg": qty_kg,
        "quality": {"moisture_pct": lot.get("moisture_pct"), "defect_ratio": lot.get("defect_ratio")},
    }
    res = _http("POST", "/offer", body)
    if not isinstance(res, dict) or "accepted" not in res:
        raise MarketError(f"POST /offer → คำตอบผิดรูปแบบ: {res!r}"[:200])
    return {"round": res.get("round"), "accepted": bool(res["accepted"]), "reason": res.get("reason", "")}


def get_results():
    return _http("GET", "/results")
