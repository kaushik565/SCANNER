# hardware.py

"""Hardware controller abstraction layer.

Selects a concrete controller based on the `settings.ini` hardware section.
Defaults to mock logging if the requested controller cannot be initialised.
"""

import logging
import time
from typing import Optional

from config import (
    ACTJ_LEGACY_GPIO_PINS,
    HARDWARE_CONTROLLER,
    HARDWARE_PIN_MODE,
    HARDWARE_PINS,
    JIG_BUSY_SIGNAL_PIN,
)

try:  # pragma: no cover - hardware optional
    import RPi.GPIO as GPIO  # type: ignore
except (ImportError, RuntimeError):  # pragma: no cover - hardware optional
    GPIO = None


class BaseHardwareController:
    """Interface for hardware operations."""

    def light_on(self, color: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def light_off(self, color: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def buzz(self, duration: float) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def set_busy(self, busy: bool) -> None:  # pragma: no cover - interface
        """Toggle busy indicator line if supported."""
        raise NotImplementedError
    
    def set_sbc_busy(self, busy: bool) -> None:  # pragma: no cover - interface
        """Toggle SBC busy pin (GPIO 18) - SCANNER hardware compatibility."""
        raise NotImplementedError
    
    def set_status(self, ready: bool) -> None:  # pragma: no cover - interface
        """Toggle status pin (GPIO 21) - SCANNER hardware compatibility."""
        raise NotImplementedError
    
    def set_rasp_in_pic(self, state: bool) -> None:  # pragma: no cover - interface
        """Toggle RASP_IN_PIC pin for ACTJv20(RJSR) legacy hardware compatibility."""
        raise NotImplementedError
    
    def signal_ready_to_firmware(self) -> None:  # pragma: no cover - interface
        """Signal ready state to ACTJv20(RJSR) firmware (RASP_IN_PIC HIGH)."""
        raise NotImplementedError
    
    def signal_busy_to_firmware(self) -> None:  # pragma: no cover - interface
        """Signal busy state to ACTJv20(RJSR) firmware (RASP_IN_PIC LOW)."""
        raise NotImplementedError
    
    def signal_rejection_pulse(self) -> None:  # pragma: no cover - interface
        """Send rejection pulse sequence to help ACTJv20 mechanism plate movement."""
        raise NotImplementedError
    
    def signal_accept_pulse(self) -> None:  # pragma: no cover - interface
        """Send accept pulse sequence to help ACTJv20 mechanism plate movement."""
        raise NotImplementedError
    
    def initialize_actj_gpio(self) -> None:  # pragma: no cover - interface
        """Initialize GPIO specifically for ACTJv20 communication."""
        raise NotImplementedError

    # Sensor helpers (optional on mock)
    def enable_sensor_edge_detect(self, edge=None) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def wait_for_cartridge(self, edge=None, timeout=None):  # pragma: no cover - interface
        raise NotImplementedError


class MockHardwareController(BaseHardwareController):
    """Default controller used during development without real hardware."""

    def __init__(self, handshake_pins: Optional[dict[str, int]] = None) -> None:
        self.logger = logging.getLogger("hardware")
        self.handshake_pins = handshake_pins or {}

    def light_on(self, color: str) -> None:
        self.logger.debug("LIGHT ON: %s", color)

    def light_off(self, color: str) -> None:
        self.logger.debug("LIGHT OFF: %s", color)

    def buzz(self, duration: float) -> None:
        self.logger.debug("BUZZ for %.2fs", duration)
        time.sleep(duration)

    def set_busy(self, busy: bool) -> None:
        state = "HIGH" if busy else "LOW"
        self.logger.debug("SBC BUSY -> %s", state)
    
    def set_sbc_busy(self, busy: bool) -> None:
        state = "HIGH" if busy else "LOW"
        self.logger.debug("GPIO 18 (SBC_BUSY) -> %s", state)
    
    def set_status(self, ready: bool) -> None:
        state = "HIGH" if ready else "LOW"
        self.logger.debug("GPIO 21 (STATUS) -> %s", state)
    
    def set_rasp_in_pic(self, state: bool) -> None:
        pin = self.handshake_pins.get("rasp_in_pic")
        pin_state = "HIGH" if state else "LOW"
        self.logger.debug("RASP_IN_PIC (pin %s) -> %s", pin if pin is not None else "n/a", pin_state)
    
    def signal_ready_to_firmware(self) -> None:
        self.logger.debug("ACTJv20(RJSR) READY: RASP_IN_PIC -> HIGH")
        self.set_rasp_in_pic(True)
    
    def signal_busy_to_firmware(self) -> None:
        self.logger.debug("ACTJv20(RJSR) BUSY: RASP_IN_PIC -> LOW")
        self.set_rasp_in_pic(False)
    
    def signal_rejection_pulse(self) -> None:
        self.logger.debug("ACTJv20(RJSR) MOCK: Rejection pulse sequence")
    
    def signal_accept_pulse(self) -> None:
        self.logger.debug("ACTJv20(RJSR) MOCK: Accept pulse sequence")
    
    def initialize_actj_gpio(self) -> None:
        self.logger.debug("ACTJv20(RJSR) MOCK: GPIO initialization")

    # --- Sensor helpers (no-op for development) ---
    def enable_sensor_edge_detect(self, edge=None) -> None:
        self.logger.debug("enable_sensor_edge_detect (mock)")

    def wait_for_cartridge(self, edge=None, timeout=None):
        self.logger.debug("wait_for_cartridge (mock): simulating detection")
        time.sleep(0.05)
        return True


class GPIOHardwareController(BaseHardwareController):  # pragma: no cover - hardware dependent
    """GPIO implementation targeting Raspberry Pi pins."""

    def __init__(
        self,
        pin_mode: str,
        pin_map: dict[str, int],
        handshake_pins: Optional[dict[str, int]] = None,
    ) -> None:
        if GPIO is None:
            raise RuntimeError("RPi.GPIO not available on this system")

        self.logger = logging.getLogger("hardware")
        self.pin_map = pin_map
        self.handshake_pins = handshake_pins or {}

        mode = pin_mode.upper()
        if mode == "BOARD":
            GPIO.setmode(GPIO.BOARD)
        else:
            GPIO.setmode(GPIO.BCM)
        
        # Disable GPIO warnings for pins already in use
        GPIO.setwarnings(False)

        for pin in pin_map.values():
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

        self.busy_pin = JIG_BUSY_SIGNAL_PIN if JIG_BUSY_SIGNAL_PIN else None
        if self.busy_pin:
            GPIO.setup(self.busy_pin, GPIO.OUT, initial=GPIO.LOW)
        
        # SCANNER hardware compatibility: GPIO 18 and 21
        self.sbc_busy_pin = 18  # SBC busy indicator (matches SCANNER)
        self.status_pin = 21    # Status output to PIC (matches SCANNER)
        GPIO.setup(self.sbc_busy_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.status_pin, GPIO.OUT, initial=GPIO.LOW)
        
        # ACTJv20(RJSR) legacy hardware compatibility handshake pins
        self.rasp_in_pic_pin = self.handshake_pins.get("rasp_in_pic", 12)
        self.int_pic_pin = self.handshake_pins.get("int_pic")
        self.shd_pic_pin = self.handshake_pins.get("shd_pic")

        if self.shd_pic_pin is not None:
            GPIO.setup(self.shd_pic_pin, GPIO.OUT, initial=GPIO.LOW)

        if self.int_pic_pin is not None:
            GPIO.setup(self.int_pic_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        if self.rasp_in_pic_pin is not None:
            GPIO.setup(self.rasp_in_pic_pin, GPIO.OUT, initial=GPIO.LOW)

        # Cartridge locating sensor pin (input, matches SCANNER)
        self.locating_sensor_pin = pin_map.get("cartridge_sensor", 20)  # Default to GPIO 20
        GPIO.setup(self.locating_sensor_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def wait_for_cartridge(self, edge=None, timeout=None):
        """Wait for cartridge locating sensor edge (blocking)."""
        # Default to RISING edge if not specified and GPIO is available
        if edge is None and GPIO is not None:  # type: ignore[name-defined]
            edge = GPIO.RISING
        self.logger.debug(f"Waiting for cartridge sensor edge on GPIO {self.locating_sensor_pin}")
        start = time.time()
        while True:
            if GPIO and GPIO.event_detected(self.locating_sensor_pin):
                self.logger.info("Cartridge detected by sensor.")
                return True
            if timeout and (time.time() - start) > timeout:
                self.logger.warning("Cartridge sensor wait timed out.")
                return False
            time.sleep(0.01)

    def enable_sensor_edge_detect(self, edge=None):
        """Enable edge detection for cartridge locating sensor."""
        if GPIO is None:
            return
        if edge is None:
            edge = GPIO.RISING
        GPIO.add_event_detect(self.locating_sensor_pin, edge)

    def _set_pin(self, color: str, state: bool) -> None:
        pin = self.pin_map.get(color.lower())
        if pin is None:
            self.logger.debug("No pin configured for color '%s'", color)
            return
        # Ensure pin is set up as OUTPUT before use
        try:
            GPIO.setup(pin, GPIO.OUT)
        except Exception:
            pass  # Ignore if already set up
        GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)

    def light_on(self, color: str) -> None:
        self._set_pin(color, True)

    def light_off(self, color: str) -> None:
        self._set_pin(color, False)

    def buzz(self, duration: float) -> None:
        buzzer_pin = self.pin_map.get("buzzer")
        if buzzer_pin is None:
            self.logger.debug("No buzzer pin configured")
            return
        # Ensure buzzer pin is set up as OUTPUT before use
        try:
            GPIO.setup(buzzer_pin, GPIO.OUT)
        except Exception:
            pass
        GPIO.output(buzzer_pin, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(buzzer_pin, GPIO.LOW)

    def set_busy(self, busy: bool) -> None:
        if not self.busy_pin:
            return
        try:
            GPIO.setup(self.busy_pin, GPIO.OUT)
        except Exception:
            pass
        GPIO.output(self.busy_pin, GPIO.HIGH if busy else GPIO.LOW)
    
    def set_sbc_busy(self, busy: bool) -> None:
        """Set GPIO 18 (SBC busy indicator) - matches SCANNER hardware."""
        try:
            GPIO.setup(self.sbc_busy_pin, GPIO.OUT)
        except Exception:
            pass
        GPIO.output(self.sbc_busy_pin, GPIO.HIGH if busy else GPIO.LOW)
    
    def set_status(self, ready: bool) -> None:
        """Set GPIO 21 (status to PIC) - matches SCANNER hardware."""
        try:
            GPIO.setup(self.status_pin, GPIO.OUT)
        except Exception:
            pass
        GPIO.output(self.status_pin, GPIO.HIGH if ready else GPIO.LOW)
    
    def set_rasp_in_pic(self, state: bool) -> None:
        """Set GPIO 12 (RASP_IN_PIC for ACTJv20(RJSR) firmware communication)."""
        if self.rasp_in_pic_pin is None:
            self.logger.debug("No RASP_IN_PIC pin configured; ignoring set request")
            return
        try:
            GPIO.output(self.rasp_in_pic_pin, GPIO.HIGH if state else GPIO.LOW)
            self.logger.debug(
                "RASP_IN_PIC (GPIO %s) -> %s",
                self.rasp_in_pic_pin,
                "HIGH" if state else "LOW",
            )
        except Exception as e:
            self.logger.error(
                "Failed to set RASP_IN_PIC GPIO %s: %s",
                self.rasp_in_pic_pin,
                e,
            )
            raise
    
    def signal_ready_to_firmware(self) -> None:
        """Signal ready state to ACTJv20(RJSR) firmware."""
        self.logger.debug("ACTJv20(RJSR) signaling READY to firmware")
        self.set_rasp_in_pic(True)
    
    def signal_busy_to_firmware(self) -> None:
        """Signal busy state to ACTJv20(RJSR) firmware."""
        self.logger.debug("ACTJv20(RJSR) signaling BUSY to firmware")
        self.set_rasp_in_pic(False)
    
    def signal_rejection_pulse(self) -> None:
        """Send rejection pulse sequence to help ACTJv20 mechanism plate movement."""
        self.logger.debug("ACTJv20(RJSR) sending rejection GPIO pulse sequence")
        import time
        # Extended pulse sequence to help mechanism plate movement when QR is rejected
        self.signal_ready_to_firmware()  # Signal ready
        time.sleep(0.1)  # Brief pulse
        self.signal_busy_to_firmware()   # Back to busy  
        time.sleep(0.1)
        self.signal_ready_to_firmware()  # Final ready state
    
    def signal_accept_pulse(self) -> None:
        """Send accept pulse sequence to help ACTJv20 mechanism plate movement."""
        self.logger.debug("ACTJv20(RJSR) sending accept GPIO pulse sequence")
        import time
        # Standard pulse sequence to help mechanism plate movement when QR is accepted
        self.signal_ready_to_firmware()  # Signal ready
        time.sleep(0.1)  # Brief pulse
        self.signal_busy_to_firmware()   # Back to busy  
        time.sleep(0.05)  # Shorter busy for accepts
        self.signal_ready_to_firmware()  # Final ready state
    
    def initialize_actj_gpio(self) -> None:
        """Initialize GPIO specifically for ACTJv20 communication."""
        self.logger.info("Initializing ACTJv20 GPIO communication...")
        if self.rasp_in_pic_pin is None:
            self.logger.debug("No RASP_IN_PIC pin configured; skipping init")
            return
        try:
            import time

            GPIO.output(self.rasp_in_pic_pin, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(self.rasp_in_pic_pin, GPIO.HIGH)
            self.logger.info(
                "ACTJv20 GPIO initialized: RASP_IN_PIC (GPIO %s) = HIGH (READY)",
                self.rasp_in_pic_pin,
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize ACTJv20 GPIO: {e}")
            raise


_controller: Optional[BaseHardwareController] = None


def get_hardware_controller() -> BaseHardwareController:
    """Return a singleton hardware controller instance."""
    global _controller
    if _controller is None:
        _controller = _create_controller()
        # Initialise PIC handshake line to BUSY/LOW until batch ready
        try:
            _controller.set_rasp_in_pic(False)
            rasp_pin = ACTJ_LEGACY_GPIO_PINS.get("rasp_in_pic")
            logging.getLogger("hardware").info(
                "[INIT] RASP_IN_PIC (GPIO %s) forced LOW until batch ready.",
                rasp_pin if rasp_pin is not None else "n/a",
            )
        except Exception as e:
            logging.getLogger("hardware").error(f"[INIT] Failed to drive RASP_IN_PIC LOW: {e}")
    return _controller


def _create_controller() -> BaseHardwareController:
    logger = logging.getLogger("hardware")
    controller = HARDWARE_CONTROLLER.lower().strip()
    if controller == "gpio":
        try:
            return GPIOHardwareController(HARDWARE_PIN_MODE, HARDWARE_PINS, ACTJ_LEGACY_GPIO_PINS)
        except Exception as exc:  # pragma: no cover - hardware dependent
            logger.exception("Falling back to mock hardware: %s", exc)
    return MockHardwareController(ACTJ_LEGACY_GPIO_PINS)
