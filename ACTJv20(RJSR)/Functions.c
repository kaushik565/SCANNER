#ifndef QR_ONLY
#define QR_ONLY 1
#endif

#include "Functions.h"

struct cont_type cont;
#if !QR_ONLY
const char* sV1_CW_FAIL="S.VM CW FAIL";
const char* sV1_ACW_FAIL="S.VM ACW FAIL";

const char* sV2_CW_FAIL="E.VM CW FAIL";
const char* sV2_ACW_FAIL="E.VM ACW FAIL";

char sV1FT_ACW_FAIL[17]="S.VM FT ACW FAIL";
char sV1FT_CW_FAIL[16]="S.VM FT CW FAIL";

char sV2FT_ACW_FAIL[17]="E.VM FT ACW FAIL";
char sV2FT_CW_FAIL[16]="E.VM FT CW FAIL";
#endif

#ifdef BOARD_VER2
	void valve_left(void){
		VAC_VLV=1;
		DELAY_50mS();
	}
	void valve_right_idle(void){
		VAC_VLV=0;
		DELAY_50mS();
	}
#else
	void valve_left(void){
		Valve_1_L=0;
		Valve_1_R=1;
		DELAY_50mS();
	}	
	void valve_right_idle(void){
		Valve_1_L=0;
		Valve_1_R=0;
		DELAY_50mS();
	}

#endif



void Tower_Write(unsigned char value)
{
#ifdef BOARD_VER2
  I2C_Start();
  I2C_Write(0b01110010);
  I2C_Write(value);
  I2C_Stop();
#endif
}

unsigned char read_eeprom(unsigned char addr){
	unsigned char data;
	EEADR = addr; // wite the required address
	EECON1 &= 0x3F; // EEPGD = 0, CFGS = 0, all other bits are kept unchanged
	EECON1 |= 0x01; // RD = 1, all other bits are kept unchanged
	while ( EECON1 & 0x01 ); // wait till RD becomes 0
	data = EEDATA; // read the data from the data register
	return data;
}

void write_eeprom(unsigned char Data, unsigned char addr ) {
	EEADR = addr; // wite the required address
	EEDATA = Data; // write the data
	EECON1 &= 0x3F; // EEPGD = 0, CFGS = 0, all other bits are kept unchanged
	EECON1 |= 0x04; // WREN = 1, all other bits are kept unchanged
	INTCONbits.GIE = 0; // disable all interrupt
	EECON2 = 0x55; // should write this value before initializing write
	EECON2 = 0xAA; // should write this value before initializing write
	EECON1 |= 0x02; // WR = 1, all other bits are kept unchanged
	INTCONbits.GIE = 1; // enable interrupts
	while ( EECON1 & 0x20 ); // wait till WR becomes 0
	 DELAY_50mS();
	EECON1 &= 0xFB; // WREN = 0, all other bits are kept unchanged
}


void DELAY_10mS(void)
{
	unsigned int i,j;
	for(j=0;j<30;j++)				
	for (i = 0; i < 73; i++);
}
void DELAY_1S(void)
{	
	unsigned int i,j;
	for(j=0;j<80;j++)				//1s=56
	for (i = 0; i < 9980; i++);
}

void DELAY_500mS(void)
{
	unsigned int i,j;
	for(j=0;j<28;j++)			
	for (i = 0; i < 9920; i++);
}

void DELAY_250mS(void)
{
	unsigned int i,j;
	for(j=0;j<14;j++)				
	for (i = 0; i < 9920; i++);
}
 
void DELAY_100mS(void)
{	
	unsigned int i,j;
	for(j=0;j<6;j++)					
	for (i = 0; i < 9265; i++);
}
void DELAY_50mS(void)
{
	unsigned int i,j;
	for(j=0;j<3;j++)				
	for (i = 0; i < 9000; i++);
}
void DELAY_1mS(void)
{
	unsigned int i,j;
	for(j=0;j<3;j++)				
	for (i = 0; i < 65; i++);
}
void DELAY_2mS(void)
{
	unsigned int i,j;
	for(j=0;j<3;j++)				
	for (i = 0; i < 180; i++);
}

void ADC_Init(void){
	ADCON1=0x0B;
	ADCON2=0x35;
	ADCON0=0x00;
}

