#include <stdio.h>
#include <unistd.h>
#include <sys/socket.h>
#include <bluetooth/bluetooth.h>
#include <bluetooth/rfcomm.h>

#include <locale.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <stdio.h>
#include <errno.h>
#include <ctype.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <getopt.h>
#include <sys/param.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>

#include <bluetooth/bluetooth.h>
#include <bluetooth/hci.h>
#include <bluetooth/hci_lib.h>

#include <bluetooth/sdp.h>
#include <bluetooth/sco.h>
#include <bluetooth/sdp_lib.h>
#include <bluetooth/rfcomm.h>
#include <bluetooth/l2cap.h>

#include <sqlite3.h>

#include <sys/types.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <sys/time.h>

#include "md5.h"

struct MD5Context md5c;

#define DATABASE_PATH "/home/pi/c_qr/catridge_database.db"
#define RUN_NO_FILE "/home/pi/c_qr/run_no"
#define SERVICE_PASSWORD "autoprep"
#define SET_POINTS_FILE "/home/pi/c_qr/setpoints"

char *zErrMsg = 0;
int rc;
char sql[1000];
const char* data = "Callback function called";
#define FILE_BUFFER_SIZE 1024*1024*10
char file_buffer[FILE_BUFFER_SIZE];

bdaddr_t my_bdaddr_any = {0, 0, 0, 0, 0, 0};
bdaddr_t my_bdaddr_local = {0, 0, 0, 0xff, 0xff, 0xff};

sdp_session_t* register_service(uint8_t rfcomm_channel);

char *run_no, *serial_no, *lot_no, *mfd_no, *type;
char file_name[50];
FILE *output_file;
char data_out[100];
unsigned int row_no;

void device_info(void);
void qr_to_bluetooth(void);
void mac_eth0(unsigned char MAC_str[13]);
void get_lysis_heater(char* B_Set_Point,char* H_Set_Point,char* B_Set_Lysis,char* H_Set_Lysis);
static int callback(void *data, int argc, char **argv, char **azColName) {
    int i;
    fprintf(stderr, "%s: ", (const char*)data);

    for (i = 0; i < argc; i++) {
        fprintf(stderr, "%s = %s\n", azColName[i], argv[i] ? argv[i] : "NULL");
    }
    strcpy(file_name,argv[5]);
    fprintf(stderr, "file name: %s", file_name);
    fprintf(stderr, "\n");
    return 0;
}

static int row_id_callback(void *data, int argc, char **argv, char **azColName) {
    int i;
    fprintf(stderr, "%s: ", (const char*)data);

    for (i = 0; i < argc; i++) {
        fprintf(stderr, "%s = %s\n", azColName[i], argv[i] ? argv[i] : "NULL");
    }
    row_no = atoi(argv[0]);

    return 0;
}



void last_data_sent(char* last_run);
void qr_data_sent(char* qr_in);

    struct sockaddr_rc loc_addr = { 0 }, rem_addr = { 0 };
    char buf[1024] = { 0 };
    int s, client;
	unsigned int bytes_read=0;
	
	#define MD5_SIGNATURE_SIZE (16)
			unsigned char signature [MD5_SIGNATURE_SIZE+1]={};
			
void sw_update(void);

