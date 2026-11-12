"""ค่าตั้งของทั้งระบบ แก้ที่ไฟล์นี้ที่เดียว (หรือใช้ environment variable ทับ)

ช่วงซ้อม : broker.hivemq.com port 1883 ไม่มีรหัส ไม่มี TLS
วันแข่ง  : เปลี่ยนเป็น broker ของผู้จัด (host/port/รหัส/TLS ยังไม่ทราบ ต้องถามผู้จัด)
"""
import os

# --- Broker ---
HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USERNAME = os.getenv("MQTT_USER", "")          # ว่าง = ไม่ใช้รหัส
PASSWORD = os.getenv("MQTT_PASS", "")
USE_TLS = os.getenv("MQTT_TLS", "0") == "1"    # HiveMQ Cloud / broker ที่ใช้ TLS → 1 และ PORT=8883

# --- Topic ---
# เปลี่ยนเป็นชื่อทีมที่ตกลงกัน (ตัวพิมพ์เล็ก ไม่มีเว้นวรรค ไม่ซ้ำใครบน public broker)
TEAM = os.getenv("TESA_TEAM", "kucoffee26")
PREFIX = f"tesa/{TEAM}"

# --- Mock market (Track 3 จำลอง ใช้ซ้อมเท่านั้น) ---
MARKET_URL = os.getenv("MARKET_URL", "http://127.0.0.1:8000")
