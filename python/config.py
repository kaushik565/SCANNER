"""Runtime configuration loader for the scanning jig."""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

CONFIG_FILE = "settings.ini"

# Defaults baked into the codebase
_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "folders": {
        "log_folder": "batch_logs",
        "setup_log_folder": "Batch_Setup_Logs",
        "recovery_file": "recovery.json",
    },
    "window": {
        "app_title": "AUTOMATIC CARTRIDGE SCANNING JIG",
        "window_width": "800",
        "window_height": "480",
        "fullscreen": "true",
        "background_color": "black",
    },
    "ui": {
        "header_text": "MOLBIO DIAGNOSTICS LIMITED",
        "footer_text": "DEVELOPED BY QA TEAM SITE-III",
        "subheader_text": "Automatic Cartridge Scanning JIG",
        "clock_format": "%d/%m/%Y %H:%M:%S",
        "auto_advance": "true",
    },
    "hardware": {
        "controller": "mock",  # options: mock, gpio
        "pin_mode": "BCM",
    "red_pin": "20",
    "green_pin": "21",
        "yellow_pin": "22",
        "buzzer_pin": "23",
    },
    "lcd": {
        "enabled": "true",
        "type": "i2c",
        "address": "0x27",
        "width": "16",
        "height": "2",
        "welcome_message": "WELCOME TO MOLBIO",
        "ready_message": "JIG READY",
        "scanning_message": "SCANNING...",
    },
    "jig": {
        "enabled": "false",
        "auto_start": "false",
        "advance_on_fail": "true",
        "push_extend_ms": "400",
        "push_retract_ms": "400",
        "settle_ms": "200",
        "detect_timeout_ms": "3000",
        "scan_timeout_ms": "5000",
        # Outputs (ASECT controller handles pusher via pins 1-14)
        # Set to 0 for pins handled by ASECT controller PCB
        "pusher_extend_pin": "0",
        "pusher_retract_pin": "0",
        "stopper_up_pin": "0",
        "stopper_down_pin": "0",
        # Inputs (only external sensors not handled by ASECT PCB)
        "sensor_stack_present_pin": "25",
        "sensor_at_scanner_pin": "24",
        "sensor_pusher_extended_pin": "0",
        "sensor_pusher_retracted_pin": "0",
        "sensor_safety_ok_pin": "26",
        "busy_signal_pin": "12",
    },
    "camera": {
        "enabled": "true",  # Enable automatic QR camera scanner
        "port": "/dev/qrscanner",  # Serial port for camera (same as SCANNER project)
        "baudrate": "115200",
        "timeout": "5",
    },
    "actj_legacy": {
        "enabled": "true",  # Enable ACTJv20(RJSR) firmware integration
        "uart_port": "/dev/serial0",  # UART port for PIC18F4550 communication
        "baudrate": "115200",  # Must match firmware SBC_UARTInit() setting
        "gpio_rasp_in_pic": "12",  # GPIO pin for RASP_IN_PIC signal
        "gpio_int_pic": "24",  # GPIO pin for INT_PIC signal  
        "gpio_shd_pic": "25",  # GPIO pin for SHD_PIC signal
        "command_timeout": "12000",  # Timeout for firmware commands (ms)
        "auto_start": "true",  # Automatically start legacy integration
    },
    "layout": {
        "entry_width": "18",
        "qr_width": "30",
        "padding_x": "8",
        "padding_y": "6",
        "section_gap": "10",
    },
    "typography": {
        "title_font": "Segoe UI,16,bold",
        "subtitle_font": "Segoe UI,12,bold",
        "body_font": "Segoe UI,11,normal",
        "small_font": "Segoe UI,9,normal",
        "scan_status_font": "Segoe UI,14,bold",
        "scan_counter_font": "Segoe UI,16,bold",
        "button_font": "Segoe UI,12,bold",
    },
    "palette": {
        "text_primary": "#e5e7ff",
        "text_muted": "#94a3b8",
        "info_text": "#60a5fa",
        "success_text": "#4caf50",
        "card_border": "#1f3251",
    },
}