int main(int argc, char **argv)
{
    int ctl, i, cmd = 0;
    int port = 1;
    struct hci_dev_req dr;
    struct hci_dev_info di;
	

	sdp_session_t* session = register_service(port);
	
	socklen_t opt = sizeof(rem_addr);
	 
	if ((ctl = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI)) < 0) {
        fprintf(stderr, "Can't open HCI socket.");
    }
	
	di.dev_id =0;
    if (ioctl(ctl, HCIGETDEVINFO, (void *) &di)) {
        fprintf(stderr, "Can't get device info");
        exit(1);
    }

	if (hci_test_bit(HCI_RAW, &di.flags) &&
			!bacmp(&di.bdaddr, BDADDR_ANY)) {
		int dd = hci_open_dev(di.dev_id);
		hci_read_bd_addr(dd, &di.bdaddr, 1000);
		hci_close_dev(dd);
	}

	
	dr.dev_id = di.dev_id;
    dr.dev_opt = SCAN_PAGE | SCAN_INQUIRY;

    if (ioctl(ctl, HCISETSCAN, (unsigned long) &dr) < 0) {
        fprintf(stderr, "Can't set scan mode on hci%d: %s (%d)\n",
                dr.dev_id, strerror(errno), errno);
        exit(1);
    }

    

    // allocate socket
    s = socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM);

    // bind socket to port 1 of the first available
    // local bluetooth adapter
    loc_addr.rc_family = AF_BLUETOOTH;
    loc_addr.rc_bdaddr = *BDADDR_ANY;
    loc_addr.rc_channel = (uint8_t) 1;
    bind(s, (struct sockaddr *)&loc_addr, sizeof(loc_addr));

    // put socket into listening mode
    listen(s, 1);

    // accept one connection
    LISTEN_CLIENT:client = accept(s, (struct sockaddr *)&rem_addr, &opt);

    ba2str( &rem_addr.rc_bdaddr, buf );
    fprintf(stderr, "accepted connection from %s\n", buf);
    memset(buf, 0, sizeof(buf));

    //write(client, "O", 2); //accepted aknowledgment

	while(1){	
		memset(buf, 0, sizeof(buf));
		bytes_read = read(client, buf, sizeof(buf));
		if ( bytes_read > 0 ) {
			fprintf(stderr, "received [%s]\n", buf);
		}
		switch (buf[0]){
			case 'Q': qr_data_sent(buf+1);break;
			case 'L': last_data_sent(buf+1);break;
			case 'I': device_info();break;
			case 'D': qr_to_bluetooth();break;
			case 'C': write(client, "C", 1);close(client);goto LISTEN_CLIENT;break;
			//case 'U': sw_update(); break;
			default : write(client, "E0", 2);break;
		}
	
	}

    close(client);
    close(s);
    return 0;
}

void setDateTime(char* dataStr)  // format like DD/MM/YY-hh/mm/ss
{
  char buf[3] = {0};

  strncpy(buf, dataStr + 0, 2);
  unsigned short day = atoi(buf);

  strncpy(buf, dataStr + 3, 2);
  unsigned short month = atoi(buf);

  strncpy(buf, dataStr + 6, 2);
  unsigned short year = atoi(buf);

  strncpy(buf, dataStr + 9, 2);
  unsigned short hour = atoi(buf);

  strncpy(buf, dataStr + 12, 2);
  unsigned short minute = atoi(buf);

  strncpy(buf, dataStr + 15, 2);
  unsigned short sec = atoi(buf);

  time_t mytime = time(0);
  struct tm* tm_ptr = localtime(&mytime);

  if (tm_ptr)
  {
    tm_ptr->tm_mon  = month - 1;
    tm_ptr->tm_mday = day;
    tm_ptr->tm_year = year + (2000 - 1900);

    tm_ptr->tm_sec = sec;    // Seconds
    tm_ptr->tm_min = minute;    // Minutes
    tm_ptr->tm_hour = hour;   // Hours

    const struct timeval tv = {mktime(tm_ptr), 0};
    settimeofday(&tv, 0);
  }
}

void get_lysis_heater(char* B_Set_Point,char* H_Set_Point,char* B_Set_Lysis,char* H_Set_Lysis){
	FILE * set_point_file = fopen(SET_POINTS_FILE, "r");
	//fscanf(set_point_file, "%s\n%s\n%s\n%s\n", B_Set_Point, H_Set_Point, B_Set_Lysis, H_Set_Lysis);
	
	fgets(B_Set_Point,3,set_point_file);
	fgets(H_Set_Point,3,set_point_file);
	fgets(B_Set_Lysis,3,set_point_file);
	fgets(H_Set_Lysis,3,set_point_file);
	
	fclose(set_point_file);
}

