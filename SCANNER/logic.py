# logic.py

import csv
import json
import logging
import os
import re
import string
import time
from datetime import datetime
from typing import Callable, Optional

# Minimal shims to avoid hard dependency on tkinter or hardware in SCANNER app
try:
    import tkinter as tk  # noqa: F401
except Exception:  # pragma: no cover - environment without Tk
    tk = None  # type: ignore

# These are optional in SCANNER context; provide safe fallbacks
try:
    from config import LOG_FOLDER, RECOVERY_FILE  # type: ignore
except Exception:
    LOG_FOLDER = "/SCANNER/LOGS"
    RECOVERY_FILE = "recovery.json"

# Hardware signaling is optional for SCANNER integration
try:
    from hardware import get_hardware_controller  # type: ignore
    _hardware = get_hardware_controller()
except Exception:  # pragma: no cover - no hardware on dev
    _hardware = None

_hardware_logger = logging.getLogger("hardware")
_hardware_error_handler: Optional[Callable[[str], None]] = None


def set_hardware_error_handler(handler: Optional[Callable[[str], None]]) -> None:
    global _hardware_error_handler
    _hardware_error_handler = handler


_last_hardware_error_time = 0
_last_hardware_error_message = ""

def _handle_hardware_exception(exc: Exception) -> None:
    global _last_hardware_error_time, _last_hardware_error_message
    message = f"Hardware failure: {exc}" if exc else "Hardware failure"
    current_time = time.time()
    if (current_time - _last_hardware_error_time < 5.0 and message == _last_hardware_error_message):
        return
    _last_hardware_error_time = current_time
    _last_hardware_error_message = message
    _hardware_logger.exception(message)
    if _hardware_error_handler:
        try:
            _hardware_error_handler(message)
        except Exception:
            _hardware_logger.exception("Hardware error handler raised an exception")


def blink_light(color, duration=0.1):
    if not _hardware:
        return
    try:
        _hardware.light_on(color)
        time.sleep(duration)
        _hardware.light_off(color)
    except Exception as exc:
        _handle_hardware_exception(exc)


def buzz(duration=0.1):
    if not _hardware:
        return
    try:
        _hardware.buzz(duration)
    except Exception as exc:
        _handle_hardware_exception(exc)


# ---------------- Validators ----------------

def validate_batch_number(batch_no: str) -> bool:
    pattern = r"^M[V][A-Z][A-Z]{2}\d{5}$"
    return re.match(pattern, batch_no) is not None


def validate_qr_format(qr_code: str) -> bool:
    return len(qr_code) == 14 and qr_code.isalnum()


def validate_qr_match(qr_code: str, line: str, mould_type: str) -> bool:
    return len(qr_code) >= 5 and qr_code[1] == line and qr_code[2:5] == mould_type


def batch_number_validator(val: str) -> bool:
    return validate_batch_number(val.upper())


def line_validator(val: str) -> bool:
    return len(val) == 1 and val.isalpha()


def mould_name_validator(val: str) -> bool:
    if len(val) != 3:
        return False
    if not val[0].isalpha():
        return False
    return all(ch.isalnum() for ch in val[1:])


def qr_validator(val: str, line_val: str, mould_type: str) -> bool:
    return validate_qr_format(val) and validate_qr_match(val, line_val, mould_type)


# ---------------- QR Scan Logic ----------------

def handle_qr_scan(qr_code: str, batch_line: str, mould_ranges: dict, duplicate_checker: Optional[Callable[[str], bool]] = None):
    """Validate a QR code and return (status, mould)."""
    if not validate_qr_format(qr_code):
        blink_light("RED")
        buzz()
        return "INVALID FORMAT", None

    if not batch_line or qr_code[1] != batch_line:
        blink_light("RED")
        buzz()
        return "LINE MISMATCH", None

    for mould, (start, end) in mould_ranges.items():
        if start <= qr_code <= end:
            if duplicate_checker and duplicate_checker(qr_code):
                blink_light("YELLOW")
                return "DUPLICATE", mould
            blink_light("GREEN")
            return "PASS", mould

    blink_light("RED")
    buzz()
    return "OUT OF BATCH", None


# ---------------- CSV Logging helpers (optional) ----------------

def init_log(batch_number: str):
    os.makedirs(LOG_FOLDER, exist_ok=True)
    csv_path = os.path.join(LOG_FOLDER, f"{batch_number}.csv")
    log_file = open(csv_path, mode="a", newline="")
    csv_writer = csv.writer(log_file)
    return log_file, csv_writer


def write_log(csv_writer, log_file, batch_number, mould, qr_code, status):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        csv_writer.writerow([timestamp, batch_number, mould or "UNKNOWN", qr_code, status])
        log_file.flush()
    except Exception:
        pass


def close_log(log_file):
    try:
        if log_file and not log_file.closed:
            log_file.close()
    except Exception:
        pass
