#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "system_functions.h"
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>

#define IN  0
#define OUT 1

#define LOW  0
#define HIGH 1

#define PIN  24 /* P1-18 */
#define POUT 4  /* P1-07 */

int GPIOExport(int pin)
{
#define BUFFER_MAX 3
	char buffer[BUFFER_MAX];
	ssize_t bytes_written;
	int fd;

	fd = open("/sys/class/gpio/export", O_WRONLY);
	if (-1 == fd) {
		fprintf(stderr, "Failed to open export for writing!\n");
		return(-1);
	}

	bytes_written = snprintf(buffer, BUFFER_MAX, "%d", pin);
	write(fd, buffer, bytes_written);
	close(fd);
	return(0);
}


int GPIOEdge(int pin, char* edge)
{
	

#define DIRECTION_MAX 35
	char path[DIRECTION_MAX];
	int fd;

	snprintf(path, DIRECTION_MAX, "/sys/class/gpio/gpio%d/edge", pin);
	fd = open(path, O_WRONLY);
	if (-1 == fd) {
		fprintf(stderr, "Failed to open gpio edge for writing!\n");
		return(-1);
	}

	if (-1 == write(fd,edge, strlen(edge))) {
		fprintf(stderr, "Failed to set edge!\n");
		return(-1);
	}

	close(fd);
	return(0);
}

int GPIODirection(int pin, int dir)
{
	static const char s_directions_str[]  = "in\0out";

#define DIRECTION_MAX 35
	char path[DIRECTION_MAX];
	int fd;

	snprintf(path, DIRECTION_MAX, "/sys/class/gpio/gpio%d/direction", pin);
	fd = open(path, O_WRONLY);
	if (-1 == fd) {
		fprintf(stderr, "Failed to open gpio direction for writing!\n");
		return(-1);
	}

	if (-1 == write(fd, &s_directions_str[IN == dir ? 0 : 3], IN == dir ? 2 : 3)) {
		fprintf(stderr, "Failed to set direction!\n");
		return(-1);
	}

	close(fd);
	return(0);
}

int GPIORead(int pin)
{
#define VALUE_MAX 30
	char path[VALUE_MAX];
	char value_str[3];
	int fd;

	snprintf(path, VALUE_MAX, "/sys/class/gpio/gpio%d/value", pin);
	fd = open(path, O_RDONLY);
	if (-1 == fd) {
		fprintf(stderr, "Failed to open gpio value for reading!\n");
		return(-1);
	}

	if (-1 == read(fd, value_str, 3)) {
		fprintf(stderr, "Failed to read value!\n");
		return(-1);
	}

	close(fd);

	return(atoi(value_str));
}

int GPIOWrite(int pin, int value)
{
	static const char s_values_str[] = "01";

	char path[VALUE_MAX];
	int fd;

	snprintf(path, VALUE_MAX, "/sys/class/gpio/gpio%d/value", pin);
	fd = open(path, O_WRONLY);
	if (-1 == fd) {
		fprintf(stderr, "Failed to open gpio value for writing!\n");
		return(-1);
	}

	if (1 != write(fd, &s_values_str[LOW == value ? 0 : 1], 1)) {
		fprintf(stderr, "Failed to write value!\n");
		return(-1);
	}

	close(fd);
	return(0);
}

// int
// main(int argc, char *argv[])
// {
	// int repeat = 10;

	// /*
	 // * Enable GPIO pins
	 // */
	// if (-1 == GPIOExport(POUT) || -1 == GPIOExport(PIN))
		// return(1);

	// /*
	 // * Set GPIO directions
	 // */
	// if (-1 == GPIODirection(POUT, OUT) || -1 == GPIODirection(PIN, IN))
		// return(2);

	// do {
		// /*
		 // * Write GPIO value
		 // */
		// if (-1 == GPIOWrite(POUT, repeat % 2))
			// return(3);

		// /*
		 // * Read GPIO value
		 // */
		// printf("I'm reading %d in GPIO %d\n", GPIORead(PIN), PIN);

		// usleep(500 * 1000);
	// }
	// while (repeat--);

	// /*
	 // * Disable GPIO pins
	 // */
	// if (-1 == GPIOUnexport(POUT) || -1 == GPIOUnexport(PIN))
		// return(4);

	// return(0);
// }

void cpu_frequency_1000(void){
	FILE *fp;
	fp = popen("cpufreq-set -f 1000Mhz", "r"); //open pipe
	#ifdef VERBOSE
    if (fp == NULL) {
        fprintf(stderr, "CPU frequency to 1000Mhz failed\n" );
        
    }
	else {
		 //fprintf(stderr, "CPU frequency set to 1000Mhz\n" );
	}
	#endif
	pclose(fp);
}

void cpu_frequency_700(void){
	FILE *fp;
	fp = popen("cpufreq-set -f 700Mhz", "r"); 
	#ifdef VERBOSE
    if (fp == NULL) {
        fprintf(stderr, "CPU frequency to 700Mhz failed\n" );
        
    }
	else {
		 //fprintf(stderr, "CPU frequency set to 700Mhz\n" );
	}
	#endif
	pclose(fp);
}

void cpu_frequency_userspace_700(void){
	FILE *fp;
	fp = popen("cpufreq-set -g userspace", "r"); //open pipe
	
#ifdef VERBOSE
    if (fp == NULL) {
        fprintf(stderr, "CPU frequency governer to userspace failed\n" );
    }
	else {
		 //fprintf(stderr, "CPU frequency set to userspace\n" );
	}
	#endif
	pclose(fp);
	
	fp = popen("cpufreq-set -f 700Mhz", "r"); //open pipe
	#ifdef VERBOSE
    if (fp == NULL) {
        fprintf(stderr, "CPU frequency to 700Mhz failed\n" );
        
    }
	else {
		 //fprintf(stderr, "CPU frequency set to 700Mhz\n" );
	}
	#endif
	pclose(fp);
}
