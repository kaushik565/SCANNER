#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <sys/wait.h>
#include <unistd.h>
#include <wiringPi.h>
#include <wiringSerial.h>
#include <sys/stat.h>

#define DEBUG_INT_PIN 22
#define VERBOSE


int main (){
	
	//enable_wifi_ssh(0,0);
	
	//fprintf (stdout,"autoprep.log dlt error\n");
    struct stat st;           
				//fprintf (stderr,"%u\n",run_no);
	sleep(1200);
				
do {
	
	 if(stat("/SCANNER/LOGS/mxsr_bin.log",&st)==0){
		 
		if(st.st_size>1000000){  //1MB
			if( remove("/SCANNER/LOGS/mxsr_bin.log") == 0 ){
				  fprintf (stderr,"mxsr_bin.log dltd\n");
				     FILE *fp;
				   fp = fopen("/SCANNER/LOGS/mxsr_bin.log", "w");
				   fputs("...", fp);
				   fclose(fp);
					if (chmod("/SCANNER/LOGS/mxsr_bin.log", S_IRWXU | S_IRWXG | S_IRWXO)) {
							perror("chmod");
					}
			}else
			{
				  fprintf (stderr,"mxsr_bin.log dlt error\n");
			}
		}
	 }
	 sleep(2);
	 if(stat("/SCANNER/LOGS/ntp_sync.log",&st)==0){
		 
		if(st.st_size>1000000){  //1MB
			if( remove("/SCANNER/LOGS/ntp_sync.log") == 0 ){
				  fprintf (stderr,"ntp_sync.log dltd\n");
				  FILE *fp;
				   fp = fopen("/SCANNER/LOGS/ntp_sync.log", "w");
				   fputs("...", fp);
				   fclose(fp);
					if (chmod("/SCANNER/LOGS/ntp_sync.log", S_IRWXU | S_IRWXG | S_IRWXO)) {
							perror("chmod");
					}
			}else
			{
				  fprintf (stderr,"ntp_sync.log dlt error\n");
			}
		}
	 }
	sleep(2);
	 if(stat("/SCANNER/LOGS/MatrixScanner.log",&st)==0){
		 
		if(st.st_size>1000000){  //1MB
			if( remove("/SCANNER/LOGS/MatrixScanner.log") == 0 ){
				  fprintf (stderr,"MatrixScanner.log dltd\n");
				  FILE *fp;
				   fp = fopen("/SCANNER/LOGS/MatrixScanner.log", "w");
				   fputs("...", fp);
				   fclose(fp);
					if (chmod("/SCANNER/LOGS/MatrixScanner.log", S_IRWXU | S_IRWXG | S_IRWXO)) {
							perror("chmod");
					}
			}else
			{
				  fprintf (stderr,"MatrixScanner.log dlt error\n");
			}
		}
	 }	
	 sleep(3600);
	
}while(1);
}