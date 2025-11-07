#!/bin/bash

/SCANNER/C_APPS/helper 2>> /SCANNER/LOGS/helper.log &
sleep 1
/SCANNER/C_APPS/ntp_sync  2>> /SCANNER/LOGS/ntp_sync.log &
sleep 1
/SCANNER/C_APPS/mxsr_bin  2>> /SCANNER/LOGS/mxsr_bin.log &
sleep 1
python3 /SCANNER/scannerclient.py
while true
do
	sleep infinity 

done
#/TRUEPREP/agent &>> /TRUEPREP/agent.log &
#/TRUEPREP/ble &>> /TRUEPREP/ble.log &
#/TRUEPREP/qr2 &>> /TRUEPREP/qr.log &
