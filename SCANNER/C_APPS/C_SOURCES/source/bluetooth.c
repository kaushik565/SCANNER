#include "autoprep.h"
#include "bluetooth.h"
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>

struct MD5Context md5c;
static char *zErrMsg = 0;
static int rc;
static char sql[1000];
static const char* data = "Callback function called";

static char file_buffer[FILE_BUFFER_SIZE];
//static char *run_no, *serial_no, *lot_no, *mfd_no, *type;
static char* file_name;
static FILE *output_file;
static char data_out[500];
static unsigned int row_no;
static unsigned int bytes_read = 0;

static sqlite3_stmt *bluetooth_statement;
GMainLoop *loop;
GDBusConnection *con;
#define AGENT_PATH  "/org/bluez/AutoPinAgent"

int  agent_thread_handle;
pthread_t agent_parent;

extern pthread_cond_t pair_condition;
volatile int pairing_ok = 0, pair_request = 0;

#define MD5_SIGNATURE_SIZE (16)
unsigned char signature [MD5_SIGNATURE_SIZE + 1] = {};
char buf[1024] = { 0 };
char buf1[1024] = { 0 };
void init_bluetooth_adapter() {
  int ctl;
  struct hci_dev_req dr;
  struct hci_dev_info di;
  if ((ctl = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI)) < 0) {
    fprintf(stderr, "Can't open HCI socket.");
  }
  di.dev_id = 0;
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
}


void run_cmd_out_socket(const char* cmd_in, int *client) {

  int c1 = 0;
  FILE *fp;
  char temp[5000] = {'\x00'};
  char c;
  fp = popen(cmd_in, "r");
  if (fp != NULL)
  {
    c = fgetc(fp);
    while (c != '\xff') {
      temp[c1] = c;
      c = fgetc(fp);
      c1++;
    }
    temp[c1] = '\x00';
  }
  else {
    strcpy(temp, "Popen failed\n");
  }
  write(*client, temp, strlen(temp));
  fprintf(stderr, "%s", temp);
  pclose(fp);
}

void network_info(int *client) {
  char data_out[500], data_in[100], cmd[600];
  strcpy(data_out, "\n\n----iwconfigresult ----\n");
  write(*client, data_out, strlen(data_out));
  run_cmd_out_socket("iwconfig", client);

  strcpy(data_out, "\n\n----ifconfig result ----\n");
  write(*client, data_out, strlen(data_out));
  run_cmd_out_socket("ifconfig", client);

  get_ip(data_in);
  sprintf(data_out, "\n\nCurrent IP:'%s\n", data_in);
  write(*client, data_out, strlen(data_out));

  strcpy(data_out, "\n---------------------------\n");
  write(*client, data_out, strlen(data_out));

  return;
}

void list_wifi_ssids(int *client) {
  char data_out[500];
  strcpy(data_out, "\n\nWifi network list\n");
  write(*client, data_out, strlen(data_out));
  run_cmd_out_socket("iwlist wlan0 scanning | grep ESSID", client);
  strcpy(data_out, "\n---------------------------\n");
  write(*client, data_out, strlen(data_out));
}

void reset_wifi_ssids(int *client) {
  char data_out[500], data_in[100], ssid[50], psk[50], cmd[600];
  strcpy(data_out, "\n\n - WiFi SSIDs reset - \n\n");
  write(*client, data_out, strlen(data_out));


  sprintf(data_out, "This will remove all saved networks. Confirm? <y=Yes/other=discard>\n");
  write(*client, data_out, strlen(data_out));

  memset(data_in, 0, sizeof(data_in));
  bytes_read = read(*client, data_in, sizeof(data_in));
  if (data_in[0] == 'y') {
    strcpy(data_out, "\nRemoving WiFi credentials\n");
    write(*client, data_out, strlen(data_out));
  }
  else {
    strcpy(data_out, "Returning to previous menu\n");
    write(*client, data_out, strlen(data_out));
    return;
  }

  strcpy(cmd, "rm /etc/wpa_supplicant/wpa_supplicant.conf");
  fprintf(stderr, "-%s-", cmd);
  run_cmd_out_socket(cmd, client);
  sleep(1);
  strcpy(cmd, "cp /etc/wpa_supplicant/wpa_supplicant.conf_bk /etc/wpa_supplicant/wpa_supplicant.conf");
  fprintf(stderr, "-%s-", cmd);
  run_cmd_out_socket(cmd, client);
  sleep(1);
  run_cmd_out_socket("wpa_cli -i wlan0 reconfigure", client);
  strcpy(data_out, "Please wait\n");
  write(*client, data_out, strlen(data_out));
  sleep(10);
  run_cmd_out_socket("iwconfig wlan0", client);
  get_ip(data_in);
  sprintf(data_out, "\n\nCurrent IP:'%s\n", data_in);
  write(*client, data_out, strlen(data_out));

  strcpy(data_out, "Returning to previous menu\n");
  write(*client, data_out, strlen(data_out));
  return;
}

