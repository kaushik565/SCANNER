"""
PLC firmware bridge for Raspberry Pi batch scanner.

This module encapsulates the UART + GPIO handshaking that previously lived
inside the legacy `ControllerLink` class in `main.py`.  It provides a
structured interface for talking to the PLC / PIC controller that drives the
mechanical jig:

* Firmware commands 0x14 (`SCAN_RETRY`) and 0x13 (`SCAN_FINAL`) trigger QR
  acquisitions on the Pi.
* The Pi responds with single-byte status codes ('A', 'R', 'D', 'S', ...).
* Busy/ready signalling is performed through the hardware abstraction layer
  (`hardware.set_busy`), which ultimately toggles the RASP_IN_PIC line.
* Optional framed messages allow the PLC to push sensor/button updates or LCD
  requests using the format `<TAG:PAYLOAD>`.

The class is UI-agnostic apart from needing a Tk `window` object to schedule
poll callbacks using `after()`.  This keeps the integration compatible with
the existing Tkinter application while making the controller bridge reusable
for headless scripts if needed (see `start_polling_in_background()`).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Iterable, Optional

try:  # pragma: no cover - serial optional on dev hosts
    import serial
    from serial import SerialException
except ImportError:  # pragma: no cover - allow running without pyserial
    serial = None  # type: ignore
    SerialException = Exception  # type: ignore

# ---- Firmware protocol constants ------------------------------------------------

CONTROLLER_RESPONSE_TIMEOUT_MS = 12_000  # Matches legacy firmware timeout
CMD_RETRY = 0x14  # Firmware "scan with retry" command
CMD_FINAL = 0x13  # Firmware "scan final attempt" command
BUSY_SETTLE_MS = 20  # Delay for PLC to sample RASP_IN_PIC after toggling
DEFAULT_CONTROLLER_PORTS = (
    "/dev/serial0",  # Pi alias to primary UART
    "/dev/ttyS0",
    "/dev/ttyAMA0",
    "/dev/ttyUSB0",
    "COM3",
    "COM4",
)


# ---- Events ----------------------------------------------------------------------


class PLCFrameType(Enum):
    """Structured messages emitted by the PLC when wrapped in <TAG:...> frames."""

    SENSOR = auto()
    BUTTON = auto()
    LCD = auto()
    RAW = auto()


@dataclass
class SensorEvent:
    name: str
    active: bool


@dataclass
class ButtonEvent:
    name: str
    pressed: bool


PLCScanCallback = Callable[[bool], None]
PLCLinkDownCallback = Callable[[Exception], None]
PLCSensorCallback = Callable[[SensorEvent], None]
PLCButtonCallback = Callable[[ButtonEvent], None]
PLCFrameCallback = Callable[[PLCFrameType, str], None]


class PLCHandshake:
    """
    Serial bridge that synchronises scans with the PLC controller.

    Parameters
    ----------
    hardware:
        Hardware abstraction providing `set_busy(bool)` (see `hardware.get_hardware_controller()`).
    window:
        Tk root or widget used to schedule serial polling via `after()`.  Optional if
        `start_polling_in_background()` is used instead.
    on_scan_request:
        Callback invoked with `final_attempt: bool` when PLC requests a QR scan.
    on_link_down:
        Callback invoked when serial link fails irrecoverably.
    on_sensor_update/on_button_event/on_frame:
        Optional callbacks for framed messages (`<TAG:...>`).
    """

    STATUS_MAP = {
        "A": "Accepted",
        "R": "Rejected",
        "D": "Duplicate QR",
        "S": "Scanner Error",
        "Q": "No QR",
        "L": "Length Error",
        "B": "Logging Error",
        "C": "Repeated Testing",
        "H": "Hardware Error",
    }

    def __init__(
        self,
        hardware,
        window,
        on_scan_request: Optional[PLCScanCallback],
        *,
        on_link_down: Optional[PLCLinkDownCallback] = None,
        on_sensor_update: Optional[PLCSensorCallback] = None,
        on_button_event: Optional[PLCButtonCallback] = None,
        on_frame: Optional[PLCFrameCallback] = None,
        ports: Iterable[str] = DEFAULT_CONTROLLER_PORTS,
        baudrate: int = 115200,
        poll_interval_ms: int = 20,
    ) -> None:
        self._hardware = hardware
        self._window = window
        self._on_scan_request = on_scan_request
        self._on_link_down = on_link_down
        self._on_sensor_update = on_sensor_update
        self._on_button_event = on_button_event
        self._on_frame = on_frame
        self._ports = tuple(ports)
        self._baudrate = baudrate
        self._poll_interval_ms = poll_interval_ms
        self._serial: Optional[serial.Serial] = None  # type: ignore[assignment]
        self._after_id = None
        self._pending = False
        self._busy_low = False
        self._active = False
        self._logger = logging.getLogger("plc.handshake")

        # Framed message state (`<TAG:...>` style payloads)
        self._frame_active = False
        self._frame_buffer: list[str] = []

        # Background polling thread for headless usage
        self._bg_thread: Optional[threading.Thread] = None
        self._bg_stop = threading.Event()

        if serial is None:
            self._logger.info("pyserial not available; PLC handshake disabled")
            return

        self._connect()

    # ------------------------------------------------------------------
    # Connection & polling helpers
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        for port in self._ports:
            try:
                ser = serial.Serial(  # type: ignore[call-arg]
                    port=port,
                    baudrate=self._baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0,
                )
                ser.reset_input_buffer()
            except SerialException as exc:
                self._logger.warning("Unable to open %s: %s", port, exc)
                continue
            except Exception as exc:  # pragma: no cover - serial discovery edge-case
                self._logger.warning("Unexpected error on %s: %s", port, exc)
                continue

            self._serial = ser
            self._active = True
            self._logger.info("Linked to PLC controller on %s", port)
            self._schedule_poll(initial=True)
            return

        self._serial = None
        self._active = False
        self._logger.error("Unable to locate PLC controller serial port; handshake disabled")

    def _schedule_poll(self, *, initial: bool = False) -> None:
        if not self._serial:
            return
        if self._window is None:
            return
        if self._after_id is not None:
            return

        delay = 0 if initial else self._poll_interval_ms
        self._after_id = self._window.after(delay, self._poll_serial)  # type: ignore[attr-defined]

    def start_polling_in_background(self) -> None:
        """Use a background thread for polling when Tk's event loop is unavailable."""
        if not self._serial:
            return
        if self._bg_thread and self._bg_thread.is_alive():
            return

        def _loop() -> None:
            while not self._bg_stop.is_set():
                self._poll_serial()
                self._bg_stop.wait(self._poll_interval_ms / 1000.0)

        self._bg_stop.clear()
        self._bg_thread = threading.Thread(target=_loop, daemon=True)
        self._bg_thread.start()

    def stop_background_polling(self) -> None:
        if self._bg_thread:
            self._bg_stop.set()
            self._bg_thread.join(timeout=1.5)
            self._bg_thread = None

    def _poll_serial(self) -> None:
        self._after_id = None
        if not self._serial:
            return

        try:
            while True:
                chunk = self._serial.read(1)
                if not chunk:
                    break
                self._handle_firmware_response(chunk[0])
        except SerialException as exc:
            self._handle_serial_failure(exc)
            return
        except Exception as exc:  # pragma: no cover - defensive
            self._handle_serial_failure(exc)
            return

        # Reschedule polling when Tk loop is used
        self._schedule_poll()

    # ------------------------------------------------------------------
    # Incoming byte handling
    # ------------------------------------------------------------------

    def _handle_firmware_response(self, code: int) -> None:
        if code in (CMD_RETRY, CMD_FINAL):
            self._logger.info(
                "Scan request received from PLC (%s)",
                "FINAL" if code == CMD_FINAL else "RETRY",
            )
            self._handle_scan_command(final_attempt=(code == CMD_FINAL))
            return

        char = chr(code)

        if char == "<":
            self._frame_active = True
            self._frame_buffer.clear()
            return
        if char == ">" and self._frame_active:
            payload = "".join(self._frame_buffer).strip()
            self._frame_active = False
            self._frame_buffer.clear()
            if payload:
                self._dispatch_frame(payload)
            return
        if self._frame_active:
            # Only accumulate printable characters
            if char.isprintable():
                self._frame_buffer.append(char)
            return

        if char in self.STATUS_MAP:
            self._logger.info("PLC status: %s - %s", char, self.STATUS_MAP[char])
            return

        if char in ("\r", "\n"):
            return  # Ignore stray line endings

        # Unrecognised data – forward upstream for troubleshooting
        if self._on_frame:
            self._on_frame(PLCFrameType.RAW, char)
        else:
            self._logger.debug("Ignoring unexpected byte 0x%02X (%r)", code, char)

    def _dispatch_frame(self, payload: str) -> None:
        """
        Parse framed payloads coming from the PLC.

        Supported formats:
            <SNS:name:value>   -> sensor update (value truthy = active)
            <BTN:name:value>   -> button state (value truthy = pressed)
            <LCD:line1|line2>  -> request Pi to update its UI/log with PLC text
        Any other payload is surfaced via `on_frame` as RAW.
        """
        if ":" not in payload:
            if self._on_frame:
                self._on_frame(PLCFrameType.RAW, payload)
            else:
                self._logger.debug("PLC frame (raw): %s", payload)
            return

        tag, body = payload.split(":", 1)
        tag_upper = tag.strip().upper()

        if tag_upper == "SNS":
            parts = body.split(":", 1)
            if len(parts) != 2:
                self._logger.warning("Malformed sensor frame: %s", payload)
                return
            name, value = parts
            active = value.strip() not in ("0", "OFF", "FALSE", "false")
            event = SensorEvent(name=name.strip(), active=active)
            if self._on_sensor_update:
                self._on_sensor_update(event)
            else:
                self._logger.info("Sensor update: %s -> %s", event.name, event.active)
            return

        if tag_upper == "BTN":
            parts = body.split(":", 1)
            if len(parts) != 2:
                self._logger.warning("Malformed button frame: %s", payload)
                return
            name, value = parts
            pressed = value.strip() not in ("0", "UP", "RELEASED", "OFF")
            event = ButtonEvent(name=name.strip(), pressed=pressed)
            if self._on_button_event:
                self._on_button_event(event)
            else:
                self._logger.info("Button event: %s -> %s", event.name, event.pressed)
            return

        if tag_upper == "LCD":
            if self._on_frame:
                self._on_frame(PLCFrameType.LCD, body)
            else:
                self._logger.info("PLC LCD request: %s", body)
            return

        if self._on_frame:
            self._on_frame(PLCFrameType.RAW, payload)
        else:
            self._logger.debug("Unhandled PLC frame: %s", payload)

    # ------------------------------------------------------------------
    # Scan request handling
    # ------------------------------------------------------------------

    def _handle_scan_command(self, final_attempt: bool) -> None:
        self._pending = True
        if not self._busy_low:
            self._set_busy(False)  # Drive BUSY (RASP_IN_PIC LOW) before scanning
            self._busy_low = True

        if self._serial:
            try:
                self._serial.reset_input_buffer()
            except Exception:  # pragma: no cover - serial drivers differ
                pass

        if self._on_scan_request:
            self._on_scan_request(final_attempt)

    # ------------------------------------------------------------------
    # Outgoing helpers
    # ------------------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        try:
            self._hardware.set_busy(busy)
        except Exception as exc:  # pragma: no cover - hardware fallback path
            self._logger.warning("Failed to drive busy line (%s): %s", busy, exc)

    def _release_busy(self) -> None:
        if self._busy_low:
            self._set_busy(True)
            self._busy_low = False

    def send_result(self, status: str) -> bool:
        """Send QR validation result to PLC ('A', 'R', 'D', 'S')."""
        return self.send_code(self._map_status(status), reason=f"status={status}")

    def _map_status(self, status: str) -> str:
        normalized = (status or "").upper()
        if normalized == "PASS":
            return "A"
        if normalized == "DUPLICATE":
            return "D"
        if normalized in {"INVALID FORMAT", "LINE MISMATCH", "OUT OF BATCH"}:
            return "R"
        return "S"

    def send_code(self, code: str, reason: str = "") -> bool:
        if not code or not self._serial or not self._pending:
            self._logger.debug(
                "send_code skipped (code=%r, serial=%s, pending=%s)",
                code,
                bool(self._serial),
                self._pending,
            )
            return False
        try:
            self._serial.write(code.encode("ascii"))
            self._serial.flush()
            self._logger.debug("Sent %r (%s)", code, reason)
        except SerialException as exc:
            self._logger.error("Serial exception sending %r: %s", code, exc)
            self._handle_serial_failure(exc)
            return False
        except Exception as exc:  # pragma: no cover - serial edge-case
            self._logger.error("Unexpected error sending %r: %s", code, exc)
            self._handle_serial_failure(exc)
            return False
        finally:
            self._pending = False
            self._release_busy()
        return True

    def send_oob_code(self, code: str) -> bool:
        """Send a one-byte out-of-band code regardless of scan pending state."""
        if not code or not self._serial:
            return False
        try:
            self._serial.write(code.encode("ascii"))
            self._serial.flush()
            return True
        except SerialException as exc:
            self._handle_serial_failure(exc)
            return False
        except Exception as exc:  # pragma: no cover
            self._handle_serial_failure(exc)
            return False

    def send_frame(self, tag: str, body: str) -> bool:
        """Send a structured frame `<TAG:body>` to the PLC."""
        if not tag:
            raise ValueError("tag must be non-empty")
        if not self._serial:
            return False
        payload = f"<{tag}:{body}>"
        try:
            self._serial.write(payload.encode("ascii"))
            self._serial.flush()
            return True
        except SerialException as exc:
            self._handle_serial_failure(exc)
            return False
        except Exception as exc:  # pragma: no cover
            self._handle_serial_failure(exc)
            return False

    def cancel_pending(self, fallback_code: str = "S", reason: str = "") -> None:
        if not self._pending:
            return
        if not self._serial:
            self._pending = False
            self._release_busy()
            return
        if not self.send_code(fallback_code, reason or "cancel_pending"):
            self._pending = False
            self._release_busy()

    # ------------------------------------------------------------------
    # Link status & teardown
    # ------------------------------------------------------------------

    def _handle_serial_failure(self, exc: Exception) -> None:
        self._logger.error("PLC link lost: %s", exc)
        if self._after_id is not None and self._window is not None:
            try:
                self._window.after_cancel(self._after_id)  # type: ignore[attr-defined]
            except Exception:
                pass
            self._after_id = None
        self.stop_background_polling()
        self._release_busy()
        self._pending = False
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._active = False
        if self._on_link_down:
            try:
                self._on_link_down(exc)
            except Exception:
                self._logger.exception("PLC on_link_down callback failed")

    def has_pending(self) -> bool:
        return self._pending

    @property
    def active(self) -> bool:
        return self._active

    def close(self) -> None:
        if self._after_id is not None and self._window is not None:
            try:
                self._window.after_cancel(self._after_id)  # type: ignore[attr-defined]
            except Exception:
                pass
            self._after_id = None

        self.stop_background_polling()

        if self._pending and self._serial:
            try:
                self.send_code("S", "closing")
            except Exception:
                self._pending = False
                self._release_busy()
        else:
            self._pending = False
            self._release_busy()

        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._active = False


# Backwards compatibility alias for existing imports in main.py
ControllerLink = PLCHandshake