def _parse_font(value: str) -> tuple[str, int, str]:
    """Convert comma-separated font string to Tk-compatible tuple."""

    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Invalid font definition: {value}")
    family, size, weight = parts
    return (family, int(size), weight)


@dataclass(frozen=True)
class AppConfig:
    entry_width: int
    qr_width: int
    log_folder: str
    setup_log_folder: str
    recovery_file: str
    app_title: str
    window_size: str
    fullscreen: bool
    background_color: str
    header_text: str
    footer_text: str
    subheader_text: str
    clock_format: str
    auto_advance: bool
    title_font: tuple[str, int, str]
    subtitle_font: tuple[str, int, str]
    body_font: tuple[str, int, str]
    small_font: tuple[str, int, str]
    scan_status_font: tuple[str, int, str]
    scan_counter_font: tuple[str, int, str]
    button_font: tuple[str, int, str]
    padding_x: int
    padding_y: int
    section_gap: int
    text_primary: str
    text_muted: str
    info_text: str
    success_text: str
    card_border: str
    hardware_controller: str
    hardware_pin_mode: str
    hardware_pins: Dict[str, int]
    jig_enabled: bool
    jig_auto_start: bool
    jig_advance_on_fail: bool
    jig_timings_ms: Dict[str, int]
    jig_output_pins: Dict[str, int]
    jig_input_pins: Dict[str, int]
    jig_busy_pin: int
    camera_enabled: bool
    camera_port: str
    camera_baudrate: int
    camera_timeout: int
    actj_legacy_enabled: bool
    actj_legacy_uart_port: str
    actj_legacy_baudrate: int
    actj_legacy_gpio_pins: Dict[str, int]
    actj_legacy_timeout: int
    actj_legacy_auto_start: bool
    lcd_enabled: bool
    lcd_type: str
    lcd_address: str
    lcd_bus: int
    lcd_width: int
    lcd_height: int
    lcd_messages: Dict[str, str]