void set_lysis_heater(void){
	char data_out[400],B_Set_Point[3],H_Set_Point[3],B_Set_Lysis[3],H_Set_Lysis[3] ;
	
	memset(buf, 0, sizeof(buf));
	sprintf(data_out,"\r\nEnter 'B_Set Point:'\r\n");
	write(client, data_out, strlen(data_out));
	bytes_read = read(client, buf, sizeof(buf));
	if ( bytes_read > 0 ) {
		fprintf(stderr, "received [%s]\n", buf);
	}
	B_Set_Point[0]=buf[0];
	B_Set_Point[1]=buf[1];
	B_Set_Point[2]=0;

	memset(buf, 0, sizeof(buf));
	sprintf(data_out,"\r\nEnter 'H_Set Point:'\r\n");
	write(client, data_out, strlen(data_out));
	bytes_read = read(client, buf, sizeof(buf));
	if ( bytes_read > 0 ) {
		fprintf(stderr, "received [%s]\n", buf);
	}
	H_Set_Point[0]=buf[0];
	H_Set_Point[1]=buf[1];
	H_Set_Point[2]=0;

	memset(buf, 0, sizeof(buf));
	sprintf(data_out,"\r\nEnter 'B_Set Lysis:'\r\n");
	write(client, data_out, strlen(data_out));
	bytes_read = read(client, buf, sizeof(buf));
	if ( bytes_read > 0 ) {
		fprintf(stderr, "received [%s]\n", buf);
	}
	B_Set_Lysis[0]=buf[0];
	B_Set_Lysis[1]=buf[1];
	B_Set_Lysis[2]=0;

	memset(buf, 0, sizeof(buf));	
	sprintf(data_out,"\r\nEnter 'H_Set Lysis:'\r\n");
	write(client, data_out, strlen(data_out));
	bytes_read = read(client, buf, sizeof(buf));
	if ( bytes_read > 0 ) {
		fprintf(stderr, "received [%s]\n", buf);
	}
	H_Set_Lysis[0]=buf[0];
	H_Set_Lysis[1]=buf[1];
	H_Set_Lysis[2]=0;
	
	sprintf(data_out,"\r\nEntered values are:\r\n\
	\t - B_Set_Point=%s\r\n\
	\t - H_Set_Point=%s\r\n\
	\t - B_Set_Lysis=%s\r\n\
	\t - H_Set_Lysis=%s\r\n\
	Confirm? ('Y'=yes/'N'=no (Return to Service Menu))", B_Set_Point,H_Set_Point,B_Set_Lysis,H_Set_Lysis);
	write(client, data_out, strlen(data_out));
	bytes_read = read(client, buf, sizeof(buf));
	if ( bytes_read > 0 ) {
		fprintf(stderr, "received [%s]\n", buf);
	}
	if(buf[0]=='Y'){
		FILE * set_point_file = fopen(SET_POINTS_FILE, "w");
		char B_Set_Point_in[3],H_Set_Point_in[3],B_Set_Lysis_in[3],H_Set_Lysis_in[3] ;
		fprintf(set_point_file, "%s\n%s\n%s\n%s\n", B_Set_Point, H_Set_Point, B_Set_Lysis, H_Set_Lysis);
		fclose(set_point_file);
		sprintf(data_out,"Values saved.\r\n");
		write(client, data_out, strlen(data_out));
		get_lysis_heater(B_Set_Point_in,H_Set_Point_in,B_Set_Lysis_in,H_Set_Lysis_in);
		sprintf(data_out,"\r\nNew setpoints: \r\n\
		\t - B_Set_Point=%s\r\n\
		\t - H_Set_Point=%s\r\n\
		\t - B_Set_Lysis=%s\r\n\
		\t - H_Set_Lysis=%s\r\n\
		",B_Set_Point_in,H_Set_Point_in,B_Set_Lysis_in,H_Set_Lysis_in);
		write(client, data_out, strlen(data_out));
		return;
	}
	else if(buf[0]=='N'){
		return;
	}
	else {
		sprintf(data_out,"ERROR: Invalid input\r\n");
		write(client, data_out, strlen(data_out));
	}
}

