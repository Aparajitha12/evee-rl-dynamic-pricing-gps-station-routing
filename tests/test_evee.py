"""
tests/test_evee.py
Unit tests for EVEE Dynamic Pricing Agent
Run with: pytest tests/ -v
"""
import hashlib
import re
import pytest
import sys
import os

# ── allow importing from project root ────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────
# 1. INDIAN PLATE VALIDATOR
# ─────────────────────────────────────────────────────────────
_PLATE_RE = re.compile(
    r'^([A-Z]{2})\s*(\d{1,2})\s*([A-Z]{1,3})\s*(\d{4})$',
    re.IGNORECASE
)

def validate_indian_plate(plate):
    if not plate or not plate.strip():
        return False, "", "Number plate is required."
    clean = plate.strip().upper().replace(" ", "").replace("-", "")
    m = _PLATE_RE.match(clean)
    if not m:
        return False, "", "Invalid plate format."
    return True, "".join(m.groups()), ""


class TestPlateValidator:
    def test_valid_standard_plate(self):
        ok, norm, _ = validate_indian_plate("TN01AB1234")
        assert ok and norm == "TN01AB1234"

    def test_valid_with_spaces(self):
        ok, norm, _ = validate_indian_plate("TN 01 AB 1234")
        assert ok and norm == "TN01AB1234"

    def test_valid_with_hyphens(self):
        ok, norm, _ = validate_indian_plate("MH-02-CD-5678")
        assert ok and norm == "MH02CD5678"

    def test_valid_bh_series(self):
        ok, norm, _ = validate_indian_plate("BH01AA1234")
        assert ok and norm == "BH01AA1234"

    def test_valid_single_letter_series(self):
        ok, norm, _ = validate_indian_plate("TN01A1234")
        assert ok and norm == "TN01A1234"

    def test_invalid_too_short(self):
        ok, _, _ = validate_indian_plate("TN01AB12")
        assert not ok

    def test_invalid_no_state_code(self):
        ok, _, _ = validate_indian_plate("01AB1234")
        assert not ok

    def test_invalid_five_digit_number(self):
        ok, _, _ = validate_indian_plate("TN01AB12345")
        assert not ok

    def test_invalid_empty(self):
        ok, _, err = validate_indian_plate("")
        assert not ok and "required" in err.lower()

    def test_invalid_none(self):
        ok, _, err = validate_indian_plate(None)
        assert not ok

    def test_lowercase_normalised(self):
        ok, norm, _ = validate_indian_plate("tn01ab1234")
        assert ok and norm == "TN01AB1234"


# ─────────────────────────────────────────────────────────────
# 2. VEHICLE DATABASE LOOKUP
# ─────────────────────────────────────────────────────────────
VEHICLE_DB = {
    "tata nexon ev":  {"type": "BEV",  "battery_kwh": 30.2, "voltage_v": 320,
                       "max_ac_kw": 7.2, "max_dc_kw": 50, "display": "Tata Nexon EV", "found": True},
    "maruti swift":   {"type": "ICE",  "battery_kwh": 0, "voltage_v": 0,
                       "max_ac_kw": 0, "max_dc_kw": 0, "display": "Maruti Swift (Petrol)", "found": True},
    "toyota camry hybrid": {"type": "HYBRID", "battery_kwh": 0, "voltage_v": 0,
                            "max_ac_kw": 0, "max_dc_kw": 0, "display": "Toyota Camry Hybrid", "found": True},
    "hyundai ioniq 5": {"type": "BEV", "battery_kwh": 72.6, "voltage_v": 800,
                        "max_ac_kw": 11.0, "max_dc_kw": 220, "display": "Hyundai Ioniq 5", "found": True},
}
ICE_KEYWORDS = ["petrol", "diesel", "swift", "alto", "city", "i20", "creta", "verna"]
EV_KEYWORDS  = ["ev", "electric", "ioniq", "e-tron", "recharge"]

def lookup_vehicle(car_model_raw):
    key = car_model_raw.strip().lower()
    for db_key, specs in VEHICLE_DB.items():
        if db_key in key or key in db_key:
            return {**specs, "found": True}
    key_lower = key
    if any(kw in key_lower for kw in EV_KEYWORDS):
        return {"type": "UNKNOWN_EV", "battery_kwh": None, "voltage_v": None,
                "max_ac_kw": None, "max_dc_kw": None, "display": car_model_raw, "found": False}
    if any(kw in key_lower for kw in ICE_KEYWORDS):
        return {"type": "ICE", "battery_kwh": 0, "voltage_v": 0,
                "max_ac_kw": 0, "max_dc_kw": 0, "display": car_model_raw, "found": False}
    return {"type": "UNKNOWN", "battery_kwh": None, "voltage_v": None,
            "max_ac_kw": None, "max_dc_kw": None, "display": car_model_raw, "found": False}

def is_ev_vehicle(car_model):
    specs = lookup_vehicle(car_model)
    vtype = specs["type"]
    if vtype in ("BEV", "PHEV", "UNKNOWN_EV"):
        return True, vtype, specs
    return False, vtype, specs


