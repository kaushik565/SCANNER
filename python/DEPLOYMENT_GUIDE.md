# ACTJv20(RJSR) Integration Deployment Guide

## Overview

This guide explains how to integrate the modern `main.py` batch scanning application with the legacy ACTJv20(RJSR) PIC18F4550 firmware.

## Integration Architecture

```
┌─────────────────────┐    UART     ┌─────────────────────┐
│   Raspberry Pi      │◄──────────►│  PIC18F4550         │
│   main.py           │   115200    │  ACTJv20(RJSR)     │
│   + Integration     │   bps       │  Firmware           │
└─────────────────────┘             └─────────────────────┘
         │                                    │
         │ GPIO Control Lines                 │
         ├── GPIO 18 → RASP_IN_PIC (RB6)     │
         ├── GPIO 24 → INT_PIC (RB5)         │
         └── GPIO 25 → SHD_PIC (RB7)         │
```

## Hardware Connections

### UART Connection
- **Pi UART TX** → **PIC RX (RC7)**
- **Pi UART RX** → **PIC TX (RC6)**
- **Common Ground** between Pi and PIC

### GPIO Control Lines
- **GPIO 18** → **RASP_IN_PIC (RB6)** - Pi status signal to PIC
- **GPIO 24** → **INT_PIC (RB5)** - Interrupt signal to PIC  
- **GPIO 25** → **SHD_PIC (RB7)** - Shutdown signal from PIC

### Power Supply
- Ensure both Pi and PIC have stable 5V/3.3V power
- Use common ground for all connections

## Software Deployment

### 1. Files to Deploy

Copy these files to Raspberry Pi `/home/pi/actj/`:

**Core Application:**
- `main.py` - Main batch scanning application
- `config.py` - Configuration loader
- `settings.ini` - Hardware configuration
- `hardware.py` - GPIO control interface
- `logic.py` - QR validation logic
- `layout.py` - GUI layout
- `duplicate_tracker.py` - Duplicate detection

**ACTJv20 Integration:**
- `actj_legacy_integration.py` - Main integration module
- `actj_uart_protocol.py` - UART communication protocol
- `actj_integration.py` - Command/response definitions

**Additional Modules:**
- All other dependency files from the python/ directory

### 2. Install Dependencies

```bash
sudo apt update
sudo apt install python3-pip python3-tk python3-serial
pip3 install pyserial configparser
```

### 3. Enable UART on Raspberry Pi

Edit `/boot/config.txt`:
```bash
sudo nano /boot/config.txt
```

Add/uncomment these lines:
```
enable_uart=1
dtparam=uart=on
```

Disable serial console in `/boot/cmdline.txt`:
```bash
sudo nano /boot/cmdline.txt
```
Remove `console=serial0,115200` if present.

### 4. Configure GPIO Permissions

```bash
sudo usermod -a -G gpio pi
sudo chmod 666 /dev/gpiomem
```

### 5. Update settings.ini

Edit the configuration for your hardware:

```ini
[actj_legacy]
enabled = true
uart_port = /dev/serial0
baudrate = 115200
gpio_rasp_in_pic = 18
gpio_int_pic = 24  
gpio_shd_pic = 25
command_timeout = 12000
auto_start = true

[hardware]
controller = gpio
pin_mode = BCM
```

## PIC18F4550 Firmware Configuration

### UART Settings (SBC_Rpi.c)
The firmware expects these UART settings:
```c
TXSTA = 0x24;
RCSTA = 0x90;
BAUDCON = 0x08;
SPBRGH = 0x00;
SPBRG = 0x68;    // 115200 @ 48Mhz
```

### GPIO Pin Definitions (Pin_Definitions.h)
```c
#define RASP_IN_PIC PORTBbits.RB6  // Status from Pi
#define INT_PIC LATBbits.LATB5     // Interrupt to Pi  
#define SHD_PIC PORTBbits.RB7      // Shutdown signal
```

## Communication Protocol

### 1. Startup Sequence
1. PIC powers up and waits for `RASP_IN_PIC` HIGH
2. Pi sets `RASP_IN_PIC` HIGH to signal ready
3. PIC enters normal operation mode