void service_menu(void){
	char data_out[400], *service_pass=SERVICE_PASSWORD;
SEVICE_MENU:sprintf(data_out,"\r\n\r\nSERVICE MENU \r\n");
	write(client, data_out, strlen(data_out));
	
	sprintf(data_out,"\
	1. Device details\r\n\
	2. Set date and time\r\n\
	3. Set Heater and Lysis values\r\n\
	4. Set Device ID\r\n");
	write(client, data_out, strlen(data_out));
	memset(buf, 0, sizeof(buf));
		bytes_read = read(client, buf, sizeof(buf));
		if ( bytes_read > 0 ) {
			fprintf(stderr, "received [%s]\n", buf);
		}
	switch (buf[0]){
			case '1': device_info();break;
			case '2': last_data_sent(buf+1);break;
			case '3': device_info();break;
			case '4': service_menu();break;
			case '5': write(client, "C", 1);close(client);break;
			//case 'U': sw_update(); break;
			default : write(client, "E0", 2);break;
		}
		
		goto SEVICE_MENU;
	
}

void mac_eth0(unsigned char MAC_str[13])
{
    #define HWADDR_len 6
    int s,i;
    struct ifreq ifr;
    s = socket(AF_INET, SOCK_DGRAM, 0);
    strcpy(ifr.ifr_name, "wlan0");
    ioctl(s, SIOCGIFHWADDR, &ifr);
    for (i=0; i<HWADDR_len; i++)
        sprintf(&MAC_str[i*2],"%02X",((unsigned char*)ifr.ifr_hwaddr.sa_data)[i]);
    MAC_str[12]='\0';
}

void device_info(void){
	unsigned char mac[13];
	char device_id[50], data_out[200];
	unsigned int run_no;
	FILE *run_no_file;
	gethostname(device_id,49);
    mac_eth0(mac);
	
    puts(mac);
	
	
	run_no_file = fopen(RUN_NO_FILE, "r");
	
        fscanf(run_no_file, "%u", &run_no);
        fprintf(stderr, "Total runs: %u\n", run_no );
        fclose(run_no_file);
		sprintf(data_out, "%s-%s-%u\n",device_id,mac,run_no);
		write(client, data_out, strlen(data_out));	
		
}
/*
void sw_update(void){
	unsigned long file_buffer_pos=0;
	unsigned char signature_in [MD5_SIGNATURE_SIZE+1]={};
	
	bytes_read = read(client, file_buffer, sizeof(file_buffer));
	MD5Init(&md5c);
	MD5Update (&md5c, file_buffer, bytes_read);
	MD5Final (signature, &md5c);
	fprintf(stderr, "MD5 Signature calculated: %s\n", signature);
	
	bytes_read = read(client, signature_in, sizeof(signature_in));
	fprintf(stderr, "MD5 Signature received: %s\n", signature_in);
	
	if(strcmp(signature_in,signature)){
		fprintf(stderr, "MD5 Signatures not matching\n");
	}
	else{
		fprintf(stderr, "MD5 Signatures matched\n");
	}
	FILE *output_archive;
	output_archive = fopen("abc.zip", "w");
	
	if(file_buffer_pos==fwrite ( file_buffer, 1, file_buffer_pos, output_archive)) {
        printf ("\n File write successfull, %u characters written \n", file_buffer_pos) ;
    }
    else {
        printf ("\n File write failed, %u characters written \n", file_buffer_pos) ;
    }
    fclose(output_archive);
}
*/
void qr_data_sent(char* qr_in){
			sqlite3 *db;
			fprintf(stderr, "QR received:%s\n", qr_in);
			/*bytes_read = read(client, buf, sizeof(buf));
			if ( bytes_read > 0 ) {
				fprintf(stderr, "received [%s] \n", buf);
			}*/

			L1:rc = sqlite3_open(DATABASE_PATH, &db);

			if ( rc ) {
				fprintf(stderr, "Can't open database: %s\n", sqlite3_errmsg(db));
				sleep(0.5);
				goto L1;
			} else {
				fprintf(stderr, "Opened database successfully\n");
			}

			sprintf(sql, "SELECT * FROM catridge WHERE SERIAL_NO = '%s'", qr_in);

			rc = sqlite3_exec(db, sql, callback, (void*)data, &zErrMsg);

			if ( rc != SQLITE_OK ) {
				fprintf(stderr, "SQL error: %s\n", zErrMsg);
				sqlite3_free(zErrMsg);
			} else {
				fprintf(stdout, "Operation done successfully\n");
				fprintf(stdout, "Filename: %s \n",file_name);
			}
			sqlite3_close(db);
			if(file_name[0]==0){
				write(client, "E1", 2);
				return;
			}
			output_file = fopen(file_name, "r");
			if(output_file){
				fprintf(stdout, "File %s opened successfully\n",file_name);
			}
			else {
				fprintf(stdout, "File '%s' open failed\n",file_name);
				return;
			}

			fseek(output_file , 0, SEEK_END);
			long fsize = ftell(output_file);
			fseek(output_file , 0, SEEK_SET);  //same as rewind(f);
			fread(file_buffer, fsize, 1, output_file );
			fclose(output_file);
			sprintf(data_out, "%u\n", fsize);
			fprintf(stderr, "file size: %s\n", data_out);
			write(client, data_out, strlen(data_out));
			//fprintf(stderr, "file data: %s\n", file_buffer);
			write(client, file_buffer, fsize);
			write(client, "\n", 1);
			MD5Init(&md5c);
			MD5Update (&md5c, file_buffer, fsize);
			MD5Final (signature, &md5c);
			fprintf(stderr, "MD5 Signature: %s\n", signature);
			write(client, signature, MD5_SIGNATURE_SIZE);
			write(client, "\n", 1);
			memset(file_name,0,sizeof(file_name));
}


