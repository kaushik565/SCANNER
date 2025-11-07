#!/usr/bin/env python3
"""
QR Scanner Diagnostic Tool
Comprehensive testing for USB, camera, and manual QR input methods.
"""

import sys
import time
import serial
import subprocess
import os
from pathlib import Path

def check_usb_devices():
    """Check for connected USB devices including scanners."""
    print("🔌 USB DEVICE SCAN")
    print("=" * 50)
    
    try:
        # Check for USB devices on Windows
        if os.name == 'nt':
            print("💻 Windows USB device detection:")
            result = subprocess.run(['wmic', 'path', 'Win32_USBHub', 'get', 'Name'], 
                                 capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                devices = result.stdout.strip().split('\n')[1:]  # Skip header
                devices = [d.strip() for d in devices if d.strip()]
                if devices:
                    for device in devices:
                        print(f"  📱 {device}")
                else:
                    print("  ❌ No USB devices detected")
            else:
                print("  ⚠️ Could not query USB devices")
        else:
            # Linux/Pi command
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            if result.returncode == 0:
                print("🐧 Linux USB devices:")
                for line in result.stdout.strip().split('\n'):
                    print(f"  📱 {line}")
            else:
                print("  ⚠️ lsusb command not available")
                
        print()
        return True
    except Exception as e:
        print(f"  ❌ USB detection failed: {e}")
        return False

def check_serial_ports():
    """Check for available serial ports (for camera scanners)."""
    print("📡 SERIAL PORT SCAN")
    print("=" * 50)
    
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        
        if ports:
            print("🔗 Available serial ports:")
            for port in ports:
                print(f"  📍 {port.device} - {port.description}")
                print(f"      Manufacturer: {port.manufacturer or 'Unknown'}")
                print(f"      VID:PID: {port.vid:04X}:{port.pid:04X}" if port.vid else "      VID:PID: Unknown")
                print()
        else:
            print("  ❌ No serial ports detected")
        
        return len(ports) > 0
    except ImportError:
        print("  ⚠️ pyserial not installed - cannot check serial ports")
        return False
    except Exception as e:
        print(f"  ❌ Serial port detection failed: {e}")
        return False

def test_keyboard_input():
    """Test if manual keyboard input works for QR scanning."""
    print("⌨️ KEYBOARD INPUT TEST")
    print("=" * 50)
    
    print("This will test if manual QR entry works.")
    print("Type a test QR code (e.g., MVANC00001A001) and press ENTER:")
    print("(Press Ctrl+C to skip this test)")
    
    try:
        test_qr = input("🔤 Enter test QR: ").strip()
        if test_qr:
            print(f"✅ Keyboard input successful: '{test_qr}'")
            print("💡 Manual QR entry is working - can be used as backup")
            return True
        else:
            print("❌ No input received")
            return False
    except KeyboardInterrupt:
        print("\n⏭️ Keyboard test skipped")
        return None
    except Exception as e:
        print(f"❌ Keyboard test failed: {e}")
        return False

def test_camera_scanner():
    """Test camera-based QR scanner connection."""
    print("\n📷 CAMERA SCANNER TEST")
    print("=" * 50)
    
    # Read current config
    try:
        from config import CAMERA_ENABLED, CAMERA_PORT, CAMERA_BAUDRATE, CAMERA_TIMEOUT
        print(f"📋 Configuration:")
        print(f"   Camera enabled: {CAMERA_ENABLED}")
        print(f"   Camera port: {CAMERA_PORT}")
        print(f"   Baudrate: {CAMERA_BAUDRATE}")
        print(f"   Timeout: {CAMERA_TIMEOUT}s")
    except Exception as e:
        print(f"⚠️ Could not read camera config: {e}")
        return False
    
    if not CAMERA_ENABLED:
        print("❌ Camera scanner disabled in config")
        return False
    
    print(f"\n🔍 Testing connection to {CAMERA_PORT}...")
    
    try:
        scanner = serial.Serial(
            CAMERA_PORT,
            baudrate=CAMERA_BAUDRATE,
            timeout=CAMERA_TIMEOUT,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS
        )
        print("✅ Camera scanner connected successfully")
        
        # Try to send a test command
        print("📤 Sending test command...")
        test_cmd = bytes([0x7E, 0x00, 0x08, 0x01, 0x00, 0x02, 0x01, 0xAB, 0xCD, 0x00])
        scanner.write(test_cmd)
        
        # Try to read response
        print("📥 Waiting for response...")
        time.sleep(1)
        
        if scanner.in_waiting > 0:
            response = scanner.read(scanner.in_waiting)
            print(f"📨 Received: {response.hex()}")
            print("✅ Camera scanner communication working")
            result = True
        else:
            print("⚠️ No response from camera scanner")
            print("💡 Device connected but may not be QR camera")
            result = False
        
        scanner.close()
        return result
        
    except serial.SerialException as e:
        print(f"❌ Camera scanner connection failed: {e}")
        if "could not open port" in str(e).lower():
            print("💡 Port not available - check device connection")
        elif "permission denied" in str(e).lower():
            print("💡 Permission denied - may need admin rights")
        return False
    except Exception as e:
        print(f"❌ Camera scanner test failed: {e}")
        return False

def test_usb_scanner():
    """Test USB barcode scanner functionality."""
    print("\n🔧 USB BARCODE SCANNER TEST")
    print("=" * 50)
    
    print("USB barcode scanners work as keyboard devices.")
    print("Testing method:")
    print("1. Open a text editor (notepad, etc.)")
    print("2. Scan a QR code with your USB scanner")
    print("3. Check if text appears + cursor moves to new line")
    print()
    
    # Check if we can detect HID devices (Windows)
    try:
        if os.name == 'nt':
            print("🔍 Checking for HID devices...")
            result = subprocess.run(
                ['wmic', 'path', 'Win32_PointingDevice', 'get', 'Name,Status'],
                capture_output=True, text=True, shell=True
            )
            if result.returncode == 0:
                lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                if len(lines) > 1:  # Skip header
                    print("🖱️ HID input devices found:")
                    for line in lines[1:]:  # Skip header
                        if line:
                            print(f"   {line}")
                    print("💡 USB scanner should appear as HID device")
                else:
                    print("❌ No HID devices detected")
            else:
                print("⚠️ Could not query HID devices")
    except Exception as e:
        print(f"⚠️ HID device check failed: {e}")
    
    print("\n🧪 MANUAL TEST REQUIRED:")
    print("1. Scan this test QR with your USB scanner: MVANC00001A001")
    print("2. Confirm it produces text + ENTER keypress")
    print("3. If working, scanner is ready for use")
    
    response = input("\n❓ Did USB scanner test work? (y/n/skip): ").lower().strip()
    if response == 'y':
        print("✅ USB scanner working correctly")
        return True
    elif response == 'n':
        print("❌ USB scanner not working - check configuration")
        return False
    else:
        print("⏭️ USB scanner test skipped")
        return None

def diagnose_scanner_issues():
    """Provide specific troubleshooting guidance."""
    print("\n🔧 SCANNER TROUBLESHOOTING GUIDE")
    print("=" * 60)
    
    print("""
🚨 COMMON SCANNER ISSUES:

1. **USB Scanner Not Responding**
   ❌ Scanner not in keyboard wedge mode
   ❌ No ENTER suffix configured  
   ❌ USB connection loose
   ❌ Scanner not powered on
   
   ✅ Solutions:
   • Configure scanner for keyboard wedge mode (scan config barcode)
   • Set suffix to ENTER/Return (usually CR LF or just LF)
   • Check USB cable and port
   • Verify scanner power/battery

2. **Camera Scanner Not Responding**  
   ❌ Wrong serial port (/dev/qrscanner vs /dev/ttyUSB0)
   ❌ Incorrect baudrate (should be 115200)
   ❌ Camera not powered or connected
   ❌ Wrong camera type (not compatible)
   
   ✅ Solutions:
   • Check available ports with 'ls /dev/tty*' (Linux)
   • Verify camera power and USB connection
   • Try different baudrates (9600, 38400, 115200)
   • Check camera model compatibility

3. **Scan Timing Issues**
   ❌ Scanning before firmware ready (QR ignored)
   ❌ Scanning too late (timeout error)
   ❌ Multiple scans (duplicate detection)
   
   ✅ Solutions:
   • Wait for "USB Scanner Ready" message
   • Scan within 10 seconds of cartridge positioning
   • Single scan per cartridge only

4. **QR Code Recognition**
   ❌ Poor lighting conditions
   ❌ QR code damaged or dirty
   ❌ Scanner not configured for QR codes
   ❌ Distance too far/close
   
   ✅ Solutions:
   • Improve lighting on scan area
   • Clean QR code labels
   • Configure scanner for all QR code types
   • Position scanner 10-30cm from QR codes

💡 **RECOMMENDED SETUP:**
• Use USB barcode scanner (most reliable)
• Configure keyboard wedge mode + ENTER suffix
• Mount scanner at fixed position above jig
• Test in text editor before using with batch system

🔄 **TESTING ORDER:**
1. Test USB device detection
2. Test scanner in text editor (keyboard wedge)
3. Test in batch application (timing sync)
4. Verify complete cycle with firmware
""")

def main():
    """Run comprehensive scanner diagnostics."""
    print("🔍 QR SCANNER DIAGNOSTIC TOOL")
    print("=" * 60)
    print("This tool will test all QR scanner input methods and identify issues.")
    print("=" * 60)
    
    results = {}
    
    # Test 1: USB Device Detection
    results['usb_devices'] = check_usb_devices()
    
    # Test 2: Serial Port Detection  
    results['serial_ports'] = check_serial_ports()
    
    # Test 3: Camera Scanner Test
    results['camera_scanner'] = test_camera_scanner()
    
    # Test 4: USB Scanner Test
    results['usb_scanner'] = test_usb_scanner()
    
    # Test 5: Keyboard Input Test
    results['keyboard_input'] = test_keyboard_input()
    
    # Show troubleshooting guide
    diagnose_scanner_issues()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 DIAGNOSTIC SUMMARY:")
    print("=" * 60)
    
    working_methods = []
    failed_methods = []
    skipped_methods = []
    
    for method, result in results.items():
        if result is True:
            working_methods.append(method)
            print(f"✅ {method.replace('_', ' ').title()}: WORKING")
        elif result is False:
            failed_methods.append(method)
            print(f"❌ {method.replace('_', ' ').title()}: FAILED")
        else:
            skipped_methods.append(method)
            print(f"⏭️ {method.replace('_', ' ').title()}: SKIPPED")
    
    print("\n🎯 RECOMMENDATIONS:")
    if working_methods:
        print(f"✅ Use: {', '.join(working_methods).replace('_', ' ')}")
    
    if not working_methods:
        print("❌ No scanner methods working - check connections and configuration")
        print("💡 Use manual keyboard entry as temporary backup")
    elif 'usb_scanner' in working_methods:
        print("🎉 USB scanner is optimal choice for production use")
    elif 'camera_scanner' in working_methods:
        print("📷 Camera scanner working - good for automated scanning")
    
    if failed_methods:
        print(f"🔧 Fix: {', '.join(failed_methods).replace('_', ' ')}")
    
    print("=" * 60)

if __name__ == "__main__":
    main()