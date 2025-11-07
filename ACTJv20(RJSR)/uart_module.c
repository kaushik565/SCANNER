#include <p18cxxx.h>
#include <usart.h>
#include "uart_module.h"


void delay100ns(void)
{
	int i,j;
	for(j=0;j<300;j++);		//500
	Nop();
	Nop();
	Nop();
}	

void delay500us(void)
{
	int j;
	for(j=0;j<5000;j++);
}

void writeusart( char data)
{
	while(BusyUSART());
	WriteUSART(data);
	Nop();
}




void UARTInit(void)
{
	static char Test1;
	Test1 = 0x24;
	TXSTA = Test1;
	RCSTA = 0x90;
	BAUDCON = 0x08;
	SPBRGH = 0x00;
	SPBRG = 0x68;	//115200 @ 48Mhz
	//IPR1bits.RCIP = 1;
	//INTCON = 0x00;	//this will enable after receiving and sorting all bits
	//PIE1bits.RCIE = 1;
}




