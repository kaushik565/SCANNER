#include "autoprep.h"
#include <fcntl.h> // Contains file controls like O_RDWR
#include <errno.h> // Error integer and strerror() function
#include <termios.h> // Contains POSIX terminal control definitions
#include <unistd.h> // write(), read(), close()
#include <time.h>
#include <semaphore.h>
#include <sys/wait.h>
#include <signal.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/inotify.h>
#include <unistd.h>


#define QR_DATA_SEPERATER '-'
static char qr_data_1[100],previous_qr[100]="--";
static char input_file_buffer[FILE_BUFFER_SIZE];
static unsigned long file_buffer_pos = 0;
static int qr_compare_try = 0;
static int qr_read_error1 = 0;
static int no_camera = 0;
static int no_qr = 0;
static char *zErrMsg = 0;
static char towerlight_st = 0;
static int rc;
static char sql[1000];

static volatile char serial_no[100] = {"NA_0"}, lot_no[100] = {"NA_0"}, mfd[100] = {"NA_0"}, type[100] = {"NA_0"}, file[100] = {"NA_0"};
static int reagent_exp_day, reagent_exp_month, reagent_exp_year;
static int catridge_exp_day, catridge_exp_month, catridge_exp_year;
static FILE *reagent_file;
static unsigned  run_no;
static volatile unsigned qr_status = 0;
static FILE *output_file, *run_no_file;
static char device_id[50];
static  volatile int qr_read_try = 0, qr_read_fn_error = 0, qr_read_try_zxing = 0, qr_read_fn_error_zxing = 0;

volatile unsigned int row_no = 0;
char* delete_file_name;
volatile unsigned int duplicate_flag = 0;

pthread_t bluetooth_parent, qr_scan_thread, shutdown_thread_handler, ntp_thread_handler;
int  iret1, iret2, iret3;
extern volatile int pairing_ok, pair_request;
pthread_cond_t pair_condition = PTHREAD_COND_INITIALIZER;

static sqlite3_stmt *autoprep_statement;
void *shutdown_thread( void *ptr );



void log_time(void) {
  time_t t = time(NULL);
  struct tm tm = *localtime(&t);
  t = time(NULL);
  tm = *localtime(&t);

  fprintf(stderr, "\n%d-%d-%d %d:%d\n", tm.tm_mday, tm.tm_mon + 1, tm.tm_year + 1900, tm.tm_hour, tm.tm_min);
}

void sync_rtc(void){
  FILE* fp;
  fp = popen("hwclock -r", "r"); //open pipe
  pclose(fp);
}
char mac_id[13];
char device_ip[50]="NC";

void user_signal_handler(int signo){
  if (signo == SIGUSR1){
        printf("received SIGUSR1\n");
		signal(SIGUSR1, SIG_IGN);
		bluetooth_thread();
  }
}
int main () {
	
	#define EVENT_SIZE  ( sizeof (struct inotify_event) )
		#define EVENT_BUF_LEN     ( 1024 * ( EVENT_SIZE + 16 ) )
		int length, i = 0;
		int fd;
		int wd;
		char buffer[EVENT_BUF_LEN];

			mkdir("/tmp/python_c_sync/", S_IRWXU | S_IRWXG | S_IRWXO);
			if (chmod("/tmp/python_c_sync/", S_IRWXU | S_IRWXG | S_IRWXO)) {
    perror("chmod");
}
			
		fd = inotify_init();
		if (fd < 0) {
			perror("inotify_init");
		}
		wd = inotify_add_watch(fd, "/tmp/python_c_sync/",
			IN_MODIFY | IN_CREATE);
		length = read(fd, buffer, EVENT_BUF_LEN);
		if (length < 0) {
			perror("read");
		}
		while (i < length) {
			struct inotify_event *event =
				(struct inotify_event *) &buffer[i];
			if (event->len) {
				if (event->mask & IN_CREATE) {
					fprintf(stderr,"File %s recieved.\n", event->name);
					bluetooth_thread();
					
				} 
			}
			i += EVENT_SIZE + event->len;
		}

		(void) inotify_rm_watch(fd, wd);
		(void) close(fd);
	
	
  /*iret1 = pthread_create( &bluetooth_parent, NULL, bluetooth_thread, NULL);
  if (iret1)
  {
    fprintf(stderr, "Error: bluetooth_thread create: %d\n", iret1);
    //exit(EXIT_FAILURE);
    log_time();
  }*/

  //pthread_create( &ntp_thread_handler, NULL, ntp_time_set, NULL);
  
    /*  sem_t *sem_id = sem_open("mxsr_bin_sem", O_CREAT, 0600, 0);
    if (sem_id == SEM_FAILED){
        fprintf(stderr,"[sem_open] Failed\n"); return;
    }
    if (sem_wait(sem_id) < 0)
       fprintf(stderr,"[sem_wait] Failed\n");*/
  // if (signal(SIGUSR1, user_signal_handler) == SIG_ERR) printf("\ncan't catch SIGINT\n");
   
    
   /* if (sem_close(sem_id) != 0){
        fprintf(stderr,"[sem_close] Failed\n"); return;
    }
    if (sem_unlink(mxsr_bin_sem) < 0){
        fprintf(stderr,"[sem_unlink] Failed\n"); return;
    }*/
  while(1)sleep(255);
}
/***********************************************************************************/


