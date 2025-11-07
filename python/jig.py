"""Jig operation controller: auto-feed cartridges to the scanner in a loop.

This module provides a state machine that controls the pusher cylinder and
monitors sensors to bring one cartridge to the scan position, wait for a scan
result from the UI, then advance the next cartridge.

Two implementations are provided:
- MockJigController: runs everywhere, logs actions, no GPIO.
- GPIOJigController: uses RPi.GPIO to drive outputs and read inputs.

Integration contract with UI (BatchScannerApp):
- Call get_jig_controller() to create a controller when a batch starts.
- Call jig.start() after UI enters scan mode; call jig.stop() when stopping.
- On every scan, call jig.notify_scan(status) with one of:
  "PASS", "DUPLICATE", "INVALID FORMAT", "LINE MISMATCH", "OUT OF BATCH".

Configuration comes from config.py [jig] section defaults if settings.ini
doesn't declare them explicitly.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from config import (
    HARDWARE_CONTROLLER,
    JIG_ADVANCE_ON_FAIL,
    JIG_ENABLED,
    JIG_INPUT_PINS,
    JIG_OUTPUT_PINS,
    JIG_TIMINGS_MS,
)

try:  # pragma: no cover - hardware optional
    import RPi.GPIO as GPIO  # type: ignore
except (ImportError, RuntimeError):  # pragma: no cover - hardware optional
    GPIO = None


SCAN_STATUSES_ADVANCE_ON = {"PASS"}


@dataclass
class JigConfig:
    advance_on_fail: bool
    timings_ms: Dict[str, int]
    outputs: Dict[str, int]
    inputs: Dict[str, int]


class BaseJigController:
    """Interface for jig operations."""

    def start(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def notify_scan(self, status: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class MockJigController(BaseJigController):
    def __init__(self, cfg: JigConfig) -> None:
        self._log = logging.getLogger("jig")
        self._cfg = cfg
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._scan_evt = threading.Event()
        self._last_status: Optional[str] = None

    # Sensor stubs (could be evolved to simulate changes if desired)
    def _sensor(self, name: str) -> bool:
        # For mock: assume stack present and safety ok, and "at_scanner" true
        return name in {"stack_present", "safety_ok", "at_scanner"}

    def _set_output(self, name: str, state: bool) -> None:
        pin = self._cfg.outputs.get(name, 0)
        if pin == 0:
            self._log.debug("OUTPUT %s -> %s (ASECT controlled)", name, "ON" if state else "OFF")
        else:
            self._log.debug("OUTPUT %s -> %s (GPIO %d)", name, "ON" if state else "OFF", pin)

    def notify_scan(self, status: str) -> None:
        self._log.debug("Scan status received: %s", status)
        self._last_status = status.upper().strip()
        self._scan_evt.set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._scan_evt.clear()
        self._thread = threading.Thread(target=self._run_loop, name="JigLoop", daemon=True)
        self._thread.start()
        self._log.info("Jig loop started (mock)")

    def stop(self) -> None:
        self._stop_evt.set()
        self._scan_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._log.info("Jig loop stopped")

    def _wait(self, ms: int) -> None:
        # Responsive sleep respecting stop signal
        end = time.time() + ms / 1000.0
        while not self._stop_evt.is_set() and time.time() < end:
            time.sleep(0.01)

    def _run_loop(self) -> None:
        cfg = self._cfg
        while not self._stop_evt.is_set():
            # Safety & supplies
            if not self._sensor("safety_ok"):
                self._log.warning("Safety not OK; waiting…")
                self._wait(200)
                continue
            if not self._sensor("stack_present"):
                self._log.info("No cartridges in stack; waiting…")
                self._wait(500)
                continue

            # Advance one cartridge: extend -> retract
            self._set_output("pusher_extend", True)
            self._set_output("pusher_retract", False)
            self._wait(cfg.timings_ms.get("push_extend_ms", 400))
            self._set_output("pusher_extend", False)
            self._set_output("pusher_retract", True)
            self._wait(cfg.timings_ms.get("push_retract_ms", 400))
            self._set_output("pusher_retract", False)
            self._wait(cfg.timings_ms.get("settle_ms", 200))

            # Wait for part to be at scanner (mock instantly true)
            detect_ms = cfg.timings_ms.get("detect_timeout_ms", 3000)
            self._log.debug("Waiting for at_scanner (<= %d ms)…", detect_ms)
            self._wait(min(100, detect_ms))

            # Wait for scan
            self._scan_evt.clear()
            timeout_ms = cfg.timings_ms.get("scan_timeout_ms", 5000)
            self._log.debug("Waiting for scan result (<= %d ms)…", timeout_ms)
            self._scan_evt.wait(timeout=timeout_ms / 1000.0)
            status = (self._last_status or "").upper()

            if not status:
                self._log.info("No scan within timeout; %s advancing", "still" if cfg.advance_on_fail else "not")
                if not cfg.advance_on_fail:
                    # Give it another chance
                    continue
            else:
                self._log.info("Scan: %s", status)
                if not cfg.advance_on_fail and status not in SCAN_STATUSES_ADVANCE_ON:
                    # Wait again for a good scan
                    self._log.debug("Holding for PASS; retrying wait…")
                    continue

            # Loop to feed next
            continue


class GPIOJigController(BaseJigController):  # pragma: no cover - hardware dependent
    def __init__(self, cfg: JigConfig) -> None:
        if GPIO is None:
            raise RuntimeError("RPi.GPIO not available on this system")
        self._log = logging.getLogger("jig")
        self._cfg = cfg
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._scan_evt = threading.Event()
        self._last_status: Optional[str] = None

        GPIO.setwarnings(False)
        # Use BCM numbering consistently with hardware config
        GPIO.setmode(GPIO.BCM)

        # Configure only red and green outputs
        for name, pin in cfg.outputs.items():
            if name in ("red", "green") and pin:
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

        # Configure inputs (pull-ups to reduce noise; adjust per wiring)
        for name, pin in self._cfg.inputs.items():
            if pin:  # Skip pins set to 0 (ASECT controlled)
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def set_light(self, result):
        # result: "pass" or "reject"
        if result == "pass":
            self._set_output("green", True)
            self._set_output("red", False)
        elif result == "reject":
            self._set_output("green", False)
            self._set_output("red", True)
        else:
            self._set_output("green", False)
            self._set_output("red", False)

    def _sensor(self, name: str) -> bool:
        pin = self._cfg.inputs.get(name)
        if pin is None or pin == 0:
            # Pin 0 means handled by ASECT controller - assume OK
            return name in {"safety_ok", "stack_present"}
        # Active-low sensors if using pull-ups; invert here
        return GPIO.input(pin) == GPIO.LOW

    def _set_output(self, name: str, state: bool) -> None:
        pin = self._cfg.outputs.get(name)
        if pin is None or pin == 0:
            # Pin 0 means handled by ASECT controller - skip GPIO control
            return
        GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)

    def notify_scan(self, status: str) -> None:
        self._last_status = status.upper().strip()
        self._scan_evt.set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._scan_evt.clear()
        self._thread = threading.Thread(target=self._run_loop, name="JigLoop", daemon=True)
        self._thread.start()
        self._log.info("Jig loop started (GPIO)")

    def stop(self) -> None:
        self._stop_evt.set()
        self._scan_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        # Make safe: de-energize outputs
        for name, pin in self._cfg.outputs.items():
            try:
                GPIO.output(pin, GPIO.LOW)
            except Exception:
                pass
        self._log.info("Jig loop stopped")

    def _wait_until(self, cond_name: str, timeout_ms: int) -> bool:
        deadline = time.time() + timeout_ms / 1000.0
        while time.time() < deadline and not self._stop_evt.is_set():
            if self._sensor(cond_name):
                return True
            time.sleep(0.01)
        return False

    def _run_loop(self) -> None:
        cfg = self._cfg
        while not self._stop_evt.is_set():
            if not self._sensor("safety_ok"):
                time.sleep(0.1)
                continue
            if not self._sensor("stack_present"):
                time.sleep(0.2)
                continue

            # Extend pusher
            self._set_output("pusher_extend", True)
            self._set_output("pusher_retract", False)
            self._wait_until("pusher_extended", cfg.timings_ms.get("push_extend_ms", 400))

            # Retract pusher
            self._set_output("pusher_extend", False)
            self._set_output("pusher_retract", True)
            self._wait_until("pusher_retracted", cfg.timings_ms.get("push_retract_ms", 400))
            self._set_output("pusher_retract", False)
            time.sleep(cfg.timings_ms.get("settle_ms", 200) / 1000.0)

            # Wait for part at scanner position
            self._wait_until("at_scanner", cfg.timings_ms.get("detect_timeout_ms", 3000))

            # Wait for scan result from UI
            self._scan_evt.clear()
            self._scan_evt.wait(timeout=cfg.timings_ms.get("scan_timeout_ms", 5000) / 1000.0)
            status = (self._last_status or "").upper()
            if not cfg.advance_on_fail and status not in SCAN_STATUSES_ADVANCE_ON:
                # Wait again; do not feed next until PASS
                continue


def get_jig_controller() -> Optional[BaseJigController]:
    """Factory that returns a jig controller or None if disabled."""
    if not JIG_ENABLED:
        return None

    from config import HARDWARE_PINS
    
    # Combine jig outputs with hardware pins for lights
    all_outputs = dict(JIG_OUTPUT_PINS)
    all_outputs.update({
        "red": HARDWARE_PINS["red"],
        "green": HARDWARE_PINS["green"]
    })
    
    cfg = JigConfig(
        advance_on_fail=JIG_ADVANCE_ON_FAIL,
        timings_ms=JIG_TIMINGS_MS,
        outputs=all_outputs,
        inputs=JIG_INPUT_PINS,
    )

    if HARDWARE_CONTROLLER.lower().strip() == "gpio" and GPIO is not None:
        try:
            return GPIOJigController(cfg)
        except Exception as exc:  # pragma: no cover - fallback
            logging.getLogger("jig").exception("Falling back to mock jig: %s", exc)
    return MockJigController(cfg)