unsigned int ADC_Read(unsigned char ChnlNo)
{
	unsigned int data1=0x00,data2=0x00,data=0x00,loop=0,data_send=0x00,loop_count=20;
	unsigned long int data_tot=0x00;

	switch (ChnlNo)
	{	
		case 0:
		ADCON0=0b00000001;
		break;
		case 1:
		ADCON0=0b00000101;
		break;
		case 2:
		ADCON0=0b00001001;
		break;
		case 3:
		ADCON0=0b00001101;
		break;
		case 4:
		ADCON0=0b00010001;
		break;
	}

	while(loop<loop_count)		// reads 0x50 times
	{
	loop++;						// increments loop
	ADCON0bits.GO=0x01;			// Start conversion
	Nop();						// wait 50 ns
	while(ADCON0bits.GO);// wait for conversion to finish
	data1=ADRESH;			// Assign the MSB to data1
	data2=ADRESL;			// Assign the LSB to data2
	data1=data1<<2;			// Left shift LSB by 2 times
	data2=data2>>6;			// Right shift MSB by 6 times
	data=data1|data2;		// bit wise ORing of MSB & LSB
	data_tot=data_tot+data;	// add the current data with last data
	Nop();					// wait for 50ns
	Nop();					// wait for 50ns
	Nop();					// wait for 50ns
	Nop();					// wait for 50ns
	}
	data_send=(data_tot/loop_count);// find the average value of data
	return(data_send);				// returns the 10-bit converted value
}


#if !QR_ONLY
char RtryValve_1_ACW(void)
{
	unsigned int q,VTG;
	if(sbc_ready==1){
		write_rom_string_rpi("\nS.VM ACW\n");

	}
	P_ValveM1_R=0;
	P_ValveM1_F=0;
	ValveM1_R=1;
	ValveM1_F=0;
	DELAY_50mS();
	DELAY_50mS();
	for(q=0;q<300;q++)
	{
		DELAY_50mS();
		VTG=ADC_Read(0);
		if(sbc_ready==1){
			sent_rpi_valve_rot(q, VTG);
		}
		if(VTG>860)
		break;
	}
	ValveM1_R=0;
	write_rpi_sect_brk();
	if(q==300){	
		BUZZER=1;
		display(0,0,sV1_ACW_FAIL,0);
		write_rom_rpi_nl();
		write_rom_string_rpi(sV1_ACW_FAIL);
		DELAY_1S();
		DELAY_1S();
		DELAY_1S();
		BUZZER=0;
		cont.v1_acw_error++;
		return 1;
	}
	cont.v1_acw_error=0;
	return 0;
}

char RtryValve_1_CW(void)
{
	unsigned int q,VTG;
	if(sbc_ready==1){
		write_rom_string_rpi("\nS.VM CW\n");
	}
	P_ValveM1_R=0;
	P_ValveM1_F=0;
	ValveM1_R=0;
	ValveM1_F=1;
	DELAY_50mS();
	DELAY_50mS();
	for(q=0;q<300;q++)
	{
		DELAY_50mS();
		VTG=ADC_Read(0);
		if(sbc_ready==1){
			sent_rpi_valve_rot(q, VTG);
		}	
		if(VTG<593)
		break;	
	}
	ValveM1_F=0;
	write_rpi_sect_brk();
	if(q==300){
		BUZZER=1;
		display(0,0,sV1_CW_FAIL,0);
		write_rom_rpi_nl();
		write_rom_string_rpi(sV1_CW_FAIL);
		DELAY_1S();
		DELAY_1S();
		DELAY_1S();
		BUZZER=0;
		cont.v1_cw_error++;
		return 1;
	}
	cont.v1_cw_error=0;
	return 0;
}
char RtryValve_2_ACW(void)
{
	unsigned int q,VTG;
	if(sbc_ready==1){
		write_rom_string_rpi("\nE.VM ACW\n");

	}
	P_ValveM2_R=0;
	P_ValveM2_F=0;
	ValveM2_R=1;
	ValveM2_F=0;
	DELAY_50mS();
	DELAY_50mS();
	for(q=0;q<300;q++)
	{
		DELAY_50mS();
		VTG=ADC_Read(1);
		if(sbc_ready==1){
			sent_rpi_valve_rot(q, VTG);
		}
		if(VTG>860)
		break;	
	}
	ValveM2_R=0;
	write_rpi_sect_brk();
	if(q==300){
		BUZZER=1;
		display(0,0,sV2_ACW_FAIL,0);
		write_rom_rpi_nl();
		write_rom_string_rpi(sV2_ACW_FAIL);
		DELAY_1S();
		DELAY_1S();
		DELAY_1S();
		BUZZER=0;
		cont.v2_acw_error++;
		return 1;
	}
	cont.v2_acw_error=0;
	return 0;
}
char RtryValve_2_CW(void)
{
	unsigned int q,VTG;
	if(sbc_ready==1){
		write_rom_string_rpi("\nE.VM CW\n");

	}
	P_ValveM2_R=0;
	P_ValveM2_F=0;
	ValveM2_R=0;
	ValveM2_F=1;
	DELAY_50mS();
	DELAY_50mS();
	for(q=0;q<300;q++)
	{
		DELAY_50mS();
		VTG=ADC_Read(1);
		if(sbc_ready==1){
			sent_rpi_valve_rot(q, VTG);
		}
		if(VTG<593)
		break;
	}
	ValveM2_F=0;
	write_rpi_sect_brk();
	if(q==300){
		BUZZER=1;
		display(0,0,sV2_CW_FAIL,0);
		write_rom_rpi_nl();
		write_rom_string_rpi(sV2_CW_FAIL);
		DELAY_1S();
		DELAY_1S();
		DELAY_1S();
		BUZZER=0;
		cont.v2_cw_error++;
		return 1;
	}
	cont.v2_cw_error=0;	
	return 0;
}

