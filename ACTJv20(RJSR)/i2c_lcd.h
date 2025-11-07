#ifndef I2C_LCD_H
#define I2C_LCD_H

#include <p18cxxx.h>
#include "delays.h"
#include "Pin_Definitions.h"
#include "functions.h"

#define LCD_FIRST_ROW          0x80
#define LCD_SECOND_ROW         0xC0
#define LCD_THIRD_ROW          0x94
#define LCD_FOURTH_ROW         0xD4
#define LCD_CLEAR              0x01
#define LCD_RETURN_HOME        0x02
#define LCD_ENTRY_MODE_SET     0x04
#define LCD_CURSOR_OFF         0x0C
#define LCD_UNDERLINE_ON       0x0E
#define LCD_BLINK_CURSOR_ON    0x0F
#define LCD_MOVE_CURSOR_LEFT   0x10
#define LCD_MOVE_CURSOR_RIGHT  0x14
#define LCD_TURN_ON            0x0C
#define LCD_TURN_OFF           0x08
#define LCD_SHIFT_LEFT         0x18
#define LCD_SHIFT_RIGHT        0x1E
#define LCD_BACKLIGHT          0x08
#define LCD_NOBACKLIGHT        0x00

#ifndef LCD_TYPE
   #define LCD_TYPE 2           // 0=5x7, 1=5x10, 2=2 lines
#endif

#define uint32_t unsigned long
#define uint8_t unsigned char
#define uint16_t unsigned int
#define int16_t int
#define char_t char

void I2C_Init(uint32_t i2c_clk_freq);
void I2C_Start();
void I2C_Stop();
void I2C_Write(uint8_t i2c_data);
void LCD_Write_Nibble(uint8_t n);
void LCD_Cmd(uint8_t Command);
void LCD_Goto(uint8_t col, uint8_t row);
void LCD_PutC(char LCD_Char);
void LCD_Print_rammem(ram char* LCD_Str);
void LCD_Print(rom char* LCD_Str);
void LCD_Begin(uint8_t _i2c_addr);
void Expander_Write(uint8_t value);
void LCD_PutInt(int16_t LCD_int);
void LCD_PrintInt(int16_t LCD_int);
void LCD_PrintNo(int16_t LCD_int);
			// Clock pin for i2c
void display(char lcd_clear, ram char* line1, ram char* line2,unsigned char delay_1_sec);
void display_ram(char lcd_clear, ram char* line1, ram char* line2,unsigned char delay_1_sec);

void display_counts(void);
void DisplayStackEmpty(void);
void DisplayCatNotDet(void);
void I2C_Init1(void);
void LCD_Print_space(rom char* LCD_Str);

#define LCD_CLEAR_L1 LCD_Cmd(LCD_FIRST_ROW),LCD_Print_space("")
#define LCD_CLEAR_L2 LCD_Cmd(LCD_SECOND_ROW),LCD_Print_space("")
extern const char* press_sm_string;

#endif