void last_data_sent(char* last_run){	
			sqlite3 *db;
			fprintf(stderr, "Last run received:%s\n", last_run);
			/*bytes_read = read(client, buf, sizeof(buf));
			if ( bytes_read > 0 ) {
				fprintf(stderr, "received [%s] \n", buf);
			}*/

			
			L2:rc = sqlite3_open(DATABASE_PATH, &db);

			if ( rc ) {
				fprintf(stderr, "Can't open database: %s\n", sqlite3_errmsg(db));
				sleep(0.5);
				goto L2;
			} else {
				fprintf(stderr, "Opened database successfully\n");
			}
		
			rc = sqlite3_exec(db, "SELECT  max(rowid) FROM catridge", row_id_callback, (void*)data, &zErrMsg);

			if ( rc != SQLITE_OK ) {
				fprintf(stderr, "SQL max row id error: %s\n", zErrMsg);
				sqlite3_free(zErrMsg);
			} else {
				fprintf(stdout, "Operation done successfully\n");
			}
			
			fprintf(stderr, "Max database number:%d\n", row_no);
			unsigned int max_row_no=row_no;
			
			rc = sqlite3_exec(db, "SELECT  min(rowid) FROM catridge", row_id_callback, (void*)data, &zErrMsg);

			if ( rc != SQLITE_OK ) {
				fprintf(stderr, "SQL min row id error: %s\n", zErrMsg);
				sqlite3_free(zErrMsg);
			} else {
				fprintf(stdout, "Operation done successfully\n");
			}
			fprintf(stderr, "Min database number:%d\n", row_no);
			unsigned int min_row_no=row_no;
			
			unsigned int number_in=atoi(last_run);
			//fprintf(stderr, "Max database number:%d\n", number_in);
			if(max_row_no>=number_in){
				fprintf(stdout, "Input number accepted\n");
			}
			else{
				fprintf(stdout, "Input number rejected\n");
				write(client, "E2", 2);
				return;
				
			}
			
			unsigned int target_row_no=max_row_no-number_in;
			fprintf(stderr, "Target database number:%d\n", target_row_no);
			if(min_row_no<=target_row_no){
				fprintf(stdout, "Input number accepted\n");
			}
			else{
				fprintf(stdout, "Input number rejected\n");
				write(client, "E3", 2);
				return;
				
			}
			
			
			sprintf(sql, "SELECT * FROM catridge WHERE rowid = '%d'", target_row_no);

			rc = sqlite3_exec(db, sql, callback, (void*)data, &zErrMsg);

			if ( rc != SQLITE_OK ) {
				fprintf(stderr, "SQL error: %s\n", zErrMsg);
				sqlite3_free(zErrMsg);
			} else {
				fprintf(stdout, "Operation done successfully\n");
			}
			sqlite3_close(db);
			if(file_name[0]==0){
				write(client, "E4", 2);
				return;
			}
			output_file = fopen(file_name, "r");
			if(output_file){
				fprintf(stdout, "File %s opened successfully\n",file_name);
				
			}
			else {
				fprintf(stdout, "File '%s' open failed\n",file_name);
				return;
			}

			fseek(output_file , 0, SEEK_END);
			long fsize = ftell(output_file);
			fseek(output_file , 0, SEEK_SET);  //same as rewind(f);
			fread(file_buffer, fsize, 1, output_file );
			fclose(output_file);
			sprintf(data_out, "%u\n", fsize);
			fprintf(stderr, "file size: %s\n", data_out);
			write(client, data_out, strlen(data_out));
			//fprintf(stderr, "file data: %s\n", file_buffer);
			write(client, file_buffer, fsize);
			write(client, "\n", 1);
			MD5Init(&md5c);
			MD5Update (&md5c, file_buffer, fsize);
			MD5Final (signature, &md5c);
			fprintf(stderr, "MD5 Signature: %s\n", signature);
			write(client, signature, MD5_SIGNATURE_SIZE);
			write(client, "\n", 1);
			memset(file_name,0,sizeof(file_name));
}