void RtryValve_1_ACW_HF(void)
{
	unsigned int q,VTG;
	P_ValveM1_R=0;
	P_ValveM1_F=0;
	ValveM1_R=1;
	ValveM1_F=0;
	DELAY_50mS();
	DELAY_50mS();
	for(q=0;q<55;q++)
	{
		DELAY_50mS();
	}
	ValveM1_R=0;
	Nop();
}

void RtryValve_1_CW_HF(void)
{
	unsigned int q,VTG;
//	extern unsigned char RtryValve_HF;
	P_ValveM1_R=0;
	P_ValveM1_F=0;
	ValveM1_R=0;
	ValveM1_F=1;
	DELAY_50mS();
	DELAY_50mS();
	for(q=0;q<(45+RtryValve_HF);q++)
	{
		DELAY_50mS();
	}
	ValveM1_F=0;
	Nop();
}

char RtryValve_1_FT(void)
{
	unsigned int q,VTG;
	
	if(sbc_ready==1){
		write_rom_string_rpi("\nS.VM FT ACW\n");

	}
	
	P_ValveM1_R=0;
	P_ValveM1_F=0;		
	ValveM1_F=0;
	ValveM1_R=1;
	DELAY_50mS();
	DELAY_50mS();
	for(q=0;q<200;q++)
	{
		DELAY_50mS();
		VTG=ADC_Read(0);
		if(sbc_ready==1){
			sent_rpi_valve_rot(q, VTG);
		}
		if(VTG>860)
		break;	
	}
	ValveM1_R=0;
	write_rpi_sect_brk();
	if(q<80 || q>128){
		char value[6];
		BUZZER=1;
		value[0]='T';
		value[1]=':';
		value[2]=q/100+'0';
		value[3]=(q/10)%10+'0';
		value[4]=q%10+'0';
		value[5]=0;
		display_ram(1,value,sV1FT_ACW_FAIL,0);
		if(sbc_ready==1){
			write_rom_rpi_nl();
			write_ram_string_rpi(sV1FT_ACW_FAIL);
		}
		DELAY_1S();
		DELAY_1S();
		DELAY_1S();
		BUZZER=0;
		cont.v1ft_acw_error++;
		return 2;
	}
	cont.v1ft_acw_error=0;
	return 0;
}

