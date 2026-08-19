#!/bin/bash

echo "Start Sena SerialGateway"

# cd /home/SerialGateway
# java -jar GatewaySerialListener-updated_200820_1920.jar &
# sleep 10

cd /home/PYSerialGateway
python3 pygw_main.py &
# Add 'DBUP' to allow Excel-DB sync, Add 'GPSUP' to allow GPS polling at pre-set timeframe, Add 'NOPOLL' to disable active polling