sdp_session_t *register_service(uint8_t rfcomm_channel) {

    /* A 128-bit number used to identify this service. The words are ordered from most to least
    * significant, but within each word, the octets are ordered from least to most significant.
    * For example, the UUID represneted by this array is 00001101-0000-1000-8000-00805F9B34FB. (The
    * hyphenation is a convention specified by the Service Discovery Protocol of the Bluetooth Core
    * Specification, but is not particularly important for this program.)
    *
    * This UUID is the Bluetooth Base UUID and is commonly used for simple Bluetooth applications.
    * Regardless of the UUID used, it must match the one that the Armatus Android app is searching
    * for.
    */
    uint32_t svc_uuid_int[] = { 0x01110000, 0x00100000, 0x80000080, 0xFB349B5F };
    const char *service_name = "Autoprep";
    const char *svc_dsc = "Autoprep";
    const char *service_prov = "Autoprep";

    uuid_t root_uuid, l2cap_uuid, rfcomm_uuid, svc_uuid,
           svc_class_uuid;
    sdp_list_t *l2cap_list = 0,
                *rfcomm_list = 0,
                 *root_list = 0,
                  *proto_list = 0,
                   *access_proto_list = 0,
                    *svc_class_list = 0,
                     *profile_list = 0;
    sdp_data_t *channel = 0;
    sdp_profile_desc_t profile;
    sdp_record_t record = { 0 };
    sdp_session_t *session = 0;

    // set the general service ID
    sdp_uuid128_create(&svc_uuid, &svc_uuid_int);
    sdp_set_service_id(&record, svc_uuid);

    char str[256] = "";
    sdp_uuid2strn(&svc_uuid, str, 256);
    fprintf(stderr, "Registering UUID % s\n", str);

    // set the service class
    sdp_uuid16_create(&svc_class_uuid, SERIAL_PORT_SVCLASS_ID);
    svc_class_list = sdp_list_append(0, &svc_class_uuid);
    sdp_set_service_classes(&record, svc_class_list);

    // set the Bluetooth profile information
    sdp_uuid16_create(&profile.uuid, SERIAL_PORT_PROFILE_ID);
    profile.version = 0x0100;
    profile_list = sdp_list_append(0, &profile);
    sdp_set_profile_descs(&record, profile_list);

    // make the service record publicly browsable
    sdp_uuid16_create(&root_uuid, PUBLIC_BROWSE_GROUP);
    root_list = sdp_list_append(0, &root_uuid);
    sdp_set_browse_groups(&record, root_list);

    // set l2cap information
    sdp_uuid16_create(&l2cap_uuid, L2CAP_UUID);
    l2cap_list = sdp_list_append(0, &l2cap_uuid);
    proto_list = sdp_list_append(0, l2cap_list);

    // register the RFCOMM channel for RFCOMM sockets
    sdp_uuid16_create(&rfcomm_uuid, RFCOMM_UUID);
    channel = sdp_data_alloc(SDP_UINT8, &rfcomm_channel);
    rfcomm_list = sdp_list_append(0, &rfcomm_uuid);
    sdp_list_append(rfcomm_list, channel);
    sdp_list_append(proto_list, rfcomm_list);

    access_proto_list = sdp_list_append(0, proto_list);
    sdp_set_access_protos(&record, access_proto_list);

    // set the name, provider, and description
    sdp_set_info_attr(&record, service_name, service_prov, svc_dsc);

    // connect to the local SDP server, register the service record,
    // and disconnect
    session = sdp_connect(BDADDR_ANY, BDADDR_LOCAL, SDP_RETRY_IF_BUSY);
    sdp_record_register(session, &record, 0);

    // cleanup
    sdp_data_free(channel);
    sdp_list_free(l2cap_list, 0);
    sdp_list_free(rfcomm_list, 0);
    sdp_list_free(root_list, 0);
    sdp_list_free(access_proto_list, 0);
    sdp_list_free(svc_class_list, 0);
    sdp_list_free(profile_list, 0);

    return session;
}


