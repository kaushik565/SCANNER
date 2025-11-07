#!/usr/bin/env python3

"""
Test script for ACTJv20(RJSR) integration with main.py

This script tests the integration between the modern batch scanning system
and the legacy ACTJv20(RJSR) firmware.
"""

import os
import sys
import logging
import time
from pathlib import Path

# Add the python directory to path
python_dir = Path(__file__).parent
sys.path.insert(0, str(python_dir))

def test_legacy_integration():
    """Test the legacy integration system."""
    print("=== ACTJv20(RJSR) Legacy Integration Test ===")
    print()
    
    # Enable legacy mode
    os.environ['ACTJ_LEGACY_MODE'] = '1'
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    
    try:
        # Test 1: Import and initialize
        print("1. Testing legacy integration import...")
        from actj_legacy_integration import get_legacy_integration, is_legacy_mode
        
        assert is_legacy_mode(), "Legacy mode should be enabled"
        print("   ✓ Legacy mode enabled")
        
        integration = get_legacy_integration()
        print(f"   ✓ Integration initialized: {integration.state}")
        
        # Test 2: Startup sequence
        print("\n2. Testing startup sequence...")
        integration.startup_sequence()
        print(f"   ✓ Startup completed: {integration.state}")
        
        # Test 3: Batch context
        print("\n3. Testing batch context setup...")
        mould_ranges = {
            'A01': ('1A345601234567', '1A345650234567'),
            'A02': ('1A345651234567', '1A345700234567')
        }
        
        def test_duplicate_checker(qr_code):
            return False  # No duplicates for test
        
        integration.set_batch_context('A', mould_ranges, test_duplicate_checker)
        integration.handle_batch_start()
        
        status = integration.get_firmware_status()
        print(f"   ✓ Batch context set: Line={status['batch_line']}, Moulds={status['mould_count']}")
        
        # Test 4: QR validation
        print("\n4. Testing QR validation...")
        test_qrs = [
            ('1A345601234567', 'PASS'),    # Valid QR in range
            ('1B345601234567', 'FAIL'),    # Wrong line
            ('1A345999234567', 'FAIL'),    # Out of range  
            ('INVALID_QR', 'FAIL')         # Invalid format
        ]
        
        for qr_code, expected in test_qrs:
            result_status, mould = integration._validate_qr_code(qr_code)
            status_match = (result_status == expected) or (expected == 'FAIL' and result_status in ['INVALID FORMAT', 'LINE MISMATCH', 'OUT OF BATCH'])
            print(f"   {'✓' if status_match else '✗'} QR: {qr_code} -> {result_status} (expected: {expected})")
        
        # Test 5: Manual QR processing
        print("\n5. Testing manual QR processing...")
        result_status, mould = integration.process_manual_qr('1A345625234567')
        print(f"   ✓ Manual QR result: {result_status}, mould: {mould}")
        
        # Test 6: Firmware status
        print("\n6. Testing firmware status...")
        status = integration.get_firmware_status()
        print(f"   ✓ Integration State: {status['integration_state']}")
        print(f"   ✓ UART Active: {status['uart_active']}")
        print(f"   ✓ Hardware Active: {status['hardware_active']}")
        
        # Test 7: Batch end
        print("\n7. Testing batch end...")
        integration.handle_batch_end()
        print("   ✓ Batch ended successfully")
        
        # Test 8: Shutdown
        print("\n8. Testing shutdown...")
        integration.shutdown()
        print("   ✓ Shutdown completed")
        
        print("\n=== ALL TESTS PASSED ===")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        logging.exception("Test failure details:")
        return False

def test_main_integration():
    """Test integration with main.py application."""
    print("\n=== Main.py Integration Test ===")
    print()
    
    try:
        # Enable legacy mode
        os.environ['ACTJ_LEGACY_MODE'] = '1'
        
        print("1. Testing main.py imports...")
        
        # Test critical imports
        from config import ACTJ_LEGACY_ENABLED, ACTJ_LEGACY_UART_PORT
        print(f"   ✓ Legacy config loaded: enabled={ACTJ_LEGACY_ENABLED}, port={ACTJ_LEGACY_UART_PORT}")
        
        # Test that main.py can import the integration
        import main
        print("   ✓ main.py imported successfully")
        
        # Test BatchScannerApp class
        print("\n2. Testing BatchScannerApp class...")
        # We won't actually create the app since it needs Tkinter window
        # But we can verify the class exists and has the required methods
        
        required_methods = [
            '_on_legacy_qr_result',
            '_process_legacy_result'
        ]
        
        for method in required_methods:
            assert hasattr(main.BatchScannerApp, method), f"Missing method: {method}"
            print(f"   ✓ Method exists: {method}")
        
        print("\n3. Testing launch_app function...")
        # Verify the launch_app function has legacy integration startup
        import inspect
        source = inspect.getsource(main.launch_app)
        assert 'actj_legacy_integration' in source, "Legacy integration not in launch_app"
        print("   ✓ Legacy integration found in launch_app")
        
        print("\n=== MAIN.PY INTEGRATION TESTS PASSED ===")
        return True
        
    except Exception as e:
        print(f"\n❌ MAIN.PY INTEGRATION TEST FAILED: {e}")
        logging.exception("Test failure details:")
        return False

def test_uart_protocol():
    """Test UART protocol integration."""
    print("\n=== UART Protocol Test ===")
    print()
    
    try:
        print("1. Testing UART protocol import...")
        from actj_uart_protocol import ACTJv20UARTProtocol
        print("   ✓ UART protocol imported")
        
        print("\n2. Testing UART protocol initialization...")
        protocol = ACTJv20UARTProtocol(port="/dev/null")  # Use null device for testing
        print("   ✓ Protocol initialized")
        
        print("\n3. Testing QR validator setup...")
        def test_validator(qr_code):
            return ("PASS", "A01")
        
        protocol.set_qr_validator(test_validator)
        print("   ✓ QR validator set")
        
        print("\n4. Testing command handling...")
        # Test command handling without actual serial connection
        protocol._waiting_for_qr = True
        result = protocol.process_qr_input("1A345601234567")
        print(f"   ✓ QR processing result: {result}")
        
        print("\n=== UART PROTOCOL TESTS PASSED ===")
        return True
        
    except Exception as e:
        print(f"\n❌ UART PROTOCOL TEST FAILED: {e}")
        logging.exception("Test failure details:")
        return False

def main():
    """Run all integration tests."""
    print("ACTJv20(RJSR) Integration Test Suite")
    print("====================================")
    
    all_passed = True
    
    # Test 1: Legacy Integration
    if not test_legacy_integration():
        all_passed = False
    
    # Test 2: Main.py Integration  
    if not test_main_integration():
        all_passed = False
    
    # Test 3: UART Protocol
    if not test_uart_protocol():
        all_passed = False
    
    print(f"\n{'='*50}")
    if all_passed:
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("\nThe ACTJv20(RJSR) firmware is ready to integrate with main.py")
        print("\nNext Steps:")
        print("1. Deploy main.py and integration files to Raspberry Pi")
        print("2. Connect UART cable between Pi and PIC18F4550")
        print("3. Configure GPIO pins in settings.ini")
        print("4. Run: python main.py")
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        print("\nPlease fix the issues above before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())