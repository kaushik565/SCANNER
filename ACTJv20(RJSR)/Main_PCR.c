#include<p18cxxx.h>
#include "Functions.h"
#include "i2c_lcd.h"
#include "SBC_Rpi.h"
#include "service.h"

#define QR_ONLY 1
#define	PICDEM_FS_USB
#define Stop_Command 'Z'
#define offset 0x046

#pragma config PLLDIV   = 5
#pragma config CPUDIV   = OSC1_PLL2
#pragma config USBDIV   = 2
#pragma config FOSC     = HSPLL_HS

// Global variables for QR_ONLY mode
char reject_flag = 1;
char testing = 0;
unsigned int count = 0;
unsigned int pass_count = 0;

// Forward declarations for QR_ONLY functions
void reject_on(void);
void reject_off(void);
void catFB_forward(void);
void mechUp_catFB_Back(void);
void reset_mechanism(void);
void port_init(void);

#if defined(__18CXX)
		void main(void)
		#else
		int main(void)
		#endif
		{
		#if QR_ONLY
			KILL_P=0; KILL=1; P_ENB_2=0; ENB_2=1;
			port_init();
			I2C_Init1();
			LCD_Begin(0b01001110);
			display(1,"CARTRIDGE QR","SCANNER JIG",1);
			SBC_UARTInit();
			display(1,"PRESS START",0,0);
			while(SW_3){ if(!SW_2){ /* no service menu in QR_ONLY */ } }
			while(!SW_3);
			while(1){
				ELECT_SOL=1;
				catFB_forward();
				ELECT_SOL=0;
				DELAY_500mS();
				if(reject_flag){ reject_on(); } else { reject_off(); }
				DELAY_500mS();
				flush_uart();
				switch(wait_for_qr()){
					case 0: reject_flag=0; reject_off(); break;
					case 1: default: reject_flag=1; reject_on(); break;
				}
				mechUp_catFB_Back();
			}
		#else
			KILL_P=0;
			KILL=1;
			P_ENB_2=0;
			ENB_2=1;
			#ifndef BOARD_VER2
				P_Valve_1_R=0;
				P_Valve_1_L=0;
				Valve_1_L=0;
				Valve_1_R=0;
			#endif

			port_init();
			I2C_Init1();
    
			ADC_Init();
			LCD_Begin(0b01001110);
			#ifdef BOARD_VER2
				display(1,"CARTRIDGE QR","SCANNER JIG v2.3",1);
			#else
				display(1,"CARTRIDGE QR","SCANNER JIG v1.3",1);
			#endif
    

			testing=0;
			  cont.leak3_error_RT=0;
			   cont.leak3_error_LT=0; 
			   cont.leak3_error_LT1=0; 
     
			   cont.v1_cw_error=0;
			   cont.v1_acw_error=0;
     
			   cont.v2_cw_error=0;
			   cont.v2_acw_error=0;
     
			   cont.v1ft_cw_error=0;
			   cont.v1ft_acw_error=0;
     
			   cont.v2ft_cw_error=0;
			   cont.v2ft_acw_error=0;
     
			   cont.clog_error_RT=0;
			   cont.clog_error_LT=0;
			   cont.clog_error_LT1=0;
     
			   cont.qr_error=0;
     
			   cont.leak1_error_RT=0;
			   cont.leak1_error_LT=0;
			   cont.leak1_error_LT1=0;
     
			   cont.leak2_error_RT=0;
			   cont.leak2_error_LT=0;
			   cont.leak2_error_LT1=0;
    
			TOWER_OFF;
			RtryValve_HF=read_eeprom(1);
			DELAY_250mS();
			sbc_disabled=read_eeprom(0);
			DELAY_250mS();
			qr_disabled=read_eeprom(2);

			Init_PowerInt();
    
    
    
			//board_test_protocol();
			SBC_UARTInit();
		 // write_rom_rpi(0);
		  INTCONbits.TMR0IE = 1; 
		  INTCONbits.TMR0IF = 0; 
		 /* T0CONbits.T08BIT = 0; 
		  T0CONbits.T0CS = 0; 
		  T0CONbits.PSA = 0; 
		  T0CONbits.T0PS2 = 1; 
		  T0CONbits.T0PS1 = 1;
		  T0CONbits.T0PS0 = 1; 
		  TMR0L = 0;
		  TMR0H = 0;
			//1/(48000000/(4*256*((2^16)-1)))=1.39808 seconds
		  T0CONbits.TMR0ON = 0; // stops Timer1*/



		  if(RCONbits.RI){
		 //   post(70);
		  }
			if(sbc_disabled==1){
				sbc_ready=0;
			}
			else {
				wait_ready_rpi();
			}
			display(1,"PRESS START",0,0);
		//  sbc_ready=1; 
			while(SW_3){
				if(!SW_2){
					service_menu();
            
				}
			}
			while(!SW_3);
			testing=1; 
			while(1){
				//LCD_Begin(0b01001110);
				check_stack();
				display_counts();
        
    
    
					//POWER_INT_DISABLE;
				ELECT_SOL=1; //solenoid stopper down
				catFB_forward();
				ELECT_SOL=0; //solenoid stopper up
				DELAY_500mS();
				if(reject_flag){
					reject_on();
				}   
				else {
					reject_off();
				}
				//mech_plate_down();
				DELAY_500mS();     
				//LCD_Cmd(LCD_CLEAR);
				//display_counts();
				flush_uart();
				if(cat_test()){         
					reject_flag=1;
				}
				else {
					reject_flag=0;
					reject_off();
            
				}
				if(sbc_ready==1){
					write_rom_rpi(0); //stop rec
					//DELAY_100mS();
					//write_rom_rpi(23);
					//write_ram_rpi(error_type+'0');         
				}   
				mechUp_catFB_Back();    
				//check_key_intrpt();    
			//  cont_error_check(); 
			}
		#endif
		}
	#pragma interruptlow YourLowPriorityISRCode
	void YourLowPriorityISRCode()
	{
		//Check which interrupt flag caused the interrupt.
		//Service the interrupt
		//Clear the interrupt flag
		//Etc.
	
	}	//This return will be a "retfie", since this is in a #pragma interruptlow section 


