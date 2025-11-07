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

import tkinter as tk

from config import LOG_FOLDER, RECOVERY_FILE
from hardware import get_hardware_controller


# Hardware controller
_hardware = get_hardware_controller()
_hardware_logger = logging.getLogger("hardware")
_hardware_error_handler: Optional[Callable[[str], None]] = None


def set_hardware_error_handler(handler: Optional[Callable[[str], None]]) -> None:
    """Register a callback that receives hardware error messages."""

    global _hardware_error_handler
    _hardware_error_handler = handler


_last_hardware_error_time = 0
_last_hardware_error_message = ""

def _handle_hardware_exception(exc: Exception) -> None:
    global _last_hardware_error_time, _last_hardware_error_message
    
    message = f"Hardware failure: {exc}" if exc else "Hardware failure"
    current_time = time.time()
    
    # Throttle repeated identical errors (don't report same error within 5 seconds)
    if (current_time - _last_hardware_error_time < 5.0 and 
        message == _last_hardware_error_message):
        return
    
    _last_hardware_error_time = current_time
    _last_hardware_error_message = message
    
    _hardware_logger.exception(message)
    if _hardware_error_handler:
        try:
            _hardware_error_handler(message)
        except Exception:  # pragma: no cover - safeguard
            _hardware_logger.exception("Hardware error handler raised an exception")


# ---------------- LED & BUZZER Integration ----------------
def blink_light(color, duration=0.3):
    """Trigger LED blink; swallow hardware errors to keep UI alive."""
    try:
        _hardware.light_on(color)
        time.sleep(duration)
        _hardware.light_off(color)
    except Exception as exc:  # pragma: no cover - hardware dependent
        _handle_hardware_exception(exc)


def buzz(duration=0.5):
    """Trigger buzzer with hardware exception handling."""
    try:
        _hardware.buzz(duration)
    except Exception as exc:  # pragma: no cover - hardware dependent
        _handle_hardware_exception(exc)


# ---------------- Highlight + Validation Helpers ----------------
def highlight_invalid(entry_widget, valid=True):
    """Highlight invalid entries with a soft red background."""
    if valid:
        entry_widget.config(bg="black", fg="#e5e7ff", insertbackground="#e5e7ff")
    else:
        entry_widget.config(bg="#ffe4e6", fg="black", insertbackground="black")


def force_uppercase(entry_widget, validator=None, on_valid=None):
    """Force uppercase text and optionally run live validation and callbacks."""

    def on_write(*_):
        current = entry_var.get()
        value = current.upper()
        if value != current:
            entry_var.set(value)
            value = entry_var.get()
        if validator:
            is_valid = validator(value)
            highlight_invalid(entry_widget, is_valid)
            if is_valid and on_valid:
                on_valid(value)
        elif on_valid:
            on_valid(value)

    entry_var = tk.StringVar()
    entry_var.trace_add("write", on_write)
    entry_widget.config(textvariable=entry_var)
    return entry_var


# ---------------- Validators ----------------
def validate_batch_number(batch_no):
    pattern = r"^M[V][A-Z][A-Z]{2}\d{5}$"
    return re.match(pattern, batch_no) is not None


def validate_qr_format(qr_code):
    return len(qr_code) == 14 and qr_code.isalnum()


def validate_qr_match(qr_code, line, mould_type):
    return len(qr_code) >= 5 and qr_code[1] == line and qr_code[2:5] == mould_type


def batch_number_validator(val):
    return validate_batch_number(val.upper())


def line_validator(val):
    return len(val) == 1 and val.isalpha()


def num_moulds_validator(val):
    try:
        return int(val) > 0
    except ValueError:
        return False


def mould_name_validator(val):
    if len(val) != 3:
        return False
    if not val[0].isalpha():
        return False
    return all(ch.isalnum() for ch in val[1:])


def qr_validator(val, line_val, mould_type):
    return validate_qr_format(val) and validate_qr_match(val, line_val, mould_type)


# ---------------- Batch Calculation ----------------
def calculate_batch_size(qr_start, qr_end):
    """Calculate the number of QR codes between the provided range."""
    match_start = re.match(r".*([A-Z])(\d{4})$", qr_start)
    match_end = re.match(r".*([A-Z])(\d{4})$", qr_end)
    if not match_start or not match_end:
        return 0
    start_alpha, start_serial = match_start.groups()
    end_alpha, end_serial = match_end.groups()
    start_serial = int(start_serial)
    end_serial = int(end_serial)
    alpha_list = list(string.ascii_uppercase)
    start_index = alpha_list.index(start_alpha)
    end_index = alpha_list.index(end_alpha)
    total_count = 0
    for offset, alpha in enumerate(alpha_list[start_index : end_index + 1]):
        if offset == 0:
            total_count += 9999 - start_serial + 1
        elif offset == (end_index - start_index):
            total_count += end_serial
        else:
            total_count += 9999
    return total_count


# ---------------- QR Scan Logic ----------------
def handle_qr_scan(qr_code, batch_line, mould_ranges, duplicate_checker=None):
    """Validate a QR code and return (status, mould).

    duplicate_checker is an optional callable that receives qr_code and
    returns True if the code has already been scanned for the active batch.
    """
    if not validate_qr_format(qr_code):
        blink_light("RED")
        buzz()
        return "INVALID FORMAT", None

    if qr_code[1] != batch_line:
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


# ---------------- CSV Logging ----------------
def init_log(batch_number):
    os.makedirs(LOG_FOLDER, exist_ok=True)
    csv_path = os.path.join(LOG_FOLDER, f"{batch_number}.csv")
    log_file = open(csv_path, mode="w", newline="")
    csv_writer = csv.writer(log_file)
    csv_writer.writerow(["Timestamp", "BatchNumber", "Mould", "QRCode", "Status"])
    return log_file, csv_writer


def write_log(csv_writer, log_file, batch_number, mould, qr_code, status):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    csv_writer.writerow([timestamp, batch_number, mould or "UNKNOWN", qr_code, status])
    log_file.flush()


def close_log(log_file):
    if log_file and not log_file.closed:
        log_file.close()


def resume_log(batch_number):
    os.makedirs(LOG_FOLDER, exist_ok=True)
    csv_path = os.path.join(LOG_FOLDER, f"{batch_number}.csv")
    file_exists = os.path.exists(csv_path)
    log_file = open(csv_path, mode="a", newline="")
    csv_writer = csv.writer(log_file)
    if not file_exists:
        csv_writer.writerow(["Timestamp", "BatchNumber", "Mould", "QRCode", "Status"])
    return log_file, csv_writer


def save_recovery_state(state_data):
    os.makedirs(LOG_FOLDER, exist_ok=True)
    recovery_path = os.path.join(LOG_FOLDER, RECOVERY_FILE)
    with open(recovery_path, "w", encoding="utf-8") as handle:
        json.dump(state_data, handle, ensure_ascii=False, indent=2)


def load_recovery_state():
    recovery_path = os.path.join(LOG_FOLDER, RECOVERY_FILE)
    try:
        with open(recovery_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        clear_recovery_state()
        return None


def clear_recovery_state():
    recovery_path = os.path.join(LOG_FOLDER, RECOVERY_FILE)
    try:
        os.remove(recovery_path)
    except FileNotFoundError:
        pass

