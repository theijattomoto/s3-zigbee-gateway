#! /usr/bin/python3
'''
External configuration loading for the gateway listener.

Command-line options are intentionally not parsed in this module. The launcher
(PYSerialGateway/pygw_main.py) passes its option string to main(), which keeps
module imports free from argparse side effects and allows the factorized
modules to be imported by tests and other Python code.

The remaining settings are loaded from PYSerialGateway/pygw_conf.py and the
encrypted rest_location/auth_key/cert bundle, preserving the existing runtime
behavior. The packaged config_PYproperties.py remains only as a fallback for
installations that do not provide the launcher-side configuration file.
'''
import sys, os
import zipfile
import cryptography.fernet as fcrypto
import psutil
try:
    from PYSerialGateway import pygw_conf
except ImportError:
    import pyserialgateway.config_PYproperties as pygw_conf
import pyserialgateway

location_mod = []
location_mod += pyserialgateway.__path__
obs_instance = [str(p.info['pid']) for p in psutil.process_iter(attrs=['pid','name','cmdline']) if p.info['cmdline'] and str(sys.argv[0]) in p.info['cmdline']]

'''[External configuration file user-defined variables]'''
file_pathname = str(os.path.abspath(os.path.dirname(sys.argv[0])))
updating_database_localpath = file_pathname + '/' + str(pygw_conf.localDBpath)
# Production may redirect operator-facing logs outside the protected runtime
# tree. If the environment variables are not set, preserve the legacy paths
# from pygw_conf.py for developer and existing non-production installations.
problemlogpath = os.getenv(
    'GATEWAY_ERROR_LOG_DIR',
    file_pathname + '/' + str(pygw_conf.problemlogpath),
)
logfilepath = os.getenv(
    'GATEWAY_LOG_DIR',
    file_pathname + '/' + str(pygw_conf.logfilepath),
)
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

# PostgreSQL connection settings, read from pygw_conf.py so deployment-specific
# details stay in one place. DB_USER may override the configured user at
# runtime (for example DB_USER=s3gw under systemd). If DB_USER is not set,
# the legacy pygw_conf.py value remains unchanged.
db_host = getattr(pygw_conf, 'db_host', None)          # None -> local Unix socket
db_port = getattr(pygw_conf, 'db_port', '5432')
db_user = os.getenv('DB_USER', getattr(pygw_conf, 'db_user', 'pi'))
db_password = getattr(pygw_conf, 'db_password', None)  # None -> peer authentication
db_name = getattr(pygw_conf, 'db_name', 'serial-gateway-program')