/** DECLARATIONS ***************************************************/
#pragma code


// Number of consecutive cycles to skip stack empty checks after a successful start.
// Set to >0 to allow debounce; currently forcing immediate check each cycle.
#define STACK_END_SKIP 0
#define PLATE_STUCK_RETRY 5
#define ERROR_TTHRSLD1 4
#define ERROR_TTHRSLD2 9

const char* cont_err_string="CONT. ERROR";
const char* press_sm_string="PRESS MENU/START";

void cont_error_check(void){
/*	if(cont.v1_cw_error>ERROR_TTHRSLD1||
		cont.v1_acw_error>ERROR_TTHRSLD1||
		cont.v2_cw_error>ERROR_TTHRSLD1||
		cont.v2_acw_error>ERROR_TTHRSLD1||
		cont.v1ft_cw_error>ERROR_TTHRSLD1||
 		cont.v2ft_cw_error>ERROR_TTHRSLD1||
		cont.v1ft_acw_error>ERROR_TTHRSLD1||
		cont.v2ft_acw_error>ERROR_TTHRSLD1
		){
		testing=0;
		display(0,cont_err_string,0,1);
		POWER_INT_ENABLE;
		reset_mechanism();
		TOWER_ON;
		while (SW_3&&SW_2){
			BUZZER=~BUZZER;
			DELAY_500mS();
		}
		TOWER_OFF;
		BUZZER=0;	
		display(1,press_sm_string,"TO CHECK V.MOTOR",1);
		while (SW_3&&SW_2);
		post(160);
		Reset();
	}*/
	if(cont.qr_error>ERROR_TTHRSLD1){
		testing=0;
		display(0,cont_err_string,0,1);
		POWER_INT_ENABLE;
		reset_mechanism();
		TOWER_ON;
		while (SW_3&&SW_2){
			BUZZER=~BUZZER;
			DELAY_500mS();
		}
		TOWER_OFF;
		BUZZER=0;	
		Reset();
	}
	/*if(cont.leak1_error_RT>ERROR_TTHRSLD1||
		cont.leak1_error_LT>ERROR_TTHRSLD1||
		cont.leak1_error_LT1>ERROR_TTHRSLD1||
		cont.leak2_error_RT>ERROR_TTHRSLD1||
		cont.leak2_error_LT>ERROR_TTHRSLD1||
		cont.leak2_error_LT1>ERROR_TTHRSLD1||
		cont.clog_error_RT>ERROR_TTHRSLD1||
		cont.clog_error_LT>ERROR_TTHRSLD1||
		cont.clog_error_LT1>ERROR_TTHRSLD1||
		cont.leak3_error_RT>ERROR_TTHRSLD2||
		cont.leak3_error_LT>ERROR_TTHRSLD2||
		cont.leak3_error_LT1>ERROR_TTHRSLD2
		){	
		testing=0;
		display(0,cont_err_string,0,1);
		POWER_INT_ENABLE;
		reset_mechanism();
		TOWER_ON;
		while (SW_3&&SW_2){
			BUZZER=~BUZZER;
			DELAY_500mS();
		}
		TOWER_OFF;
		BUZZER=0;	
		display(1,press_sm_string,"TO CHECK VACUUM",1);
		while (SW_3&&SW_2);
		
		POWER_INT_DISABLE;
		vacuum_test();
		Reset();
	}*/
	
}




