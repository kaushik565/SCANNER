#ifndef BLUETOOTH_H
#define BLUETOOTH_H

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

#include <glib.h>
#include <gio/gio.h>
#include <errno.h>
#include <stdio.h>

#include "md5.h"
#include "autoprep.h"

int s, client;	

void device_info(int *client);
void qr_to_bluetooth(int *client);
void mac_eth0(unsigned char MAC_str[13]);
void get_lysis_heater(char* B_Set_Point,char* H_Set_Point,char* B_Set_Lysis,char* H_Set_Lysis);

void last_data_sent(int *client,char* last_run);
void qr_data_sent(int *client,char* qr_in);
			
void sw_update(int *client);
sdp_session_t *register_service(uint8_t rfcomm_channel);
void bluetooth_thread( void);
void init_bluetooth_adapter(void);

void *agent_thread( void *ptr );
void max_runid_sent(int* client);
void enable_wifi_ssh(int *client,char blutooth_sent);

#endif