#!/usr/bin/env python3
"""Simple UART test to verify PIC communication."""

import serial
import time

print("=== PIC UART Test ===")
print("This will read raw bytes from the PIC")
print("Press START button on PIC to send scan command")
print("Expected: byte 20 (0x14) for scan command")
print("")

try:
    # Open UART
    ser = serial.Serial(
        port="/dev/serial0",
        baudrate=115200,
        timeout=1.0,
        bytesize=8,
        parity='N',
        stopbits=1
    )
    print(f"✓ UART opened: {ser.name}")
    print(f"  Baudrate: {ser.baudrate}")
    print(f"  Waiting for data...")
    print("")
    
    # Read loop
    while True:
        if ser.in_waiting > 0:
            data = ser.read(1)
            byte_val = data[0]
            print(f"Received: {byte_val} (0x{byte_val:02X}) = '{chr(byte_val) if 32 <= byte_val < 127 else '?'}'")
            
            # Interpret common commands
            if byte_val == 20:
                print("  → This is SCAN command (20 = 0x14)")
                print("  → Sending 'A' (Accept) response...")
                ser.write(b'A')
            elif byte_val == 19:
                print("  → This is FINAL SCAN command (19 = 0x13)")
                print("  → Sending 'A' (Accept) response...")
                ser.write(b'A')
            elif byte_val == 0:
                print("  → This is STOP command (0 = 0x00)")
            
        time.sleep(0.01)
        
except KeyboardInterrupt:
    print("\nTest stopped by user")
except Exception as e:
    print(f"ERROR: {e}")
    print("\nTroubleshooting:")
    print("1. Check UART cable connection (TX->RX, RX->TX)")
    print("2. Verify /dev/serial0 exists: ls -l /dev/serial0")
    print("3. Check if it's the correct port: ls -l /dev/tty*")
    print("4. Verify PIC firmware is running and sending data")
finally:
    try:
        ser.close()
    except:
        pass
