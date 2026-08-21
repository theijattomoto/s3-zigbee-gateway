'''
MainHTTPURLThread: client thread that forwards queued messages to the
configured rest_location (and, when not in test mode, the main server) over
HTTP/HTTPS, with optional basic auth.
'''
import time
import datetime
import threading
import urllib
import requests
import ssl

from .config import auth_key_pair, cert_location

class MainHTTPURLThread(threading.Thread):
    '''
    A super-type Thread designed to grant it the ability to manage its variables and resources within a MULTIthreading environment.
    This thread focuses on sending all valid node data packets to the processing server on Selmos. All packetes are HTTP-type URL encoded.
    Statistics are also collected daily on the main loop to observe the HTTP URL link performances. 
    The reason why this Thread is always enabled despite in 'NOSELMOS' mode is due to the need to clear out msg_queue to avoid buffer overflow and memory issues.
    '''
    def __init__(self, *args):
        '''Start up variables taken from INIT arguments. Also starts up Event control functions and statistics variables.'''
        super(MainHTTPURLThread, self).__init__()
        self.arguments = args
        self.packet_logger = args[0]
        self.simple_packet_logger = args[1]
        self.problem_logger = args[2]
        self.msg_queue = args[3]
        self.full_URLstring = args[4]
        self.interval_sec = args[5]
        self.options_dict = args[6]
        self.test_align_flag = args[7]
        self.no_upload_flag = self.options_dict['NOSELMOS']
        self.no_auth_flag = self.options_dict['NOAUTH']
        self.test_flag = self.options_dict['TESTUP']
        self.stop_event = threading.Event()
        self.name = 'MainHTTPURLConnection'
        self.glob_POST_counter = 0
        self.glob_ACK_counter = 0
    
    def get_stats(self):
        '''Returns an integer tuple stating the statistics of the total number of packets sent versus the total number of OK acknowledged messages.'''
        return (self.glob_POST_counter, self.glob_ACK_counter)
    
    def set_stats(self):
        '''Resets the statistics integer tuple daily, which in this case, is controlled by an external caller.'''
        self.glob_POST_counter = 0
        self.glob_ACK_counter = 0
    
    def set_input_param(self, *args):
        self.options_dict = args
        self.no_upload_flag = self.options_dict['NOSELMOS']
        self.no_auth_flag = self.options_dict['NOAUTH']
        self.test_flag = self.options_dict['TESTUP']
    
    def status(self):
        return self.stop_event.is_set()
    
    def clone(self):
        return MainHTTPURLThread(*self.arguments)    
    
    def run(self):
        '''
        Functions to be executed once the MainHTTPURLThread is started.
        While waiting for the data in msg_queue, this thread will consistently go into sleep.
        If not, at an period specified by self.interval_sec, the thread will have obtained a packet data, processed it and sent it via the HTTP link. This process happens once per loop.
        The thread also records the HTTP sending status and processes the sending/receiving statistics on every loop.
        '''
        while not self.stop_event.is_set():
            if self.interval_sec > 0:
                time.sleep(self.interval_sec/2)
            while self.msg_queue.qsize() > 0:
                if self.stop_event.is_set():
                    break
                if self.interval_sec > 0:
                    time.sleep(self.interval_sec/4)
                node_id, packet_data, packet_type = self.msg_queue.get()
                if self.no_upload_flag:
                    self.msg_queue.task_done()
                    continue
                self.glob_POST_counter += 1
                try:
                    # split packet data info into a list
                    raw_data = packet_data.replace(b'#', b'').decode('utf-8')
                    split_raw_data = raw_data.split('|',22)
                except:
                    self.msg_queue.task_done()
                    continue
                # transform packet UTC time into proper system gmt8 timestamp
                if node_id != split_raw_data[1]:
                    self.msg_queue.task_done()
                    continue
                datestamp_y = str(datetime.datetime.utcnow().timetuple().tm_year)
                datestamp_m = str(datetime.datetime.utcnow().timetuple().tm_mon)
                try:
                    ds_utc = datestamp_y + '-' + datestamp_m + '-' + split_raw_data[3].replace('-',' ')
                    ds_utc_dt = datetime.datetime.strptime(ds_utc, '%Y-%m-%d %H:%M:%S')
                    ds_gmt8_dt = ds_utc_dt.replace(tzinfo=datetime.timezone.utc).astimezone(tz=datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo)
                    gmt8_dtime = time.strftime('%d-%H:%M:%S', ds_gmt8_dt.timetuple())
                except:
                    gmt8_dtime = time.strftime('%d-%H:%M:%S', time.localtime())
                # Payload data construction
                try:
                    ack = split_raw_data[0]
                    msg_id = split_raw_data[2]
                    time_stamp = gmt8_dtime
                except:
                    self.msg_queue.task_done()
                    continue
                try:
                    satellite = split_raw_data[4]
                    hdop = split_raw_data[5]
                except:
                    if isinstance(packet_type, int):
                        self.msg_queue.task_done()
                        continue
                    else:
                        satellite = hdop = '00'
                try:
                    timesync_gps = split_raw_data[6]
                    ac_status = split_raw_data[7]
                    ac_zcd = split_raw_data[8]
                    ac_Vsense = split_raw_data[9]
                    off_ctrl = split_raw_data[10]
                    on_ctrl = split_raw_data[11]
                    dim_ctrl = split_raw_data[12]
                    auto_profile = split_raw_data[13]
                    ctrl_mode = split_raw_data[14]
                    queue_msg = split_raw_data[16]
                except:
                    if isinstance(packet_type, int):
                        self.msg_queue.task_done()
                        continue
                    else:
                        timesync_gps = '0'
                        ac_status = ac_zcd = ac_Vsense = off_ctrl = on_ctrl = dim_ctrl = '0'
                        auto_profile = ctrl_mode = '0'
                        queue_msg = '0'
                try:
                    dc_status = split_raw_data[17]
                    lamp_ctrl = split_raw_data[15]
                    vrms = split_raw_data[18].strip()
                    irms = split_raw_data[19]
                    pwr = split_raw_data[20].strip()
                    pf = split_raw_data[21]
                except:
                    if isinstance(packet_type, int):
                        self.msg_queue.task_done()
                        continue
                    else:
                        dc_status = '5.000'
                        if ack[0] == 'X':
                            if ack[1] == '1':
                                lamp_ctrl = '1'
                                vrms = '240.00'
                                irms = '0.800'
                                pwr = '192.0'
                                pf = '0.990'
                            else:
                                lamp_ctrl = '0'
                                vrms = '0.00'
                                irms = '0.033'
                                pwr = '0.0'
                                pf = '0.850'
                        else:
                            lamp_ctrl = '0'
                            vrms = '0.00'
                            irms = '0.000'
                            pwr = '0.0'
                            pf = '0.000'
                # HTTP POST and response
                try:
                    conn_name = '/requests'
                    input_str = 'ack_code=' + ack + '&node_id=' + node_id + '&vrms=' + vrms + '&irms=' + irms + '&pwr=' + pwr + '&dim_ctrl=' + dim_ctrl + '&ctrl_mode=' + ctrl_mode + '&time_stamp=' + time_stamp + '&ac_status=' + ac_status + '&lamp_ctrl=' + lamp_ctrl + '&dc_status=' + dc_status + '&msg_id=' + msg_id + '&siv=' + satellite + '&hdop=' + hdop + '&gps_timefix=' + timesync_gps + '&zcd=' + ac_zcd + '&vsensor=' + ac_Vsense + '&off_ctrl=' + off_ctrl + '&on_ctrl=' + on_ctrl + '&auto_profile=' + auto_profile + '&queue_msg=' + queue_msg + '&pf=' + pf
                    indata = input_str.encode('utf-8')
                    spec_string = self.name + ' - INPUT DATA TO SERVER for node ' + input_str 
                    self.packet_logger.debug(spec_string)
                    self.simple_packet_logger.debug(spec_string)
                    '''
                    1/7/2021 - Due to independent network design complications, new self.test_align_flag added to give options in all possibilities of deployment.
                    Possibilities: single/double sending to test/main server(s) with auth/noauth enabled.
                    (Controlled from config)
                    If self.test_align_flag = True, only either single connection made to test/main server depending on self.test_flag. Free to choose auth/noauth.
                    (Controlled from startup input param, with self.test_align_flag = False)
                    If self.test_flag = True, single connection made to test server. Only noauth enabled.
                    If self.test_flag = False, double connections made to both servers. Noauth for test server, free to choose auth/noauth for main server.
                    '''
                    if self.test_align_flag:
                        if self.test_flag:
                            if self.no_auth_flag:
                                post_req = urllib.request.Request(self.full_URLstring, data=indata, method='POST')
                            else:
                                auth_filter = requests.auth.HTTPBasicAuth(auth_key_pair[2], auth_key_pair[3])
                                post_req = auth_filter(urllib.request.Request(self.full_URLstring, data=indata, method='POST'))
                            post_req.add_header('Content-Type','application/x-www-form-urlencoded')
                            conn_name = '/post_conn'
                            with urllib.request.urlopen(post_req, timeout=0.5) as _:
                                try:
#                                     if self.interval_sec > 0:
#                                         time.sleep(self.interval_sec/4)
#                                     HTTPresponse_flag = int(post_conn.read().decode('utf-8'))
#                                     HTTPresponse_code = int(post_conn.getcode())
#                                     if HTTPresponse_code is 200:
                                    self.glob_ACK_counter += 1
                                except:
                                    raise
                    else:
                        post_req = urllib.request.Request(self.full_URLstring, data=indata, method='POST')
                        post_req.add_header('Content-Type','application/x-www-form-urlencoded')
                        conn_name = '/post_conn'
                        with urllib.request.urlopen(post_req, timeout=0.5) as _:
                            try:
#                                 if self.interval_sec > 0:
#                                     time.sleep(self.interval_sec/4)
#                                 HTTPresponse_flag = int(post_conn.read().decode('utf-8'))
#                                 HTTPresponse_code = int(post_conn.getcode())
#                                 if HTTPresponse_code is 200:
                                self.glob_ACK_counter += 1
                            except:
                                raise
                    if not self.test_flag:
                        if len(auth_key_pair[1]) == 0:
                            ms_dest = auth_key_pair[0]
                        else:
                            ms_dest = auth_key_pair[0]+str(':')+auth_key_pair[1]
                        if 'http' in self.full_URLstring or 'https' in self.full_URLstring:
                            _q = self.full_URLstring.find('//')
                            _p = self.full_URLstring[_q+2:].find('/')
                            ori_url = self.full_URLstring[_q+2:].replace(self.full_URLstring[_q+2:][_p:],'')
                        else:
                            _p = self.full_URLstring.find('/')
                            ori_url = self.full_URLstring.replace(self.full_URLstring[_p:],'')
                        ms_URL = self.full_URLstring.replace(ori_url,ms_dest).replace('http','https')
                        _context = ssl.SSLContext(ssl.PROTOCOL_TLS)
                        _context.load_cert_chain(cert_location)
                        if self.no_auth_flag:
                            ss_main_req = urllib.request.Request(ms_URL, data=indata, method='POST')
                        else:
                            auth_filter = requests.auth.HTTPBasicAuth(auth_key_pair[2], auth_key_pair[3])
                            ss_main_req = auth_filter(urllib.request.Request(ms_URL, data=indata, method='POST'))
                        ss_main_req.add_header('Content-Type','application/x-www-form-urlencoded')
                        conn_name = '/ss_main_conn'
                        with urllib.request.urlopen(ss_main_req, timeout=0.5, context=_context) as _:
                            try:
#                                 if self.interval_sec > 0:
#                                     time.sleep(self.interval_sec/4)
#                                 HTTPresponse_flag = int(post_conn.read().decode('utf-8'))
#                                 HTTPresponse_code = int(post_conn.getcode())
#                                 if HTTPresponse_code is 200:
                                self.glob_ACK_counter += 1
                            except:
                                pass
                    self.msg_queue.task_done()
                except urllib.error.HTTPError as error:
                    if int(error.code) == 500:
                        spec_string = self.name + conn_name + ' - HTTP response 500 Internal Server Error for node ID ' + node_id #+ ', retrying request number ' + str(internal_retry_count)
                        self.packet_logger.debug(spec_string)
                        self.problem_logger.error(spec_string)
                    else:
                        spec_string = self.name + conn_name + ' - ' + str(error) + ' for node ID ' + node_id #+ ', retrying request number ' + str(internal_retry_count)
                        self.packet_logger.debug(spec_string)
                        self.problem_logger.error(spec_string)
                    self.msg_queue.task_done()
                except urllib.error.URLError as error:
                    spec_string = self.name + conn_name + ' - ' + str(error.reason) + ' for node ID ' + node_id #+ ', retrying request number ' + str(internal_retry_count)
                    self.packet_logger.debug(spec_string)
#                     self.problem_logger.error(spec_string)
                    self.msg_queue.task_done()
                except IOError as error:
                    spec_string = self.name + conn_name + ' - ' + str(error) + ' for node ID ' + node_id #+ ', retrying request number ' + str(internal_retry_count)
                    if str(error).find('timed out') == -1:
                        self.packet_logger.debug(spec_string)
                        self.problem_logger.error(spec_string)
                    self.msg_queue.task_done()
                except Exception as error:
                    spec_string = self.name + conn_name + ' - ' + str(error) + ' for node ID ' + node_id #+ ', retrying request number ' + str(internal_retry_count)
                    self.packet_logger.debug(spec_string)
                    self.problem_logger.error(spec_string)
                    self.msg_queue.task_done()
    
    def stop(self):
        '''Functions to be executed if an unexpected exit has occurred, to both the super thread or the overall script. Stop event is set to cleanly exit the super thread.'''
        self.stop_event.set()

        

