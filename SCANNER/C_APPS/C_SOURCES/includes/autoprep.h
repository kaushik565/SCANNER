#ifndef AUTOPREP_H
#define AUTOPREP_H

#define SBC_VERSION "1.1"

#define VERBOSE 1

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <sys/wait.h>
#include <unistd.h>
#include <wiringPi.h>
#include <wiringSerial.h>
#include <sqlite3.h>
#include <time.h>
#include <pthread.h>
#include <poll.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>
#include "bluetooth.h"
#include "system_functions.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <sys/wait.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/usbdevice_fs.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <sys/time.h>

#define QR_RETRY 5
#define QR_COMPARE_RETRY 2
#define QR_MAX_LEN 99
#define FILE_BUFFER_SIZE 1024*1024*5

#define FILE_STORE_COUNT 50000
#define DATABASE_MAX_ROW FILE_STORE_COUNT   //change later
#define REAGENT_STORE_COUNT 400
#define REAGENT_MAX_ROW REAGENT_STORE_COUNT   //change later

#define REAGENT_DETECTED 10
#define DUPLICATE_DETECTED 11

#define RUN_NO_FILE "/ACTJ/META_DATA/run_no"
#define REAGENT_NO_FILE "/ACTJ/META_DATA/reagent_no"
#define DATABASE_FILE "/ACTJ/META_DATA/prep_database.db"
#define DEVICE_CONFIG_FILE "/ACTJ/DEVICE/DEVICE_CONFIGRATION"
#define REAGENT_FILE "/ACTJ/META_DATA/REAGENT_INFO"
#define IMAGE_FILE "/tmp/Image.jpg"
#define FILE_PATH "/ACTJ/DATA/"
#define ZXING_FILE "/TRUEPREP/LIBRARIES/zxing"

#define SERVICE_PASSWORD "autoprep"
#define SET_POINTS_FILE "/home/pi/c_qr/setpoints"

#define SHUTDOWN_INT_PIN 17
//#define SHUTDOWN_INT_PIN 0

#define DEBUG_INT_PIN 22
//#define STATUS_PIN 1
#define STATUS_PIN 18

#define RED_LED 16
#define GREEN_LED 20
#define BLUE_LED 21

void *qr_thread( void *ptr );
int qr_read(char*);
char qr_scan_purse(void);
void start_data_recording_20(void);
void start_data_recording_15(void);

void shutdown_int_handler(void);
void debug_int_handler(void);

int serial_port;

int qr_read_zxing(char* qr_data_pointer) ;
int qr_read_zbar(char* qr_data_pointer);
int read_qr(char* qr_out, unsigned int qr_out_size);
volatile pthread_mutex_t pair_lock,database_lock; 
volatile sqlite3 *db;
volatile unsigned int extraction_status; 
#endif