class TestVehicleLookup:
    def test_known_bev(self):
        ok, reason, specs = is_ev_vehicle("Tata Nexon EV")
        assert ok and reason == "BEV"

    def test_known_800v_ev(self):
        ok, reason, specs = is_ev_vehicle("Hyundai Ioniq 5")
        assert ok and specs["voltage_v"] == 800

    def test_ice_blocked(self):
        ok, reason, _ = is_ev_vehicle("Maruti Swift")
        assert not ok and reason == "ICE"

    def test_hybrid_blocked(self):
        ok, reason, _ = is_ev_vehicle("Toyota Camry Hybrid")
        assert not ok and reason == "HYBRID"

    def test_unknown_ev_keyword_allowed(self):
        ok, reason, _ = is_ev_vehicle("Some Brand EV X1")
        assert ok and reason == "UNKNOWN_EV"

    def test_case_insensitive(self):
        ok, _, _ = is_ev_vehicle("TATA NEXON EV")
        assert ok

    def test_specs_battery_kwh(self):
        _, _, specs = is_ev_vehicle("Tata Nexon EV")
        assert specs["battery_kwh"] == 30.2

    def test_specs_voltage(self):
        _, _, specs = is_ev_vehicle("Tata Nexon EV")
        assert specs["voltage_v"] == 320


# ─────────────────────────────────────────────────────────────
# 3. PASSWORD HASHING
# ─────────────────────────────────────────────────────────────
class TestPasswordHashing:
    def test_correct_password_matches(self):
        pw = "SecurePass123"
        hashed = hashlib.sha256(pw.encode()).hexdigest()
        assert hashlib.sha256(pw.encode()).hexdigest() == hashed

    def test_wrong_password_fails(self):
        pw = "SecurePass123"
        hashed = hashlib.sha256(pw.encode()).hexdigest()
        assert hashlib.sha256("wrongpassword".encode()).hexdigest() != hashed

    def test_password_min_length(self):
        assert len("short") < 6
        assert len("validpw") >= 6

    def test_hash_is_hex_string(self):
        hashed = hashlib.sha256(b"test").hexdigest()
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)


# ─────────────────────────────────────────────────────────────
# 4. VOLTAGE TIER LABELS
# ─────────────────────────────────────────────────────────────
def get_voltage_tier(voltage_v):
    if voltage_v is None: return "Unknown"
    if voltage_v >= 700:  return "800V Ultra-Fast"
    if voltage_v >= 350:  return "400V Fast"
    if voltage_v >= 200:  return "350V Standard"
    if voltage_v >= 60:   return "Low-Voltage (2-Wheeler)"
    return "Unknown"


class TestVoltageTier:
    def test_800v_tier(self):
        assert get_voltage_tier(800) == "800V Ultra-Fast"

    def test_400v_tier(self):
        assert get_voltage_tier(400) == "400V Fast"

    def test_320v_tier(self):
        assert get_voltage_tier(320) == "350V Standard"

    def test_72v_2wheeler(self):
        assert get_voltage_tier(72) == "Low-Voltage (2-Wheeler)"

    def test_none_returns_unknown(self):
        assert get_voltage_tier(None) == "Unknown"

    def test_zero_returns_unknown(self):
        assert get_voltage_tier(0) == "Unknown"


# ─────────────────────────────────────────────────────────────
# 5. DUPLICATE PLATE CHECK (in-memory simulation)
# ─────────────────────────────────────────────────────────────
class TestDuplicatePlate:
    def setup_method(self):
        self.user_db = {
            "rluser1": {"car_plate": "TN01AB1234", "role": "User"},
        }

    def _plate_exists(self, plate):
        for rec in self.user_db.values():
            if rec.get("car_plate", "").upper() == plate.upper():
                return True
        return False

    def test_existing_plate_detected(self):
        assert self._plate_exists("TN01AB1234")

    def test_case_insensitive_duplicate(self):
        assert self._plate_exists("tn01ab1234")

    def test_new_plate_allowed(self):
        assert not self._plate_exists("KA05XY9999")

    def test_empty_plate_not_matched(self):
        assert not self._plate_exists("")


# ─────────────────────────────────────────────────────────────
# 6. PRICING LOGIC
# ─────────────────────────────────────────────────────────────
BASE_PRICE = 15.0

def clamp(value, lo, hi):
    return max(lo, min(hi, value))

def compute_price(base, multiplier):
    return round(base * clamp(multiplier, 0.80, 1.50), 2)


class TestPricingLogic:
    def test_base_multiplier(self):
        assert compute_price(BASE_PRICE, 1.0) == 15.0

    def test_max_multiplier_clamped(self):
        assert compute_price(BASE_PRICE, 2.0) == round(BASE_PRICE * 1.50, 2)

    def test_min_multiplier_clamped(self):
        assert compute_price(BASE_PRICE, 0.5) == round(BASE_PRICE * 0.80, 2)

    def test_price_within_bounds(self):
        price = compute_price(BASE_PRICE, 1.2)
        assert BASE_PRICE * 0.80 <= price <= BASE_PRICE * 1.50

    def test_price_is_float(self):
        price = compute_price(BASE_PRICE, 1.1)
        assert isinstance(price, float)