char RtryValve_2_FT(void)
{
	unsigned int q,VTG;
	if(sbc_ready==1){
		write_rom_string_rpi("\nE.VM FT CW\n");
	}
	P_ValveM2_R=0;
	P_ValveM2_F=0;
	ValveM2_R=0;
	ValveM2_F=1;
	DELAY_50mS();
	DELAY_50mS();
	for(q=0;q<200;q++)
	{
		DELAY_50mS();
		VTG=ADC_Read(1);
		if(sbc_ready==1){
			sent_rpi_valve_rot(q, VTG);
		}
		if(VTG<593)
		break;
	}
	
	ValveM2_F=0;
	write_rpi_sect_brk();
	if(q<80 || q>128){
		char value[6];
		BUZZER=1;
		value[0]='T';
		value[1]=':';
		value[2]=q/100+'0';
		value[3]=(q/10)%10+'0';
		value[4]=q%10+'0';
		value[5]=0;
		display_ram(1,value,sV2FT_CW_FAIL,0);
		if(sbc_ready==1){
			write_rom_rpi_nl();
			write_ram_string_rpi(sV2FT_CW_FAIL);
		}
		DELAY_1S();
		DELAY_1S();
		DELAY_1S();
		BUZZER=0;
		cont.v2ft_cw_error++;
		return 2;
	}
	cont.v2ft_cw_error=0;	
	return 0;
}
#endif // !QR_ONLY



#if !QR_ONLY
void Step_1Sec_Clk2(void)
{
	unsigned int i;
//	ENB=0;
	for(i=0;i<650;i++)
	{
		CLK_2=1;
		DELAY_2mS();
		CLK_2=0;
		DELAY_2mS();
	}
//	ENB=1;
}



void Step_1Sec_Clk4(void)
{
	unsigned int i;
//	ENB=0;
	for(i=0;i<325;i++)
	{
		CLK_2=1;
		DELAY_2mS();DELAY_2mS();
		CLK_2=0;
		DELAY_2mS();DELAY_2mS();
	}
//	ENB=1;
}
#endif // !QR_ONLY


void Init_PowerInt(void){
	INTCON2bits.INTEDG2=0;                     
	INTCON3bits.INT2IF=0;                       
	INTCON3bits.INT2IP=1;  
	INTCON3bits.INT2IE=1; 
	INTCONbits.GIE=1;
}



//#define BOARD_TEST
	#ifdef BOARD_TEST
void read_current_test(unsigned char adc,unsigned int current_adc_offset){

	char c;
	unsigned char first_digit,second_digit, third_digit, fourth_digit;
	unsigned int current_adc=0,current_adc_avg=0,current_v=0, current_c=0,current_adc_min=1023 ,current_adc_max=0;
	char string[17]="Current=      ";  
	while(SW_1){
		current_adc_avg=0;
				for(c=0;c<20;c++){
					current_adc=ADC_Read(adc);
					current_adc_avg+=current_adc;					
				}
				current_adc_avg=current_adc_avg/20;
				if(current_adc_offset>current_adc_avg){
				current_c = (((unsigned long int)current_adc_offset) - current_adc_avg);
					
				current_c =((unsigned long int)current_c*((unsigned long int)1000))/((unsigned long int)1023);
				
					string[0+8] ='-';
				 	string[1+8] = ((int) current_c / 100) + '0';
				    string[2+8] = (((current_c) % 100) / 10) + '0';
				    string[3+8] = ((current_c) % 10) + '0';
				    string[4+8] = ' ';
				    string[5+8] = 'm';
				    string[6+8] = 'A';			
				    string[7+8] = 0;
				    
				     LCD_Cmd(LCD_SECOND_ROW );
				   	 LCD_Print_rammem(string);
				}
				else if(current_adc_avg>current_adc_offset){
					current_c = (((unsigned long int)current_adc_avg) - current_adc_offset);
				//	current_c = (current_c * 65.178*CURRENT_CALIB_VALUE) / 100;
				
					current_c =((unsigned long int)current_c*((unsigned long int)1000))/((unsigned long int)1023);
				
					string[0+8] ='+';
				 	string[1+8] = ((int) current_c / 100) + '0';
				    string[2+8] = (((current_c) % 100) / 10) + '0';
				    string[3+8] = ((current_c) % 10) + '0';
				    string[4+8] = ' ';
				    string[5+8] = 'm';
				    string[6+8] = 'A';
				    string[7+8] = 0;

				    LCD_Cmd(LCD_SECOND_ROW );
				   	 LCD_Print_rammem(string);
				   
				   
				}
				else {
					
					current_c = 0;
					string[0+8] =  ' ';
				    string[1+8] = '0';
				    string[2+8] = '0';
				    string[3+8] = '0';
				    string[4+8] = ' ';
				    string[5+8] = 'm';
				    string[6+8] = 'A';
				    string[7+8] = 0;
				 
				    LCD_Cmd(LCD_SECOND_ROW );
				   	 LCD_Print_rammem(string);
				}
		//DELAY_100mS();
			}

}
	#endif