/******************************************************************************
 * Function:        void main(void)
 * PreCondition:    None
 * Side Effects:    None
 * Overview:        Main program entry point.
 * Note:            None
 *******************************************************************/
#if 0
#if defined(__18CXX)
void main(void)
#else
int main(void)
#endif
{   
    /* Legacy non-QR main permanently disabled */
}
#endif
void mech_plate_down(void){
	unsigned int i=0;
	PLATE_UD=1;//plate down
	while(MECH_UP_SNS){
		i++;
		DELAY_1mS();
		if(i==6000){
			POWER_INT_ENABLE;
			display(1,0,"MCH PLT D STUCK",5);
			mech_error_loop();
		}
	}
}

void reject_on(void){
	unsigned int i=0;
	REJECT_SV=1; //plate down
	#ifdef BOARD_VER2
	while(RJT_SNS){
		i++;
		DELAY_1mS();
		if(i==6000){
			POWER_INT_ENABLE;
			display(1,0,"REJECT PLT STUCK",2);
			mech_error_loop();
		}
	}
	#endif
}

void reject_off(void){
	unsigned int i=0;
	REJECT_SV=0; 
	#ifdef BOARD_VER2
	while(!RJT_SNS){
		i++;
		DELAY_1mS();
		if(i==6000){
			POWER_INT_ENABLE;
			display(1,0,"PASS PLT STUCK",2);
			mech_error_loop();
		}
	}
	#endif
}



