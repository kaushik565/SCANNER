// Minimal service module: only error indication handlers retained for QR-only firmware
#include "service.h"

extern void reset_mechanism(void);

void mech_error_botton(void) {
    while (SW_3 && SW_2) {
        TOWER_OFF;
        BUZZER = 1;
        DELAY_500mS();
        TOWER_ON;
        BUZZER = 0;
        DELAY_500mS();
    }
    TOWER_OFF;
}

void mech_error_loop(void) {
    reset_mechanism();
    while (1) {
        TOWER_OFF;
        BUZZER = 1;
        DELAY_500mS();
        TOWER_ON;
        BUZZER = 0;
        DELAY_500mS();
        
        // Check if SW_2 or SW_3 pressed to clear error and return
        if(!SW_2 || !SW_3) {
            BUZZER = 0;
            TOWER_OFF;
            LCD_Cmd(LCD_CLEAR);
            display(0,0,"ERROR CLEARED",0);
            DELAY_1S();
            LCD_Cmd(LCD_CLEAR);
            return; // Exit error loop
        }
    }
}