void add_wifi_network(int *client) {
  char data_out[500], data_in[100], ssid[50], psk[50], cmd[600];
  strcpy(data_out, "\n\n - WiFi SETUP - \nEnter WiFi SSID:\n");
  write(*client, data_out, strlen(data_out));

  memset(ssid, 0, sizeof(ssid));
  bytes_read = read(*client, ssid, sizeof(ssid));
  if ( bytes_read < 1 || bytes_read > 49 ) {
    strcpy(data_out, "\n\nError\n");
    write(*client, data_out, strlen(data_out));
    return;
  }

  if (ssid[bytes_read - 2] == '\n' || ssid[bytes_read - 2] == '\r')ssid[bytes_read - 2] = 0;
  if (ssid[bytes_read - 1] == '\n' || ssid[bytes_read - 1] == '\r')ssid[bytes_read - 1] = 0;
  memset(psk, 0, sizeof(psk));
  strcpy(data_out, "Enter WiFi password:\n");
  write(*client, data_out, strlen(data_out));
  bytes_read = read(*client, psk, sizeof(psk));
  if ( bytes_read < 1 || bytes_read > 49 ) {
    strcpy(data_out, "\n\nError\n");
    write(*client, data_out, strlen(data_out));
    return;
  }
  if (psk[bytes_read - 2] == '\n' || psk[bytes_read - 2] == '\r')psk[bytes_read - 2] = 0;
  if (psk[bytes_read - 1] == '\n' || psk[bytes_read - 1] == '\r')psk[bytes_read - 1] = 0;


  sprintf(data_out, "SSID:'%s' \nPSK:'%s' \n", ssid, psk);
  write(*client, data_out, strlen(data_out));
  sprintf(data_out, "Confirm? <y=Yes/other=discard>\n");
  write(*client, data_out, strlen(data_out));

  memset(data_in, 0, sizeof(data_in));
  bytes_read = read(*client, data_in, sizeof(data_in));
  if (data_in[0] == 'y') {
    strcpy(data_out, "\nAdding new WiFi credentials\n");
    write(*client, data_out, strlen(data_out));
  }
  else {
    strcpy(data_out, "Returning to previous menu\n");
    write(*client, data_out, strlen(data_out));
    return;
  }
  // WifiTest1 12121212
  sprintf(cmd, "echo '\nnetwork={\n    ssid=\"%s\"\n    psk=\"%s\"\n    key_mgmt=WPA-PSK\n}'", ssid, psk);
  strcat(cmd, " | tee -a /etc/wpa_supplicant/wpa_supplicant.conf");

  /*sprintf(cmd,"\"\nnetwork={\
        ssid=\"%s\"\n\
        psk=\"%s\"\n\
        key_mgmt=WPA-PSK\n\
    }\n\" | tee -a /etc/wpa_supplicant/wpa_supplicant.conf", ssid, psk);*/
  fprintf(stderr, "-%s-", cmd);
  run_cmd_out_socket(cmd, client);
  sleep(1);
  run_cmd_out_socket("wpa_cli -i wlan0 reconfigure", client);
  strcpy(data_out, "Connecting jig to WiFi, wait for 10 seconds\n");
  write(*client, data_out, strlen(data_out));
  sleep(11);
  run_cmd_out_socket("iwconfig wlan0", client);
  get_ip(data_in);
  sprintf(data_out, "\n\nCurrent IP:'%s\n", data_in);
  write(*client, data_out, strlen(data_out));

  strcpy(data_out, "Returning to previous menu\n");
  write(*client, data_out, strlen(data_out));
  return;
}


static void int_sig(int signo)
{
  
}