def load_config(config_path: str | Path = CONFIG_FILE) -> AppConfig:
    """Read configuration, falling back to defaults when missing."""

    parser = configparser.ConfigParser(interpolation=None)
    for section, options in _DEFAULTS.items():
        parser[section] = options

    config_path = Path(config_path)
    if config_path.exists():
        parser.read(config_path, encoding="utf-8")

    window_width = parser.getint("window", "window_width")
    window_height = parser.getint("window", "window_height")
    window_size = f"{window_width}x{window_height}"

    return AppConfig(
        entry_width=parser.getint("layout", "entry_width"),
        qr_width=parser.getint("layout", "qr_width"),
        log_folder=parser.get("folders", "log_folder"),
        setup_log_folder=parser.get("folders", "setup_log_folder"),
        recovery_file=parser.get("folders", "recovery_file"),
        app_title=parser.get("window", "app_title"),
        window_size=window_size,
        fullscreen=parser.getboolean("window", "fullscreen"),
        background_color=parser.get("window", "background_color"),
        header_text=parser.get("ui", "header_text"),
        footer_text=parser.get("ui", "footer_text"),
        subheader_text=parser.get("ui", "subheader_text"),
        clock_format=parser.get("ui", "clock_format"),
        auto_advance=parser.getboolean("ui", "auto_advance"),
        title_font=_parse_font(parser.get("typography", "title_font")),
        subtitle_font=_parse_font(parser.get("typography", "subtitle_font")),
        body_font=_parse_font(parser.get("typography", "body_font")),
        small_font=_parse_font(parser.get("typography", "small_font")),
        scan_status_font=_parse_font(parser.get("typography", "scan_status_font")),
        scan_counter_font=_parse_font(parser.get("typography", "scan_counter_font")),
        button_font=_parse_font(parser.get("typography", "button_font")),
        padding_x=parser.getint("layout", "padding_x"),
        padding_y=parser.getint("layout", "padding_y"),
        section_gap=parser.getint("layout", "section_gap"),
        text_primary=parser.get("palette", "text_primary"),
        text_muted=parser.get("palette", "text_muted"),
        info_text=parser.get("palette", "info_text"),
        success_text=parser.get("palette", "success_text"),
        card_border=parser.get("palette", "card_border"),
        hardware_controller=parser.get("hardware", "controller"),
        hardware_pin_mode=parser.get("hardware", "pin_mode"),
        hardware_pins={
            "red": parser.getint("hardware", "red_pin"),
            "green": parser.getint("hardware", "green_pin"),
            "yellow": parser.getint("hardware", "yellow_pin"),
            "buzzer": parser.getint("hardware", "buzzer_pin"),
        },
        jig_enabled=parser.getboolean("jig", "enabled"),
        jig_auto_start=parser.getboolean("jig", "auto_start"),
        jig_advance_on_fail=parser.getboolean("jig", "advance_on_fail"),
        jig_timings_ms={
            "push_extend_ms": parser.getint("jig", "push_extend_ms"),
            "push_retract_ms": parser.getint("jig", "push_retract_ms"),
            "settle_ms": parser.getint("jig", "settle_ms"),
            "detect_timeout_ms": parser.getint("jig", "detect_timeout_ms"),
            "scan_timeout_ms": parser.getint("jig", "scan_timeout_ms"),
        },
        jig_output_pins={
            "pusher_extend": parser.getint("jig", "pusher_extend_pin"),
            "pusher_retract": parser.getint("jig", "pusher_retract_pin"),
            "stopper_up": parser.getint("jig", "stopper_up_pin"),
            "stopper_down": parser.getint("jig", "stopper_down_pin"),
        },
        jig_input_pins={
            "stack_present": parser.getint("jig", "sensor_stack_present_pin"),
            "at_scanner": parser.getint("jig", "sensor_at_scanner_pin"),
            "pusher_extended": parser.getint("jig", "sensor_pusher_extended_pin"),
            "pusher_retracted": parser.getint("jig", "sensor_pusher_retracted_pin"),
            "safety_ok": parser.getint("jig", "sensor_safety_ok_pin"),
        },
        jig_busy_pin=parser.getint("jig", "busy_signal_pin", fallback=12),
        camera_enabled=parser.getboolean("camera", "enabled", fallback=True),
        camera_port=parser.get("camera", "port", fallback="/dev/qrscanner"),
        camera_baudrate=parser.getint("camera", "baudrate", fallback=115200),
        camera_timeout=parser.getint("camera", "timeout", fallback=5),
        actj_legacy_enabled=parser.getboolean("actj_legacy", "enabled", fallback=True),
        actj_legacy_uart_port=parser.get("actj_legacy", "uart_port", fallback="/dev/serial0"),
        actj_legacy_baudrate=parser.getint("actj_legacy", "baudrate", fallback=115200),
        actj_legacy_gpio_pins={
            "rasp_in_pic": parser.getint("actj_legacy", "gpio_rasp_in_pic", fallback=18),
            "int_pic": parser.getint("actj_legacy", "gpio_int_pic", fallback=24),
            "shd_pic": parser.getint("actj_legacy", "gpio_shd_pic", fallback=25),
        },
        actj_legacy_timeout=parser.getint("actj_legacy", "command_timeout", fallback=12000),
        actj_legacy_auto_start=parser.getboolean("actj_legacy", "auto_start", fallback=True),
        lcd_enabled=parser.getboolean("lcd", "enabled"),
        lcd_type=parser.get("lcd", "type"),
        lcd_address=parser.get("lcd", "address"),
        lcd_bus=parser.getint("lcd", "bus", fallback=0),
        lcd_width=parser.getint("lcd", "width"),
        lcd_height=parser.getint("lcd", "height"),
        lcd_messages={
            "welcome": parser.get("lcd", "welcome_message"),
            "ready": parser.get("lcd", "ready_message"),
            "scanning": parser.get("lcd", "scanning_message"),
        },
    )