#define REAGENT_DETECTED 10
#define DUPLICATE_DETECTED 11


int usb_reset(void)
{
  const char *filename;
  int fd;
  int rc;


  filename = "/dev/bus/usb/002/002";

  fd = open(filename, O_WRONLY);
  if (fd < 0) {
    perror("Error opening output file");
    return 1;
  }

  printf("Resetting USB device %s\n", filename);
  rc = ioctl(fd, USBDEVFS_RESET, 0);
  if (rc < 0) {
    perror("Error in ioctl");
    return 1;
  }
  fprintf(stderr, "UsbRstOk\n");

  close(fd);
  return 0;
}


void *shutdown_thread( void *ptr )
{
  char str[256];
  struct timeval tv;
  struct pollfd pfd;
  int fd, gpio;
  char buf[8];
  unsigned int stime_out = 0;
  GPIOExport(SHUTDOWN_INT_PIN);
RE_INIT: GPIODirection(SHUTDOWN_INT_PIN, 0);
  GPIOEdge(SHUTDOWN_INT_PIN, "rising");

  //gpio = SHUTDOWN_INT_PIN; //bcm 17

#ifdef VERBOSE
  sprintf(str, "/sys/class/gpio/gpio%d/value", SHUTDOWN_INT_PIN);
#endif

  if ((fd = open(str, O_RDONLY)) < 0)
  {
#ifdef VERBOSE
    fprintf(stderr, "Failed, gpio %d not exported.\n", SHUTDOWN_INT_PIN);
#endif
    exit(1);
  }

  pfd.fd = fd;

  pfd.events = POLLPRI;

  lseek(fd, 0, SEEK_SET);    /* consume any prior interrupt */
  read(fd, buf, sizeof buf);

  poll(&pfd, 1, -1);         /* wait for interrupt */

  lseek(fd, 0, SEEK_SET);    /* consume interrupt */
  read(fd, buf, sizeof buf);

  delay(100);
  stime_out = 0;
  do {
    if (GPIORead(SHUTDOWN_INT_PIN) == 1)break;
    delay(10);
    stime_out++;
    if (stime_out > 300)goto RE_INIT;
  } while (1);


  sqlite3_close(db);
#ifdef VERBOSE
  fprintf (stderr, "shutdown\n");
#endif
  delay(500);
  system("sudo poweroff");
  delay(500);
  exit(0);
}