### 2. QR Scan Sequence
1. **PIC** sends `20` (scan command) via UART
2. **PIC** waits for `RASP_IN_PIC` to go LOW (Pi busy)
3. **Pi** processes QR scan and validates against batch
4. **Pi** sends response: `A` (accept), `R` (reject), `S` (error)
5. **Pi** sets `RASP_IN_PIC` HIGH (ready)
6. **PIC** advances mechanism based on response

### 3. Command Set

**PIC → Pi Commands:**
- `20` - QR scan request (with retry)
- `19` - Final QR scan attempt
- `0` - Stop/reset command

**Pi → PIC Responses:**
- `A` - Accept/Pass (GREEN light)
- `R` - Reject/Fail (RED light)
- `D` - Duplicate (YELLOW light)
- `S` - Scanner error
- `Q` - No QR detected
- `L` - Length error

## Running the Integration

### 1. Start the Application
```bash
cd /home/pi/actj
python3 main.py
```

### 2. Setup Batch
1. Enter batch number (10 alphanumeric characters)
2. Enter batch line (single letter: A, B, C, etc.)
3. Configure mould ranges with start/end QR codes
4. Click "Start Scanning"

### 3. Automatic Operation
- Fill cartridge stack on ACTJv20 jig
- Press START button on PIC controller
- System will automatically:
  - Advance cartridges one by one
  - Request QR scans from Pi
  - Sort cartridges based on validation results
  - Display results on LCD and GUI

## Troubleshooting

### Common Issues

**1. UART Communication Fails**
```bash
# Check UART device
ls -la /dev/serial*
# Test UART loopback
sudo minicom -D /dev/serial0
```

**2. GPIO Permission Denied**
```bash
sudo chmod 666 /dev/gpiomem
sudo usermod -a -G gpio pi
```

**3. Pi Not Ready Signal**
- Check GPIO 18 connection to RASP_IN_PIC (RB6)
- Verify 3.3V/5V level compatibility
- Use logic analyzer to verify signal timing

**4. QR Validation Errors**
- Check batch line configuration matches QR codes
- Verify QR format is exactly 14 alphanumeric characters
- Ensure mould ranges are properly configured

### Debug Mode

Enable debug logging in `main.py`:
```python
logging.basicConfig(level=logging.DEBUG)
```

Monitor UART traffic:
```bash
sudo minicom -D /dev/serial0 -b 115200
```

### Log Files

Check these log files for issues:
- `/home/pi/actj/batch_logs/jig.log` - Main application logs
- `/home/pi/actj/batch_logs/[BATCH_NAME].csv` - Scan results
- `/var/log/syslog` - System-level errors

## Firmware Modifications (If Needed)

If you need to modify the PIC firmware:

### 1. Update Communication Timing
In `SBC_Rpi.c`, adjust timeouts:
```c
// Increase timeout for Pi response
unsigned int count=3000;  // was 500
```

### 2. Add New Commands
In `wait_for_qr()` function:
```c
case 'X':  // New custom command
    // Add custom handling
    break;
```

### 3. Modify GPIO Behavior
In `Main_PCR.c`, adjust GPIO control:
```c
// Custom GPIO signaling
INT_PIC = 1;  // Signal Pi
DELAY_100mS();
INT_PIC = 0;
```

## Performance Optimization

### 1. Reduce Scan Timeouts
```ini
[actj_legacy]
command_timeout = 8000  # Reduce from 12000ms
```

### 2. Enable Fast Mode
```c
// In firmware, reduce delays
DELAY_50mS();  // Instead of DELAY_100mS()
```

### 3. Optimize QR Validation
```python
# Pre-compile regex patterns
import re
qr_pattern = re.compile(r'^[A-Z0-9]{14}$')
```

## Integration Status

✅ **Completed Features:**
- UART communication protocol
- GPIO handshaking
- Batch validation integration
- Error handling and recovery
- Configuration management
- Legacy firmware compatibility

🔄 **Testing Required:**
- Hardware deployment verification
- Full scan cycle testing
- Error recovery scenarios
- Performance optimization

📋 **Future Enhancements:**
- LCD display integration via PIC
- Advanced error diagnostics  
- Remote monitoring capabilities
- Firmware update over UART

## Support

For technical support:
- Check integration test results: `python3 test_integration.py`
- Review configuration: Verify `settings.ini` matches your hardware
- Hardware issues: Use multimeter to verify connections
- Firmware issues: Rebuild with MPLAB X IDE

The integration is now ready for deployment and testing with your ACTJv20(RJSR) hardware!