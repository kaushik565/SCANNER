
 //gcc main.c -o ntpClient.out

#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <time.h>
#include <sys/time.h>



int ntp_sync(void){
	
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
    fprintf (stderr,"ERROR opening socket" );
	return 1;
  }
  server = gethostbyname( host_name ); // Convert URL to IP.
  if ( server == NULL ){
    fprintf (stderr, "ERROR, no such host" );
	return 1;
  }
   // Zero out the server address structure.
  bzero( ( char* ) &serv_addr, sizeof( serv_addr ) );
  serv_addr.sin_family = AF_INET;
  // Copy the server's IP address to the server address structure.
  bcopy( ( char* )server->h_addr, ( char* ) &serv_addr.sin_addr.s_addr, server->h_length );
  // Convert the port number integer to network big-endian style and save it to the server address structure.
  serv_addr.sin_port = htons( portno );
  // Call up the server using its IP address and port number.
  if ( connect( sockfd, ( struct sockaddr * ) &serv_addr, sizeof( serv_addr) ) < 0 ){
    fprintf (stderr,"ERROR connecting" );
	return 1;
  }
 
  // Send it the NTP packet it wants. If n == -1, it failed.
  n = write( sockfd, ( char* ) &packet, sizeof( ntp_packet ) );
  if ( n < 0 ){
    fprintf (stderr, "ERROR writing to socket" );
	return 1;
  }
   
  // Wait and receive the packet back from the server. If n == -1, it failed.
  n = read( sockfd, ( char* ) &packet, sizeof( ntp_packet ) );
  if ( n < 0 ){
    fprintf (stderr, "ERROR reading from socket" );
	return 1;
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
  time_t txTm = ( time_t ) ( (packet.txTm_s - 2208988800ull )+30); //for compansating network travel
  // Print the time we got from the server, accounting for local timezone and conversion from UTC time.  
  printf( "NTP:%s", ctime( ( const time_t* ) &txTm ) );
  struct tm* tm_ptr = localtime(&txTm);
  int year= tm_ptr->tm_year + 1900; 
  if((year>2020)&&(year<2039)){
		const struct timeval tv = {mktime(tm_ptr), 0};
		settimeofday(&tv, 0);
		FILE* fp;
		sleep(1);
		fp = popen("hwclock -w", "r"); //open pipe
		if (fp == NULL) {
		  fprintf (stderr, "hw clock pipe failed");
		}
		pclose(fp);
		sleep(10);
		return 0;
  }
  else {
	 fprintf (stderr,"Error ntp year %d\n",year); //11-11-11-10-10-10
  }
  return 1;
	
}



int main( int argc, char* argv[ ] )
{
sleep(5);
	if(ntp_sync()){
		sleep(10);
		if(ntp_sync()){
			sleep(20);
			if(ntp_sync()){
				sleep(60);
				if(ntp_sync()){
					sleep(120);
					ntp_sync();
					while(ntp_sync()){
						sleep(300);
					}
				}
			}
		}
	}

  sleep(10);
  exit(0);
}