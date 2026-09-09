'''
Top-level orchestration: creates the shared queues, the long-lived Main*
threads, and runs the serial-read / packet-dispatch loop.

This is main() exactly as it was in the original single-file script, just
now pulling its collaborator classes and config values in from the other
modules in this package instead of finding them as bare names in the same
file.
'''
import time
import sys, os, subprocess
import serial
import datetime
import multiprocessing
import logging, logging.handlers as handlers

from .config import (
    first_GW_data, second_GW_data,
    GPS_style1, GPS_style2, GPS_style3,
    test_align_flag, between_flag, MQTT_client_ID,
    problemlogpath, logfilepath, maplogpath,
    cycletime, pollinggap,
    active_time, GPS_active_time, inactive_time, LM_active_time, node_off_time,
    aggressive_poll_duration_mins, location_mod, full_URLstring,
)
from .utils import StatObjectExceptionAPI
from .database_aligner import DatabaseAligner
from .kml_manager import KMLMapManager
from .serial_manager import SerialObjectManager
from .rest_api import RESTAPI, RESTMainControllerThread
from .http_thread import MainHTTPURLThread
from .record_thread import MainRecordThread
from .reset_thread import MainResetThread
from .polling_thread import MainPollingThread
from .main_listener_thread import MainListenerThread
from ..mqtt_service.mirroring import start_mqtt_mirroring, stop_mqtt_mirroring

