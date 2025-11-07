#ifndef SBC_RPI_H
#define SBC_RPI_H

#include <p18cxxx.h>
#include"i2c_lcd.h"
#include "Functions.h"
#define SBC_ENABLED



extern unsigned char  sbc_ready, sbc_disabled, qr_disabled;

void wait_ready_rpi(void);
unsigned char wait_log_rpi(void);
void flush_uart(void);
char wait_for_qr(void);
void sent_rpi_RTD(void);
void sent_rpi_uint16(unsigned int data);
void sent_rpi_valve_rot(unsigned int data1, unsigned int data2);

void Init_UART_RPi(void);

void read_string_rpi(char* string_in);
char wait_busy_rpi(void);
//void write_rom_string_rpi(rom char* in) ;
//void write_rom_rpi(char data) ;
void write_rom_string_rpi(rom char* in);
void write_rom_rpi(const char data);
void write_rom_rpi_nl(void);
void write_rpi_sect_brk(void);

void write_ram_string_rpi(char* in) ;
void write_ram_rpi(char data);
void reset_wrapper(void);
void stop_logging(void);

void disable_qr(void);
void enable_qr(void);
void enable_sbc(void);
void disable_sbc(void);
void catridge_read_error(void);

char wait_for_reagent_qr(void);
void SBC_UARTInit(void);
#define SBC_DISABLE_LIMIT 3

#endif