#if !QR_ONLY
void DisplayPressure(unsigned int adc_val)
{
char	SBC_String[12];
	double output_vol;
	unsigned char first_digit,second_digit, third_digit, fourth_digit;
	char string[18]="P=        T=   s"; 
	unsigned long voltage_value;
	extern unsigned int C_BaseValue;
	extern unsigned int TM;

/*********************************/
//	init_adc_thermistor();
	C_BaseValue=adc_val;
	output_vol=C_BaseValue;
	voltage_value=output_vol/.2046;	
/********************************/
	first_digit=(int) voltage_value/1000;
	second_digit=((voltage_value)%1000)/100;
	third_digit=((voltage_value)%100)/10;
	fourth_digit=(voltage_value)%10;
	SBC_String[3]=',';
	SBC_String[4]=string[2] =first_digit+0x30;
	SBC_String[5]=string[3] ='.';
	SBC_String[6]=string[4] =second_digit+0x30;
	SBC_String[7]=string[5] =third_digit+0x30;
	SBC_String[8]=string[6] =fourth_digit+0x30;
	string[7]='V';
	SBC_String[9]='\n';
	SBC_String[10]=0;
	
	first_digit= (int) 	TM/100;
	second_digit=((TM)%100)/10;
	third_digit=(TM)%10;

	SBC_String[0]=string[12] =first_digit+0x30;
	SBC_String[1]=string[13] =second_digit+0x30;
	SBC_String[2]=string[14] =third_digit+0x30;

/********************************/
	if(sbc_ready==1){
	write_ram_string_rpi(SBC_String);
	}

/********************************/

	LCD_Cmd(LCD_SECOND_ROW );
	LCD_Print_rammem(string);
}
#endif // !QR_ONLY

	void board_test_protocol(void)
	{
	#ifdef BOARD_TEST
		/* Board test routine intentionally disabled in production builds. */
	#endif
	}

