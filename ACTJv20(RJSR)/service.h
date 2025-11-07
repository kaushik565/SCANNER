#ifndef SERVICE_H
#define SERVICE_H

#include <p18cxxx.h>
#include "Pin_Definitions.h"
#include "i2c_lcd.h"
#include "SBC_Rpi.h"
#include "Functions.h"

// Legacy service/test features removed; only critical error handlers remain.
void mech_error_botton(void);
void mech_error_loop(void);

#endif // SERVICE_H
