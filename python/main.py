import csv
import logging
import os
import socket
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

# GPIO setup for PIC communication - CORRECTED PIN ASSIGNMENTS
# These pins must match Pin_Definitions.h in firmware:
# GPIO 18: Connected to RASP_IN_PIC (RB6) - Pi status signal to PIC
# GPIO 24: Connected to INT_PIC (RB5) - Interrupt signal to PIC  
# GPIO 25: Connected to SHD_PIC (RB7) - Shutdown signal from PIC
gpio_available = False
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    
    # CRITICAL: Set up all control pins
    GPIO.setup(18, GPIO.OUT)  # RASP_IN_PIC - Pi status to PIC
    GPIO.setup(24, GPIO.OUT)  # INT_PIC - Interrupt to PIC
    GPIO.setup(25, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # SHD_PIC - Shutdown from PIC
    
    # Initialize to safe states
    GPIO.output(18, GPIO.LOW)   # Start as BUSY - batch setup not complete
    GPIO.output(24, GPIO.LOW)   # No interrupt initially
    
    gpio_available = True
    print("GPIO pins 18, 24, 25 initialized for PIC communication")
    print("GPIO 18 (RASP_IN_PIC) = LOW - Pi in setup mode")
    print("GPIO 24 (INT_PIC) = LOW - No interrupt")
    print("GPIO 25 (SHD_PIC) = INPUT - Shutdown monitoring")
except Exception as e:
    print(f"GPIO setup failed: {e}")

def set_pi_ready_state(ready=True):
    """Set GPIO 18 to signal PIC about Pi readiness
    ready=True: GPIO HIGH (Pi ready for commands)
    ready=False: GPIO LOW (Pi busy, don't send commands)
    """
    if gpio_available:
        try:
            GPIO.output(18, GPIO.HIGH if ready else GPIO.LOW)
            state = "READY" if ready else "BUSY"
            print(f"GPIO 18 (RASP_IN_PIC) set to signal Pi is {state}")
        except Exception as e:
            print(f"GPIO control failed: {e}")

def send_interrupt_to_pic():
    """Send interrupt pulse to PIC via GPIO 24"""
    if gpio_available:
        try:
            GPIO.output(24, GPIO.HIGH)
            time.sleep(0.001)  # 1ms pulse
            GPIO.output(24, GPIO.LOW)
            print("Interrupt pulse sent to PIC via GPIO 24")
        except Exception as e:
            print(f"Interrupt signal failed: {e}")

def check_shutdown_signal():
    """Check if PIC is requesting shutdown via GPIO 25"""
    if gpio_available:
        try:
            return not GPIO.input(25)  # Active low signal
        except Exception as e:
            print(f"Shutdown check failed: {e}")
            return False
    return False

try:  # Optional dependency – skip controller sync if unavailable
    import serial
    try:
        from serial.tools import list_ports
    except (ImportError, AttributeError):  # pragma: no cover - pyserial minimal install
        list_ports = None
except ImportError:  # pragma: no cover - dev environments without pyserial
    serial = None
    list_ports = None

from config import (
    ENTRY_WIDTH,
    INFO_TEXT_COLOR,
    QR_WIDTH,
    SETUP_LOG_FOLDER,
    SUCCESS_TEXT_COLOR,
    CARD_BORDER,
    TEXT_PRIMARY,
    TEXT_MUTED,
    AUTO_ADVANCE,
    TITLE_FONT,
    SUBTITLE_FONT,
    BODY_FONT,
    SMALL_FONT,
    SCAN_STATUS_FONT,
    SCAN_COUNTER_FONT,
    BUTTON_FONT,
    PADDING_X,
    PADDING_Y,
    SECTION_GAP,
    CAMERA_ENABLED,
    CAMERA_PORT,
    CAMERA_BAUDRATE,
    CAMERA_TIMEOUT,
)
from duplicate_tracker import DuplicateTracker
from layout import create_main_window
from logic import (
    batch_number_validator,
    clear_recovery_state,
    close_log,
    force_uppercase,
    handle_qr_scan,
    highlight_invalid,
    init_log,
    load_recovery_state,
    line_validator,
    mould_name_validator,
    num_moulds_validator,
    qr_validator,
    resume_log,
    set_hardware_error_handler,
    save_recovery_state,
    write_log,
)
from hardware import get_hardware_controller
from plc_firmware import (
    BUSY_SETTLE_MS,
    CONTROLLER_RESPONSE_TIMEOUT_MS,
    ControllerLink,
    DEFAULT_CONTROLLER_PORTS,
    ButtonEvent,
    PLCFrameType,
    SensorEvent,
)

STATUS_TEXT_COLORS = {
    "PASS": "#e8ffe8",
    "DUPLICATE": "#fff3e0",
    "READY": "#ffffff",
    "INVALID FORMAT": "#ffebee",
    "LINE MISMATCH": "#ffebee",
    "OUT OF BATCH": "#ffebee",
}

STATUS_BG_COLORS = {
    "PASS": "#20ed2a",
    "DUPLICATE": "#eae20d",
    "READY": "#263238",
    "INVALID FORMAT": "#f50a0a",
    "LINE MISMATCH": "#f21313",
    "OUT OF BATCH": "#ef1515",
}

class CameraQRScanner:
    """
    Automatic QR scanner using serial camera interface.
    Compatible with /dev/qrscanner hardware from SCANNER project.
    """
    
    def __init__(self, port="/dev/qrscanner", baudrate=115200, timeout=5, on_qr_detected=None):
        """
        Initialize camera QR scanner.
        
        Args:
            port: Serial port for QR camera (default: /dev/qrscanner)
            baudrate: Serial baudrate for the camera interface
            timeout: Read timeout in seconds
            on_qr_detected: Callback function(qr_code) when QR is detected
        """
        self.preferred_port = port
        self.port = None
        self.baudrate = baudrate
        self.timeout = timeout
        self.on_qr_detected = on_qr_detected
        self.scanner = None
        self.running = False
        self.scan_thread = None
        self._logger = logging.getLogger("CameraQRScanner")

    def _candidate_ports(self):
        """Return prioritized list of serial ports to probe for the camera scanner."""
        candidates = []
        seen = set()

        def add(port):
            if not port or port in seen:
                return
            seen.add(port)
            candidates.append(port)

        add(self.preferred_port)

        if serial and list_ports:
            port_candidates = []
            try:
                for info in list_ports.comports():
                    device = info.device
                    if not device or device in DEFAULT_CONTROLLER_PORTS:
                        continue
                    descriptor = " ".join(
                        filter(None, [info.device, getattr(info, "description", ""), getattr(info, "hwid", "")])
                    ).lower()
                    priority = 5
                    if any(keyword in descriptor for keyword in ("qr", "scan", "barcode", "matrix")):
                        priority = 0
                    elif device.startswith("/dev/ttyUSB") or device.startswith("/dev/ttyACM"):
                        priority = 1
                    elif device.startswith("/dev/ttyAMA") or device.startswith("/dev/ttyS"):
                        priority = 2
                    port_candidates.append((priority, device))
            except Exception as exc:  # pragma: no cover - diagnostics only
                self._logger.debug("Unable to enumerate serial ports: %s", exc)
            else:
                for _, device in sorted(port_candidates):
                    add(device)

        for fallback in ("/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1"):
            if fallback in DEFAULT_CONTROLLER_PORTS:
                continue
            add(fallback)

        return candidates
        
    def connect(self):
        """Open connection to camera scanner."""
        if serial is None:
            raise RuntimeError("pyserial not installed - cannot use camera scanner")

        candidates = self._candidate_ports()
        if not candidates:
            self._logger.error("Failed to locate any serial ports to probe for the camera scanner")
            return False

        last_error = None
        for port in candidates:
            if os.name != "nt" and not os.path.exists(port):
                self._logger.debug("Skipping missing port %s", port)
                continue
            try:
                self.scanner = serial.Serial(
                    port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                )
                self.port = port
                self._logger.info(f"Camera scanner connected on {port}")
                return True
            except Exception as exc:
                last_error = exc
                self._logger.debug("Camera scanner not available on %s: %s", port, exc)

        self.scanner = None
        self.port = None
        if last_error:
            self._logger.error(
                "Failed to connect camera scanner; attempted ports: %s (last error: %s)",
                ", ".join(candidates),
                last_error,
            )
        else:
            self._logger.error(
                "Failed to connect camera scanner; none of the candidate ports are present: %s",
                ", ".join(candidates),
            )
        return False
    
    def start_scanning(self):
        """Start automatic QR detection in background thread."""
        if self.scanner is None:
            self._logger.warning("Cannot start scan - scanner not connected")
            return False
        
        if self.running:
            self._logger.warning("Scan already in progress")
            return False
        
        self.running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        self._logger.info("Camera scanning started")
        return True
    
    def stop_scanning(self):
        """Stop automatic QR detection."""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=2.0)
        self._logger.info("Camera scanning stopped")
    
    def _trigger_scan(self):
        """Send trigger command to camera to capture QR code."""
        try:
            # Command structure from SCANNER/matrix.py
            trigger_cmd = bytes([0x7E, 0x00, 0x08, 0x01, 0x00, 0x02, 0x01, 0xAB, 0xCD, 0x00])
            
            self.scanner.flush()
            self.scanner.write(trigger_cmd)
            
            # Read 7-byte response header
            response = self.scanner.read(size=7)
            
            if len(response) != 7:
                self._logger.warning(f"Invalid response length: {len(response)}")
                return None
            
            # Check for success response: 02 00 00 01 00 33 31
            if (response[0] == 0x02 and response[1] == 0x00 and 
                response[2] == 0x00 and response[3] == 0x01 and
                response[4] == 0x00 and response[5] == 0x33 and 
                response[6] == 0x31):
                
                # Read QR code data (up to 50 bytes)
                qr_data = self.scanner.readline(50)
                qr_text = qr_data.decode('utf-8', errors='ignore').strip()
                
                if len(qr_text) >= 10:  # Minimum valid QR length
                    self._logger.info(f"QR detected: {qr_text}")
                    return qr_text
                else:
                    self._logger.warning(f"QR too short: '{qr_text}'")
                    return None
            else:
                self._logger.warning(f"Bad response: {response.hex()}")
                return None
                
        except Exception as e:
            self._logger.error(f"Scan trigger error: {e}")
            return None
    
    def _scan_loop(self):
        """Background thread that continuously triggers scans."""
        last_qr = None
        
        while self.running:
            try:
                qr_code = self._trigger_scan()
                
                if qr_code and qr_code != last_qr:
                    last_qr = qr_code
                    
                    # Call callback with detected QR
                    if self.on_qr_detected:
                        self.on_qr_detected(qr_code)
                    
                    # Stop after successful detection
                    self.running = False
                    break
                
                time.sleep(0.3)  # Brief delay between scans
                
            except Exception as e:
                self._logger.error(f"Scan loop error: {e}")
                time.sleep(1)  # Longer delay on error
    
    def close(self):
        """Close scanner connection."""
        self.stop_scanning()
        if self.scanner:
            try:
                self.scanner.close()
                self._logger.info("Camera scanner closed")
            except Exception as e:
                self._logger.error(f"Error closing scanner: {e}")
        self.scanner = None
        self.port = None
