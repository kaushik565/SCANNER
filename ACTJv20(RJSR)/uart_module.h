
void InitUSART(void);
void writeusart( char);
void UARTInit(void);

void thermistor_data1(unsigned int);
void thermistor_data2(unsigned int);
void optical_data1(unsigned int);
void optical_data2(unsigned int);
void optical_data3(unsigned int);
void cycle_display(unsigned int);
void delay500us(void);
void delay100ns(void);

void send_SP_Start(void);
void send_SP_End(void);
void send_SP_Ch1_Start(void);
void send_SP_Ch1_End(void);
void send_SP_Ch2_Start(void);
void send_SP_Ch2_End(void);
void send_SP_Ch3_Start(void);
void send_SP_Ch3_End(void);




unsigned char read_serial_port(void);
unsigned char usart_main(void);