void catFB_forward(void){
	unsigned int i=0,plate_stuck_retry=PLATE_STUCK_RETRY;
	CAT_FB=1; //cartride forward
		while(!FW_SNS){
			i++;
			DELAY_1mS();
			if(i==5000){
				if(plate_stuck_retry--){
					CAT_FB=0;//Move cartridge plate backward
					i=0;
					while(!BW_SNS){
						i++;
						DELAY_1mS();
						if(i==6000){
							display(1,0,"CAT PLT BK STUCK",0);
							POWER_INT_ENABLE;
							ELECT_SOL=0; 
							mech_error_loop();
						
						}
					}
				
					
					i=0;
					ELECT_SOL=1; //solenoid stopper down
					CAT_FB=1; //cartride forward
					continue;
				}
				else {
					display(1,0,"CAT PLT FW STUCK",0);
					POWER_INT_ENABLE;
					ELECT_SOL=0; 
					reset_mechanism();
					mech_error_botton();
					DELAY_100mS();
					LCD_Begin(0b01001110);
					display_counts();
					
					i=0;
					plate_stuck_retry=PLATE_STUCK_RETRY;
					ELECT_SOL=1; //solenoid stopper down
					CAT_FB=1; //cartride forward
					continue;
				}
			}	
		}
}
void mechUp_catFB_Back(void){
	unsigned int i=0;
	// PLATE_UD=0;//raise up the plate - REMOVED: No vacuum testing mechanism
	CAT_FB=0;//Move cartridge plate backward
	i=0;
	while(!BW_SNS){
		i++;
		DELAY_1mS();
		
		// Allow button press to skip error
		if(!SW_2 || !SW_3) {
			BUZZER = 0;
			LCD_Cmd(LCD_CLEAR);
			display(0,0,"ERROR SKIPPED",0);
			DELAY_1S();
			LCD_Cmd(LCD_CLEAR);
			return; // Skip the error and continue
		}
		
		if(i==10000){
			
			POWER_INT_ENABLE;
			display(1,0,"CAT PLT BK STUCK",5);
			mech_error_loop();
			
		}
	}
	// Removed MECH_UP_SNS check - vacuum testing hardware removed
	// i=0;
	// while(!MECH_UP_SNS){ //check mech plate is up
	// 	i++;
	// 	DELAY_1mS();
	// 	if(i==6000){
	// 		
	// 		POWER_INT_ENABLE;
	// 		display(1,0,"MCH PLT U STUCK",5);
	// 		mech_error_loop();
	// 		
	// 	}
	// }				
}

void check_stack(void){
	// Debounce counter (optional); currently zero so we always evaluate
	static unsigned char stack_skip = STACK_END_SKIP;
	// Treat logic HIGH (1) as stack present, LOW (0) as empty. If wiring inverted, swap condition.
	if (STACK_SNS == 0) { // stack empty condition
		if (!stack_skip) {
			POWER_INT_ENABLE;
			reset_mechanism();
			TOWER_ON;
			// Show blocking "STACK EMPTY" message and wait for operator
			DisplayStackEmpty();
			BUZZER = 0;
			TOWER_OFF;
			// Wait until operator presses START (SW_3 released then pressed)
			while(!SW_3); // ensure button released
			while(SW_3);  // wait for fresh press
			stack_skip = STACK_END_SKIP; // reset skip counter
			LCD_Begin(0b01001110); // re-initialize LCD (I2C expander may glitch during long buzzer)
		} else {
			stack_skip--; // countdown debounce
		}
	} else { // stack present
		BUZZER = 0;
		stack_skip = STACK_END_SKIP; // reset skip counter
	}
}

void check_key_intrpt(void){
/*	unsigned int wait_time=400;
	if(INTCON3bits.INT2IF){
		display(1,"SHUTDOWN?","START->PAUSE",0);
		DELAY_500mS();
		POWER_INT_ENABLE;
		while(SW_3){
			wait_time--;
			DELAY_50mS();
			if(!wait_time){	
				POWER_INT_DISABLE;
				return;
			}
		}
	
		while(!SW_3);
		display(1,"SHUTDOWN?","START?",1);
		while(SW_3);
		while(!SW_3);
		POWER_INT_DISABLE;
	}*/
}

void reset_mechanism(void){
//	T0CONbits.TMR0ON = 0;
	//INTCONbits.TMR0IE = 0; 
	BUZZER=0;
	valve_right_idle();	
	PLATE_UD=0;//raise up the plate
	CAT_FB=0;//Move cartridge plate backward
	REJECT_SV=0;//Move reject plate forward
	ELECT_SOL=0;//stoper up	
	TOWER_OFF;
}