void bluetooth_thread(void) {
  sleep(20);
  int bytes_read = 0;
  int port = 1;
  struct sockaddr_rc loc_addr = { 0 }, rem_addr = { 0 };
  char incomming_dev_addr[50];

 

  init_bluetooth_adapter();
  //sdp_session_t* session =
  register_service(port);
  socklen_t opt = sizeof(rem_addr);
  s = socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM);
  loc_addr.rc_family = AF_BLUETOOTH;
  loc_addr.rc_bdaddr = *BDADDR_ANY;
  loc_addr.rc_channel = (uint8_t) 1;
  bind(s, (struct sockaddr *)&loc_addr, sizeof(loc_addr));

  agent_thread_handle = pthread_create( &agent_parent, NULL, agent_thread, NULL);
  if (agent_thread_handle)
  {
    fprintf(stderr, "Error - agent pthread_create() return code: %d\n", agent_thread_handle);
  }
  listen(s, 1);
LISTEN_CLIENT: client = accept(s, (struct sockaddr *)&rem_addr, &opt);
#ifdef VERBOSE
  ba2str( &rem_addr.rc_bdaddr, incomming_dev_addr );
  fprintf(stdout, "accepted connection from %s\n", incomming_dev_addr);
#endif
  memset(buf1, 0, sizeof(buf1));
  /*if(client<0){
    #ifdef VERBOSE
    fprintf(stderr, "accepted connection error\n");
    #endif
    close(client);
    goto LISTEN_CLIENT;

    }*/
  //write(client, "O", 2); //accepted aknowledgment
  while (1) {
    memset(buf1, 0, sizeof(buf1));
    bytes_read = read(client, buf1, sizeof(buf1));
#ifdef VERBOSE
    if ( bytes_read > 0 ) {
      fprintf(stdout, "received [%s]\n", buf1);
    }
#endif
    switch (buf1[0]) {
      /*case 'Q': qr_data_sent(&client, buf1 + 1); break;
      case 'L': last_data_sent(&client, buf1 + 1); break;
      case 'R': runid_data_sent(&client, buf1 + 1); break;
      case 'I': device_info(&client); break;
      case 'M': max_runid_sent(&client); break;*/
      case 'C': write(client, "C", 1); close(client); goto LISTEN_CLIENT; break;
      case 'S': service_menu(&client); break;
      //case 'L': sent_logs(&client,buf1[1],incomming_dev_addr);
      //case 'U': commit_update(&client,buf1[1]);break;
      //case 'X': extraction_state(&client); break;
      default : write(client, "E0", 2); break;
    }
  }

  close(client);
  close(s);
  return 0;

}


setTruePrepID(int *client) {
  char data_out[500], device_id[50];
  strcpy(data_out, "\n\nEnter the Cartridge Test Jig ID\n");
  write(*client, data_out, strlen(data_out));
  memset(buf, 0, sizeof(buf));
  bytes_read = read(*client, buf, sizeof(buf));
  if ( bytes_read < 3 ) {
    strcpy(data_out, "\n\nError\n");
    write(*client, data_out, strlen(data_out));
    return;
  }
  gethostname(device_id, 49);
  FILE* fp;
  sprintf(data_out, "echo %s > /etc/hostname", buf);
  fp = popen(data_out, "r"); //open pipe
  pclose(fp);

  FILE* fp2;
  sprintf(data_out, "sed -i \"s/127.0.1.1.*%s/127.0.1.1\t%s/g\" /etc/hosts", device_id, buf);
  fp2 = popen(data_out, "r"); //open pipe
  pclose(fp2);
  memset(device_id, 0, sizeof(device_id));
  if (sethostname(buf, strlen(buf))) {

    strcpy(data_out, "\nHostname set failed\n");
    write(*client, data_out, strlen(data_out));
  }
  else {
    gethostname(device_id, 49);
    sprintf(data_out, "\nDevice ID set to %s\n", device_id);
    write(*client, data_out, strlen(data_out));
    fprintf(stderr, "Device ID changed to %s\n", device_id);
  }
}

