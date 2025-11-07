@echo off
echo ====================================================
echo Building PIC18F4550 Firmware for QR Scanner Jig
echo Using XC8 v3.10 Compiler
echo ====================================================
echo.

cd /d "D:\PROJECT FINAL\Scanner with ACTJ mechanism\ACTJv20(RJSR)"

echo Compiling with XC8...
echo.

"C:\Program Files\Microchip\xc8\v3.10\bin\xc8-cc.exe" ^
  -mcpu=18F4550 ^
  --output=default,-mcof,+elf ^
  -o"TulabDX.hex" ^
  Main_PCR.c ^
  service.c ^
  Functions.c ^
  i2c_lcd.c ^
  LCD_module.c ^
  SBC_Rpi.c ^
  uart_module.c

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ====================================================
    echo BUILD SUCCESSFUL!
    echo Output: TulabDX.hex
    echo ====================================================
    echo.
    echo You can now flash TulabDX.hex to your PIC18F4550
    echo.
) else (
    echo.
    echo ====================================================
    echo BUILD FAILED - See errors above
    echo ====================================================
    echo.
)

pause
