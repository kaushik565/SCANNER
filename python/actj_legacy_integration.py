#!/usr/bin/env python3

"""
ACTJv20(RJSR) Legacy Firmware Integration

This module integrates the modern main.py batch scanning application 
with the existing ACTJv20(RJSR) PIC18F4550 firmware.

Integration Features:
- UART protocol compatibility with existing SBC_Rpi.c functions
- GPIO handshaking using RASP_IN_PIC, INT_PIC, SHD_PIC signals  
- Batch validation logic that works with firmware QR commands
- Automatic mechanism control via firmware responses
- Legacy LCD display and buzzer control through PIC
"""

import logging
import os
import time
import threading
from typing import Optional, Callable, Dict, Tuple
from enum import Enum

try:
    from actj_uart_protocol import ACTJv20UARTProtocol, get_uart_protocol
    from hardware import get_hardware_controller
except ImportError:
    # Fallback for systems without hardware
    ACTJv20UARTProtocol = None
    get_uart_protocol = None
    get_hardware_controller = None

class ACTJLegacyState(Enum):
    """State machine for ACTJ legacy integration"""
    INITIALIZING = "INITIALIZING"
    READY = "READY"  
    BATCH_ACTIVE = "BATCH_ACTIVE"
    SCANNING = "SCANNING"
    ERROR = "ERROR"
    SHUTDOWN = "SHUTDOWN"