void setDateTime(int *client)  // format like DD/MM/YY-hh/mm/ss
{
  char data_out[400];
  strcpy(data_out, "\n\nEnter date and time in DD/MM/YY-hh/mm/ss format:\n");
  write(*client, data_out, strlen(data_out));
  memset(buf, 0, sizeof(buf));
  bytes_read = read(*client, buf, sizeof(buf));
  if ( bytes_read < 16 ) {
    strcpy(data_out, "\n\nError\n");
    write(*client, data_out, strlen(data_out));
    return;
  }

  char temp[3] = {0};

  strncpy(temp, buf + 0, 2);
  unsigned short day = atoi(temp);

  strncpy(temp, buf + 3, 2);
  unsigned short month = atoi(temp);

  strncpy(temp, buf + 6, 2);
  unsigned short year = atoi(temp);

  strncpy(temp, buf + 9, 2);
  unsigned short hour = atoi(temp);
  //if(hour>=12)hour--;

  strncpy(temp, buf + 12, 2);
  unsigned short minute = atoi(temp);

  strncpy(temp, buf + 15, 2);
  unsigned short sec = atoi(temp);

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
    tm_ptr->tm_isdst = 0;
    const struct timeval tv = {mktime(tm_ptr), 0};
    settimeofday(&tv, 0);

    FILE* fp;
    fp = popen("hwclock -w", "r"); //open pipe
    if (fp == NULL) {
      strcpy(data_out, "hw clock pipe failed");
      write(*client, data_out, strlen(data_out));
    }
    else {
      while (fgets(data_out, sizeof(data_out) - 1, fp) != NULL) {
        write(*client, data_out, strlen(data_out));
      }
    }
    pclose(fp);
  }
}


void enable_wifi_ssh(int *client, char blutooth_sent) {
  //sudo systemctl disable dhcpcd.service
  FILE* fp;
  fp = popen("systemctl start dhcpcd.service", "r"); //open pipe
  if (blutooth_sent) {
    if (fp == NULL) {
      strcpy(data_out, "dhcpcd.service pipe failed");
      write(*client, data_out, strlen(data_out));

    }
    else {
      while (fgets(data_out, sizeof(data_out) - 1, fp) != NULL) {
        write(*client, data_out, strlen(data_out));
      }


    }


    strcpy(data_out, "dhcpcd.service enabled\n");
    write(*client, data_out, strlen(data_out));
  }
  pclose(fp);
  //sudo systemctl disable ssh.service
  fp = popen("systemctl start ssh.service", "r"); //open pipe
  if (blutooth_sent) {
    if (fp == NULL) {
      strcpy(data_out, "ssh.service pipe failed");
      write(*client, data_out, strlen(data_out));

    }
    else {
      while (fgets(data_out, sizeof(data_out) - 1, fp) != NULL) {
        write(*client, data_out, strlen(data_out));
      }


    }


    strcpy(data_out, "ssh.service enabled\n");
    write(*client, data_out, strlen(data_out));
  }
  pclose(fp);
  //avahi-daemon.service
  fp = popen("systemctl start avahi-daemon.service", "r"); //open pipe
  if (blutooth_sent) {
    if (fp == NULL) {
      strcpy(data_out, "avahi-daemon.service pipe failed");
      write(*client, data_out, strlen(data_out));

    }
    else {
      while (fgets(data_out, sizeof(data_out) - 1, fp) != NULL) {
        write(*client, data_out, strlen(data_out));
      }


    }


    strcpy(data_out, "avahi-daemon.service enabled\n");
    write(*client, data_out, strlen(data_out));
  }
  pclose(fp);
  //keyboard-setup.service

  fp = popen("systemctl start keyboard-setup.service", "r"); //open pipe
  if (blutooth_sent) {
    if (fp == NULL) {
      strcpy(data_out, "keyboard-setup.service pipe failed");
      write(*client, data_out, strlen(data_out));

    }
    else {
      while (fgets(data_out, sizeof(data_out) - 1, fp) != NULL) {
        write(*client, data_out, strlen(data_out));
      }

    }

    strcpy(data_out, "keyboard-setup.service enabled\n");
    write(*client, data_out, strlen(data_out));
  }
  pclose(fp);
  //raspi-config
  fp = popen("systemctl start raspi-config.service", "r"); //open pipe
  if (blutooth_sent) {
    if (fp == NULL) {
      strcpy(data_out, "raspi-config.service pipe failed");
      write(*client, data_out, strlen(data_out));

    }
    else {
      while (fgets(data_out, sizeof(data_out) - 1, fp) != NULL) {
        write(*client, data_out, strlen(data_out));
      }


    }
    strcpy(data_out, "raspi-config.service enabled\n");
    write(*client, data_out, strlen(data_out));
  }
  pclose(fp);
  //triggerhappy.service
  fp = popen("systemctl start triggerhappy.service", "r"); //open pipe
  if (blutooth_sent) {
    if (fp == NULL) {
      strcpy(data_out, "triggerhappy.service pipe failed");
      write(*client, data_out, strlen(data_out));

    }
    else {
      while (fgets(data_out, sizeof(data_out) - 1, fp) != NULL) {
        write(*client, data_out, strlen(data_out));
      }


    }
    strcpy(data_out, "triggerhappy.service enabled\n");
    write(*client, data_out, strlen(data_out));
  }
  pclose(fp);
  //wifi-country.service
  fp = popen("systemctl start wifi-country.service", "r"); //open pipe
  if (blutooth_sent) {
    if (fp == NULL) {
      strcpy(data_out, "wifi-country.service pipe failed");
      write(*client, data_out, strlen(data_out));

    }
    else {
      while (fgets(data_out, sizeof(data_out) - 1, fp) != NULL) {
        write(*client, data_out, strlen(data_out));
      }


    }
    strcpy(data_out, "wifi-country.service enabled\n");
    write(*client, data_out, strlen(data_out));
  }
  pclose(fp);
  /*
    sudo dphys-swapfile swapoff
    sudo dphys-swapfile uninstall
    sudo update-rc.d dphys-swapfile remove
    apt purge dphys-swapfile
  */


  //remove systemd-logind.service also
}