class BatchScannerApp:
    def __init__(self, window, hardware_controller=None):
        self.window = window
        self.setup_frame = None
        self.scan_frame = None
        self.start_scan_btn = None
        self.create_fields_button = None
        self.dynamic_widgets = []
        self.mould_rows = []
        self.mould_ranges = {}
        self.duplicate_tracker = DuplicateTracker()
        self.csv_writer = None
        self.log_file = None
        self.batch_number = ""
        self.batch_line = ""
        self.counters = {"accepted": 0, "duplicate": 0, "rejected": 0, "total": 0}
        self.scanning_active = False
        self.last_qr = "None"
        self.last_status = "READY"
        self.session_start = None
        self.banner_after_id = None
        self.auto_advance = AUTO_ADVANCE
        # Use pre-initialized hardware controller if provided (from launch_app)
        self.hardware = hardware_controller if hardware_controller else get_hardware_controller()
        self.controller_link = None
        self.awaiting_hardware = False
        self._controller_timeout_id = None
        self._manual_scan_timeout_id = None
        
        # Initialize camera QR scanner
        self.camera_scanner = None
        self._init_camera_scanner()

        self._build_setup_frame()
        self._build_scan_frame()
        self._maybe_resume_session()
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        set_hardware_error_handler(self._on_hardware_error)

        # Initialize hardware pins to match firmware expectations
        if not hardware_controller:
            try:
                self.hardware.set_busy(True)  # RASP_IN_PIC HIGH (Pi ready)
            except Exception as exc:
                logging.getLogger("hardware").warning("Unable to assert busy line: %s", exc)

        try:
            self.controller_link = ControllerLink(
                self.hardware,
                self.window,
                self._handle_controller_request,
                on_link_down=self._on_controller_link_down,
                on_sensor_update=self._on_plc_sensor_update,
                on_button_event=self._on_plc_button_event,
                on_frame=self._on_plc_frame,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            logging.getLogger("actj.sync").exception("Controller link setup failed: %s", exc)
            self.controller_link = None
        if self.controller_link and self.controller_link.active:
            try:
                self.controller_link.send_oob_code("H")
                logging.getLogger("actj.sync").info("Initialised controller link; sent 'H' (setup) to firmware")
            except Exception as exc:
                logging.getLogger("actj.sync").warning("Unable to send initial setup signal: %s", exc)

    # (Stacker sensor and LCD messaging handled by PLC/PIC only)
    
    def _init_camera_scanner(self):
        """Initialize automatic camera QR scanner (same hardware as SCANNER project)."""
        if not CAMERA_ENABLED:
            logging.getLogger("camera").info("Camera scanner disabled in config")
            return
            
        try:
            self.camera_scanner = CameraQRScanner(
                port=CAMERA_PORT,
                baudrate=CAMERA_BAUDRATE,
                timeout=CAMERA_TIMEOUT,
                on_qr_detected=self._on_camera_qr_detected,
            )

            # Try to connect (will fail gracefully if hardware not present)
            if self.camera_scanner.connect():
                active_port = self.camera_scanner.port or CAMERA_PORT
                logging.getLogger("camera").info(f"Camera QR scanner ready on {active_port}")
            else:
                logging.getLogger("camera").warning("Camera scanner not available - using manual entry")
                self.camera_scanner = None
        except Exception as e:
            logging.getLogger("camera").warning(f"Camera scanner initialization failed: {e}")
            self.camera_scanner = None
        
        # Connect camera scanner to legacy integration if available
        try:
            from actj_legacy_integration import get_legacy_integration, is_legacy_mode
            if is_legacy_mode() and self.camera_scanner:
                legacy = get_legacy_integration(camera_scanner=self.camera_scanner)
                logging.getLogger("camera").info("Camera scanner connected to ACTJv20 UART protocol")
        except ImportError:
            pass  # Legacy integration not available
    
    def _on_camera_qr_detected(self, qr_code):
        """Called when camera automatically detects a QR code."""
        # Update UI with scanned QR (runs in background thread, so use after())
        self.window.after(0, self._process_camera_qr, qr_code)
    
    def _process_camera_qr(self, qr_code):
        """Process QR code detected by camera (runs in main thread)."""
        logger = logging.getLogger("camera")
        logger.info(f"Camera detected QR: {qr_code}")
        
        # Only process if firmware is waiting for scan result
        if not self.awaiting_hardware:
            logger.warning("Camera QR detected but firmware not waiting - ignoring")
            return
        
        # Update entry field
        self.qr_entry.delete(0, tk.END)
        self.qr_entry.insert(0, qr_code)
        
        # Trigger validation as if user pressed Enter
        self._scan_qr_event(None)
    # ---------------- UI Construction ----------------
    def _build_setup_frame(self):
        self.setup_frame = tk.Frame(self.window, bg="black", padx=16, pady=16)

        tk.Label(
            self.setup_frame,
            text="Batch Setup",
            font=TITLE_FONT,
            bg="black",
            fg=TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, PADDING_Y))

        indicator_text = "Auto Advance: ON" if self.auto_advance else "Auto Advance: OFF"
        indicator_color = "#0ea5e9" if self.auto_advance else TEXT_MUTED
        tk.Label(
            self.setup_frame,
            text=indicator_text,
            font=SMALL_FONT,
            bg="black",
            fg=indicator_color,
        ).pack(anchor="w", pady=(0, PADDING_Y // 2))

        default_hint = (
            "Focus moves automatically after valid entries."
            if self.auto_advance
            else "Auto advance is off – press Tab or tap to move ahead."
        )
        self.auto_hint_var = tk.StringVar(value=default_hint)
        tk.Label(
            self.setup_frame,
            textvariable=self.auto_hint_var,
            font=SMALL_FONT,
            bg="black",
            fg=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, SECTION_GAP // 2))

        content_wrapper = tk.Frame(self.setup_frame, bg="black")
        content_wrapper.pack(fill="both", expand=True)

        self.setup_canvas = tk.Canvas(content_wrapper, bg="black", highlightthickness=0, relief="flat")
        self.setup_scrollbar = tk.Scrollbar(content_wrapper, orient="vertical", command=self.setup_canvas.yview)
        self.setup_canvas.configure(yscrollcommand=self.setup_scrollbar.set)
        self.setup_canvas.pack(side="left", fill="both", expand=True)
        self.setup_scrollbar.pack(side="right", fill="y")
        self.setup_scrollbar.configure(bg="black", activebackground=INFO_TEXT_COLOR, troughcolor="black")

        self.setup_inner = tk.Frame(self.setup_canvas, bg="black", padx=8, pady=10)
        self.canvas_window = self.setup_canvas.create_window((0, 0), window=self.setup_inner, anchor="nw")

        self.setup_inner.bind(
            "<Configure>", lambda _: self.setup_canvas.configure(scrollregion=self.setup_canvas.bbox("all"))
        )
        self.setup_canvas.bind(
            "<Configure>", lambda event: self.setup_canvas.itemconfigure(self.canvas_window, width=event.width)
        )

        self._mousewheel_bound = False
        self.setup_canvas.bind("<Enter>", self._enable_mousewheel)
        self.setup_canvas.bind("<Leave>", self._disable_mousewheel)

        self.setup_inner.columnconfigure(1, weight=1)

        tk.Label(
            self.setup_inner,
            text="Batch Number",
            font=SUBTITLE_FONT,
            bg="black",
            fg=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=PADDING_X, pady=(PADDING_Y // 2, 0), columnspan=2)
        self.batch_number_entry = tk.Entry(
            self.setup_inner,
            width=ENTRY_WIDTH,
            font=BODY_FONT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=CARD_BORDER,
            highlightcolor=INFO_TEXT_COLOR,
            bg="black",
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
        )
        self.batch_number_entry.grid(row=1, column=0, sticky="ew", padx=PADDING_X, pady=2, columnspan=2)
        self._apply_focus_cue(self.batch_number_entry)
        self.batch_number_var = force_uppercase(
            self.batch_number_entry,
            batch_number_validator,
            on_valid=lambda _value: self._focus_if_auto(self.batch_line_entry, "Batch line"),
        )
        tk.Label(
            self.setup_inner,
            text="Ex:MVANC00001",
            font=SMALL_FONT,
            fg=TEXT_MUTED,
            bg="black",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=PADDING_X, pady=(0, SECTION_GAP - 2))

        tk.Label(
            self.setup_inner,
            text="Batch Line",
            font=SUBTITLE_FONT,
            bg="black",
            fg=TEXT_PRIMARY,
        ).grid(row=3, column=0, sticky="w", padx=PADDING_X)
        self.batch_line_entry = tk.Entry(
            self.setup_inner,
            width=ENTRY_WIDTH,
            font=BODY_FONT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=CARD_BORDER,
            highlightcolor=INFO_TEXT_COLOR,
            bg="black",
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
        )
        self.batch_line_entry.grid(row=4, column=0, sticky="ew", padx=PADDING_X, pady=2, columnspan=2)
        self._apply_focus_cue(self.batch_line_entry)
        self.batch_line_var = force_uppercase(
            self.batch_line_entry,
            line_validator,
            on_valid=lambda _value: self._focus_if_auto(self.num_moulds_entry, "Number of moulds"),
        )
        tk.Label(
            self.setup_inner,
            text="production line A,B,C...",
            font=SMALL_FONT,
            fg=TEXT_MUTED,
            bg="black",
        ).grid(row=5, column=0, columnspan=3, sticky="w", padx=PADDING_X, pady=(0, SECTION_GAP - 2))

        tk.Label(
            self.setup_inner,
            text="Number of Moulds",
            font=SUBTITLE_FONT,
            bg="black",
            fg=TEXT_PRIMARY,
        ).grid(row=6, column=0, sticky="w", padx=PADDING_X)
        self.num_moulds_entry = tk.Entry(
            self.setup_inner,
            width=ENTRY_WIDTH,
            font=BODY_FONT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=CARD_BORDER,
            highlightcolor=INFO_TEXT_COLOR,
            bg="black",
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
        )
        self.num_moulds_entry.grid(row=7, column=0, sticky="ew", padx=PADDING_X, pady=2, columnspan=2)
        self.num_moulds_var = tk.StringVar()
        self.num_moulds_entry.config(textvariable=self.num_moulds_var)
        self._apply_focus_cue(self.num_moulds_entry)
        self.num_moulds_var.trace_add("write", lambda *_: self._validate_mould_count())
        tk.Label(
            self.setup_inner,
            text="Ex: 1,2,3...",
            font=SMALL_FONT,
            fg=TEXT_MUTED,
            bg="black",
        ).grid(row=8, column=0, columnspan=3, sticky="w", padx=PADDING_X, pady=(0, SECTION_GAP))

        self.create_fields_button = tk.Button(
            self.setup_inner,
            text="Create Mould Fields",
            font=BUTTON_FONT,
            height=2,
            width=20,
            command=self._create_mould_entries,
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            relief="flat",
            highlightthickness=0,
        )
        self.create_fields_button.grid(row=7, column=2, padx=PADDING_X, pady=2, rowspan=2, sticky="n")
        self._refresh_scroll_region()
        self._scroll_to_bottom()

    def _build_scan_frame(self):
        self.scan_frame = tk.Frame(self.window, padx=18, pady=18, bg="black")

        self.batch_label = tk.Label(
            self.scan_frame,
            text="Batch: -",
            font=TITLE_FONT,
            bg="black",
            fg=TEXT_PRIMARY,
        )
        self.batch_label.pack(pady=(0, SECTION_GAP), anchor="w")

        self.last_qr_label = tk.Label(
            self.scan_frame,
            text="Last QR Scanned: None",
            font=SUBTITLE_FONT,
            bg="black",
            fg=TEXT_PRIMARY,
            width=40,
            padx=PADDING_X * 2,
            pady=PADDING_Y * 2,
            relief="flat",
            anchor="w",
        )
        self.last_qr_label.pack(fill="x", pady=(0, SECTION_GAP))

        self.status_label = tk.Label(
            self.scan_frame,
            text="Status: READY TO SCAN",
            font=self._scale_font(SCAN_STATUS_FONT, 2),
            padx=PADDING_X * 2,
            pady=PADDING_Y + 4,
            relief="flat",
            bg=STATUS_BG_COLORS["READY"],
            fg=STATUS_TEXT_COLORS["READY"],
        )
        self.status_label.pack(fill="x", pady=(2, SECTION_GAP + 2))

        counts_frame = tk.Frame(self.scan_frame, bg="black")
        counts_frame.pack(fill="x", pady=(0, SECTION_GAP))
        self.counter_labels = {}

        tile_specs = [
            ("accepted", "Accepted", "#10DF5F"),
            ("duplicate", "Duplicate", "#f0ce21"),
            ("rejected", "Rejected", "#f11b1b"),
        ]
        for idx, (key, title, color) in enumerate(tile_specs):
            tile = tk.Frame(counts_frame, bg="black", padx=10, pady=6)
            tile.grid(row=0, column=idx, padx=8, pady=4, sticky="nsew")
            counts_frame.columnconfigure(idx, weight=1, uniform="counter")
            header = tk.Label(tile, text=title.upper(), font=SMALL_FONT, bg=color, fg="white", padx=10, pady=5)
            header.pack(fill="x", anchor="w")
            value_label = tk.Label(
                tile,
                text="0",
                font=self._scale_font(SCAN_COUNTER_FONT, 1),
                bg=color,
                fg="white",
                padx=10,
                pady=6,
                anchor="center",
                justify="center",
            )
            value_label.pack(fill="both", expand=True, pady=(2, 0))
            note_label = tk.Label(tile, text="Since last reset", font=SMALL_FONT, bg=color, fg="#fefce8", padx=10, anchor="center")
            note_label.pack(fill="x", pady=(0, 4))
            self.counter_labels[key] = value_label

        self.qr_entry = tk.Entry(
            self.scan_frame,
            font=self._scale_font(SCAN_STATUS_FONT, 3),
            width=28,
            state="normal",  # Always enabled for HID QR scanner
            relief="flat",
            highlightthickness=2,
            highlightbackground="#334155",
            highlightcolor=SUCCESS_TEXT_COLOR,
            insertbackground=TEXT_PRIMARY,
            bg="black",
            fg=TEXT_PRIMARY,
        )
        self.qr_entry.pack(pady=(4, SECTION_GAP + 4))
        self.qr_entry.bind("<FocusIn>", lambda _: self._set_qr_focus(True))
        self.qr_entry.bind("<FocusOut>", lambda _: self._set_qr_focus(False))
        self.qr_entry.bind("<Return>", self._scan_qr_event)

        tk.Frame(self.scan_frame, bg="#1f2937", height=2).pack(fill="x", pady=(0, 6))

        self.status_banner = tk.Label(
            self.scan_frame,
            text="",
            font=SMALL_FONT,
            bg="#0f172a",
            fg=TEXT_PRIMARY,
            pady=PADDING_Y,
            padx=PADDING_X * 2,
            anchor="w",
            highlightthickness=1,
            highlightbackground="#1f2937",
            bd=0,
        )
        self.status_banner.pack(fill="x", pady=(0, SECTION_GAP + 2))

        self.stop_button = tk.Button(
            self.scan_frame,
            text="Stop Batch (Right-click to confirm)",
            bg="#eb1111",
            fg="white",
            font=BUTTON_FONT,
            height=2,
            width=18,
            padx=8,
            pady=4,
            wraplength=180,
            activebackground="#b91c1c",
            relief="raised",
            bd=4,
            highlightthickness=1,
            highlightbackground="#7f1d1d",
            highlightcolor="#fca5a5",
        )
        self.stop_button.place(relx=1.0, y=0, anchor="ne")
        self.stop_button.bind("<Button-1>", self._block_touch_stop)
        self.stop_button.bind("<ButtonRelease-1>", self._block_touch_stop)
        self.stop_button.bind("<Button-2>", self._block_touch_stop)
        self.stop_button.bind("<ButtonRelease-2>", self._block_touch_stop)
        self.stop_button.bind("<ButtonRelease-3>", self._handle_stop_request)

        self.stop_hint = tk.Label(
            self.scan_frame,
            text="Tip: Use a mouse right-click to stop. Left taps are ignored to prevent accidental stops.",
            font=SMALL_FONT,
            fg=TEXT_MUTED,
            bg="black",
            wraplength=360,
            justify="center",
        )
        self.stop_hint.pack(pady=(0, SECTION_GAP))

        footer_frame = tk.Frame(self.scan_frame, bg="black", highlightthickness=1, highlightbackground="#1f2937")
        footer_frame.pack(side="bottom", fill="x", pady=(8, 0), ipady=4)
        self.session_footer = tk.Label(
            footer_frame,
            text="No active batch",
            font=SMALL_FONT,
            fg=TEXT_MUTED,
            bg="black",
            pady=4,
        )
        self.session_footer.pack(side="top", fill="x")
        self.ip_address_var = tk.StringVar(value="Device IP: resolving…")
        self.ip_address_label = tk.Label(
            footer_frame,
            textvariable=self.ip_address_var,
            font=SMALL_FONT,
            fg=TEXT_MUTED,
            bg="black",
            pady=2,
        )
        self.ip_address_label.pack(side="top", fill="x")
        self._update_device_ip_label()

    def _refresh_scroll_region(self):
        self.setup_inner.update_idletasks()
        self.setup_canvas.configure(scrollregion=self.setup_canvas.bbox("all"))

    def _scroll_to_bottom(self):
        def _do_scroll():
            self.setup_canvas.yview_moveto(1.0)

        self.window.after_idle(_do_scroll)

    def _focus_if_auto(self, widget, hint=None):
        if hasattr(self, "auto_hint_var"):
            if self.auto_advance:
                self.auto_hint_var.set(f"Next: {hint}" if hint else "Auto advance active.")
            else:
                self.auto_hint_var.set("Manual advance mode – press Tab to move ahead.")

        if self.auto_advance and widget:
            self.window.after_idle(widget.focus_set)

    def _check_duplicate(self, qr_code: str) -> bool:
        if not self.batch_number:
            return False
        return self.duplicate_tracker.already_scanned(self.batch_number, qr_code)

    def _focus_next_after_qr_end(self, index):
        next_index = index + 1
        if next_index < len(self.mould_rows):
            self._focus_if_auto(self.mould_rows[next_index]["mould_entry"], f"Mould {next_index + 1} name")
        else:
            self._focus_if_auto(self.start_scan_btn, "Start scanning button")

    def _attach_auto_focus_handlers(self, index, row_info, line_getter):
        mould_var = row_info["mould_var"]
        qr_start_var = row_info["qr_start_var"]
        qr_end_var = row_info["qr_end_var"]
        qr_start_entry = row_info["qr_start_entry"]
        qr_end_entry = row_info["qr_end_entry"]
        display_index = index + 1
        mould_name = lambda: mould_var.get().upper()

        def on_mould(*_):
            if mould_name_validator(mould_name()):
                self._focus_if_auto(qr_start_entry, f"Mould {display_index} QR start")

        def on_qr_start(*_):
            if qr_validator(qr_start_var.get(), line_getter(), mould_name()):
                self._focus_if_auto(qr_end_entry, f"Mould {display_index} QR end")

        def on_qr_end(*_):
            if qr_validator(qr_end_var.get(), line_getter(), mould_name()):
                self._focus_next_after_qr_end(index)

        mould_var.trace_add("write", on_mould)
        qr_start_var.trace_add("write", on_qr_start)
        qr_end_var.trace_add("write", on_qr_end)

    def _on_mousewheel(self, event):
        if self.setup_frame.winfo_manager():
            self.setup_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _enable_mousewheel(self, event=None):
        if not getattr(self, "_mousewheel_bound", False):
            self.setup_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
            self._mousewheel_bound = True

    def _disable_mousewheel(self, event=None):
        if getattr(self, "_mousewheel_bound", False):
            self.setup_canvas.unbind_all("<MouseWheel>")
            self._mousewheel_bound = False

    def _scale_font(self, font_tuple, delta=0):
        """Return a resized copy of a Tk font tuple."""
        if not isinstance(font_tuple, (tuple, list)):
            return font_tuple
        try:
            family, size, weight = font_tuple
            return (family, max(int(size) + int(delta), 1), weight)
        except (ValueError, TypeError):
            return font_tuple

    def _apply_focus_cue(self, entry_widget, focus_color="#22d3ee"):
        """Give focused entries a prominent cyan outline."""
        if not entry_widget:
            return

        try:
            base_thickness = int(float(entry_widget.cget("highlightthickness")))
        except (TypeError, ValueError):
            base_thickness = 0

        base_bg = entry_widget.cget("highlightbackground") or entry_widget.cget("bg")
        base_color = entry_widget.cget("highlightcolor") or base_bg
        base_bd = entry_widget.cget("bd")
        focus_thickness = max(base_thickness, 1) + 2

        def on_focus_in(_event):
            entry_widget.configure(
                highlightbackground=focus_color,
                highlightcolor=focus_color,
                highlightthickness=focus_thickness,
                bd=0,
            )

        def on_focus_out(_event):
            entry_widget.configure(
                highlightbackground=base_bg,
                highlightcolor=base_color,
                highlightthickness=base_thickness,
                bd=base_bd,
            )

        entry_widget.bind("<FocusIn>", on_focus_in, add="+")
        entry_widget.bind("<FocusOut>", on_focus_out, add="+")

    def _resolve_device_ip(self):
        ip = "Unavailable"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(('8.8.8.8', 80))
                ip = sock.getsockname()[0]
        except Exception:
            pass
        if not ip or ip.startswith('127.') or ip == '0.0.0.0':
            try:
                hostname = socket.gethostname()
                for candidate in socket.gethostbyname_ex(hostname)[2]:
                    if candidate and not candidate.startswith('127.'):
                        ip = candidate
                        break
            except Exception:
                pass
        return ip

    def _update_device_ip_label(self):
        if hasattr(self, 'ip_address_var'):
            self.ip_address_var.set(f"Device IP: {self._resolve_device_ip()}")

    def _set_qr_focus(self, active):
        color = SUCCESS_TEXT_COLOR if active else "#555555"
        self.qr_entry.config(highlightbackground=color, highlightcolor=color)

    def _block_touch_stop(self, event=None):
        self._show_banner("Stop button locked", "Right-click with a mouse to stop.", status_key="DUPLICATE")
        return "break"

    def _handle_stop_request(self, event=None):
        if messagebox.askyesno("Confirm Stop", "Stop current batch scanning?"):
            self._show_banner("Stopping batch", "Halting scanner…", status_key="DUPLICATE")
            self.stop_scanning()
        else:
            self._show_banner("Continue scanning", "Batch remains active.", status_key="PASS")
        return "break"

    # ---------------- Controller Sync ----------------
    def _handle_controller_request(self, final_attempt: bool) -> None:
        """
        Handle scan request from firmware. 
        Firmware timing: cartridge is positioned and held by pins, ready for QR scan.
        """
        logger = logging.getLogger("actj.sync")
        if not self.controller_link or not self.controller_link.active:
            return
        if not self.scanning_active:
            logger.warning("Controller requested scan while no batch is active")
            self.controller_link.cancel_pending("S", "batch_inactive")
            return

        self.awaiting_hardware = True
        self._clear_controller_timeout()
        self._controller_timeout_id = self.window.after(
            CONTROLLER_RESPONSE_TIMEOUT_MS,
            self._on_controller_timeout,
        )

        if not self.scan_frame.winfo_manager():
            self._show_scan()

        # Set busy status immediately (firmware waits for this)
        try:
            self.hardware.set_busy(False)  # Signal Pi is busy processing
        except Exception as e:
            logger.warning(f"Unable to set busy line: {e}")

        detail = f"Cartridge positioned. QR scan {'(final attempt)' if final_attempt else 'requested'}..."
        self._show_banner("Scanning QR", detail, status_key="READY")

        # Allow BUSY_SETTLE_MS for hardware to settle before QR scan
        self.window.after(BUSY_SETTLE_MS, self._start_qr_scan_sequence)

    def _start_qr_scan_sequence(self):
        """
        Start QR scanning after busy settle delay.
        At this point, cartridge is positioned and held by pins - safe to scan.
        """
        logger = logging.getLogger("actj.sync")
        
        # Enable manual entry for USB scanners or keyboard input
        self.qr_entry.config(state="normal")
        self.qr_entry.focus_set()
        
        # Clear any previous QR code
        self.qr_entry.delete(0, tk.END)
        
        # Start automatic camera scanning if available (USB camera or built-in camera)
        if self.camera_scanner:
            logger.info("Starting automatic USB/camera QR scan - cartridge positioned")
            try:
                self.camera_scanner.start_scanning()
                self._show_banner("Auto scanning", "Camera scanning QR code...", status_key="READY")
            except Exception as e:
                logger.warning(f"Camera scan failed: {e}")
                self._show_banner("Manual entry", "Camera failed - use USB scanner or type QR", status_key="DUPLICATE")
        else:
            # USB barcode scanner mode - scanner will input directly to qr_entry when triggered
            logger.info("Waiting for USB QR scanner input - cartridge positioned")
            self._show_banner("USB Scanner Ready", "Scan QR code with USB scanner or type manually", status_key="READY")
            
        # Set timeout for manual/USB scanner input
        self._manual_scan_timeout_id = self.window.after(
            CONTROLLER_RESPONSE_TIMEOUT_MS - 1000,  # Leave 1s buffer for processing
            self._on_manual_scan_timeout
        )

    def _on_manual_scan_timeout(self):
        """Handle timeout when no QR input received within timeout period."""
        logger = logging.getLogger("actj.sync")
        logger.warning("No QR input received within timeout period")
        
        if hasattr(self, '_manual_scan_timeout_id'):
            self._manual_scan_timeout_id = None
            
        # Send timeout response to firmware
        if self.awaiting_hardware:
            self._show_banner("Scan timeout", "No QR received - sending skip to firmware", status_key="OUT OF BATCH")
            self._complete_controller_request("SKIP")  # Send 'S' to firmware

    def _on_controller_timeout(self) -> None:
        self._controller_timeout_id = None
        if not self.awaiting_hardware:
            return
        logging.getLogger("actj.sync").warning("Timed out waiting for QR after controller request")
        self._abort_pending_controller_request(code="Q", reason="timeout")
        self._show_banner(
            "Scan timeout",
            "No QR received; controller notified.",
            status_key="OUT OF BATCH",
        )

    def _clear_controller_timeout(self) -> None:
        if self._controller_timeout_id:
            self.window.after_cancel(self._controller_timeout_id)
            self._controller_timeout_id = None

    def _abort_pending_controller_request(self, code: str = "S", reason: str = "") -> None:
        self._clear_controller_timeout()
        if self.controller_link and self.controller_link.has_pending():
            self.controller_link.cancel_pending(code, reason)
        self.awaiting_hardware = False

    def _complete_controller_request(self, status: str) -> None:
        """
        Send result to firmware and release busy signal.
        Firmware will then move cartridge out based on result.
        """
        if not self.controller_link or not self.controller_link.has_pending():
            self.awaiting_hardware = False
            self._clear_controller_timeout()
            return
        
        # Cancel any pending manual scan timeout
        if hasattr(self, '_manual_scan_timeout_id') and self._manual_scan_timeout_id:
            self.window.after_cancel(self._manual_scan_timeout_id)
            self._manual_scan_timeout_id = None
        
        sent = self.controller_link.send_result(status)
        if not sent:
            logging.getLogger("actj.sync").warning("Failed to deliver %s to controller", status)
        
        # Release busy signal so firmware can proceed with mechanical operations
        try:
            self.hardware.set_busy(True)  # Release busy (HIGH = ready)
        except Exception as e:
            logging.getLogger("actj.sync").warning(f"Unable to release busy line: {e}")
        
        self.awaiting_hardware = False
        self._clear_controller_timeout()
        
        # Stop camera scanning if active
        if self.camera_scanner:
            self.camera_scanner.stop_scanning()
            
        # Clear QR entry for next scan
        self.qr_entry.delete(0, tk.END)

    def _on_plc_sensor_update(self, event: SensorEvent) -> None:
        """Log PLC sensor state changes (stacker, stopper, pusher, etc.)."""
        logger = logging.getLogger("plc.sensor")
        logger.info("Sensor %s -> %s", event.name, "ACTIVE" if event.active else "inactive")

    def _on_plc_button_event(self, event: ButtonEvent) -> None:
        """Handle physical button events routed through the PLC."""
        logger = logging.getLogger("plc.button")
        logger.info("Button %s -> %s", event.name, "pressed" if event.pressed else "released")

    def _on_plc_frame(self, frame_type: PLCFrameType, payload: str) -> None:
        """Handle miscellaneous PLC frames (LCD text, raw diagnostics, etc.)."""
        logger = logging.getLogger("plc.frame")
        if frame_type == PLCFrameType.LCD:
            logger.info("PLC LCD request: %s", payload)
        elif frame_type == PLCFrameType.RAW:
            logger.debug("PLC raw frame: %s", payload)

    def _on_controller_link_down(self, exc=None) -> None:
        message = f"Controller link lost: {exc}" if exc else "Controller link lost"
        logging.getLogger("actj.sync").error(message)
        self._abort_pending_controller_request(code="S", reason="link_down")
        self._show_banner("Controller offline", "Check UART cable and power.", status_key="OUT OF BATCH")

    def _on_hardware_error(self, message: str) -> None:
        def show_banner():
            self._show_banner("Hardware error", message, status_key="OUT OF BATCH")

        self.window.after_idle(show_banner)

    def _format_status_detail(self, status, qr_code, mould):
        qr_display = qr_code if qr_code and qr_code not in {"", "None"} else "No QR"
        mould_note = f" for mould {mould}" if mould else ""
        status = status.upper()
        templates = {
            "PASS": f"{qr_display} accepted. Keep scanning.",
            "DUPLICATE": f"Duplicate detected.",
            "INVALID FORMAT": f"{qr_display} has an invalid format. Check the code and try again.",
            "LINE MISMATCH": f"{qr_display} belongs to a different line.",
            "OUT OF BATCH": f"{qr_display} is outside the defined range.",
            "READY": "Scanner ready – waiting for the next QR.",
        }
        return templates.get(status, f"{qr_display}{mould_note}.")

    def _show_banner(self, headline, detail=None, status_key=None):
        if not hasattr(self, "status_banner"):
            return
        key = status_key or headline
        message = f"{headline} — {detail}" if detail else str(headline)
        lookup_key = key.upper() if isinstance(key, str) else key
        bg = STATUS_BG_COLORS.get(lookup_key, "#424242")
        fg = STATUS_TEXT_COLORS.get(lookup_key, "#ffffff")
        self.status_banner.config(text=message, bg=bg, fg=fg)
        if self.banner_after_id:
            self.scan_frame.after_cancel(self.banner_after_id)
        self.banner_after_id = self.scan_frame.after(
            4000, lambda: self.status_banner.config(text="", bg="black", fg=TEXT_PRIMARY)
        )

    def _update_session_footer(self):
        if not hasattr(self, "session_footer"):
            return
        if not self.scanning_active or not self.batch_number:
            self.session_footer.config(text="No active batch")
            return
        started_at = self.session_start.strftime("%d/%m/%Y %H:%M:%S") if self.session_start else "--/--/---- --:--:--"
        total = self.counters.get("total", 0)
        self.session_footer.config(
            text=f"Batch {self.batch_number} | Line {self.batch_line or '-'} | Started {started_at} | Total scans {total}"
        )

    def _maybe_resume_session(self):
        state = load_recovery_state()
        if not state or not state.get("scanning_active"):
            self._show_setup()
            return

        try:
            self.batch_number = state["batch_number"].strip().upper()
            self.batch_line = state["batch_line"].strip().upper()
            moulds = state["moulds"]
        except (KeyError, AttributeError):
            clear_recovery_state()
            self._show_setup()
            return

        if not self.batch_number or not self.batch_line or not moulds:
            clear_recovery_state()
            self._show_setup()
            return

        self.batch_number_var.set(self.batch_number)
        self.batch_line_var.set(self.batch_line)
        self.num_moulds_var.set(str(len(moulds)))
        self._create_mould_entries()

        self.mould_ranges = {}
        for data, row in zip(moulds, self.mould_rows):
            name = data.get("name", "").strip().upper()
            start = data.get("qr_start", "").strip().upper()
            end = data.get("qr_end", "").strip().upper()
            row["mould_var"].set(name)
            row["qr_start_var"].set(start)
            row["qr_end_var"].set(end)
            if name and start and end:
                self.mould_ranges[name] = (start, end)

        if not self.mould_ranges:
            clear_recovery_state()
            self._show_setup()
            return

        stored_counters = state.get("counters", {})
        for key in self.counters:
            self.counters[key] = int(stored_counters.get(key, 0))

        self.last_qr = state.get("last_qr", "None")
        self.last_status = state.get("last_status", "READY")
        session_start_str = state.get("session_start")
        if session_start_str:
            try:
                self.session_start = datetime.fromisoformat(session_start_str)
            except ValueError:
                self.session_start = datetime.now()
        else:
            self.session_start = datetime.now()

        self.log_file, self.csv_writer = resume_log(self.batch_number)
        self.scanning_active = True
        self._show_scan()
        self._update_scan_display(self.last_qr, self.last_status, mould=None, persist=False)
        self._update_session_footer()
    # self._persist_state() removed: not needed, function does not exist

    # ---------------- Setup Helpers ----------------
    def _validate_mould_count(self):
        value = self.num_moulds_var.get()
        valid = num_moulds_validator(value)
        highlight_invalid(self.num_moulds_entry, valid)
        if valid and self.create_fields_button:
            self._focus_if_auto(self.create_fields_button, "Create mould fields")
        return valid

    def _clear_mould_entries(self):
        for widget in self.dynamic_widgets:
            widget.destroy()
        self.dynamic_widgets.clear()
        self.mould_rows = []
        self.start_scan_btn = None
        self._refresh_scroll_region()

    def _create_mould_entries(self):
        try:
            count = int(self.num_moulds_var.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid number of moulds")
            return

        if count <= 0:
            messagebox.showerror("Error", "Number of moulds must be greater than 0")
            return

        self._clear_mould_entries()
        line_var_getter = lambda: self.batch_line_var.get().upper()

        for index in range(count):
            row_base = 9 + index * 6
            if index > 0:
                divider = tk.Frame(self.setup_inner, bg="#1e293b", height=1)
                divider.grid(
                    row=row_base - 1,
                    column=0,
                    columnspan=3,
                    sticky="ew",
                    padx=(PADDING_X, PADDING_X),
                    pady=(SECTION_GAP // 2, SECTION_GAP // 2),
                )
                self.dynamic_widgets.append(divider)

            card_bg = "#111827"
            mould_card = tk.Frame(
                self.setup_inner,
                bg=card_bg,
                padx=PADDING_X,
                pady=PADDING_Y,
                highlightbackground=CARD_BORDER,
                highlightthickness=1,
                bd=0,
            )
            mould_card.grid(
                row=row_base,
                column=0,
                columnspan=3,
                sticky="ew",
                padx=(PADDING_X, PADDING_X),
                pady=(0, SECTION_GAP),
            )
            mould_card.columnconfigure(1, weight=1)
            self.dynamic_widgets.append(mould_card)

            header = tk.Frame(mould_card, bg=card_bg)
            header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, PADDING_Y // 2))
            tk.Label(
                header,
                text=f"Mould {index + 1}",
                font=SUBTITLE_FONT,
                bg=card_bg,
                fg=TEXT_PRIMARY,
            ).pack(side="left")
            tk.Label(
                header,
                text="Define QR range for this Mould",
                font=SMALL_FONT,
                bg=card_bg,
                fg=TEXT_MUTED,
            ).pack(side="right")
 
            tk.Label(
                mould_card,
                text="Name / Code",
                font=SMALL_FONT,
                bg=card_bg,
                fg=TEXT_MUTED,
            ).grid(row=1, column=0, sticky="w", padx=(0, PADDING_X // 2))
            mould_entry = tk.Entry(
                mould_card,
                width=ENTRY_WIDTH,
                font=BODY_FONT,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=CARD_BORDER,
                highlightcolor=INFO_TEXT_COLOR,
                bg="black",
                fg=TEXT_PRIMARY,
                insertbackground=TEXT_PRIMARY,
            )
            mould_entry.grid(row=1, column=1, sticky="ew", pady=2)
            self._apply_focus_cue(mould_entry)

            tk.Label(
                mould_card,
                text="QR Start",
                font=SMALL_FONT,
                bg=card_bg,
                fg=TEXT_MUTED,
            ).grid(row=2, column=0, sticky="w", padx=(0, PADDING_X // 2), pady=(PADDING_Y // 2, 0))
            qr_start_entry = tk.Entry(
                mould_card,
                width=QR_WIDTH,
                font=BODY_FONT,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=CARD_BORDER,
                highlightcolor=INFO_TEXT_COLOR,
                bg="black",
                fg=TEXT_PRIMARY,
                insertbackground=TEXT_PRIMARY,
            )
            qr_start_entry.grid(row=2, column=1, sticky="ew", pady=(PADDING_Y // 2, 2))
            self._apply_focus_cue(qr_start_entry)

            tk.Label(
                mould_card,
                text="QR End",
                font=SMALL_FONT,
                bg=card_bg,
                fg=TEXT_MUTED,
            ).grid(row=3, column=0, sticky="w", padx=(0, PADDING_X // 2))
            qr_end_entry = tk.Entry(
                mould_card,
                width=QR_WIDTH,
                font=BODY_FONT,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=CARD_BORDER,
                highlightcolor=INFO_TEXT_COLOR,
                bg="black",
                fg=TEXT_PRIMARY,
                insertbackground=TEXT_PRIMARY,
            )
            qr_end_entry.grid(row=3, column=1, sticky="ew", pady=2)
            self._apply_focus_cue(qr_end_entry)

            mould_var = force_uppercase(mould_entry, mould_name_validator)
            qr_start_var = force_uppercase(
                qr_start_entry,
                lambda value: qr_validator(value, line_var_getter(), mould_var.get().upper()),
            )
            qr_end_var = force_uppercase(
                qr_end_entry,
                lambda value: qr_validator(value, line_var_getter(), mould_var.get().upper()),
            )

            row_info = {
                "mould_entry": mould_entry,
                "qr_start_entry": qr_start_entry,
                "qr_end_entry": qr_end_entry,
                "mould_var": mould_var,
                "qr_start_var": qr_start_var,
                "qr_end_var": qr_end_var,
            }
            self.mould_rows.append(row_info)

            if self.auto_advance:
                self._attach_auto_focus_handlers(index, row_info, line_var_getter)

        start_row = 9 + count * 6
        self.start_scan_btn = tk.Button(
            self.setup_inner,
            text="Start Scanning",
            font=BUTTON_FONT,
            height=3,
            width=26,
            command=self.start_scanning,
            bg="#0d9488",
            fg="white",
            activebackground="#0f766e",
            relief="flat",
        )
        self.start_scan_btn.grid(
            row=start_row,
            column=0,
            columnspan=3,
            pady=SECTION_GAP,
            sticky="ew",
            padx=(PADDING_X, PADDING_X),
        )
        self.dynamic_widgets.append(self.start_scan_btn)
        self._refresh_scroll_region()
        self._scroll_to_bottom()
        if self.mould_rows:
            self.mould_rows[0]["mould_entry"].focus_set()
            if hasattr(self, "auto_hint_var") and self.auto_advance:
                self.auto_hint_var.set("Next: Mould 1 name")

    # ---------------- Scanning Flow ----------------
    def start_scanning(self):
        self.batch_number = self.batch_number_var.get().strip().upper()
        self.batch_line = self.batch_line_var.get().strip().upper()
        valid = True

        if not batch_number_validator(self.batch_number):
            highlight_invalid(self.batch_number_entry, False)
            messagebox.showerror("Error", "Invalid Batch Number format")
            valid = False
        else:
            highlight_invalid(self.batch_number_entry, True)

        if not line_validator(self.batch_line):
            highlight_invalid(self.batch_line_entry, False)
            messagebox.showerror("Error", "Batch Line must be a single alphabet")
            valid = False
        else:
            highlight_invalid(self.batch_line_entry, True)

        try:
            mould_count = int(self.num_moulds_var.get())
            highlight_invalid(self.num_moulds_entry, mould_count > 0)
        except ValueError:
            highlight_invalid(self.num_moulds_entry, False)
            valid = False
            mould_count = 0

        if mould_count <= 0:
            messagebox.showerror("Error", "Enter a valid number of moulds")
            valid = False

        if not self.mould_rows:
            messagebox.showerror("Error", "Please create mould entries first")
            return

        mould_data = []
        self.mould_ranges.clear()
        seen_moulds = set()

        for row in self.mould_rows:
            mould = row["mould_var"].get().strip().upper()
            qr_start = row["qr_start_var"].get().strip().upper()
            qr_end = row["qr_end_var"].get().strip().upper()

            mould_valid = mould_name_validator(mould)
            highlight_invalid(row["mould_entry"], mould_valid)

            start_valid = qr_validator(qr_start, self.batch_line, mould)
            highlight_invalid(row["qr_start_entry"], start_valid)

            end_valid = qr_validator(qr_end, self.batch_line, mould)
            highlight_invalid(row["qr_end_entry"], end_valid)

            if not all([mould_valid, start_valid, end_valid]):
                valid = False
                continue

            if mould in seen_moulds:
                messagebox.showerror("Error", f"Duplicate mould name: {mould}")
                valid = False
                highlight_invalid(row["mould_entry"], False)
                continue

            seen_moulds.add(mould)
            self.mould_ranges[mould] = (qr_start, qr_end)
            mould_data.append([self.batch_number, self.batch_line, mould, qr_start, qr_end])

        if not valid:
            return

        os.makedirs(SETUP_LOG_FOLDER, exist_ok=True)
        setup_path = os.path.join(SETUP_LOG_FOLDER, f"{self.batch_number}_setup.csv")
        with open(setup_path, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["BatchNo", "Line", "MouldType", "QR_Start", "QR_End"])
            writer.writerows(mould_data)

        clear_recovery_state()
        self.log_file, self.csv_writer = init_log(self.batch_number)
        self.session_start = datetime.now()
        self._reset_scan_state()
        
        # ACTJv20(RJSR) Legacy Integration - Batch Start
        try:
            from actj_legacy_integration import get_legacy_integration, is_legacy_mode
            if is_legacy_mode():
                legacy = get_legacy_integration()
                
                # Set batch context for QR validation (include batch number for LCD)
                legacy.set_batch_context(
                    self.batch_line, 
                    self.mould_ranges, 
                    lambda code: self._check_duplicate(code),
                    self.batch_number
                )
                
                # Set result callback to update UI
                legacy.set_result_callback(self._on_legacy_qr_result)
                
                # Handle batch start
                legacy.handle_batch_start()
                logging.getLogger("actj.legacy").info("ACTJv20(RJSR) batch start sequence completed")
                
                # Signal PIC that batch setup is complete and Pi is ready for commands
                set_pi_ready_state(ready=True)
                
                self._show_banner("ACTJv20 Ready", "ACTJv20 Legacy Mode - Press START on jig to begin automatic operation.", status_key="PASS")
                
        except ImportError:
            pass  # Legacy integration not available

        if self.controller_link and self.controller_link.active:
            try:
                self.controller_link.send_oob_code("G")
                logging.getLogger("actj.sync").info("Signalled batch ready ('G') to firmware")
            except Exception as exc:
                logging.getLogger("actj.sync").warning("Unable to send batch ready signal: %s", exc)
        else:
            logging.getLogger("actj.sync").info("Controller link unavailable - skipping 'G' signal")

        self._show_scan()
        self._update_session_footer()
        self._persist_state()

    def _reset_scan_state(self):
        self._abort_pending_controller_request(reason="state_reset")
        if self.batch_number:
            self.duplicate_tracker.reset_batch(self.batch_number)
        for key in self.counters:
            self.counters[key] = 0
        self.last_qr = "None"
        self.last_status = "READY"
        self._update_scan_display("None", "READY", mould=None, persist=False)

    def _scan_qr_event(self, event=None):
        """
        Process QR code scan - called from manual entry, USB scanner, or camera detection.
        Only processes if firmware is waiting for a scan result.
        """
        if not self.scanning_active:
            return
        qr_code = self.qr_entry.get().strip().upper()
        self.qr_entry.delete(0, tk.END)
        if not qr_code:
            return

        logger = logging.getLogger("qr.scan")
        logger.info(f"Processing QR from USB/manual input: {qr_code}")

        # Cancel manual scan timeout since we got input
        if hasattr(self, '_manual_scan_timeout_id') and self._manual_scan_timeout_id:
            self.window.after_cancel(self._manual_scan_timeout_id)
            self._manual_scan_timeout_id = None

        # Check if legacy integration should handle this
        try:
            from actj_legacy_integration import get_legacy_integration, is_legacy_mode
            if is_legacy_mode():
                legacy = get_legacy_integration()
                status, mould = legacy.process_manual_qr(qr_code)
                
                # The result will be sent to firmware by the legacy integration
                # and we'll get callback via _on_legacy_qr_result
                logger.info(f"QR processed via legacy integration: {qr_code} -> {status}")
                return
        except ImportError:
            pass

        # Fallback to direct processing if legacy integration not available
        # Parse multi-byte ASCII/CSV data if present (simulate firmware data parsing)
        if ',' in qr_code or qr_code.isdigit():
            # Example: parse valve positions or sensor readings
            try:
                values = [int(x) for x in qr_code.split(',') if x.strip().isdigit()]
                logger.info(f"Parsed firmware data: {values}")
            except Exception as e:
                logger.warning(f"Failed to parse firmware data: {e}")

        status, mould = handle_qr_scan(
            qr_code,
            self.batch_line,
            self.mould_ranges,
            duplicate_checker=lambda code: self._check_duplicate(code),
        )

        # Map error codes to user feedback
        error_map = {
            "S": "Scanner Error",
            "Q": "No QR detected",
            "L": "Length Error",
            "B": "Logging Error",
            "C": "Repeated Testing",
            "H": "Scanner Hardware Error",
        }
        user_message = error_map.get(status, None)
        if user_message:
            self._show_banner("Firmware Error", user_message, status_key=status)

        if status == "PASS":
            self.counters["accepted"] += 1
            self.duplicate_tracker.record_scan(self.batch_number, qr_code)
            logger.info(f"QR accepted: {qr_code} -> {mould}")
        elif status == "DUPLICATE":
            self.counters["duplicate"] += 1
            logger.warning(f"QR duplicate: {qr_code}")
        else:
            self.counters["rejected"] += 1
            logger.warning(f"QR rejected ({status}): {qr_code}")

        self.counters["total"] += 1
        self._update_scan_display(qr_code, status, mould)

        if self.csv_writer and self.log_file:
            write_log(self.csv_writer, self.log_file, self.batch_number, mould, qr_code, status)

        # Send result to firmware controller if active
        logger.info("[DEBUG] Sending result to firmware after QR validation")
        if self.controller_link and self.controller_link.active:
            self.controller_link.send_result(status)
        self.awaiting_hardware = False

    def _update_scan_display(self, qr_code, status, mould=None, persist=True):
        self.last_qr = qr_code
        self.last_status = status
        self.last_qr_label.config(text=f"Last QR Scanned: {qr_code}")
        status_bg = STATUS_BG_COLORS.get(status, STATUS_BG_COLORS["OUT OF BATCH"])
        status_fg = STATUS_TEXT_COLORS.get(status, STATUS_TEXT_COLORS["OUT OF BATCH"])
        self.status_label.config(text=f"Status: {status}", bg=status_bg, fg=status_fg)
        self.counter_labels["accepted"].config(text=str(self.counters["accepted"]))
        self.counter_labels["duplicate"].config(text=str(self.counters["duplicate"]))
        self.counter_labels["rejected"].config(text=str(self.counters["rejected"]))
        self._update_session_footer()
        detail = self._format_status_detail(status, qr_code, mould)
        moulds_data = []
        for row in self.mould_rows:
            name = row["mould_var"].get().strip().upper()
            start = row["qr_start_var"].get().strip().upper()
            end = row["qr_end_var"].get().strip().upper()
            if name and start and end:
                moulds_data.append({"name": name, "qr_start": start, "qr_end": end})
        if not moulds_data:
            return
        state = {
            "batch_number": self.batch_number,
            "batch_line": self.batch_line,
            "moulds": moulds_data,
            "counters": dict(self.counters),
            "last_qr": self.last_qr,
            "last_status": self.last_status,
            "scanning_active": True,
            "session_start": self.session_start.isoformat() if self.session_start else None,
        }
        save_recovery_state(state)

    def stop_scanning(self, show_message=True):
        self._abort_pending_controller_request(reason="batch_stop")
        
        # ACTJv20(RJSR) Legacy Integration - Batch End
        try:
            from actj_legacy_integration import get_legacy_integration, is_legacy_mode
            if is_legacy_mode():
                legacy = get_legacy_integration()
                legacy.handle_batch_end()
                
                # Signal PIC that Pi is now busy (batch ended, setup required)
                set_pi_ready_state(ready=False)
                
                # Send batch end notification to firmware
                legacy.send_firmware_command('E')  # End batch command
                
                logging.getLogger("actj.legacy").info("ACTJv20(RJSR) batch end sequence completed")
        except ImportError:
            pass  # Legacy integration not available
            
        if not self.scanning_active and not self.log_file:
            return
        self.scanning_active = False
        self.qr_entry.config(state="disabled")
        self._set_qr_focus(False)
        self.qr_entry.delete(0, tk.END)
        close_log(self.log_file)
        self.log_file = None
        self.csv_writer = None
        clear_recovery_state()
        if self.batch_number:
            self.duplicate_tracker.reset_batch(self.batch_number)
        self.mould_ranges.clear()
        for key in self.counters:
            self.counters[key] = 0
        self.last_qr = "None"
        self.last_status = "READY"
        self.session_start = None
        self.batch_number = ""
        self.batch_line = ""
        self.batch_number_var.set("")
        self.batch_line_var.set("")
        self.num_moulds_var.set("")
        highlight_invalid(self.batch_number_entry, True)
        highlight_invalid(self.batch_line_entry, True)
        highlight_invalid(self.num_moulds_entry, True)
        self._clear_mould_entries()
        if hasattr(self, "status_banner"):
            self.status_banner.config(text="", bg="#1e1e1e", fg="white")
        if self.banner_after_id:
            self.scan_frame.after_cancel(self.banner_after_id)
            self.banner_after_id = None
        self._update_session_footer()
        if show_message:
            messagebox.showinfo("Info", "Batch scanning stopped.")
        self._show_setup()

    # ---------------- Frame Visibility ----------------
    def _show_setup(self):
        if self.scan_frame.winfo_manager():
            self.scan_frame.pack_forget()
        if not self.setup_frame.winfo_manager():
            self.setup_frame.pack(fill="x", padx=18, pady=12)
        self._refresh_scroll_region()
        self.setup_canvas.yview_moveto(0.0)
        self._enable_mousewheel()
        self.scanning_active = False
        if self.batch_number_entry:
            self.window.after_idle(self.batch_number_entry.focus_set)
        if self.controller_link and self.controller_link.active:
            try:
                self.controller_link.send_oob_code("H")
                logging.getLogger("actj.sync").info("Signalled setup mode ('H') to firmware")
            except Exception as exc:
                logging.getLogger("actj.sync").warning("Unable to send setup signal: %s", exc)

    def _show_scan(self):
        if self.setup_frame.winfo_manager():
            self.setup_frame.pack_forget()
        self.scan_frame.pack(fill="both", expand=True, padx=18, pady=12)
        self.batch_label.config(text=f"Batch: {self.batch_number}")
        self.status_label.config(
            text="Status: READY",
            fg=STATUS_TEXT_COLORS["READY"],
            bg=STATUS_BG_COLORS["READY"],
        )
        self.qr_entry.config(state="normal")
        self.qr_entry.focus_set()
        self._disable_mousewheel()
        self.scanning_active = True
        self._update_device_ip_label()

    # ---------------- Shutdown ----------------
    def _on_legacy_qr_result(self, qr_code: str, status: str, mould: str):
        """
        Handle QR scan results from ACTJv20 legacy integration.
        This is called when the firmware requests QR scanning.
        """
        logger = logging.getLogger("actj.legacy")
        logger.info(f"Legacy QR result: {qr_code} -> {status} (mould: {mould})")
        
        # Update counters and UI in main thread
        self.window.after(0, self._process_legacy_result, qr_code, status, mould)
    
    def _process_legacy_result(self, qr_code: str, status: str, mould: str):
        """Process legacy QR result in main UI thread."""
        if not self.scanning_active:
            return
            
        # Update counters based on result
        if status == "PASS":
            self.counters["accepted"] += 1
            if self.duplicate_tracker and self.batch_number:
                self.duplicate_tracker.record_scan(self.batch_number, qr_code)
        elif status == "DUPLICATE":
            self.counters["duplicate"] += 1
        else:
            self.counters["rejected"] += 1
        
        self.counters["total"] += 1
        
        # Update UI display
        self._update_scan_display(qr_code, status, mould)
        
        # Log to CSV if active
        if self.csv_writer and self.log_file:
            write_log(self.csv_writer, self.log_file, self.batch_number, mould, qr_code, status)
    
    def _on_close(self):
        set_hardware_error_handler(None)
        self._abort_pending_controller_request(reason="shutdown")
        
        # Shutdown legacy integration
        try:
            from actj_legacy_integration import stop_legacy_integration, is_legacy_mode
            if is_legacy_mode():
                stop_legacy_integration()
                logging.getLogger("shutdown").info("ACTJv20(RJSR) integration shutdown")
        except ImportError:
            pass
        
        if self.scanning_active:
            self._persist_state()
        if self.log_file:
            close_log(self.log_file)
            self.log_file = None
            self.csv_writer = None
        if self.controller_link:
            self.controller_link.close()
        if self.camera_scanner:
            self.camera_scanner.close()
        try:
            self.hardware.set_busy(False)
        except Exception:
            pass
        self.duplicate_tracker.close()
        self.window.destroy()


def launch_app():
    """Initialize logging and start the Tkinter application."""
    import os
    os.makedirs("batch_logs", exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('batch_logs/jig.log')
        ]
    )
    
    # CRITICAL: Assert busy lines HIGH immediately so PIC controller can boot
    # This matches SCANNER hardware initialization pattern
    # This must happen BEFORE any Tkinter UI construction to prevent PIC timeout
    hardware = get_hardware_controller()
    try:
        hardware.set_busy(True)  # GPIO 12 (if configured)
        hardware.set_sbc_busy(True)  # GPIO 18 (SCANNER hardware)
        hardware.set_status(True)  # GPIO 21 (SCANNER hardware)
        logging.getLogger("startup").info("All busy/status lines asserted HIGH - PIC can proceed")
    except Exception as exc:
        logging.getLogger("startup").warning("Unable to assert busy lines on startup: %s", exc)
    
    # ACTJv20(RJSR) Legacy Integration - startup sequence  
    try:
        from actj_legacy_integration import get_legacy_integration, is_legacy_mode
        if is_legacy_mode():
            legacy = get_legacy_integration()
            legacy.startup_sequence()
            logging.getLogger("startup").info("ACTJv20(RJSR) legacy startup sequence completed")
            logging.getLogger("startup").info("UART communication active for automatic operation")
    except ImportError:
        pass  # Legacy integration not available
    
    app_reference = {}

    def build(window):
        # Pass hardware instance to avoid re-initialization
        app_reference["instance"] = BatchScannerApp(window, hardware_controller=hardware)

    window = create_main_window(build)
    window.mainloop()


if __name__ == "__main__":
    launch_app()
