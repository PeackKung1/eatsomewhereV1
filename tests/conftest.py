"""ให้ pytest หา common/config (services/mqtt) และโมดูล agent (agent/src) เจอ"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for p in ("services/mqtt", "agent/src"):
    sys.path.insert(0, str(ROOT / p))