void service_menu(int *client) {
  char data_out[400], *service_pass = SERVICE_PASSWORD;
SEVICE_MENU:

  strcpy(data_out, "\r\n\r\nSERVICE MENU \r\n");
  write(*client, data_out, strlen(data_out));

  stpcpy(data_out, "\
  1. Device details\r\n\
  2. Set date and time\r\n\
  3. Enable debug services\r\n\
  4. Set Device ID\r\n\
  5. Add WiFi network\r\n\
  6. Network info\r\n\
  7. Available WiFi networks\r\n\
  8. Remove all WiFi networks\r\n\
  0. Exit\r\n");
  write(*client, data_out, strlen(data_out));
  memset(buf, 0, sizeof(buf));
  bytes_read = read(*client, buf, sizeof(buf));
  if ( bytes_read > 0 ) {
    fprintf(stderr, "received [%s]\n", buf);
  }
  switch (buf[0]) {
    case '1': device_info(client); break;
    case '2': setDateTime(client); break;
    case '3': enable_wifi_ssh(client, 1); break;
    case '4': setTruePrepID(client); break;
    case '5': add_wifi_network(client); break;
    case '6': network_info(client); break;
    case '7': list_wifi_ssids(client); break;
    case '8': reset_wifi_ssids(client); break;
    case '0': return;
    //case 'U': sw_update(client); break;
    default : write(client, "E0", 2); break;
  }

  goto SEVICE_MENU;

}

void get_ip(char* ip_out) {
  int s;
  struct ifreq ifr = {};

  s = socket(PF_INET, SOCK_DGRAM, 0);

  strncpy(ifr.ifr_name, "wlan0", sizeof(ifr.ifr_name));

  if (ioctl(s, SIOCGIFADDR, &ifr) >= 0) {
    strcpy(ip_out,
           inet_ntoa(((struct sockaddr_in *)&ifr.ifr_addr)->sin_addr));
  }
}


void mac_eth0(unsigned char MAC_str[13])
{
#define HWADDR_len 6
  int s, i;
  struct ifreq ifr;
  s = socket(AF_INET, SOCK_DGRAM, 0);
  strcpy(ifr.ifr_name, "wlan0");
  ioctl(s, SIOCGIFHWADDR, &ifr);
  for (i = 0; i < HWADDR_len; i++)
    //sprintf(&MAC_str[i*2],"%02X",((unsigned char*)ifr.ifr_hwaddr.sa_data)[i]);
    sprintf(&MAC_str[i * 2], "%02X", ((unsigned char*)ifr.ifr_hwaddr.sa_data)[i]);
  MAC_str[12] = '\0';
}

