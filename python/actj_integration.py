"""
ACTJ Integration Module - Bridge between mechanical jig and QR validation
This module handles communication with the existing ACTJ controller while
adding intelligent QR validation and batch tracking.
"""

import serial
import time
import logging
from typing import Optional, Tuple
import threading
from enum import Enum

class ACTJCommands(Enum):
    """Command codes for ACTJ controller communication"""
    START_SCAN = 20      # Start QR scanning (with retry)
    START_SCAN_FINAL = 19  # Final QR scan attempt
    STOP_RECORDING = 0   # Stop recording
    START_RECORDING = 23 # Start recording
    
class ACTJResponses(Enum):
    """Response codes from ACTJ controller"""
    ACCEPTED = 'A'       # QR code accepted (PASS)
    REJECTED = 'R'       # QR code rejected (FAIL)
    SCANNER_ERROR = 'S'  # Scanner hardware error
    HARDWARE_ERROR = 'H' # Hardware error
    NO_QR = 'Q'          # No QR code detected
    LENGTH_ERROR = 'L'   # QR length error
    DUPLICATE = 'D'      # Duplicate QR code
    REPEATED_TEST = 'C'  # Cartridge already tested
    LOG_ERROR = 'B'      # Logging error

class ACTJController:
    """Interface to existing ACTJ controller via UART"""
    
    def __init__(self, port: str = "/dev/ttyS0", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.logger = logging.getLogger("actj")
        self._running = False
        self._response_callback = None
        
    def connect(self) -> bool:
        """Establish UART connection to ACTJ controller"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            self.logger.info(f"Connected to ACTJ controller on {self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to ACTJ controller: {e}")
            return False
    
    def disconnect(self):
        """Close UART connection"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.logger.info("Disconnected from ACTJ controller")
    
    def send_command(self, command: ACTJCommands) -> bool:
        """Send command to ACTJ controller"""
        if not self.serial_conn or not self.serial_conn.is_open:
            self.logger.error("ACTJ controller not connected")
            return False
        
        try:
            command_byte = bytes([command.value])
            self.serial_conn.write(command_byte)
            self.serial_conn.flush()
            self.logger.debug(f"Sent command: {command.name} ({command.value})")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send command {command.name}: {e}")
            return False
    
    def read_response(self, timeout: float = 12.0) -> Optional[ACTJResponses]:
        """Read response from ACTJ controller"""
        if not self.serial_conn or not self.serial_conn.is_open:
            return None
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if self.serial_conn.in_waiting > 0:
                    response = self.serial_conn.read(1).decode('ascii')
                    for resp in ACTJResponses:
                        if resp.value == response:
                            self.logger.debug(f"Received response: {resp.name}")
                            return resp
                    self.logger.warning(f"Unknown response: {response}")
                    return None
                time.sleep(0.01)
            except Exception as e:
                self.logger.error(f"Error reading response: {e}")
                break
        
        self.logger.warning("Response timeout")
        return None
    
    def start_scanning_sequence(self, retry: bool = True) -> Optional[ACTJResponses]:
        """Start the QR scanning sequence"""
        command = ACTJCommands.START_SCAN if retry else ACTJCommands.START_SCAN_FINAL
        
        if not self.send_command(command):
            return None
        
        # Wait for mechanical positioning and QR scan
        response = self.read_response(timeout=12.0)
        return response
    
    def notify_scan_result(self, qr_result: str) -> bool:
        """Notify ACTJ of QR validation result"""
        # Map our validation results to ACTJ response codes
        if qr_result == "PASS":
            response_char = ACTJResponses.ACCEPTED.value
        elif qr_result in ["DUPLICATE", "INVALID FORMAT", "LINE MISMATCH", "OUT OF BATCH"]:
            response_char = ACTJResponses.REJECTED.value
        else:
            response_char = ACTJResponses.SCANNER_ERROR.value
        
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.write(response_char.encode())
                self.serial_conn.flush()
                return True
        except Exception as e:
            self.logger.error(f"Failed to send scan result: {e}")
        
        return False

class MechanicalJigInterface:
    """High-level interface combining mechanical control with QR validation"""
    
    def __init__(self, actj_controller: ACTJController, qr_validator):
        self.actj = actj_controller
        self.qr_validator = qr_validator
        self.logger = logging.getLogger("mech_jig")
        self._running = False
        self._scan_callback = None
        
    def set_scan_callback(self, callback):
        """Set callback function for scan events"""
        self._scan_callback = callback
    
    def start_operation(self) -> bool:
        """Start the integrated jig operation"""
        if not self.actj.connect():
            return False
        
        self._running = True
        self.logger.info("Mechanical jig operation started")
        return True
    
    def stop_operation(self):
        """Stop jig operation"""
        self._running = False
        self.actj.disconnect()
        self.logger.info("Mechanical jig operation stopped")
    
    def process_single_cartridge(self, qr_code: str, batch_info: dict) -> Tuple[str, str]:
        """
        Process a single cartridge with integrated mechanical and QR validation
        
        Returns:
            (status, message) where status is PASS/REJECT and message explains result
        """
        # Step 1: Validate QR code against batch parameters
        validation_result = self._validate_qr_with_batch(qr_code, batch_info)
        
        # Step 2: Notify ACTJ controller of result
        self.actj.notify_scan_result(validation_result["status"])
        
        # Step 3: Trigger appropriate mechanical response
        self._trigger_mechanical_response(validation_result["status"])
        
        return validation_result["status"], validation_result["message"]
    
    def _validate_qr_with_batch(self, qr_code: str, batch_info: dict) -> dict:
        """Validate QR code using your existing validation logic"""
        # This integrates with your existing handle_qr_scan function
        # Import and use your existing validation logic here
        
        from logic import handle_qr_scan
        
        try:
            # Use your existing validation logic
            status, qr_display, mould = handle_qr_scan(
                qr_code, 
                batch_info["batch_number"],
                batch_info["line"], 
                batch_info["num_moulds"],
                batch_info.get("duplicate_tracker")
            )
            
            return {
                "status": status,
                "message": f"QR: {qr_display} - {status}",
                "qr_display": qr_display,
                "mould": mould
            }
        except Exception as e:
            self.logger.error(f"QR validation failed: {e}")
            return {
                "status": "INVALID FORMAT",
                "message": f"Validation error: {str(e)}",
                "qr_display": qr_code,
                "mould": None
            }
    
    def _trigger_mechanical_response(self, status: str):
        """Trigger mechanical response based on validation result"""
        if status == "PASS":
            # ACTJ will handle pass mechanism (forward to next position)
            self.logger.info("Cartridge PASSED - mechanical advance")
        else:
            # ACTJ will handle reject mechanism (divert to reject bin)
            self.logger.info(f"Cartridge REJECTED ({status}) - mechanical reject")
    
    def run_continuous_operation(self):
        """Run continuous jig operation (called from your main loop)"""
        while self._running:
            try:
                # Wait for ACTJ to signal ready for scan
                response = self.actj.read_response(timeout=1.0)
                
                if response == ACTJResponses.ACCEPTED:
                    # ACTJ processed a cartridge successfully
                    if self._scan_callback:
                        self._scan_callback("CARTRIDGE_ADVANCED")
                
                elif response == ACTJResponses.REJECTED:
                    # ACTJ rejected a cartridge
                    if self._scan_callback:
                        self._scan_callback("CARTRIDGE_REJECTED") 
                
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error in continuous operation: {e}")
                time.sleep(1.0)

def create_integrated_jig() -> MechanicalJigInterface:
    """Factory function to create integrated jig controller"""
    actj = ACTJController()
    
    # Your existing QR validator (reuse existing logic)
    from logic import handle_qr_scan
    
    mech_jig = MechanicalJigInterface(actj, handle_qr_scan)
    
    return mech_jig

# Usage example for integration with your main.py:
"""
# In your BatchScannerApp class:

def _setup_mechanical_integration(self):
    if JIG_ENABLED:
        self.mechanical_jig = create_integrated_jig()
        self.mechanical_jig.set_scan_callback(self._on_mechanical_event)
        
def _on_mechanical_event(self, event_type: str):
    # Handle mechanical jig events
    if event_type == "CARTRIDGE_ADVANCED":
        self._update_scan_count()
    elif event_type == "CARTRIDGE_REJECTED":
        self._update_reject_count()
        
def _handle_qr_scan_with_mechanical(self, qr_code: str):
    if self.mechanical_jig:
        batch_info = {
            "batch_number": self.batch_number_var.get(),
            "line": self.line_var.get(),
            "num_moulds": self.num_moulds,
            "duplicate_tracker": self.duplicate_tracker
        }
        
        status, message = self.mechanical_jig.process_single_cartridge(qr_code, batch_info)
        self._update_ui_with_result(status, message)
        
        # Update jig lights
        if hasattr(self.jig, 'set_light'):
            light_status = "pass" if status == "PASS" else "reject"
            self.jig.set_light(light_status)
    else:
        # Fall back to existing manual QR handling
        self._handle_qr_scan_original(qr_code)
"""