CONFIG = load_config()

# Convenience re-exports for current codebase usage
ENTRY_WIDTH = CONFIG.entry_width
QR_WIDTH = CONFIG.qr_width
LOG_FOLDER = CONFIG.log_folder
SETUP_LOG_FOLDER = CONFIG.setup_log_folder
RECOVERY_FILE = CONFIG.recovery_file
APP_TITLE = CONFIG.app_title
WINDOW_SIZE = CONFIG.window_size
FULLSCREEN = CONFIG.fullscreen
BACKGROUND_COLOR = CONFIG.background_color
HEADER_TEXT = CONFIG.header_text
FOOTER_TEXT = CONFIG.footer_text
CLOCK_FORMAT = CONFIG.clock_format
SUBHEADER_TEXT = CONFIG.subheader_text
AUTO_ADVANCE = CONFIG.auto_advance
TITLE_FONT = CONFIG.title_font
SUBTITLE_FONT = CONFIG.subtitle_font
BODY_FONT = CONFIG.body_font
SMALL_FONT = CONFIG.small_font
SCAN_STATUS_FONT = CONFIG.scan_status_font
SCAN_COUNTER_FONT = CONFIG.scan_counter_font
BUTTON_FONT = CONFIG.button_font
PADDING_X = CONFIG.padding_x
PADDING_Y = CONFIG.padding_y
SECTION_GAP = CONFIG.section_gap
TEXT_PRIMARY = CONFIG.text_primary
TEXT_MUTED = CONFIG.text_muted
INFO_TEXT_COLOR = CONFIG.info_text
SUCCESS_TEXT_COLOR = CONFIG.success_text
CARD_BORDER = CONFIG.card_border
HARDWARE_CONTROLLER = CONFIG.hardware_controller
HARDWARE_PIN_MODE = CONFIG.hardware_pin_mode
HARDWARE_PINS = CONFIG.hardware_pins
JIG_ENABLED = CONFIG.jig_enabled
JIG_AUTO_START = CONFIG.jig_auto_start
JIG_ADVANCE_ON_FAIL = CONFIG.jig_advance_on_fail
JIG_TIMINGS_MS = CONFIG.jig_timings_ms
JIG_OUTPUT_PINS = CONFIG.jig_output_pins
JIG_INPUT_PINS = CONFIG.jig_input_pins
JIG_BUSY_SIGNAL_PIN = CONFIG.jig_busy_pin
CAMERA_ENABLED = CONFIG.camera_enabled
CAMERA_PORT = CONFIG.camera_port
CAMERA_BAUDRATE = CONFIG.camera_baudrate
CAMERA_TIMEOUT = CONFIG.camera_timeout
ACTJ_LEGACY_ENABLED = CONFIG.actj_legacy_enabled
ACTJ_LEGACY_UART_PORT = CONFIG.actj_legacy_uart_port
ACTJ_LEGACY_BAUDRATE = CONFIG.actj_legacy_baudrate
ACTJ_LEGACY_GPIO_PINS = CONFIG.actj_legacy_gpio_pins
ACTJ_LEGACY_TIMEOUT = CONFIG.actj_legacy_timeout
ACTJ_LEGACY_AUTO_START = CONFIG.actj_legacy_auto_start
LCD_ENABLED = CONFIG.lcd_enabled
LCD_TYPE = CONFIG.lcd_type
LCD_ADDRESS = CONFIG.lcd_address
LCD_BUS = CONFIG.lcd_bus
LCD_WIDTH = CONFIG.lcd_width
LCD_HEIGHT = CONFIG.lcd_height
LCD_MESSAGES = CONFIG.lcd_messages