//
//void board_test_protocol(void){
//	
//	#ifdef BOARD_TEST
//	unsigned char i=0;
//	display(1,"BOARD TESTING",0,2);
//	DISABLE_POWER_INT;
//	
////	goto L_RTC;
//	
//	display(1,"PRESS SW1",0,1);
//	while(SW_1);
//	display(0,0,"SW1 PRESSED",1);
//	while(!SW_1);
//	
//	display(1,"PRESS SW2",0,1);
//	while(SW_2);
//	display(0,0,"SW2 PRESSED",1);
//	while(!SW_2);
//	
//	display(1,"PRESS SW3",0,1);
//	while(SW_3);
//	display(0,0,"SW3 PRESSED",1);
//	while(!SW_3);
//	
//
//	
//	display(1,"BUZZER TEST",0,1);
//	display(0,0,"BUZZER ON?",1);
//	BUZZER=1;
//	while(SW_1);
//	while(!SW_1);
//	BUZZER=0;
//	display(0,0,"BUZZER OFF?",1);
//	while(SW_1);
//	while(!SW_1);
//	
//	display(1,"SHORT J7",0,1);
//	while(CAT_SNS);
//	display(0,0,"J7 SHORTED",1);
//	while(!CAT_SNS);
//	
//	display(1,"SHORT J4 PIN 1&2",0,1);
//	if(STACK_SNS){
//			display(0,0,"ERROR-SHORTED!",1);
//			while(SW_1&&SW_2);
//	}
//	while(!STACK_SNS);
//	display(0,0,"J4 SHORTED",1);
//	while(STACK_SNS);
//	
//	display(1,"SHORT J3 PIN 1&2",0,1);
//	if(MECH_UP_SNS){
//			display(0,0,"ERROR-SHORTED!",1);
//			while(SW_1&&SW_2);
//	}
//	while(!MECH_UP_SNS);
//	display(0,0,"J3 SHORTED",1);
//	while(MECH_UP_SNS);
//	
//	display(1,"SHORT J2 PIN 1&2",0,1);
//	if(FW_SNS){
//			display(0,0,"ERROR-SHORTED!",1);
//			while(SW_1&&SW_2);
//	}
//	while(!FW_SNS);
//	display(0,0,"J2 SHORTED",1);
//	while(FW_SNS);
//	
//	display(1,"SHORT J1 PIN 1&2",0,1);
//	if(BW_SNS){
//			display(0,0,"ERROR-SHORTED!",1);
//			while(SW_1&&SW_2);
//	}
//	while(!BW_SNS);
//	display(0,0,"J1 SHORTED",1);
//	while(BW_SNS);
//	
//	
//{
//	unsigned int current_adc_offset;
//	
//		
//	/*********************Valve Motor 2 IDLE**********************/
//		display(1,"VM 2 OFF","J9 PIN 1->2 = 0V",0);
//		ValveM2_F=0;ValveM2_R=0;
//	
//		DELAY_100mS();
//		while(SW_1);
//		DELAY_100mS();
//		while(!SW_1);
//		DELAY_250mS();
//		current_adc_offset=ADC_Read(1);
//		
//		
//		
//	/*********************Valve Motor 2 FW**********************/
//		display(1,"VM 2 RW","J9 PIN 1->2 =-V?",0);
//		ValveM2_F=1;ValveM2_R=0;
//		DELAY_100mS();
//		while(SW_1);
//		DELAY_100mS();
//		while(!SW_1);
//		DELAY_100mS();
//		
//	/*********************Valve Motor 2 FW STALL**********************/	
//		display(1,"VM2 RW STL",0,0);
//		read_current_test(1,current_adc_offset);
//	
//		DELAY_100mS();
//		while(SW_1);
//		DELAY_100mS();
//		while(!SW_1);
//		DELAY_250mS();	
//		 
//	/*********************Valve Motor 2 RW**********************/
//		display(1,"VM 2 FW","J9 PIN 1->2 =+V?",0);
//		ValveM2_F=0;ValveM2_R=1;
//		while(SW_1);
//		DELAY_100mS();
//		while(!SW_1);
//		DELAY_250mS();
//		
//	/*********************Valve Motor 2 RW STALL**********************/	
//		display(1,"VM2 FW STL",0,0);
//		read_current_test(1,current_adc_offset);
//	
//		DELAY_100mS();
//		while(!SW_1);
//		DELAY_250mS();		
//		
//		ValveM2_F=0;ValveM2_R=0;
//
//	/*********************Valve Motor 1 IDLE**********************/
//		display(1,"VM 1 OFF","J8 PIN 1->2 = 0V",0);
//		ValveM1_F=0;ValveM1_R=0;
//		DELAY_100mS();
//		while(SW_1);
//		DELAY_100mS();
//		while(!SW_1);
//		DELAY_100mS();
//		current_adc_offset=ADC_Read(0);
//	/*********************Valve Motor 1 FW**********************/
//		display(1,"VM1 RW","J8 PIN 1->2 =-V?",0);
//		ValveM1_F=1;ValveM1_R=0;
//		
//		DELAY_100mS();
//		while(SW_1);
//		DELAY_100mS();
//		while(!SW_1);
//		DELAY_100mS();
//		
//	/*********************Valve Motor 1 FW STALL**********************/	
//		display(1,"VM1 RW STL",0,0);
//		read_current_test(0,current_adc_offset);
//	
//		DELAY_100mS();
//		while(SW_1);
//		DELAY_100mS();
//		DELAY_250mS();
//	/*********************Valve Motor 1 RW**********************/
//		display(1,"VM1 FW","J8 PIN 1->2 =+V?",0);
//		ValveM1_F=0;ValveM1_R=1;
//	
//		DELAY_100mS();
//		while(SW_1);
//		DELAY_100mS();
//		while(!SW_1);
//		DELAY_250mS();
//		
//		
//	/*********************Valve Motor 1 RW STALL**********************/	
//		display(1,"VM1 FW STL",0,0);
//		read_current_test(0,current_adc_offset);
//	
//		DELAY_100mS();
//		while(!SW_1);
//		DELAY_100mS();	
//		
//		ValveM1_F=0;ValveM1_R=0;
//	
//	}
///*********************STEPPER CLOCKWISE**********************/
//	display(1,"STEPPER TEST","",0);
//            CLK_2 = 0;
//          //  DIR_2 = 0;
//            ENB_2 = 0;
//            while(SW_1){
//                CLK_2 = 1;
//                DELAY_1mS();              
//                CLK_2 = 0;
//                DELAY_1mS();
//            }
//            ENB_2 = 1;
//            DELAY_1mS();
//	DELAY_100mS();
//	while(!SW_1);
//	DELAY_100mS();
//	
//	
//display(1,"LATCH SOLINOID","J10 PIN 1->2=0V?",0);	
//Valve_1_L=0;
//Valve_1_R=0;
//DELAY_250mS();
//while(!SW_1);
//DELAY_250mS();
//while(SW_1);
//DELAY_250mS();
//
//
//display(0,0,"J10 PIN 1->2=+V?",0);	
//Valve_1_L=0;
//Valve_1_R=1;
//DELAY_250mS();
//while(!SW_1);
//DELAY_250mS();
//while(SW_1);
//Valve_1_R=0;
//
//display(0,0,"J10 PIN 1->2=-V?",0);
//DELAY_250mS();DELAY_250mS();
//	
//Valve_1_L=1;
//Valve_1_R=0;
//while(!SW_1);
//DELAY_250mS();
//while(SW_1);
//Valve_1_L=0;
//DELAY_250mS();
//
//display(1,"CARTRIDGE F/B","J11 PIN 1->2=0V?",0);	
//CAT_FB=0;
//DELAY_100mS();
//while(SW_1);
//DELAY_100mS();
//while(!SW_1);
//
//display(0,0,"J11 PIN 1->2= V?",0);	
//CAT_FB=1;
//DELAY_100mS();
//while(SW_1);
//DELAY_100mS();
//while(!SW_1);
//CAT_FB=0;
//
//display(1,"REJECTION","J12 PIN 1->2=0V?",0);	
//REJECT_SV=0;
//DELAY_100mS();
//while(SW_1);
//DELAY_100mS();
//while(!SW_1);
//
//display(0,0,"J12 PIN 1->2= V?",0);	
//REJECT_SV=1;
//DELAY_100mS();
//while(SW_1);
//DELAY_100mS();
//REJECT_SV=0;
//
//
//display(1,"ELECTRIC SOLIN.D","J13 PIN 1->2=0V?",0);	
//ELECT_SOL=0;
//DELAY_100mS();
//while(SW_1);
//DELAY_100mS();
//while(!SW_1);
//
//display(0,0,"J13 PIN 1->2= V?",0);	
//ELECT_SOL=1;
//DELAY_100mS();
//while(SW_1);
//DELAY_100mS();
//ELECT_SOL=0;
//
//
//display(1,"PLATE U/D","J14 PIN 1->2=0V?",0);	
//PLATE_UD=0;
//DELAY_100mS();
//while(SW_1);
//DELAY_100mS();
//while(!SW_1);
//
//display(0,0,"J14 PIN 1->2= V?",0);	
//PLATE_UD=1;
//DELAY_100mS();
//while(SW_1);
//DELAY_100mS();
//PLATE_UD=0;
//
//
//L_RTC:while(!SW_1);
//	
//	{
//		char calender_temp[16],Temp1;
//		unsigned char pRTCArray1[4];
//		unsigned char pRTCArray2[4];
//		pRTCArray1[2] = 23;
//	    pRTCArray1[1] = 59;
//	    pRTCArray1[0] = 58;
//	    Set_DS1307_RTC_Time(TwentyFourHoursMode, pRTCArray1[2], pRTCArray1[1], pRTCArray1[0]);
//	    Set_DS1307_RTC_Date(31, 12, 19, 0); // Set date
//	       i=0; 
//	    while(SW_1){    
//	    	 InitI2C();
//	        Read_Bytes_From_DS1307_RTC(0x00, pRTCArray1, 3);
//	        Temp1 = pRTCArray1[0];
//	        pRTCArray1[0] = ((Temp1 & 0x7F) >> 4)*10 + (Temp1 & 0x0F); //sec
//	        Temp1 = pRTCArray1[1];
//	        pRTCArray1[1] = (Temp1 >> 4)*10 + (Temp1 & 0x0F); //min
//	        Temp1 = pRTCArray1[2];
//	        pRTCArray1[2] = (Temp1 >> 4)*10 + (Temp1 & 0x0F); //hour  
//	        Read_Bytes_From_DS1307_RTC(0x03, pRTCArray2, 4);
//	        // Convert Day back from BCD into number
//	        Temp1 = pRTCArray2[0];
//	        pRTCArray2[0] = (Temp1 >> 4)*10 + (Temp1 & 0x0F);
//	        // Convert Date back from BCD into number
//	        Temp1 = pRTCArray2[1];
//	        pRTCArray2[1] = (Temp1 >> 4)*10 + (Temp1 & 0x0F);
//	        // Convert Month back from BCD into number
//	        Temp1 = pRTCArray2[2];
//	        pRTCArray2[2] = (Temp1 >> 4)*10 + (Temp1 & 0x0F);
//	        // Convert Year back from BCD into number
//	        Temp1 = pRTCArray2[3];
//	        pRTCArray2[3] = (Temp1 >> 4)*10 + (Temp1 & 0x0F);
//	         calender_temp[1]= pRTCArray2[1]%10+'0';
//	        calender_temp[0]= pRTCArray2[1]/10+'0';
//	        
//	        calender_temp[3]= pRTCArray2[2]%10+'0';
//	        calender_temp[2]= pRTCArray2[2]/10+'0';
//	        
//	        calender_temp[5]=pRTCArray2[3]%10+'0';
//	        calender_temp[4]=pRTCArray2[3]/10+'0';
//	        calender_temp[6]='-';
//	        calender_temp[8]= pRTCArray1[2]%10+'0';
//	        calender_temp[7]= pRTCArray1[2]/10+'0';
//	        
//	        calender_temp[10]=pRTCArray1[1]%10+'0';
//	        calender_temp[9]=pRTCArray1[1]/10+'0';
//	        
//	        calender_temp[12]= pRTCArray1[0]%10+'0';
//	        calender_temp[11]= pRTCArray1[0]/10+'0';
//	    
//	        calender_temp[13]=0;
//	        
//	        LCD_Cmd(LCD_FIRST_ROW );
//			LCD_Print_rammem(calender_temp);
//			DELAY_50mS();
//			
//			
//		}
//	}
//	DELAY_250mS();
//	while(!SW_1);
//	DELAY_100mS();
//	
//	
//	display(1,"SBC GPIO TEST","A=B=C=3.3V|D=5V",1);
//	INT_PIC_P=0;
//	TX_PIC_P=0; 
//	RX_PIC_P=0; 
//	
//	while(SW_1){
//		INT_PIC=1;
//		TX_PIC=1;
//		RX_PIC=1;
//		i=30;
//		while(i--){
//			DELAY_100mS();
//			if(SW_1==0)break;
//		}
//		INT_PIC=0;	
//		TX_PIC=0;
//		RX_PIC=0;	
//		i=30;
//		while(i--){
//			DELAY_100mS();
//			if(SW_1==0)break;
//		}
//	}
//	
//	INT_PIC=0;	
//	TX_PIC=0;
//	RX_PIC=0;
//		
//	DELAY_250mS();
//	while(!SW_1);
//	DELAY_100mS();
//
//	
///********************Pressure************************/
//	display(1,"PRESSURE TEST",0,0);	
//	while(SW_1)DisplayPressure(ADC_Read(2)); 
//	DELAY_100mS();
//	while(!SW_1);
//	DELAY_100mS();
//
///********************Power off************************/
//	display(1,"PWR OFF TEST",0,0);	
//	while(SW_3||SW_2){
//		char pdown_time=0, pdown_time_string[4]={' ', ' ','S',0};
//		display(0,0,"PRESS POWER SW1",0);	
//		pdown_time=0;
//		if (!SW_1){
//			
//			while(!SW_1){
//				DELAY_500mS();DELAY_100mS();DELAY_100mS();DELAY_100mS();DELAY_100mS();
//				pdown_time++;
//				if(pdown_time==10){
//					display(0,0,"PDN TIME ERROR",0);	
//					while(1);
//				}
//				pdown_time_string[0]=pdown_time+'0';
//				LCD_Cmd(LCD_FIRST_ROW );
//				LCD_Print_rammem(pdown_time_string);
//			}
//		}
//	}
//	DELAY_250mS();
//	while(!SW_1);
//	DELAY_100mS();			
//	display(1,"TEST","COMPLETED",1);			
//	while(!SW_1);
//	DELAY_100mS();			
//Reset();	
//			
//#endif
//
//}
//
