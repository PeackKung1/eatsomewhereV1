from openai import OpenAI
import json, re, logging, os, time, math

from prompts import SYSTEM_PROMPT, build_prompt

log = logging.getLogger("llm")

#--------ตั้งค่า----------
BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1/")
API_KEY = os.getenv("LLM_API_KEY", "ollama")
MODEL = os.getenv("LLM_MODEL", "qwen3.5:2b")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "20"))
REASONING = os.getenv("LLM_REASONING", "none")
JSON_MODE = os.getenv("LLM_JSON_MODE", "1") == "1"

#-------client---------
client = OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=TIMEOUT, max_retries=1)

# SYSTEM_PROMPT และ build_prompt ย้ายไปอยู่ prompts.py (แก้กลยุทธ์ที่นั่นที่เดียว)
# ช่วงราคา min/max ย้ายไปอยู่ validator.py (ใช้ค่าเดียวกับที่ตรวจข้อเสนอจริง)

# ---------- เรียก LLM ----------
def call_llm(prompt):
    kw = {}
    if JSON_MODE:
        kw["response_format"] = {"type": "json_object"}
    if REASONING:
        kw["reasoning_effort"] = REASONING
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}],
        **kw,
    )
    return r.choices[0].message.content or ""

# ---------- แปลงคำตอบเป็น dict ----------
def parse_json(text):
    text = re.sub(r"```(?:json)?", "", text)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    return d if isinstance(d, dict) else None

# ---------- ตรวจรูปแบบ ----------
def check_format(d):
    if not isinstance(d.get("buyer_id"), str):
        return False
    try:
        d["price_per_kg"] = float(d["price_per_kg"])
    except (KeyError, TypeError, ValueError):
        return False
    return math.isfinite(d["price_per_kg"]) and d["price_per_kg"] > 0

# ---------- ฟังก์ชันหลักที่ agent.py เรียก ----------
def ask_llm(situation):
    t0 = time.time()
    try:
        d = parse_json(call_llm(build_prompt(situation)))
        if d and check_format(d):
            d["source"] = "llm"
            log.info("LLM %.1fs → %s @ %.2f : %s", time.time() - t0,
                     d["buyer_id"], d["price_per_kg"], d.get("reason", ""))
            return d
        log.warning("LLM ตอบผิดรูปแบบ → ใช้ค่าจากกฎ")
    except Exception as e:
        log.warning("LLM error: %s → ใช้ค่าจากกฎ", e)
    return {**situation["suggested"], "source": "fallback"}

# ---------- ทดสอบ: python llm.py ----------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s | %(message)s")
    situation = {
        "lot": {"lot_id": "L1", "moisture_pct": 11.6, "defect_ratio": 0.10},
        # options มาจาก tools.PriceBook.options() (ตัวอย่างหลัง B1 โดนปฏิเสธที่ 168)
        "options": [
            {"buyer_id": "B2", "rule_price": 130.0, "expected": 65.0, "sold": 0, "rejected": 0,
             "max_sold_price": None, "min_rejected_price": None},
            {"buyer_id": "B1", "rule_price": 156.24, "expected": 52.08, "sold": 0, "rejected": 1,
             "max_sold_price": None, "min_rejected_price": 168.0},
        ],
        "suggested": {"buyer_id": "B2", "price_per_kg": 130.0},
        "history": [{"buyer_id": "B1", "price_per_kg": 168.0, "accepted": False, "reason": "ราคาสูงเกินไป"}],
    }
    print(ask_llm(situation))