void device_info(int *client) {
  char mac[13];
  char device_id[50], data_out[1000], ip[50];

  
  gethostname(device_id, sizeof(device_id));
  
  mac_eth0(mac);
  //puts(mac);
  int s;
  struct ifreq ifr = {};

  s = socket(PF_INET, SOCK_DGRAM, 0);

  strncpy(ifr.ifr_name, "wlan0", sizeof(ifr.ifr_name));

  if (ioctl(s, SIOCGIFADDR, &ifr) >= 0) {
    strcpy(ip,
           inet_ntoa(((struct sockaddr_in *)&ifr.ifr_addr)->sin_addr));
  }


  time_t t = time(NULL);
  struct tm tm = *localtime(&t);

  sprintf(data_out, "\
    Device ID:%s\r\n\
    SBC SW Version:"SBC_VERSION"\r\n\
    MAC ID:%s\r\n\
    IP:%s\r\n\
    ", device_id, mac, ip);
  write(*client, data_out, strlen(data_out));
  sprintf(data_out, "Device Date:%d-%d-%d \r\n Device Time:%d:%d:%d\r\n", tm.tm_mday, tm.tm_mon + 1, tm.tm_year + 1900, tm.tm_hour, tm.tm_min, tm.tm_sec);
  write(*client, data_out, strlen(data_out));
}


