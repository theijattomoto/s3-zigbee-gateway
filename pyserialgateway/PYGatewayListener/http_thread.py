'''
MainHTTPURLThread: forwards validated gateway packets to the configured REST
server and mirrors the same payload to the DBKL HTTPS endpoint.

DBKL HTTPS defaults to normal server-certificate verification. A custom CA
bundle can be supplied when the server omits an intermediate certificate.
Client certificates are optional and disabled by default.
'''
import base64
import datetime
import os
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .config import auth_key_pair, cert_location


def _env_bool(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def build_dbkl_https_url(rest_url, auth_values, explicit_url=None):
    if explicit_url:
        return explicit_url.strip()

    if not auth_values or not auth_values[0]:
        raise ValueError('DBKL host is missing from auth_key configuration')

    host = auth_values[0]
    port = auth_values[1] if len(auth_values) > 1 else ''
    destination = host if not port else host + ':' + str(port)

    parsed = urllib.parse.urlsplit(rest_url)
    if parsed.scheme and parsed.netloc:
        return urllib.parse.urlunsplit(
            ('https', destination, parsed.path, parsed.query, parsed.fragment)
        )

    path_index = rest_url.find('/')
    path = rest_url[path_index:] if path_index >= 0 else ''
    return 'https://' + destination + path


def _basic_auth_header(username, password):
    token = ('%s:%s' % (username, password)).encode('utf-8')
    return 'Basic ' + base64.b64encode(token).decode('ascii')


class MainHTTPURLThread(threading.Thread):
    def __init__(self, *args):
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

        self.dbkl_https_enabled = _env_bool('DBKL_HTTPS_ENABLED', True)
        self.dbkl_https_url = os.getenv('DBKL_HTTPS_URL', '').strip()
        try:
            self.dbkl_https_timeout = float(os.getenv('DBKL_HTTPS_TIMEOUT', '0.5'))
        except ValueError:
            self.dbkl_https_timeout = 0.5

        self.dbkl_tls_verify = _env_bool('DBKL_TLS_VERIFY', True)
        self.dbkl_ca_cert = os.getenv('DBKL_CA_CERT', '').strip()
        self.dbkl_client_cert_enabled = _env_bool('DBKL_CLIENT_CERT_ENABLED', False)
        self.dbkl_client_cert = os.getenv('DBKL_CLIENT_CERT', '').strip()
        self.dbkl_client_key = os.getenv('DBKL_CLIENT_KEY', '').strip()

    def get_stats(self):
        return (self.glob_POST_counter, self.glob_ACK_counter)

    def set_stats(self):
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

    def _build_payload(self, node_id, packet_data, packet_type):
        try:
            raw_data = packet_data.replace(b'#', b'').decode('utf-8')
            split_raw_data = raw_data.split('|', 22)
        except Exception:
            return None

        if len(split_raw_data) < 4 or node_id != split_raw_data[1]:
            return None

        datestamp_y = str(datetime.datetime.utcnow().timetuple().tm_year)
        datestamp_m = str(datetime.datetime.utcnow().timetuple().tm_mon)
        try:
            ds_utc = datestamp_y + '-' + datestamp_m + '-' + split_raw_data[3].replace('-', ' ')
            ds_utc_dt = datetime.datetime.strptime(ds_utc, '%Y-%m-%d %H:%M:%S')
            ds_gmt8_dt = ds_utc_dt.replace(tzinfo=datetime.timezone.utc).astimezone(
                tz=datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
            )
            gmt8_dtime = time.strftime('%d-%H:%M:%S', ds_gmt8_dt.timetuple())
        except Exception:
            gmt8_dtime = time.strftime('%d-%H:%M:%S', time.localtime())

        try:
            ack = split_raw_data[0]
            msg_id = split_raw_data[2]
            time_stamp = gmt8_dtime
        except Exception:
            return None

        try:
            satellite = split_raw_data[4]
            hdop = split_raw_data[5]
        except Exception:
            if isinstance(packet_type, int):
                return None
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
        except Exception:
            if isinstance(packet_type, int):
                return None
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
        except Exception:
            if isinstance(packet_type, int):
                return None
            dc_status = '5.000'
            if ack and ack[0] == 'X':
                if len(ack) > 1 and ack[1] == '1':
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

        input_str = (
            'ack_code=' + ack +
            '&node_id=' + node_id +
            '&vrms=' + vrms +
            '&irms=' + irms +
            '&pwr=' + pwr +
            '&dim_ctrl=' + dim_ctrl +
            '&ctrl_mode=' + ctrl_mode +
            '&time_stamp=' + time_stamp +
            '&ac_status=' + ac_status +
            '&lamp_ctrl=' + lamp_ctrl +
            '&dc_status=' + dc_status +
            '&msg_id=' + msg_id +
            '&siv=' + satellite +
            '&hdop=' + hdop +
            '&gps_timefix=' + timesync_gps +
            '&zcd=' + ac_zcd +
            '&vsensor=' + ac_Vsense +
            '&off_ctrl=' + off_ctrl +
            '&on_ctrl=' + on_ctrl +
            '&auto_profile=' + auto_profile +
            '&queue_msg=' + queue_msg +
            '&pf=' + pf
        )
        return input_str, input_str.encode('utf-8')

    def _send_request(self, url, indata, conn_name, use_auth=False, context=None, timeout=0.5):
        req = urllib.request.Request(url, data=indata, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')

        if use_auth and len(auth_key_pair) >= 4:
            req.add_header(
                'Authorization',
                _basic_auth_header(auth_key_pair[2], auth_key_pair[3]),
            )

        with urllib.request.urlopen(req, timeout=timeout, context=context) as _:
            self.glob_ACK_counter += 1

        self.packet_logger.debug('%s%s - delivery acknowledged', self.name, conn_name)

    def _log_delivery_error(self, conn_name, node_id, error):
        if isinstance(error, urllib.error.HTTPError) and int(error.code) == 500:
            message = (
                self.name + conn_name +
                ' - HTTP response 500 Internal Server Error for node ID ' + node_id
            )
        elif isinstance(error, urllib.error.URLError):
            message = self.name + conn_name + ' - ' + str(error.reason) + ' for node ID ' + node_id
        else:
            message = self.name + conn_name + ' - ' + str(error) + ' for node ID ' + node_id

        self.packet_logger.debug(message)
        if not (isinstance(error, IOError) and str(error).find('timed out') != -1):
            self.problem_logger.error(message)

    def _send_primary_rest(self, indata, node_id):
        if self.test_align_flag and not self.test_flag:
            return

        use_auth = self.test_align_flag and self.test_flag and not self.no_auth_flag
        try:
            self._send_request(
                self.full_URLstring,
                indata,
                '/post_conn',
                use_auth=use_auth,
                timeout=0.5,
            )
        except Exception as error:
            self._log_delivery_error('/post_conn', node_id, error)

    def _build_dbkl_ssl_context(self):
        if self.dbkl_tls_verify:
            context = ssl.create_default_context(
                cafile=self.dbkl_ca_cert or None,
            )
        else:
            context = ssl._create_unverified_context()

        if self.dbkl_client_cert_enabled:
            client_cert = self.dbkl_client_cert or cert_location
            client_key = self.dbkl_client_key or None
            if not client_cert:
                raise ValueError('DBKL client certificate is enabled but no certificate path is configured')
            context.load_cert_chain(client_cert, keyfile=client_key)

        return context

    def _send_dbkl_https(self, indata, node_id):
        if not self.dbkl_https_enabled:
            return

        if self.test_flag:
            return

        try:
            dbkl_url = build_dbkl_https_url(
                self.full_URLstring,
                auth_key_pair,
                explicit_url=self.dbkl_https_url,
            )
            context = self._build_dbkl_ssl_context()
            self._send_request(
                dbkl_url,
                indata,
                '/dbkl_https',
                use_auth=not self.no_auth_flag,
                context=context,
                timeout=self.dbkl_https_timeout,
            )
        except Exception as error:
            self._log_delivery_error('/dbkl_https', node_id, error)

    def run(self):
        while not self.stop_event.is_set():
            if self.interval_sec > 0:
                time.sleep(self.interval_sec / 2)

            while self.msg_queue.qsize() > 0:
                if self.stop_event.is_set():
                    break
                if self.interval_sec > 0:
                    time.sleep(self.interval_sec / 4)

                node_id, packet_data, packet_type = self.msg_queue.get()
                try:
                    if self.no_upload_flag:
                        continue

                    payload = self._build_payload(node_id, packet_data, packet_type)
                    if payload is None:
                        continue

                    input_str, indata = payload
                    self.glob_POST_counter += 1
                    spec_string = self.name + ' - INPUT DATA TO SERVER for node ' + input_str
                    self.packet_logger.debug(spec_string)
                    self.simple_packet_logger.debug(spec_string)

                    self._send_primary_rest(indata, node_id)
                    self._send_dbkl_https(indata, node_id)
                finally:
                    self.msg_queue.task_done()

    def stop(self):
        self.stop_event.set()
