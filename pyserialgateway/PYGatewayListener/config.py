#! /usr/bin/python3
'''
Startup argument parsing and external configuration loading for the gateway listener.

This module is unchanged in *logic* from the original single-file script -
it just gathers the bits that used to sit at the top and in the middle of
PYGatewayListener.py (argument parsing, the pygw_conf-derived settings, and
the encrypted rest_location/auth_key/cert bundle loading) into one place.

Every other module in this package imports the values it needs from here,
the same way they used to read them as bare module-level globals when
everything lived in one file.
'''
import argparse

desp_parser = argparse.ArgumentParser(description='Process house for Serial data in gateways.')
desp_parser.add_argument('test_gps_flag', metavar='GPSUP', type=str, nargs='?', help='Enable GPS node mapping function.')
desp_parser.add_argument('test_db_refresh_flag', metavar='DBUP', type=str, nargs='?', help='Enable local DB refresh function.')
desp_parser.add_argument('test_demo_flag', metavar='DEMOUP', type=str, nargs='?', help='Enable non-recovery static demo mode.')
desp_parser.add_argument('test_nopoll_flag', metavar='NOPOLL', type=str, nargs='?', help='Disable active data polling feature.')
desp_parser.add_argument('test_noselmos_flag', metavar='NOSELMOS', type=str, nargs='?', help='Disable all data sending features to main server.')
desp_parser.add_argument('test_noauth_flag', metavar='NOAUTH', type=str, nargs='?', help='Disable \'level 1 security feature\'.')
desp_parser.add_argument('test_uptest_flag', metavar='TESTUP', type=str, nargs='?', help='Redirect data to only backup server.')
args = desp_parser.parse_args()

import sys, os
import zipfile
import cryptography.fernet as fcrypto
import psutil
try:
    import pygw_conf
except:
    import pyserialgateway.config_PYproperties as pygw_conf
import pyserialgateway

location_mod = []
location_mod += pyserialgateway.__path__
obs_instance = [str(p.info['pid']) for p in psutil.process_iter(attrs=['pid','name','cmdline']) if p.info['cmdline'] and str(sys.argv[0]) in p.info['cmdline']]

'''[External configuration file user-defined variables]'''
file_pathname = str(os.path.abspath(os.path.dirname(sys.argv[0])))
updating_database_localpath = file_pathname + '/' + str(pygw_conf.localDBpath)
problemlogpath = file_pathname + '/' + str(pygw_conf.problemlogpath)
logfilepath = file_pathname + '/' + str(pygw_conf.logfilepath)
maplogpath = file_pathname + '/' + str(pygw_conf.maplogpath)
cycletime = pygw_conf.cycletime
pollinggap = pygw_conf.pollinggap
msgID = pygw_conf.msgID
msgID_vers = pygw_conf.msgID_vers
active_time = pygw_conf.active_time
GPS_active_time = pygw_conf.GPS_poll_time
inactive_time = pygw_conf.inactive_time
LM_active_time = pygw_conf.LM_active_time
node_off_time = pygw_conf.node_off_time
aggressive_poll_duration_mins = pygw_conf.aggressive_poll_duration_mins
off_state_wattage = pygw_conf.minimum_power
max_msgID_count = pygw_conf.max_msgID_count
MQTT_topic_header = pygw_conf.topic_header
try:
    if obs_instance.index(str(os.getpid())) == 0:
        MQTT_client_ID = pygw_conf.client_ID
    else:
        MQTT_client_ID = pygw_conf.client_ID_2
except:
    MQTT_client_ID = pygw_conf.client_ID
first_GW_data = pygw_conf.first_GW_data
second_GW_data = pygw_conf.second_GW_data
GPS_style1 = pygw_conf.GPS_style1
GPS_style2 = pygw_conf.GPS_style2
GPS_style3 = pygw_conf.GPS_style3
test_align_flag = pygw_conf.test_align_flag
cert_codename = pygw_conf.cert_codename

'''[External control variables]'''
start_marker = int(active_time[0:2])*60 + int(active_time[3:5])
GPS_start_marker = int(GPS_active_time[0:2])*60 + int(GPS_active_time[3:5])
end_marker = int(inactive_time[0:2])*60 + int(inactive_time[3:5])
LM_start_marker = int(LM_active_time[0:2])*60 + int(LM_active_time[3:5])
node_end_marker = int(node_off_time[0:2])*60 + int(node_off_time[3:5])
if start_marker > end_marker:
    between_flag = 0
elif end_marker > start_marker:
    between_flag = 1
else:
    between_flag = 2
if GPS_start_marker > end_marker:
    GPS_between_flag = 0
elif end_marker > GPS_start_marker:
    GPS_between_flag = 1
else:
    GPS_between_flag = 2
if LM_start_marker > end_marker:
    LM_between_flag = 0
elif end_marker > LM_start_marker:
    LM_between_flag = 1
else:
    LM_between_flag = 2
if node_end_marker > end_marker:
    OF_between_flag = 0
elif end_marker > node_end_marker:
    OF_between_flag = 1
else:
    OF_between_flag = 2
with zipfile.ZipFile(str(location_mod[0])+'/required-'+cert_codename+'gw.zip','r') as zip_reader:
    key_info = zip_reader.read('required-'+cert_codename+'gw.key').decode('utf-8')
    encrypt_rdata = zip_reader.read('required-'+cert_codename+'gw.txt')
fernet = fcrypto.Fernet(key_info)
final_rdata = fernet.decrypt(encrypt_rdata).decode('utf-8')
param_dict = {}
while final_rdata.find('\r\n\r\n') != -1:
    bp = [final_rdata.find('\r\n\r\n'), final_rdata.find('{\r\n'), final_rdata.find('\r\n}'), final_rdata.find(' = ')]
    v_name = final_rdata[:bp[3]]
    v_data = final_rdata[bp[1]+len('{\r\n'):bp[2]]
    param_dict[v_name] = v_data
    final_rdata = final_rdata[bp[0]+len('\r\n\r\n'):]
full_URLstring = param_dict['rest_location'].replace('[','').replace(']','').replace('\'','').split(',')[0]
auth_key_pair = param_dict['auth_key'].replace('[','').replace(']','').replace('\'','').replace(' ','').split(',')
cert_location = param_dict['cert_loc_linux'].replace('[','').replace(']','').replace('\'','').split(',')[0]

