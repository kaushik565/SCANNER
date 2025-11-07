#ifndef SYS_F_H
#define SYS_F_H

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
#include <fcntl.h>
#include <sys/time.h>
#include <poll.h>
#include "bluetooth.h"
#include "autoprep.h"


void cpu_frequency_1000(void);
void cpu_frequency_700(void);
void cpu_frequency_userspace_700(void);

int GPIOWrite(int pin, int value);
int GPIORead(int pin);
int GPIODirection(int pin, int dir);
int GPIOExport(int pin);
int GPIOEdge(int pin, char* edge);

#endif