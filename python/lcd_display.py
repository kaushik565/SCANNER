"""LCD display controller for the jig's small LCD panel.

This module provides LCD display support for showing status messages
on a small LCD connected to the ASECT controller PCB.

Supports:
- I2C LCD displays (16x2, 20x4, etc.)
- Mock LCD for testing without hardware
- Welcome messages, status updates, batch info
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from config import (
    LCD_ENABLED,
    LCD_TYPE,
    LCD_ADDRESS,
    LCD_WIDTH,
    LCD_HEIGHT,
    LCD_MESSAGES,
)

try:  # pragma: no cover - hardware optional
    import RPi.GPIO as GPIO  # type: ignore
    from RPLCD.i2c import CharLCD  # type: ignore
except (ImportError, RuntimeError):  # pragma: no cover - hardware optional
    GPIO = None
    CharLCD = None


class BaseLCDController:
    """Interface for LCD operations."""
    
    def __init__(self, width: int = 16, height: int = 2) -> None:
        self.width = width
        self.height = height
    
    def clear(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError
    
    def write_line(self, line: int, text: str, center: bool = False) -> None:  # pragma: no cover - interface
        raise NotImplementedError
    
    def write_lines(self, lines: list[str]) -> None:  # pragma: no cover - interface
        raise NotImplementedError
    
    def close(self) -> None:  # pragma: no cover - interface
        pass


class MockLCDController(BaseLCDController):
    """Mock LCD controller for development without hardware."""
    
    def __init__(self, width: int = 16, height: int = 2) -> None:
        super().__init__(width, height)
        self._log = logging.getLogger("lcd")
        self._screen = [" " * width for _ in range(height)]
        self._log.info("Mock LCD initialized (%dx%d)", width, height)
    
    def clear(self) -> None:
        self._screen = [" " * self.width for _ in range(self.height)]
        self._log.debug("LCD cleared")
        self._print_screen()
    
    def write_line(self, line: int, text: str, center: bool = False) -> None:
        if 0 <= line < self.height:
            if center:
                text = text.center(self.width)
            else:
                text = text.ljust(self.width)
            self._screen[line] = text[:self.width]
            self._log.debug("LCD line %d: '%s'", line, text.strip())
            self._print_screen()
    
    def write_lines(self, lines: list[str]) -> None:
        for i, line in enumerate(lines[:self.height]):
            self.write_line(i, line, center=True)
    
    def _print_screen(self) -> None:
        """Print current LCD state for debugging."""
        border = "+" + "-" * self.width + "+"
        self._log.debug("LCD Display:")
        self._log.debug(border)
        for line in self._screen:
            self._log.debug("|%s|", line)
        self._log.debug(border)


class I2CLCDController(BaseLCDController):  # pragma: no cover - hardware dependent
    """I2C LCD controller for real hardware."""
    
    def __init__(self, address: str, width: int = 16, height: int = 2, bus: int = 0) -> None:
        super().__init__(width, height)
        self._log = logging.getLogger("lcd")
        
        if CharLCD is None:
            raise RuntimeError("RPLCD library not available")
        
        # Convert hex address string to int
        addr = int(address, 16) if isinstance(address, str) else address
        
        try:
            # Use specified I2C bus (default to bus 0 for Raspberry Pi compatibility)
            self._lcd = CharLCD('PCF8574', addr, port=bus, cols=width, rows=height)
            self._log.info("I2C LCD initialized at address %s on bus %d (%dx%d)", address, bus, width, height)
            self.clear()
        except Exception as e:
            self._log.error("Failed to initialize I2C LCD: %s", e)
            raise
    
    def clear(self) -> None:
        try:
            self._lcd.clear()
            time.sleep(0.1)  # Allow LCD to process
        except Exception as e:
            self._log.error("LCD clear failed: %s", e)
    
    def write_line(self, line: int, text: str, center: bool = False) -> None:
        if not (0 <= line < self.height):
            return
        
        try:
            if center:
                text = text.center(self.width)
            else:
                text = text.ljust(self.width)
            
            self._lcd.cursor_pos = (line, 0)
            self._lcd.write_string(text[:self.width])
        except Exception as e:
            self._log.error("LCD write failed: %s", e)
    
    def write_lines(self, lines: list[str]) -> None:
        self.clear()
        for i, line in enumerate(lines[:self.height]):
            self.write_line(i, line, center=True)
    
    def close(self) -> None:
        try:
            if hasattr(self, '_lcd'):
                self._lcd.close()
        except Exception:
            pass


def get_lcd_controller() -> Optional[BaseLCDController]:
    """Factory function to create appropriate LCD controller."""
    if not LCD_ENABLED:
        return None
    
    try:
        if LCD_TYPE.lower() == "i2c" and CharLCD is not None:
            return I2CLCDController(LCD_ADDRESS, LCD_WIDTH, LCD_HEIGHT)
        elif LCD_TYPE.lower() == "mock":
            return MockLCDController(LCD_WIDTH, LCD_HEIGHT)
    except Exception as e:
        logging.getLogger("lcd").exception("Falling back to mock LCD: %s", e)
    
    # Fallback to mock
    return MockLCDController(LCD_WIDTH, LCD_HEIGHT)


class LCDManager:
    """High-level LCD manager for the jig application."""
    
    def __init__(self) -> None:
        self.lcd = get_lcd_controller()
        self._log = logging.getLogger("lcd")
    
    def show_welcome(self) -> None:
        """Display welcome message on startup."""
        if self.lcd:
            welcome_msg = LCD_MESSAGES.get("welcome", "WELCOME")
            self.lcd.write_lines([welcome_msg, "MOLBIO JIG"])
    
    def show_ready(self) -> None:
        """Display ready status."""
        if self.lcd:
            ready_msg = LCD_MESSAGES.get("ready", "JIG READY")
            self.lcd.write_lines([ready_msg, ""])
    
    def show_batch_info(self, batch_number: str, line: str) -> None:
        """Display current batch information."""
        if self.lcd:
            batch_display = f"B:{batch_number[:10]}" if len(batch_number) <= 10 else f"B:{batch_number[:9]}+"
            line_display = f"L:{line}"
            self.lcd.write_lines([batch_display, line_display])
    
    def show_scanning(self) -> None:
        """Display scanning status."""
        if self.lcd:
            scanning_msg = LCD_MESSAGES.get("scanning", "SCANNING...")
            self.lcd.write_lines([scanning_msg, ""])
    
    def show_scan_result(self, status: str, count: int = 0) -> None:
        """Display scan result briefly."""
        if self.lcd:
            status_icons = {
                "PASS": "✓ PASS",
                "DUPLICATE": "⚠ DUP",
                "INVALID FORMAT": "✗ FORMAT",
                "LINE MISMATCH": "✗ LINE",
                "OUT OF BATCH": "✗ RANGE",
            }
            display_status = status_icons.get(status, status)
            count_display = f"#{count}" if count > 0 else ""
            self.lcd.write_lines([display_status[:16], count_display])
    
    def show_error(self, message: str) -> None:
        """Display error message."""
        if self.lcd:
            self.lcd.write_lines(["ERROR", message[:16]])
    
    def clear(self) -> None:
        """Clear the display."""
        if self.lcd:
            self.lcd.clear()
    
    def close(self) -> None:
        """Clean up LCD resources."""
        if self.lcd:
            self.lcd.close()