def main(*args):
    '''
    [Creating several multiprocessing Queues, used by Main type threads to obtain data from processes]
    # polling_queue :- MainPolling, refreshes H1 packets obtained from nodes in DB list
    # residual_polling_queue :- MainPolling, accommodates low-priority H1 polling for already-known status nodes to decrease H2 packet floods                    
    # reset_queue :- MainReset, resets nodes according to faults detected by MainListener                
    # record_queue :- MainRecord, logs descriptive faults in error.log.*                                
    # msg_queue :- MainHTTPURL, forwards valid packets from MainListener up to REST service                
    # (unused) mqtt_msg_queue :- MainMsgServer, forwards valid packets from MainListener to MQTT broker    
    # GPS_confirmed_queue :- MainPolling & MainListener, daily mapping & memory keeping for G0 packets    
    # reset_G0_confirmed_queue :- MainReset & MainListener, auto node insert in DB for new installation 
    # TT_query_queue :- MainReset & MainListener, auto timetable rectify for nodes w/ odd lamp status    
    # REST_controller_queue :- MainReset, serial asynchronous command entry from REST server            
    '''
    polling_queue = multiprocessing.JoinableQueue()
    residual_polling_queue = multiprocessing.JoinableQueue()
    reset_queue = multiprocessing.JoinableQueue()
    record_queue = multiprocessing.JoinableQueue()
    msg_queue = multiprocessing.JoinableQueue()
    GPS_confirmed_queue = multiprocessing.JoinableQueue()
    reset_G0_confirmed_queue = multiprocessing.JoinableQueue()
    TT_query_queue = multiprocessing.JoinableQueue()
    REST_controller_queue = multiprocessing.JoinableQueue()
    
    '''
    [Start up variables to support functions used by Main function & dynamic objects]    
    # *_datetimenow :- Formation of time stamps according to times declared in config.properties                    
    '''
    my_logger = logging.getLogger('PacketListener')
    my_logger.setLevel(logging.DEBUG)
    my_logger_simple = logging.getLogger('PollingListener')
    my_logger_simple.setLevel(logging.DEBUG)
    my_logger_problem = logging.getLogger('MainReset')
    my_logger_problem.setLevel(logging.DEBUG)
    formatter_simplelog = logging.Formatter('%(asctime)s:%(levelname)s %(threadName)s:%(lineno)d - %(message)s\n', datefmt='%Y-%m-%d,%H:%M:%S')
    formatter_log = logging.Formatter('%(asctime)s  %(levelname)s  %(threadName)s:%(lineno)d -\n%(message)s\n')
    formatter_stdo = logging.Formatter('%(asctime)s  %(threadName)s:%(lineno)d - %(message)s\n', datefmt='%Y-%m-%d,%H:%M:%S')
    options_string = ''.join(str(elements) for elements in args)
    all_other_main_threads = []
    datenow = time.strftime('%d-%m-%Y', time.localtime())
    GPSactive_datetimenow = datetime.datetime.strptime(datenow + ' ' + GPS_active_time + ':00', '%d-%m-%Y %H:%M:%S')
    LMactive_datetimenow = datetime.datetime.strptime(datenow + ' ' + LM_active_time + ':00', '%d-%m-%Y %H:%M:%S')
    nodeoff_datetimenow = datetime.datetime.strptime(datenow + ' ' + node_off_time + ':00', '%d-%m-%Y %H:%M:%S')
    active_datetimenow = datetime.datetime.strptime(datenow + ' ' + active_time + ':00', '%d-%m-%Y %H:%M:%S')
    inactive_datetimenow = datetime.datetime.strptime(datenow + ' ' + inactive_time + ':00', '%d-%m-%Y %H:%M:%S')
    aggressivepoll_datetimenow = active_datetimenow + datetime.timedelta(minutes=aggressive_poll_duration_mins)
    if between_flag == 2:
        pass
    elif between_flag == 1:
        LMactive_datetimenow += datetime.timedelta(days=-1)
    elif between_flag == 0:
        active_datetimenow += datetime.timedelta(days=-1)
        aggressivepoll_datetimenow += datetime.timedelta(days=-1)
        LMactive_datetimenow += datetime.timedelta(days=-2)
        nodeoff_datetimenow += datetime.timedelta(days=-1)
    datein = list(time.localtime()[0:3])
    simple_fh = handlers.RotatingFileHandler(logfilepath+'/gateway.log', maxBytes=5000000, backupCount=100)
    simple_fh.setLevel(logging.DEBUG)
    simple_fh.setFormatter(formatter_simplelog)
    my_logger_simple.addHandler(simple_fh)
    fh = handlers.RotatingFileHandler(logfilepath+'/gateway.log', maxBytes=5000000, backupCount=100)
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter_log)
    my_logger.addHandler(fh)
    stdoh = logging.StreamHandler(sys.stdout)
    stdoh.setLevel(logging.DEBUG)
    stdoh.setFormatter(formatter_stdo)
    my_logger.addHandler(stdoh)
    problem_fh = handlers.RotatingFileHandler(problemlogpath+'/error.log', maxBytes=500000, backupCount=25)
    problem_fh.setLevel(logging.INFO)
    problem_fh.setFormatter(formatter_simplelog)
    my_logger_problem.addHandler(problem_fh)
    kmllogfilename = '_'.join(str(it) for it in datein) + '_' + MQTT_client_ID + '_GPSscan.kml'
    kmlpathname = maplogpath+'/'+kmllogfilename

    mqtt_started = start_mqtt_mirroring()
    if mqtt_started:
        my_logger.info('MQTT transport started independently of Zigbee serial.')
    else:
        my_logger.warning('MQTT transport is disabled or failed to start.')

    DBAligner = StatObjectExceptionAPI(DatabaseAligner,my_logger,my_logger_problem)
    KMLMapper = StatObjectExceptionAPI(KMLMapManager,my_logger,my_logger_problem)
    SerialProcessObject = SerialObjectManager()
    RESTAPIObject = RESTAPI()

    try:
        if not os.path.isfile(kmlpathname):
            raise
        KMLDocumentElement, GPS_confirmed_list = KMLMapper.inherit_old_document_info(kmlpathname, [GPS_style1, GPS_style2, GPS_style3])
        if KMLDocumentElement is None:
            raise
    except:
        KMLDocumentElement = KMLMapper.ini_run(kmlpathname, [GPS_style1, GPS_style2, GPS_style3])
    port_status, port_name, port_data, port_index = SerialProcessObject.ini_run(my_logger, my_logger_simple, my_logger_problem, 1, [first_GW_data, second_GW_data], None)
    RESTAPIObject.ini_run(my_logger, my_logger_simple, REST_controller_queue, msg_queue)
    options_status_dict = {
        'DBUP': False,
        'DBUP_ONLY': False,
        'GPSUP': False,
        'DEMOUP': False,
        'TESTUP': False,
        'NOSELMOS': False,
        'NOPOLL': False,
        'NOAUTH': False
    }
    try:
        for flag in options_status_dict:
            if options_string.find(str(flag)) != -1:
                options_status_dict[flag] = True
    except:
        pass

    if not port_status:
        my_logger.warning('No Zigbee gateway serial port detected. MQTT remains active; waiting for Zigbee gateway.')
        retry_interval = max(1.0, float(os.getenv('ZIGBEE_SERIAL_RETRY_SECONDS', '5')))
        last_wait_log = 0.0
        try:
            while not port_status:
                now = time.monotonic()
                if now - last_wait_log >= 30.0:
                    my_logger.info('Waiting for Zigbee gateway serial port; retrying every %.1fs.', retry_interval)
                    last_wait_log = now
                time.sleep(retry_interval)
                port_status, port_name, port_data, port_index = SerialProcessObject.ini_run(my_logger, my_logger_simple, my_logger_problem, 1, [first_GW_data, second_GW_data], None)
        except KeyboardInterrupt:
            my_logger.info('Gateway shutdown requested while waiting for Zigbee serial.')
            if mqtt_started:
                stop_mqtt_mirroring()
            return
        my_logger.info('Zigbee gateway serial port detected: %s', port_name)

    dbup_requested = options_status_dict['DBUP'] or options_status_dict['DBUP_ONLY']
    node_database_list = DBAligner.run(my_logger, my_logger_simple, my_logger_problem, port_data, [first_GW_data, second_GW_data], dbup_requested)
    if node_database_list == []:
        error_string = 'DBUP - PostgreSQL database has no target nodes, deactivating code.'
        my_logger.debug(error_string)
        my_logger_problem.error(error_string)

    if options_status_dict['DBUP_ONLY']:
        my_logger.info('DBUP_ONLY completed. Database synchronized; exiting before gateway runtime starts.')
        if mqtt_started:
            stop_mqtt_mirroring()
        return

    try:
        if port_status == False or options_status_dict['NOPOLL']:
            raise
        poll_t = MainPollingThread(my_logger, my_logger_simple, my_logger_problem, polling_queue, residual_polling_queue, GPS_confirmed_queue, pollinggap, cycletime, node_database_list, SerialProcessObject, [first_GW_data[0], second_GW_data[0]], DBAligner, LMactive_datetimenow, nodeoff_datetimenow, active_datetimenow, aggressivepoll_datetimenow, options_status_dict['GPSUP'])
        poll_t.start()
        poll_flag = True
        all_other_main_threads.append((poll_t.name, poll_t))
    except:
        poll_t = MainPollingThread(my_logger, my_logger_simple, my_logger_problem, polling_queue, residual_polling_queue, GPS_confirmed_queue, pollinggap, cycletime, node_database_list, SerialProcessObject, [first_GW_data[0], second_GW_data[0]], DBAligner, LMactive_datetimenow, nodeoff_datetimenow, active_datetimenow, aggressivepoll_datetimenow, options_status_dict['GPSUP'])
        poll_t.stop()
        poll_flag = False
        my_logger.warning('Polling thread disabled.')
    try:
        if port_status == False:
            raise
        reset_t = MainResetThread(my_logger_simple, my_logger_problem, reset_queue, REST_controller_queue, reset_G0_confirmed_queue, TT_query_queue, 0.5, 3, SerialProcessObject)
        reset_t.start()
        reset_flag = True
        all_other_main_threads.append((reset_t.name, reset_t))
    except:
        reset_t = MainResetThread(my_logger_simple, my_logger_problem, reset_queue, REST_controller_queue, reset_G0_confirmed_queue, TT_query_queue, 0.5, 3, SerialProcessObject)
        reset_t.stop()
        reset_flag = False
        my_logger.warning('Reset thread disabled.')
    try:
        record_t = MainRecordThread(my_logger_problem, record_queue)
        record_t.start()
        record_flag = True
        all_other_main_threads.append((record_t.name, record_t))
    except:
        record_t = MainRecordThread(my_logger_problem, record_queue)
        record_t.stop()
        record_flag = False
        my_logger.warning('Record thread disabled.')
    try:
        REST_t = RESTMainControllerThread(my_logger, my_logger_simple, RESTAPIObject)
        REST_t.start()
        REST_flag = True
        all_other_main_threads.append((REST_t.name, REST_t))
    except:
        REST_t = RESTMainControllerThread(my_logger, my_logger_simple, RESTAPIObject)
        REST_t.stop()
        REST_flag = False
        my_logger.warning('REST controller thread disabled.')
    try:
        http_t = MainHTTPURLThread(my_logger, my_logger_simple, my_logger_problem, msg_queue, full_URLstring, 0.5, options_status_dict, test_align_flag)
        http_t.start()
        http_flag = True
        all_other_main_threads.append((http_t.name, http_t))
    except:
        http_t = MainHTTPURLThread(my_logger, my_logger_simple, my_logger_problem, msg_queue, full_URLstring, 0.5, options_status_dict, test_align_flag)
        http_t.stop()
        http_flag = False
        my_logger.warning('HTTP-URL thread disabled.')

    listener_threads = []
    inactive_threads = []
    inactive_other_main_threads = []
    new_other_main_threads = []
    read_port_status = port_status
    msg_recv = None
    msg_publish = None
    hoursoffset = 24
    last_port_index = None
    forced_port_switch_flag = False
    try:
        if len(GPS_confirmed_list) != 0 and poll_t:
            poll_t.insert_GPS_confirmed_list(list(set(GPS_confirmed_list)))
    except:
        pass
    GPS_confirmed_list = None

    try:
        spec_string = '[START] PYGATEWAY LISTENER @ ' + time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
        my_logger.info(spec_string)
        portcheck_datetimenow = datetime.datetime(*time.localtime()[:6]) + datetime.timedelta(hours=1)
        while True:
            datetimenow = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
            dt_datetimenow = datetime.datetime(*time.localtime()[:6])
            if len(all_other_main_threads) >= 1:
                for k in range(0, len(all_other_main_threads)):
                    main_thread_name, main_thread_obj = all_other_main_threads[k]
                    try:
                        if main_thread_obj.status():
                            raise AttributeError
                    except:
                        if main_thread_name == 'MainController':
                            err_type, err_reason = main_thread_obj.status_error_reason()
                            if err_type == 'OSError' and err_reason.find('Address already in use') != -1:
                                my_logger.debug(main_thread_name + ' in use by other processes.')
                                my_logger_problem.error(main_thread_name + ' in use by other processes.')
                                inactive_other_main_threads.append(all_other_main_threads[k])
                                continue
                        my_logger.debug(main_thread_name + ' exited unexpectedly, reviving thread...')
                        my_logger_problem.error(main_thread_name + ' exited unexpectedly, reviving thread...')
                        new_main_thread_obj = main_thread_obj.clone()
                        main_thread_obj.stop()
                        if main_thread_name == 'MainPolling':
                            poll_t = new_main_thread_obj
                            poll_t.set_pause_status(SerialProcessObject)
                            poll_flag = True
                        elif main_thread_name == 'MainReset':
                            reset_t = new_main_thread_obj
                            reset_t.set_pause_status(SerialProcessObject)
                            reset_flag = True
                        elif main_thread_name == 'MainRecord':
                            record_t = new_main_thread_obj
                            record_flag = True
                        elif main_thread_name == 'MainHTTPURLConnection':
                            http_t = new_main_thread_obj
                            http_flag = True
                        elif main_thread_name == 'MainController':
                            REST_t = new_main_thread_obj
                            REST_flag = True
                        inactive_other_main_threads.append(all_other_main_threads[k])
                        new_main_thread_obj.start()
                        new_other_main_threads.append((new_main_thread_obj.name, new_main_thread_obj))
                if len(inactive_other_main_threads) >= 1:
                    for l in range(0, len(inactive_other_main_threads)):
                        all_other_main_threads.remove(inactive_other_main_threads[l])
                    inactive_other_main_threads.clear()
                if len(new_other_main_threads) >= 1:
                    for m in range(0, len(new_other_main_threads)):
                        all_other_main_threads.append(new_other_main_threads[m])
                    new_other_main_threads.clear()
            if poll_flag:
                all_poll_loop_count = poll_t.get_all_poll_loop_count()
                if all_poll_loop_count >= 100.0:
                    try:
                        last_port_index = port_index
                        location_hwreset = str(location_mod[0]) + '/hardware_reset.py'
                        _ = subprocess.check_output('sudo python3 '+location_hwreset, shell=True)
                        poll_t.set_all_poll_loop_count()
                        forced_port_switch_flag = True
                    except subprocess.CalledProcessError as err:
                        err_string = '[HWRESET] - Error number ' + str(err.returncode) + ': ' + str(err.output)
                        my_logger.info(err_string)
                        my_logger_problem.warning(err_string)
                else:
                    poll_pulse_flag = poll_t.get_poll_pulse_status()
                    if poll_pulse_flag is False:
                        _ , poll_exempt_list = DBAligner.final_read(port_data)
                        poll_t.set_poll_list(node_database_list, poll_exempt_list)
                        poll_t.set_poll_pulse_status()
            portchecktimedelta = portcheck_datetimenow - dt_datetimenow
            if portchecktimedelta.days < 0:
                portcheck_datetimenow += datetime.timedelta(hours=1)
                read_port_status, port_data = SerialProcessObject.gw_initial(port_index, None)
            GPStimedelta = GPSactive_datetimenow - dt_datetimenow
            if GPStimedelta.days < 0:
                GPSactive_datetimenow += datetime.timedelta(days=1)
                if reset_flag:
                    reset_t.set_awaiting_E1_list()
            if between_flag != 2:
                activetimedelta = active_datetimenow - dt_datetimenow
                inactivetimedelta = inactive_datetimenow - dt_datetimenow
                aggressivepolltimedelta = aggressivepoll_datetimenow - dt_datetimenow
                if aggressivepolltimedelta.days < 0 and activetimedelta.days == 0:
                    if poll_flag:
                        aggressive_poll_list_loaded_flag, aggressive_poll_ongoing_flag = poll_t.get_aggressive_poll_status()
                        if aggressive_poll_list_loaded_flag is True and aggressive_poll_ongoing_flag is True:
                            no_data_list = poll_t.timeout_aggressive_poll_ongoing()
                            spec_string = '[AGG POLL CLOSE] Remaining nodes: ' + str(no_data_list)
                            my_logger_simple.debug(spec_string)
                        else:
                            _ = poll_t.timeout_aggressive_poll_ongoing()
                if activetimedelta.days < 0 and inactivetimedelta.days == 0:
                    msg_recv, msg_publish = http_t.get_stats()
                    active_datetimenow += datetime.timedelta(hours=1)
                    hoursoffset -= 1
                    spec_string = '[ACTIVE] HTTP link quality: ' + str(msg_publish) + '/' + str(msg_recv) + ' messages.'
                    my_logger_simple.debug(spec_string)
                    if poll_flag:
                        aggressive_poll_list_loaded_flag, aggressive_poll_ongoing_flag = poll_t.get_aggressive_poll_status()
                        if aggressivepolltimedelta.days == 0:
                            if aggressive_poll_list_loaded_flag is False and aggressive_poll_ongoing_flag is False:
                                poll_t.set_aggressive_poll_ongoing_flag()
                    _ = DBAligner.dtime_active_check()
                elif activetimedelta.days == 0 and inactivetimedelta.days < 0:
                    msg_recv, msg_publish = http_t.get_stats()
                    active_datetimenow += datetime.timedelta(hours=hoursoffset)
                    aggressivepoll_datetimenow += datetime.timedelta(days=1)
                    inactive_datetimenow += datetime.timedelta(days=1)
                    LMactive_datetimenow += datetime.timedelta(days=1)
                    nodeoff_datetimenow += datetime.timedelta(days=1)
                    spec_string = '[CLOSING] HTTP link quality: ' + str(msg_publish) + '/' + str(msg_recv) + ' messages.'
                    my_logger_simple.debug(spec_string)
                    hoursoffset = 24
                    if poll_flag:
                        poll_t.set_override_off_timeframe(LMactive_datetimenow, nodeoff_datetimenow)
                        poll_t.set_aggressive_poll_timeframe(active_datetimenow, aggressivepoll_datetimenow)
                        poll_t.timeout_aggressive_poll_list_loaded_flag()
                    if http_flag:
                        http_t.set_stats()
                    _ = DBAligner.dtime_active_check()
                elif activetimedelta.days < 0 and inactivetimedelta.days < 0:
                    active_datetimenow += datetime.timedelta(days=1)
                    aggressivepoll_datetimenow += datetime.timedelta(days=1)
                    inactive_datetimenow += datetime.timedelta(days=1)
                    LMactive_datetimenow += datetime.timedelta(days=1)
                    nodeoff_datetimenow += datetime.timedelta(days=1)
                    hoursoffset = 24
                    if poll_flag:
                        poll_t.set_override_off_timeframe(LMactive_datetimenow, nodeoff_datetimenow)
                        poll_t.set_aggressive_poll_timeframe(active_datetimenow, aggressivepoll_datetimenow)
                    if http_flag:
                        http_t.set_stats()
                    _ = DBAligner.dtime_active_check()
            if datetimenow[0:10] != datenow:
                datein = list(time.localtime()[0:3])
                datenow = datetimenow[0:10]
                kmllogfilename = '_'.join(str(it) for it in datein) + '_' + MQTT_client_ID + '_GPSscan.kml'
                kmlpathname = maplogpath+'/'+kmllogfilename
                new_KMLMapper = KMLMapManager()
                try:
                    if not os.path.isfile(kmlpathname):
                        raise
                    new_KMLDocumentElement, GPS_confirmed_list = new_KMLMapper.inherit_old_document_info(kmlpathname, [GPS_style1, GPS_style2, GPS_style3])
                    try:
                        if len(GPS_confirmed_list) != 0 and poll_t:
                            poll_t.insert_GPS_confirmed_list(list(set(GPS_confirmed_list)))
                    except:
                        pass
                    if new_KMLDocumentElement is None:
                        raise
                except:
                    new_KMLDocumentElement = new_KMLMapper.ini_run(kmlpathname, [GPS_style1, GPS_style2, GPS_style3])
                GPS_confirmed_list = None
                KMLMapper = new_KMLMapper
                KMLDocumentElement = new_KMLDocumentElement
                node_database_list = DBAligner.run(my_logger, my_logger_simple, my_logger_problem, port_data, [first_GW_data, second_GW_data], options_status_dict['DBUP'])
                if poll_flag:
                    poll_t.set_poll_list(node_database_list, None)
                    poll_t.set_GPS_confirmed_list()
            '''Loop-based packet listener invoker'''
            try:
                # Node application packets terminate with b'#\r\n'. PySerial
                # requires a bytes delimiter; the previous string delimiter
                # (and trailing space) could never match, so reads ended only
                # on timeout and split control frames at arbitrary byte offsets.
                packet = SerialProcessObject.read_until(b'#\r\n')
            except Exception as error:
                if abs(dt_datetimenow.second) == 0:
                    my_logger.error(error)
                    my_logger_problem.error(error)
                    time.sleep(0.5)
                packet = b''
                try:
                    SerialProcessObject.force_close()
                except:
                    pass
                read_port_status = False
                if poll_flag:
                    poll_t.freeze_monitor_clock()
            if packet:
                main_t = MainListenerThread(options_status_dict['DEMOUP'], my_logger, my_logger_problem, reset_queue, record_queue, msg_queue, GPS_confirmed_queue, reset_G0_confirmed_queue, TT_query_queue, node_database_list, [first_GW_data[0], second_GW_data[0]], port_data, packet, SerialProcessObject, ['D0'], ['E1', 'E2', 'E4', 'H1', 'H2', 'G0', 'P0'], KMLMapper, KMLDocumentElement, poll_t, reset_t)
                main_t.start()
                main_t.join()
                listener_threads.append(main_t)
            if len(listener_threads) >= 1:    
                for i in range(0, len(listener_threads)):
                    if listener_threads[i].status():
                        listener_threads[i].join()
                        inactive_threads.append(listener_threads[i])
                    if listener_threads[i].get_pause_status():
                        read_port_status = False
                if len(inactive_threads) >= 1:
                    for j in range(0, len(inactive_threads)):
                        listener_threads.remove(inactive_threads[j])
                    inactive_threads.clear()
            retry_logic = not read_port_status 
            if poll_flag:
                retry_logic |= poll_t.get_pause_status()
            if reset_flag:
                retry_logic |= reset_t.get_pause_status()
            if retry_logic:
                spo_2 = SerialObjectManager()
                try:
                    retry_port_status, retry_port_name, retry_port_data, retry_port_index = spo_2.ini_run(my_logger, my_logger_simple, my_logger_problem, 1, [first_GW_data, second_GW_data], port_index)
                    if retry_port_status == True:
                        if reset_flag:
                            reset_t.set_pause_status(spo_2)
                        else:
                            all_other_main_threads.append((reset_t.name, reset_t))
                        SerialProcessObject = spo_2
                        read_port_status = True
                        port_data = retry_port_data
                        port_index = retry_port_index
                        port_name = retry_port_name
                        if poll_flag:
                            poll_t.set_pause_status(spo_2)
                        my_logger.info('Serial port recovered: %s', port_name)
                    else:
                        time.sleep(0.5)
                except Exception as error:
                    my_logger_problem.exception('Serial port recovery failed.')
                    time.sleep(0.5)
    except KeyboardInterrupt:
        my_logger.info('Gateway shutdown requested.')
    finally:
        try:
            for _, thread_obj in all_other_main_threads:
                thread_obj.stop()
        except Exception:
            pass
        try:
            SerialProcessObject.force_close()
        except Exception:
            pass
        if mqtt_started:
            stop_mqtt_mirroring()