void qr_to_bluetooth(void){
	FILE* fp;
	char out[500], data_out[200];
	if (0 == access("bimage.jpg", 0)) {
            //fp = popen("rm ./image.jpg", "w");
            if (remove("bimage.jpg") == 0) {
                fprintf(stderr, "old image deletion failed\n" );
				
            }
            else {
                fprintf(stderr, "old image deleted\n" );
            }
            //pclose(fp);
        }
	
		  /* Open the command for reading. */
 		 fp = popen("fswebcam -d /dev/video0 -s brightness=60% -s Sharpness=60% --no-banner --delay 1 --skip 5 --frames 5 -r 640x480 --jpeg 95 bimage.jpg", "r");
		  if (fp == NULL) {
		    printf("FSWebCam command failed\n" );
			sprintf(data_out,"ERROR: FSWebCam command failed\r\n");
			write(client, data_out, strlen(data_out));
		    exit(1);
 		 }
 		 /* Read the output a line at a time - output it. */
 		 while (fgets(out, sizeof(out)-1, fp) != NULL) {
 		   printf("%s", out);
 		 }
 		 /* close */
 		 pclose(fp);
		 if (0 == access("bimage.jpg", 0)) {
            fprintf(stderr, "Image capture ok\n" );
			sprintf(data_out,"Image capture ok\r\n");
			write(client, data_out, strlen(data_out));
        }
        else {
            fprintf(stderr, "Image capture failed\n" );
			sprintf(data_out,"ERROR: Image capture failed\r\n");
		write(client, data_out, strlen(data_out));
            return ;
        }

 		 fp = popen("/TRUEPREP/zxing --try-harder bimage.jpg", "r");
  		if (fp == NULL) {
  		  printf("Zxing command failed\n" );
		  sprintf(data_out,"ERROR: Zxing command failed\r\n");
		write(client, data_out, strlen(data_out));
		  
		  
   		 exit(1);
  		}
  		printf ("**** QR VALUE****");
  		write(client,"\n\r",2); 
		write(client,"\n\r",2); 
 		 /* Read the output a line at a time - output it. */
 		 while (fgets(out, sizeof(out)-1, fp) != NULL) {
  		  	printf("%s", out);
			write(client,out,strlen(out)); 
			write(client,"\r",1); 
  		}
  		/* close */
  		pclose(fp);

}		