class ACTJLegacyIntegration:
    """
    Integration layer between main.py and ACTJv20(RJSR) firmware.
    
    This class handles:
    - UART communication with PIC18F4550 
    - GPIO control signals (RASP_IN_PIC, INT_PIC, SHD_PIC)
    - Batch context management for QR validation
    - Legacy LCD and mechanism control
    """
    
    def __init__(self, camera_scanner=None):
        self.logger = logging.getLogger("actj.legacy")
        self.state = ACTJLegacyState.INITIALIZING
        self.uart_protocol = None
        self.hardware = None
        self.camera_scanner = camera_scanner
        self.lcd_controller = None  # LCD is controlled by PIC firmware, not Python
        
        # Batch context for QR validation
        self.current_batch_line = None
        self.current_batch_number = None
        self.current_mould_ranges = {}
        self.duplicate_checker = None
        
        # Integration callbacks
        self.qr_result_callback = None
        self.error_callback = None
        
        # Initialize hardware and UART if available
        self._initialize_hardware()
        
    def _initialize_hardware(self):
        """Initialize hardware controllers and UART protocol."""
        try:
            if get_hardware_controller:
                self.hardware = get_hardware_controller()
                self.logger.info("Hardware controller initialized")
            
            if get_uart_protocol:
                self.uart_protocol = get_uart_protocol(camera_scanner=self.camera_scanner)
                self.uart_protocol.set_qr_validator(self._validate_qr_code)
                self.logger.info("UART protocol initialized with camera scanner")
                
            self.state = ACTJLegacyState.READY
            
        except Exception as e:
            self.logger.error(f"Hardware initialization failed: {e}")
            self.state = ACTJLegacyState.ERROR
    
    def startup_sequence(self):
        """
        Perform startup sequence to match ACTJv20 expectations.
        This replicates the behavior in Main_PCR.c initialization.
        """
        try:
            if self.hardware:
                # Signal that Pi has booted and is ready for commands
                # RASP_IN_PIC must be HIGH for firmware to proceed
                self.hardware.signal_ready_to_firmware()
                time.sleep(0.1)
                self.logger.info("ACTJv20 startup sequence completed - Pi ready (RASP_IN_PIC HIGH)")
                
            if self.uart_protocol:
                self.uart_protocol.start_listening()
                self.logger.info("Started listening for ACTJv20 commands")
                
            self.state = ACTJLegacyState.READY
            
        except Exception as e:
            self.logger.error(f"Startup sequence failed: {e}")
            self.state = ACTJLegacyState.ERROR
    
    def set_batch_context(self, batch_line: str, mould_ranges: Dict[str, Tuple[str, str]], 
                         duplicate_checker: Callable[[str], bool], batch_number: str = ""):
        """
        Set batch context for QR validation.
        
        Args:
            batch_line: Single letter batch line (A, B, C, etc.)
            mould_ranges: Dict mapping mould names to (start_qr, end_qr) tuples
            duplicate_checker: Function to check if QR is duplicate
            batch_number: Batch number for display purposes
        """
        self.current_batch_line = batch_line.upper()
        self.current_mould_ranges = mould_ranges
        self.duplicate_checker = duplicate_checker
        self.current_batch_number = batch_number
        
        # Display batch setup on LCD
        if self.lcd_controller:
            self.lcd_controller.display_message(
                f"SETUP: {batch_line}",
                f"MOULDS: {len(mould_ranges)}",
                clear=True, delay=2
            )
        
        self.logger.info(f"Batch context set - Line: {batch_line}, Moulds: {len(mould_ranges)}")
        
    def handle_batch_start(self):
        """Handle batch start operations for ACTJv20 integration."""
        try:
            self.state = ACTJLegacyState.BATCH_ACTIVE
            
            # Signal PIC that Pi is ready to accept start command
            if self.hardware:
                self.hardware.signal_ready_to_firmware()

            if self.send_firmware_command('B'):
                self.logger.info("Sent 'B' batch-ready handshake to firmware")
            else:
                self.logger.warning("Unable to transmit 'B' batch-ready handshake")
                
            self.logger.info("ACTJv20 batch started - firmware ready for scanning")
            
        except Exception as e:
            self.logger.error(f"Batch start failed: {e}")
            self.state = ACTJLegacyState.ERROR
    
    def handle_batch_end(self):
        """Handle batch end operations for ACTJv20 integration."""
        try:
            self.state = ACTJLegacyState.READY
            
            # Clear batch context
            self.current_batch_line = None
            self.current_mould_ranges = {}
            self.duplicate_checker = None
            
            if self.hardware:
                self.hardware.signal_busy_to_firmware()
                
            self.logger.info("ACTJv20 batch ended - firmware returned to ready state")
            
        except Exception as e:
            self.logger.error(f"Batch end failed: {e}")
            self.state = ACTJLegacyState.ERROR
    
    def _validate_qr_code(self, qr_code: str) -> Tuple[str, Optional[str]]:
        """
        Validate QR code using current batch context.
        This function is called by the UART protocol when QR scan is requested.
        
        Args:
            qr_code: The scanned QR code
            
        Returns:
            Tuple of (status, mould) where status is 'PASS', 'FAIL', etc.
        """
        try:
            if not self.current_batch_line or not self.current_mould_ranges:
                self.logger.warning("QR validation requested but no batch context set")
                return ("FAIL", None)
            
            # Import QR validation logic from main.py
            try:
                from logic import handle_qr_scan
            except ImportError:
                # Fallback validation logic for testing
                self.logger.warning("Logic module not found, using fallback validation")
                return self._fallback_qr_validation(qr_code)
            
            status, mould = handle_qr_scan(
                qr_code,
                self.current_batch_line,
                self.current_mould_ranges,
                duplicate_checker=self.duplicate_checker if self.duplicate_checker else lambda x: False
            )
            
            self.logger.info(f"QR validation: {qr_code} -> {status} (mould: {mould})")
            
            # Display result on LCD via PIC
            if self.lcd_controller:
                self.lcd_controller.show_scanning_status(status, qr_code)
            
            # Call result callback if set (for UI updates)
            if self.qr_result_callback:
                self.qr_result_callback(qr_code, status, mould)
            
            return (status, mould)
            
        except Exception as e:
            self.logger.error(f"QR validation error: {e}")
            return ("FAIL", None)
    
    def _fallback_qr_validation(self, qr_code: str) -> Tuple[str, Optional[str]]:
        """Fallback QR validation for testing when logic module is not available."""
        try:
            # Basic validation - check format and line
            if len(qr_code) != 14 or not qr_code.isalnum():
                return ("INVALID FORMAT", None)
            
            # Check batch line (position 1)
            if qr_code[1] != self.current_batch_line:
                return ("LINE MISMATCH", None)
            
            # Check if QR is in any mould range
            for mould_name, (start_qr, end_qr) in self.current_mould_ranges.items():
                if start_qr <= qr_code <= end_qr:
                    # Check for duplicates
                    if self.duplicate_checker and self.duplicate_checker(qr_code):
                        return ("DUPLICATE", mould_name)
                    return ("PASS", mould_name)
            
            return ("OUT OF BATCH", None)
            
        except Exception as e:
            self.logger.error(f"Fallback validation error: {e}")
            return ("FAIL", None)
    
    def process_manual_qr(self, qr_code: str) -> Tuple[str, Optional[str]]:
        """
        Process manually entered QR code (for testing or backup).
        
        Args:
            qr_code: The QR code to process
            
        Returns:
            Tuple of (status, mould)
        """
        try:
            if self.uart_protocol:
                result = self.uart_protocol.process_qr_input(qr_code)
                if result is not None:
                    return result
            
            # Fallback to direct validation
            return self._validate_qr_code(qr_code)
        except Exception as e:
            self.logger.error(f"Manual QR processing failed: {e}")
            return ("FAIL", None)
    
    def set_result_callback(self, callback: Callable[[str, str, Optional[str]], None]):
        """
        Set callback function for QR scan results.
        
        Args:
            callback: Function that takes (qr_code, status, mould) parameters
        """
        self.qr_result_callback = callback
    
    def set_error_callback(self, callback: Callable[[str], None]):
        """
        Set callback function for errors.
        
        Args:
            callback: Function that takes error message parameter
        """
        self.error_callback = callback
    
    def get_firmware_status(self) -> dict:
        """
        Get current firmware status information.
        
        Returns:
            Dictionary with firmware status data
        """
        return {
            'integration_state': self.state.value,
            'uart_active': self.uart_protocol is not None,
            'hardware_active': self.hardware is not None,
            'batch_line': self.current_batch_line,
            'mould_count': len(self.current_mould_ranges) if self.current_mould_ranges else 0
        }
    
    def send_firmware_command(self, command: str) -> bool:
        """
        Send direct command to firmware (for advanced control).
        
        Args:
            command: Single character command
            
        Returns:
            True if command sent successfully
        """
        try:
            if self.uart_protocol and self.uart_protocol.serial_port:
                self.uart_protocol.serial_port.write(command.encode('ascii'))
                self.logger.debug(f"Sent firmware command: {command}")
                return True
            else:
                self.logger.warning("Cannot send firmware command - UART not available")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to send firmware command: {e}")
            return False
    
    def shutdown(self):
        """Shutdown the legacy integration system."""
        try:
            self.state = ACTJLegacyState.SHUTDOWN
            
            if self.uart_protocol:
                self.uart_protocol.stop_listening()
            
            if self.hardware:
                # Signal shutdown to firmware
                try:
                    self.hardware.signal_shutdown_to_firmware()
                except:
                    pass
            
            self.logger.info("ACTJv20 legacy integration shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Shutdown error: {e}")

