#include<p18cxxx.h>
//#define BOARD_VER2 1

#ifdef BOARD_VER2
	#define	VAC_VLV_P	TRISEbits.TRISE1
	#define	RJT_SNS_P	TRISEbits.TRISE2
	#define	VAC_VLV	LATEbits.LATE1
	#define	RJT_SNS	PORTEbits.RE2
#else
	#define	P_Valve_1_R	TRISEbits.TRISE1
	#define	P_Valve_1_L	TRISEbits.TRISE2
	#define	Valve_1_R	LATEbits.LATE1
	#define	Valve_1_L	LATEbits.LATE2
#endif

#define	P_ValveM1_R	TRISDbits.TRISD0
#define	P_ValveM1_F	TRISDbits.TRISD1
#define	P_ValveM2_R	TRISDbits.TRISD2
#define	P_ValveM2_F	TRISDbits.TRISD3
#define	ValveM1_R	LATDbits.LATD0
#define	ValveM1_F	LATDbits.LATD1
#define	ValveM2_R	LATDbits.LATD2
#define	ValveM2_F	LATDbits.LATD3

#define LED_PASS_PORT TRISBbits.TRISB2
#define LED_CLOG_PORT TRISBbits.TRISB4
#define LED_LEAK_PORT TRISBbits.TRISB3
#define LED_VALVE_PORT TRISBbits.TRISB5
#define LED_PASS LATBbits.LATB2
#define LED_CLOG LATBbits.LATB4
#define LED_LEAK LATBbits.LATB3
#define LED_VALVE LATBbits.LATB5

#define SW_1_P TRISBbits.TRISB2 //power
#define SW_2_P TRISBbits.TRISB3
#define SW_3_P TRISBbits.TRISB4

#define SW_1 PORTBbits.RB2
#define SW_2 PORTBbits.RB3
#define SW_3 PORTBbits.RB4

#define LM_SW_EJ_PORT TRISAbits.TRISA5
#define LM_SW_DET_PORT TRISAbits.TRISA4

#define LM_SW_EJ PORTAbits.RA5
#define LM_SW_DET PORTAbits.RA4

#define	P_ENB_2	TRISDbits.TRISD6
#define	P_CLK_2	TRISDbits.TRISD7
//#define	P_DIR_2	TRISDbits.TRISD5

#define	ENB_2	LATDbits.LATD6
#define	CLK_2	LATDbits.LATD7
///#define	DIR_2	LATDbits.LATD5

#define BUZZER_P TRISDbits.TRISD5
#define BUZZER LATDbits.LATD5

#define KILL_P TRISDbits.TRISD4
#define KILL LATDbits.LATD4

#define BW_SNS_P TRISCbits.TRISC0
#define BW_SNS PORTCbits.RC0
#define FW_SNS_P TRISCbits.TRISC1
#define FW_SNS PORTCbits.RC1
#define MECH_UP_SNS_P TRISCbits.TRISC2
#define MECH_UP_SNS PORTCbits.RC2
#define STACK_SNS PORTCbits.RC4

#define CAT_SNS PORTCbits.RC5

#define CAT_FB_P TRISEbits.TRISE0
#define CAT_FB LATEbits.LATE0
#define PLATE_UD_P TRISAbits.TRISA5
#define PLATE_UD LATAbits.LATA5
#define REJECT_SV_P TRISAbits.TRISA4
#define REJECT_SV LATAbits.LATA4
#define ELECT_SOL_P TRISAbits.TRISA3
#define ELECT_SOL LATAbits.LATA3

#define RX_PIC_P TRISCbits.TRISC7
#define TX_PIC_P TRISCbits.TRISC6

#define RX_PIC LATCbits.LATC7
#define TX_PIC LATCbits.LATC6

#define INT_PIC_P TRISBbits.TRISB5
#define RASP_IN_PIC_P TRISBbits.TRISB6
#define SHD_PIC_P TRISBbits.TRISB7

#define INT_PIC LATBbits.LATB5    //Shutdown interrupt signal to rpi
#define RASP_IN_PIC PORTBbits.RB6
#define SHD_PIC PORTBbits.RB7  //powered off signal from rpi