const char* PASSs="PASS";
const char* FAILs="FAIL";
char cat_test(void){
	char qr_result=0, retry=3;
	//	if(!CAT_SNS){
	//		DELAY_250mS();
	//		if(!CAT_SNS){
		
				count++;
				while(retry--){	
				if(sbc_ready==1){
					if(!qr_disabled){
						if(retry)
							write_rom_rpi(20);
						else 
							write_rom_rpi(19);
						if(wait_busy_rpi()){
							if(retry)
								write_rom_rpi(20);
							else 
								write_rom_rpi(19);
								if(wait_busy_rpi()){
									if(retry)
										write_rom_rpi(20);
									else 
										write_rom_rpi(19);
										if(wait_busy_rpi()){
											display(0,0,"SBC Er-2",0);
											mech_error_loop();
										}
								}
						}
						//DELAY_100mS();
						flush_uart();
						qr_result=wait_for_qr();
						if(qr_result==0){
							display(1,0,PASSs,0);
				
							pass_count++;
							display_counts();
							return 0; 	
						}
						else if(qr_result==1){
							return 1;
						}
						else if(qr_result==2){
							return reject_flag;
						}
						else if(qr_result==3){
							//return 1;
							display(0,"RETRYING",0,0);
							DELAY_500mS();
						}	
						
						else {
							return 1;
						}
						
						
						
					}	
				//	DELAY_500mS();
				//	write_rom_rpi(21);
					
					

					}	
				}
				
			
							
						display(1,"QR NOT READABLE ",press_sm_string,1);
								
								while (SW_3&&SW_2){
									BUZZER=~BUZZER;
									DELAY_500mS();
								}
							
								BUZZER=0;
					
				return 1;
				
	//		}
	//	}
		/*	POWER_INT_ENABLE;
			reset_mechanism();
			DisplayCatNotDet();
			while(!SW_3);
			LCD_Begin(0b01001110);	
			//POWER_INT_DISABLE;
			return 3; */
}

char ValveTest(void)
{
  
}


void vacuum_leak_error(char errortype){
	
}

char VacuumTest(void)
{

}


void port_init(void){

	BUZZER_P=0;
	BUZZER=0;
	#ifdef BOARD_VER2
		RJT_SNS_P=1;
		VAC_VLV_P=0;
		VAC_VLV=0;
	#else
		P_Valve_1_R=0;
		P_Valve_1_L=0;
		Valve_1_L=0;
		Valve_1_R=1;
	#endif

	P_ValveM1_R=0;
	P_ValveM1_F=0;
	ValveM1_R=0;
	ValveM1_F=0;
	P_ValveM2_R=0;
	P_ValveM2_F=0;
	ValveM2_R=0;
	ValveM2_F=0;
	PORTEbits.RDPU=0;
	//LATE=0x06;
	P_ENB_2=0;
	P_CLK_2=0;

	TRISAbits.TRISA0=1;
	TRISAbits.TRISA1=1;
	TRISAbits.TRISA2=1;	
	TRISAbits.TRISA3=1;
	SW_1_P=1;
	SW_2_P=1;
	SW_3_P=1;
	
	LM_SW_DET_PORT=1;
	INT_PIC_P=0;
	RASP_IN_PIC_P=1;
	SHD_PIC_P=1;
	INT_PIC=0;
	
	CAT_FB_P=0;
	PLATE_UD_P=0;
	REJECT_SV_P=0;
	ELECT_SOL_P =0;
	
	CAT_FB=0;
	PLATE_UD=0;
	REJECT_SV=0;
	ELECT_SOL =0;
	
	BW_SNS_P=1;
	FW_SNS_P=1;
	MECH_UP_SNS_P=1;

	
	UCONbits.USBEN = 0; //disable usb module and transceiver to use RC4 and RC5
	UCFGbits.UTRDIS = 1; 

}




/******************************************************/