sdp_session_t *register_service(uint8_t rfcomm_channel) {

  /* A 128-bit number used to identify this service. The words are ordered from most to least
    significant, but within each word, the octets are ordered from least to most significant.
    For example, the UUID represneted by this array is 00001101-0000-1000-8000-00805F9B34FB. (The
    hyphenation is a convention specified by the Service Discovery Protocol of the Bluetooth Core
    Specification, but is not particularly important for this program.)

    This UUID is the Bluetooth Base UUID and is commonly used for simple Bluetooth applications.
    Regardless of the UUID used, it must match the one that the Armatus Android app is searching
    for.
  */
  uint32_t svc_uuid_int[] = { 0x01110000, 0x00100000, 0x80000080, 0xFB349B5F };
  const char *service_name = "MolbioScanner";
  const char *svc_dsc = "MolbioScanner";
  const char *service_prov = "MolbioScanner";

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
#ifdef VERBOSE
  fprintf(stdout, "Registering UUID %s\n", str);
#endif
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









static void bluez_agent_method_call(GDBusConnection *conn,
                                    const gchar *sender,
                                    const gchar *path,
                                    const gchar *interface,
                                    const gchar *method,
                                    GVariant *params,
                                    GDBusMethodInvocation *invocation,
                                    void *userdata)
{
  int pass;
  int entered;
  char *opath;
  GVariant *p = g_dbus_method_invocation_get_parameters(invocation);

  g_print("Agent method call: %s.%s()\n", interface, method);
  if (!strcmp(method, "RequestPinCode")) {
    gchar *ret = NULL;
    FILE * fp;
    fp = fopen ("/SCANNER/C_APPS/bluetooth_key", "r");
    if (fp != NULL)
      printf("key file open passed\n");
    else
      printf("key file open failed\n");

    g_print("Enter pincode: ");
    errno = 0;

    fscanf(fp, "%ms", &ret);
    printf("pin code %s\n", ret);

    fclose (fp);
    g_dbus_method_invocation_return_value(invocation, g_variant_new ("(s)", ret));

    ;
  }
  else if (!strcmp(method, "DisplayPinCode")) {
    ;
  }
  else if (!strcmp(method, "RequestPasskey")) {
    //g_print("Getting the Pin from user: ");
    //fscanf(stdin, "%d", &pass);
    //g_print("\n");
    pass = 1212;
    g_dbus_method_invocation_return_value(invocation, g_variant_new("(u)", pass));
  }
  else if (!strcmp(method, "DisplayPasskey")) {
		fprintf(stderr, "pairing ok");
      g_print("pairing_ok");
      g_variant_get(params, "(ouq)", &opath, &pass, &entered);
      g_dbus_method_invocation_return_value(invocation, NULL);

  }
  else if (!strcmp(method, "RequestConfirmation")) {
	  
	
      g_print("pairing_ok");
      g_variant_get(params, "(ou)", &opath, &pass);
      g_dbus_method_invocation_return_value(invocation, NULL);

  }
  else if (!strcmp(method, "RequestAuthorization")) {
    ;
  }
  else if (!strcmp(method, "AuthorizeService")) {
    ;
  }
  else if (!strcmp(method, "Cancel")) {
    ;
  }
  else
    g_print("unknown method\n");
}

static const GDBusInterfaceVTable agent_method_table = {
  .method_call = bluez_agent_method_call,
};

int bluez_register_agent(GDBusConnection *con)
{
  GError *error = NULL;
  guint id = 0;
  GDBusNodeInfo *info = NULL;

  static const gchar bluez_agent_introspection_xml[] =
    "<node name='/org/bluez/SampleAgent'>"
    "   <interface name='org.bluez.Agent1'>"
    "       <method name='Release'>"
    "       </method>"
    "       <method name='RequestPinCode'>"
    "           <arg type='o' name='device' direction='in' />"
    "           <arg type='s' name='pincode' direction='out' />"
    "       </method>"
    "       <method name='DisplayPinCode'>"
    "           <arg type='o' name='device' direction='in' />"
    "           <arg type='s' name='pincode' direction='in' />"
    "       </method>"
    "       <method name='RequestPasskey'>"
    "           <arg type='o' name='device' direction='in' />"
    "           <arg type='u' name='passkey' direction='out' />"
    "       </method>"
    "       <method name='DisplayPasskey'>"
    "           <arg type='o' name='device' direction='in' />"
    "           <arg type='u' name='passkey' direction='in' />"
    "           <arg type='q' name='entered' direction='in' />"
    "       </method>"
    "       <method name='RequestConfirmation'>"
    "           <arg type='o' name='device' direction='in' />"
    "           <arg type='u' name='passkey' direction='in' />"
    "       </method>"
    "       <method name='RequestAuthorization'>"
    "           <arg type='o' name='device' direction='in' />"
    "       </method>"
    "       <method name='AuthorizeService'>"
    "           <arg type='o' name='device' direction='in' />"
    "           <arg type='s' name='uuid' direction='in' />"
    "       </method>"
    "       <method name='Cancel'>"
    "       </method>"
    "   </interface>"
    "</node>";

  info = g_dbus_node_info_new_for_xml(bluez_agent_introspection_xml, &error);
  if (error) {
    g_printerr("Unable to create node: %s\n", error->message);
    g_clear_error(&error);
    return 0;
  }

  id = g_dbus_connection_register_object(con,
                                         AGENT_PATH,
                                         info->interfaces[0],
                                         &agent_method_table,
                                         NULL, NULL, &error);
  g_dbus_node_info_unref(info);
  //g_dbus_connection_unregister_object(con, id);
  /* call register method in AgentManager1 interface */
  return id;
}

static int bluez_agent_call_method(const gchar *method, GVariant *param)
{
  GVariant *result;
  GError *error = NULL;

  result = g_dbus_connection_call_sync(con,
                                       "org.bluez",
                                       "/org/bluez",
                                       "org.bluez.AgentManager1",
                                       method,
                                       param,
                                       NULL,
                                       G_DBUS_CALL_FLAGS_NONE,
                                       -1,
                                       NULL,
                                       &error);
  if (error != NULL) {
    g_print("Register %s: %s\n", AGENT_PATH, error->message);
    return 1;
  }

  g_variant_unref(result);
  return 0;
}



void *agent_thread( void *ptr )
{
  int id;
  int rc;

  fprintf(stdout, "agent thread\n");



  con = g_bus_get_sync(G_BUS_TYPE_SYSTEM, NULL, NULL);
  if (con == NULL) {
    g_print("Not able to get connection to system bus\n");
    return 0;
  }

  loop = g_main_loop_new(NULL, FALSE);

  id = bluez_register_agent(con);
  if (id != 0) {

    rc = bluez_agent_call_method("RegisterAgent", g_variant_new("(os)", AGENT_PATH, "DisplayOnly"));
    if (!rc) {

      rc = bluez_agent_call_method("RequestDefaultAgent", g_variant_new("(o)", AGENT_PATH));
      if (rc) {
        bluez_agent_call_method("UnregisterAgent", g_variant_new("(o)", AGENT_PATH));

      }

      g_main_loop_run(loop);
    }
    if (rc) {
      g_print("Not able to register default autopair agent\n");

    }


  }
  g_dbus_connection_unregister_object(con, id);
  g_object_unref(con);
  return 0;
}