void *ntp_time_set( void *ptr ){
  sleep(100);
  int sockfd, n; // Socket file descriptor and the n return result from writing/reading from the socket.
  int portno = 123; // NTP UDP port number.
  char* host_name = "pool.ntp.org"; // NTP server host-name.
  // Structure that defines the 48 byte NTP packet protocol.
  typedef struct
  {

    uint8_t li_vn_mode;      // Eight bits. li, vn, and mode.
                             // li.   Two bits.   Leap indicator.
                             // vn.   Three bits. Version number of the protocol.
                             // mode. Three bits. Client will pick mode 3 for client.

    uint8_t stratum;         // Eight bits. Stratum level of the local clock.
    uint8_t poll;            // Eight bits. Maximum interval between successive messages.
    uint8_t precision;       // Eight bits. Precision of the local clock.

    uint32_t rootDelay;      // 32 bits. Total round trip delay time.
    uint32_t rootDispersion; // 32 bits. Max error aloud from primary clock source.
    uint32_t refId;          // 32 bits. Reference clock identifier.

    uint32_t refTm_s;        // 32 bits. Reference time-stamp seconds.
    uint32_t refTm_f;        // 32 bits. Reference time-stamp fraction of a second.

    uint32_t origTm_s;       // 32 bits. Originate time-stamp seconds.
    uint32_t origTm_f;       // 32 bits. Originate time-stamp fraction of a second.

    uint32_t rxTm_s;         // 32 bits. Received time-stamp seconds.
    uint32_t rxTm_f;         // 32 bits. Received time-stamp fraction of a second.

    uint32_t txTm_s;         // 32 bits and the most important field the client cares about. Transmit time-stamp seconds.
    uint32_t txTm_f;         // 32 bits. Transmit time-stamp fraction of a second.

  } ntp_packet;              // Total: 384 bits or 48 bytes.
  // Create and zero out the packet. All 48 bytes worth.
  ntp_packet packet = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
  memset( &packet, 0, sizeof( ntp_packet ) );
  // Set the first byte's bits to 00,011,011 for li = 0, vn = 3, and mode = 3. The rest will be left set to zero.
  *( ( char * ) &packet + 0 ) = 0x1b; // Represents 27 in base 10 or 00011011 in base 2.
  // Create a UDP socket, convert the host-name to an IP address, set the port number,
  // connect to the server, send the packet, and then read in the return packet.
  struct sockaddr_in serv_addr; // Server address data structure.
  struct hostent *server;      // Server data structure.
  sockfd = socket( AF_INET, SOCK_DGRAM, IPPROTO_UDP ); // Create a UDP socket.
  if ( sockfd < 0 ){
    perror( "ERROR opening socket" );
	return;
  }
  server = gethostbyname( host_name ); // Convert URL to IP.
  if ( server == NULL ){
    perror( "ERROR, no such host" );
	return;
  }
  get_ip(device_ip); //set device ip 
  // Zero out the server address structure.
  bzero( ( char* ) &serv_addr, sizeof( serv_addr ) );
  serv_addr.sin_family = AF_INET;
  // Copy the server's IP address to the server address structure.
  bcopy( ( char* )server->h_addr, ( char* ) &serv_addr.sin_addr.s_addr, server->h_length );
  // Convert the port number integer to network big-endian style and save it to the server address structure.
  serv_addr.sin_port = htons( portno );
  // Call up the server using its IP address and port number.
  if ( connect( sockfd, ( struct sockaddr * ) &serv_addr, sizeof( serv_addr) ) < 0 ){
    perror( "ERROR connecting" );
	return;
  }
  // Send it the NTP packet it wants. If n == -1, it failed.
  n = write( sockfd, ( char* ) &packet, sizeof( ntp_packet ) );
  if ( n < 0 ){
    perror( "ERROR writing to socket" );
	return;
  }
  // Wait and receive the packet back from the server. If n == -1, it failed.
  n = read( sockfd, ( char* ) &packet, sizeof( ntp_packet ) );
  if ( n < 0 ){
    perror( "ERROR reading from socket" );
	return;
  }
  // These two fields contain the time-stamp seconds as the packet left the NTP server.
  // The number of seconds correspond to the seconds passed since 1900.
  // ntohl() converts the bit/byte order from the network's to host's "endianness".

  packet.txTm_s = ntohl( packet.txTm_s ); // Time-stamp seconds.
  packet.txTm_f = ntohl( packet.txTm_f ); // Time-stamp fraction of a second.

  // Extract the 32 bits that represent the time-stamp seconds (since NTP epoch) from when the packet left the server.
  // Subtract 70 years worth of seconds from the seconds since 1900.
  // This leaves the seconds since the UNIX epoch of 1970.
  // (1900)------------------(1970)**************************************(Time Packet Left the Server)
  time_t txTm = ( time_t ) ( (packet.txTm_s - 2208988800ull )+120); //NTP_TIMESTAMP_DELTA
  // Print the time we got from the server, accounting for local timezone and conversion from UTC time.  
  printf( "NTP:%s", ctime( ( const time_t* ) &txTm ) );
  struct tm* tm_ptr = localtime(&txTm);
  int year= tm_ptr->tm_year + 1900; 
  if((year>2019)&&(year<2039)){
		const struct timeval tv = {mktime(tm_ptr), 0};
		settimeofday(&tv, 0);
		FILE* fp;
		sleep(1);
		fp = popen("hwclock -w", "r"); //open pipe
		if (fp == NULL) {
		  perror( "hw clock pipe failed");
		}
		pclose(fp);
  }
  else {
	 printf( "Error ntp year %d\n",year); //11-11-11-10-10-10
  }
  sleep(10);
  return NULL;
}