/*
sdp_session_t* register_service(uint8_t rfcomm_channel)
{
// Adapted from http://www.btessentials.com/examples/bluez/sdp-register.c
uint32_t svc_uuid_int[] = {   0x01110000, 0x00100000, 0x80000080, 0xFB349B5F };
const char *service_name = "Roto - Rooter Data Router";
const char *svc_dsc = "An experimental plumbing router";
const char *service_prov = "Roto - Rooter";

uuid_t root_uuid, l2cap_uuid, rfcomm_uuid, svc_uuid, svc_class_uuid;
sdp_list_t *l2cap_list = 0,
*rfcomm_list = 0,
*root_list = 0,
*proto_list = 0,
*access_proto_list = 0,
*svc_class_list = 0,
*profile_list = 0;
sdp_data_t *channel = 0;
sdp_profile_desc_t profile;
sdp_record_t record = { 0 };
sdp_session_t *session = 0;

// set the general service ID
sdp_uuid128_create( &svc_uuid, &svc_uuid_int );
sdp_set_service_id( &record, svc_uuid );

char str[256] = {0};
sdp_uuid2strn(&svc_uuid, str, 256);


fprintf(stderr, "Registering UUID % s\n", str);

// set the service class
sdp_uuid16_create(&svc_class_uuid, SERIAL_PORT_SVCLASS_ID);
svc_class_list = sdp_list_append(0, &svc_class_uuid);
sdp_set_service_classes(&record, svc_class_list);

// set the Bluetooth profile information
sdp_uuid16_create(&profile.uuid, SERIAL_PORT_PROFILE_ID);
profile.version = 0x0100;
profile_list = sdp_list_append(0, &profile);
sdp_set_profile_descs(&record, profile_list);

// make the service record publicly browsable
sdp_uuid16_create(&root_uuid, PUBLIC_BROWSE_GROUP);
root_list = sdp_list_append(0, &root_uuid);
sdp_set_browse_groups( &record, root_list );

// set l2cap information
sdp_uuid16_create(&l2cap_uuid, L2CAP_UUID);
l2cap_list = sdp_list_append( 0, &l2cap_uuid );
proto_list = sdp_list_append( 0, l2cap_list );

// register the RFCOMM channel for RFCOMM sockets
sdp_uuid16_create(&rfcomm_uuid, RFCOMM_UUID);
channel = sdp_data_alloc(SDP_UINT8, &rfcomm_channel);
rfcomm_list = sdp_list_append( 0, &rfcomm_uuid );
sdp_list_append( rfcomm_list, channel );
sdp_list_append( proto_list, rfcomm_list );

access_proto_list = sdp_list_append( 0, proto_list );
sdp_set_access_protos( &record, access_proto_list );

// set the name, provider, and description
sdp_set_info_attr(&record, service_name, service_prov, svc_dsc);

// connect to the local SDP server, register the service record,
// and disconnect
session = sdp_connect(&my_bdaddr_any, &my_bdaddr_local, SDP_RETRY_IF_BUSY);

sdp_record_register(session, &record, 0);

// cleanup
sdp_data_free( channel );
sdp_list_free( l2cap_list, 0 );
sdp_list_free( rfcomm_list, 0 );
sdp_list_free( root_list, 0 );
sdp_list_free( access_proto_list, 0 );
sdp_list_free( svc_class_list, 0 );
sdp_list_free( profile_list, 0 );

return session;
}
*/