# Singleton instance management
_legacy_integration: Optional[ACTJLegacyIntegration] = None
_legacy_mode_enabled = os.getenv('ACTJ_LEGACY_MODE', '1').lower() in ('1', 'true', 'yes', 'on')

def get_legacy_integration(camera_scanner=None) -> ACTJLegacyIntegration:
    """Get singleton legacy integration instance."""
    global _legacy_integration
    if _legacy_integration is None:
        _legacy_integration = ACTJLegacyIntegration(camera_scanner=camera_scanner)
    elif camera_scanner and not _legacy_integration.camera_scanner:
        # Update camera scanner if not already set
        _legacy_integration.camera_scanner = camera_scanner
        if _legacy_integration.uart_protocol:
            _legacy_integration.uart_protocol.camera_scanner = camera_scanner
    return _legacy_integration

def is_legacy_mode() -> bool:
    """Check if legacy mode is enabled."""
    return _legacy_mode_enabled

def start_legacy_integration():
    """Start the legacy integration system."""
    if is_legacy_mode():
        integration = get_legacy_integration()
        integration.startup_sequence()
        return integration
    return None

def stop_legacy_integration():
    """Stop the legacy integration system."""
    global _legacy_integration
    if _legacy_integration:
        _legacy_integration.shutdown()
        _legacy_integration = None

# Example usage and testing
if __name__ == "__main__":
    # Test the legacy integration
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    
    print("ACTJv20(RJSR) Legacy Integration Test")
    print("=====================================")
    
    # Initialize integration
    integration = get_legacy_integration()
    print(f"Integration state: {integration.state}")
    
    # Test batch context
    mould_ranges = {
        'A01': ('1A345601234567', '1A345650234567'),
        'A02': ('1A345651234567', '1A345700234567')
    }
    
    def test_duplicate_checker(qr_code):
        return False  # No duplicates for test
    
    integration.set_batch_context('A', mould_ranges, test_duplicate_checker)
    integration.handle_batch_start()
    
    # Test QR validation
    test_qrs = [
        '1A345601234567',  # Should pass
        '1B345601234567',  # Wrong line
        '1A345999234567',  # Out of range
        'INVALID_QR'       # Invalid format
    ]
    
    for qr in test_qrs:
        status, mould = integration._validate_qr_code(qr)
        print(f"QR: {qr} -> Status: {status}, Mould: {mould}")
    
    # Test firmware status
    status = integration.get_firmware_status()
    print(f"\nFirmware Status: {status}")
    
    # Cleanup
    integration.handle_batch_end()
    integration.shutdown()
    print("\nTest completed successfully!")