#!/usr/bin/env python3

"""
ACTJv20(RJSR) LCD Display Integration

The I2C LCD display is controlled entirely by the PIC18F4550 firmware.
The Raspberry Pi sends display commands via UART to the PIC, which then
handles the I2C communication to the LCD.

PIC Firmware LCD Functions Used:
- display(clear, line1, line2, delay) - Main display function
- LCD_Cmd() - Send commands to LCD
- LCD_Print() - Print ROM strings  
- LCD_Print_rammem() - Print RAM strings
- LCD_Clear() - Clear display
- LCD_Begin() - Initialize LCD

UART Protocol for LCD Commands:
- Pi sends: 'D' + line1 + '\n' + line2 + '\n' 
- PIC receives and calls: display(1, line1, line2, 0)
"""

import logging
import time
from typing import Optional

class ACTJLCDController:
    """
    LCD display controller that sends commands to PIC via UART.
    The PIC handles all I2C communication with the actual LCD.
    """
    
    def __init__(self, uart_protocol=None):
        self.logger = logging.getLogger("actj.lcd")
        self.uart_protocol = uart_protocol
        self.lcd_width = 16
        self.lcd_height = 2
        
    def set_uart_protocol(self, uart_protocol):
        """Set the UART protocol for communication with PIC."""
        self.uart_protocol = uart_protocol
        
    def display_message(self, line1: str = "", line2: str = "", clear: bool = True, delay: int = 0):
        """
        Display message on LCD via PIC firmware.
        
        Args:
            line1: First line text (max 16 characters)
            line2: Second line text (max 16 characters)  
            clear: Whether to clear display first
            delay: Delay in seconds after displaying
        """
        try:
            if not self.uart_protocol:
                self.logger.warning("No UART protocol available for LCD display")
                return False
                
            # Truncate lines to LCD width
            line1 = (line1 or "")[:self.lcd_width].ljust(self.lcd_width)
            line2 = (line2 or "")[:self.lcd_width].ljust(self.lcd_width)
            
            # Send LCD command to PIC
            # Format: 'L' + clear_flag + line1 + '\n' + line2 + '\n' + delay
            clear_flag = '1' if clear else '0'
            command = f"L{clear_flag}{line1}\n{line2}\n{delay:02d}"
            
            if self.uart_protocol.serial_port:
                self.uart_protocol.serial_port.write(command.encode('ascii'))
                self.uart_protocol.serial_port.flush()
                self.logger.info(f"LCD Display: '{line1}' | '{line2}'")
                return True
            else:
                self.logger.warning("UART serial port not available")
                return False
                
        except Exception as e:
            self.logger.error(f"LCD display error: {e}")
            return False
    
    def clear_display(self):
        """Clear the LCD display."""
        return self.display_message("", "", clear=True)
    
    def show_welcome(self):
        """Show welcome message."""
        return self.display_message("ACTJ SCANNER", "SYSTEM READY", clear=True, delay=2)
    
    def show_batch_info(self, batch_number: str, batch_line: str):
        """Show batch information."""
        line1 = f"BATCH: {batch_number[:10]}"
        line2 = f"LINE: {batch_line}  READY"
        return self.display_message(line1, line2, clear=True)
    
    def show_scanning_status(self, status: str, qr_code: str = ""):
        """Show scanning status."""
        if status == "SCANNING":
            return self.display_message("QR SCANNING...", "PLEASE WAIT", clear=True)
        elif status == "PASS":
            qr_short = qr_code[:16] if qr_code else ""
            return self.display_message("ACCEPTED", qr_short, clear=True, delay=1)
        elif status == "REJECT" or status == "FAIL":
            return self.display_message("REJECTED", "CHECK QR CODE", clear=True, delay=1)
        elif status == "DUPLICATE":
            return self.display_message("DUPLICATE QR", "ALREADY SCANNED", clear=True, delay=1)
        else:
            return self.display_message("STATUS:", status, clear=True)
    
    def show_counters(self, accepted: int, rejected: int, total: int):
        """Show scan counters."""
        line1 = f"ACC:{accepted:3d} REJ:{rejected:3d}"
        line2 = f"TOTAL: {total:4d}"
        return self.display_message(line1, line2, clear=True)
    
    def show_error(self, error_msg: str):
        """Show error message."""
        return self.display_message("ERROR:", error_msg[:16], clear=True, delay=3)
    
    def show_firmware_status(self, status: str):
        """Show firmware status."""
        return self.display_message("FIRMWARE:", status[:16], clear=True)

# Integration with legacy firmware
class ACTJLCDProtocolHandler:
    """
    Handles LCD-related UART protocol commands for PIC firmware integration.
    This extends the existing UART protocol to handle LCD display commands.
    """
    
    def __init__(self, uart_protocol):
        self.uart_protocol = uart_protocol
        self.lcd_controller = ACTJLCDController(uart_protocol)
        self.logger = logging.getLogger("actj.lcd.protocol")
        
        # Register LCD command handler
        if hasattr(uart_protocol, 'register_command_handler'):
            uart_protocol.register_command_handler('L', self._handle_lcd_command)
    
    def _handle_lcd_command(self, data: str):
        """
        Handle LCD command from main application.
        Format: 'L' + clear_flag + line1 + '\n' + line2 + '\n' + delay
        """
        try:
            # Parse the command data
            if len(data) < 2:
                return False
                
            clear = data[0] == '1'
            lines = data[1:].split('\n')
            
            if len(lines) >= 2:
                line1 = lines[0]
                line2 = lines[1] 
                delay = int(lines[2]) if len(lines) > 2 and lines[2].isdigit() else 0
                
                # Forward to PIC firmware display function
                return self._send_to_pic_display(line1, line2, clear, delay)
            
            return False
            
        except Exception as e:
            self.logger.error(f"LCD command handling error: {e}")
            return False
    
    def _send_to_pic_display(self, line1: str, line2: str, clear: bool, delay: int):
        """
        Send display command to PIC firmware.
        This maps to the firmware's display() function.
        """
        try:
            if not self.uart_protocol.serial_port:
                return False
                
            # The PIC firmware display() function expects:
            # display(char lcd_clear, ram char* line1, ram char* line2, unsigned char delay_1_sec)
            
            # Send a custom command that the PIC can interpret
            # We'll use 'D' command for display
            clear_byte = b'1' if clear else b'0'
            command = b'D' + clear_byte + line1.encode('ascii')[:16].ljust(16, b'\0') + line2.encode('ascii')[:16].ljust(16, b'\0') + bytes([delay])
            
            self.uart_protocol.serial_port.write(command)
            self.uart_protocol.serial_port.flush()
            
            self.logger.debug(f"Sent LCD command to PIC: '{line1}' | '{line2}'")
            return True
            
        except Exception as e:
            self.logger.error(f"PIC LCD command error: {e}")
            return False

# Example PIC firmware handler (to be added to ACTJv20 firmware)
"""
// Add this to SBC_Rpi.c in the command handler

case 'D': {  // Display command
    char clear_flag;
    char line1[17];
    char line2[17]; 
    unsigned char delay_sec;
    
    // Read display command data
    clear_flag = RCREG;  // Clear flag
    for(int i = 0; i < 16; i++) {
        while(!PIR1bits.RCIF);
        line1[i] = RCREG;
    }
    line1[16] = 0;
    
    for(int i = 0; i < 16; i++) {
        while(!PIR1bits.RCIF);
        line2[i] = RCREG;
    }
    line2[16] = 0;
    
    while(!PIR1bits.RCIF);
    delay_sec = RCREG;
    
    // Call existing display function
    display(clear_flag, line1, line2, delay_sec);
    break;
}
"""

# Integration example
if __name__ == "__main__":
    # Test the LCD integration
    logging.basicConfig(level=logging.INFO)
    
    # Mock UART protocol for testing
    class MockUARTProtocol:
        def __init__(self):
            self.serial_port = None
            
        def write(self, data):
            print(f"[MOCK UART] Sending to PIC: {data}")
    
    # Test LCD controller
    uart = MockUARTProtocol()
    lcd = ACTJLCDController(uart)
    
    # Test various display functions
    print("Testing LCD Display Functions:")
    print("=" * 40)
    
    lcd.show_welcome()
    time.sleep(1)
    
    lcd.show_batch_info("BATCH12345", "A")
    time.sleep(1)
    
    lcd.show_scanning_status("SCANNING")
    time.sleep(1)
    
    lcd.show_scanning_status("PASS", "1A345601234567")
    time.sleep(1)
    
    lcd.show_counters(accepted=15, rejected=3, total=18)
    time.sleep(1)
    
    lcd.show_error("UART ERROR")
    
    print("\nLCD Integration test completed!")