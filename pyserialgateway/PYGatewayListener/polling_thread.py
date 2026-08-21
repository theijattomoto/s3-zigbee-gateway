'''
MainPollingThread: active/aggressive polling loop for node heartbeat and GPS
data, driven by the daily active/inactive/override time windows.
'''
import time
import threading
import fcntl

from .utils import Clock
from .config import (
    LM_between_flag, LM_start_marker, end_marker,
    GPS_between_flag, GPS_start_marker,
    OF_between_flag, node_end_marker,
)

class MainPollingThread(threading.Thread):
    '''
    A super-type Thread designed to grant it the ability to manage its variables and resources within a MULTIthreading environment.
    This thread focuses on realising polling cycles for a full node list, which its polling gap being timely crucial with timing errors of <= 0.01s.
    1. Using an internally declared Clock function, the real polling cycle for each loop can be calculated, with the remaining waiting time being used to off-load the ZigBee network.
    2. By default, the polling cycle will only incorporate polling for heart beats (H1) packets. 
    3. If GPS scan is turned ON, the cycle will dual poll for both heart beat and GPS packets at a declared time frame.
    The daily GPS scanning contains memory properties, i.e. if a node's GPS data is historically obtained within the current day, the script will no longer poll for GPS data for this particular node.
    4. The thread also instigates a full refresh on the node list and polling list with each loop, controlled by the main loop by feeding back the poll_pulse_flag.
    The reason of the refresh is asynchronous is due to the fact that DB data reading is time-intensive, and will mess up the polling cycle if the original node list is long.
    5. During inactive hours, this thread also contains a third layer, where it acts as an overriding OFF agent during the polling cycle.
    6. During the first X minutes of the active hours/one-time action on first time script initiation during active hours after the X minutes, the thread also contains an ALTERNATE, more aggressive polling feature, which continuously repeats polling for non-updated nodes (cross compared between filter_time_py and node_database). 
    '''
    def __init__(self, *args):
        '''Start up variables taken from INIT arguments. Also starts up Event control functions, port control variables and memory variables.'''
        super(MainPollingThread, self).__init__()
        self.arguments = args
        self.packet_logger = args[0]
        self.simple_msg_logger = args[1]
        self.problem_logger = args[2]
        self.polling_queue = args[3]
        self.residual_polling_queue = args[4]
        self.GPS_confirmed_queue = args[5]
        self.stop_event = threading.Event()
        self.interval_sec = args[6]
        self.cycle_sec = args[7]
        self.node_database_list = args[8]
        self.serial_obj = args[9]
        self.gatewaynode_idlist = args[10]
        self.DBAligner = args[11]
        self.LMactive_datetimenow = args[12]
        self.nodeoff_datetimenow = args[13]
        self.active_datetimenow = args[14]
        self.aggressivepoll_datetimenow = args[15]
        self.GPS_poll_flag = args[16]
        self.name = 'MainPolling'
        self.pause_flag = False
        self.GPS_confirmed_list = []
        self.GPS_varying_list = []
        self.GPS_poll_list = []
        self.monitor_clock = None
        self.load_override_off_flag = True
        self.out_of_timerange_nodelist = []
        self.override_off_poll_list = []
        self.poll_pulse_flag = True
        self.poll_exempt_list = []
        self.aggressive_poll_ongoing_flag = False
        self.aggressive_poll_list_loaded_flag = False
        self.aggressive_poll_list = []
        self.all_poll_loop_count = 0
        self.force_cont_flag = False
    
    def data_snip(self):
        '''
        Using the full node list alongside with filters from gateway node list and poll exempted node list, insert the valid nodes into the real polling queue.
        '''
        try:
            poll_count = 0
            for g in self.node_database_list:
                if g in self.poll_exempt_list:
                    pass
                else:
                    if g in self.gatewaynode_idlist:
                        self.GPS_confirmed_list.append(g)
                    else:
                        poll_count += 1
                        polling_command = '+PM' + g + '\r\n'
                        self.polling_queue.put(polling_command.encode('utf-8'))
            info_string = self.name + '- Poll: ' + str(poll_count) + ' existing nodes in node_database table...'
            self.simple_msg_logger.debug(info_string)
            self.packet_logger.debug(info_string)
        except:
            self.stop()
    
    def data_snip_GPS(self):
        '''
        Using the full node list with filters from GPS received node data ID list, compute the GPS poll checking list 
        '''
        self.GPS_confirmed_list = list(set(self.GPS_confirmed_list))
        if self.GPS_poll_flag:
            self.GPS_poll_list = list(set(self.node_database_list) - set(self.GPS_confirmed_list))
        else:
            self.GPS_poll_list = []
    
    def get_all_poll_loop_count(self):
        return self.all_poll_loop_count
    
    def set_all_poll_loop_count(self):
        self.all_poll_loop_count = 0        
    
    def get_pause_status(self):
        '''Returns to the caller on the pausing status of the whole command sending loop that is triggered due to the port status.'''
        return self.pause_flag
    
    def get_poll_pulse_status(self):
        '''Returns to the caller on the polling cycle looping status (non-blocking), primarily to load in specific non-crucial, but required data in all future loops.'''
        return self.poll_pulse_flag
    
    def get_aggressive_poll_status(self):
        '''Returns to the caller on the flag tuple that indicates the list-loading daily one-time flag and aggressive poll mode status'''
        return (self.aggressive_poll_list_loaded_flag, self.aggressive_poll_ongoing_flag)
    
    def get_GPS_varying_list(self):
        '''
        Returns to the caller on all the node IDs that its GPS varying data has been received within this daily GPS polling cycle.
        In consensus to the packet design, it is more logical to remove a node ID from this list only if a 'GPS confirmed' data can be obtained ('GPS confirmed' can equal GPS varying for a set number of packets as well).
        '''
        return self.GPS_varying_list
    
    def get_GPS_confirmed_list(self):
        '''
        Returns to the caller on all the node IDs that its GPS confirmed data has been received within this daily GPS polling cycle.
        This list ensures that the KML map generated will have a minimum possible amount of GPS data (ideally 1) from the same node in a daily cycle.
        '''
        return self.GPS_confirmed_list
        
    def set_pause_status(self, *args):
        '''Resumes the command sending loop by correcting the pausing status. In the process, the serial port used is reloaded from the caller after the port recovery action is done.'''
        self.pause_flag = False
        self.serial_obj.close()
        self.serial_obj = args[0]
    
    def set_poll_pulse_status(self):
        '''Resets the polling cycle looping status (non-blocking).'''
        self.poll_pulse_flag = True
        
    def set_check_override_off_status(self):
        self.load_override_off_flag = True
    
    def set_aggressive_poll_ongoing_flag(self):
        self.aggressive_poll_ongoing_flag = True
        
    def timeout_aggressive_poll_ongoing(self):
        self.aggressive_poll_ongoing_flag = False
        return self.aggressive_poll_list
    
    def refresh_aggressive_poll_list(self, *args):
        active_dt, aggressivepoll_dt = args
        self.aggressive_poll_list_loaded_flag = True
        poll_count = 0
        residual_aggressive_poll_list, self.aggressive_poll_list = self.DBAligner.select_aggressive_poll_list(active_dt, aggressivepoll_dt)
        info_string = 'Database - Aggressive polling nodes: '+ str(self.aggressive_poll_list)
        self.simple_msg_logger.debug(info_string)
        self.packet_logger.debug(info_string)
        residual_aggressive_poll_list = list(set(residual_aggressive_poll_list))
        for h in self.aggressive_poll_list:
            poll_count += 1
            polling_command = '+PM' + h + '\r\n'
            self.polling_queue.put(polling_command.encode('utf-8'))
        for i in residual_aggressive_poll_list:
            residual_polling_command = '+PM' + i + '\r\n'
            self.residual_polling_queue.put(residual_polling_command.encode('utf-8'))
        info_string = self.name + '- Aggressive Polling: ' + str(poll_count) + ' existing nodes in node_database table...'
        self.simple_msg_logger.debug(info_string)
        self.packet_logger.debug(info_string)
        return poll_count
    
    def timeout_aggressive_poll_list_loaded_flag(self):
        self.aggressive_poll_list_loaded_flag = False
        self.aggressive_poll_list = []
    
    def set_poll_list(self, *args):
        '''
        Loads in the new full node list, and computes all related polling lists, when a situation arise where these lists need to be refreshed. (port switch, daily repositories refresh, etc.)
        However, it does not affect the process in the current main polling cycle if it is already occurring, and all changes reflected in the lists will only be translated to the queues on the next cycle.
        Also starts the paused internal clock monitor_clock to accurately calculate the real polling cycle time used.
        '''
        if args[0] is not None:
            self.node_database_list = args[0]
        if args[1] is not None:
            self.poll_exempt_list = args[1]
        self.data_snip_GPS()
        if self.monitor_clock is not None:
            self.monitor_clock.start()
    
    def set_aggressive_poll_timeframe(self, *args):
        self.active_datetimenow, self.aggressivepoll_datetimenow = args
    
    def set_override_off_timeframe(self, *args):
        '''
        Loads in the date time stamps required for the auto-override OFF monitoring during inactive hours.
        It is required to be refreshed daily for accurate results.
        '''
        self.LMactive_datetimenow, self.nodeoff_datetimenow = args
    
    def refresh_polling_state(self):
        self.all_poll_loop_count = 0
        while self.polling_queue.qsize() > 0:
            if self.interval_sec > 0:
                time.sleep(self.interval_sec/30)
            _ = self.polling_queue.get()
            self.polling_queue.task_done()
        if self.monitor_clock is not None:
            self.monitor_clock.start()
        
    def refresh_override_off_list(self, *args):
        '''
        Using the date time stamps that indicates the active time period for the previous day, the latest data entry for each valid node in the data entry PostgreSQl full node list is computed.
        The function then observes each latest data entry for their supposed logic, and registers the node IDs for those nodes whom had their lamp_status being ON, at a time frame out of this active hours.
        Considering that the data entry is consistently updated and replaced during the active time, this would give enough confidence that this node is still ON and being a day burner on-site, and thus the script will constantly send override OFF commands for this node.
        The process will stop for a node until the system properly registers the last lamp_status of this particular node as OFF during the this inactive period.
        All nodes that are not updated within the last active time frame are also displayed.    
        '''
        LMactive_dt, nodeoff_dt = args
        timenow = time.strftime('%H:%M', time.localtime())
        current_marker = int(timenow[0:2])*60 + int(timenow[3:5])
        if LM_between_flag == 2:
            pass
        elif LM_between_flag == 1:
            if current_marker >= LM_start_marker and current_marker < end_marker:
                self.out_of_timerange_nodelist = []
                self.override_off_poll_list = []
                self.load_override_off_flag = True
            else:
                if self.load_override_off_flag:
                    self.out_of_timerange_nodelist, self.override_off_poll_list = self.DBAligner.select_override_OFF_list(LMactive_dt, nodeoff_dt)
                    self.load_override_off_flag = False
        elif LM_between_flag == 0:
            if current_marker >= end_marker and current_marker < LM_start_marker:
                if self.load_override_off_flag:
                    self.out_of_timerange_nodelist, self.override_off_poll_list = self.DBAligner.select_override_OFF_list(LMactive_dt, nodeoff_dt)
                    self.load_override_off_flag = False
            else:
                self.out_of_timerange_nodelist = []
                self.override_off_poll_list = []
                self.load_override_off_flag = True
        info_string = 'Database - Nodes out of update: '+ str(self.out_of_timerange_nodelist)
        self.simple_msg_logger.debug(info_string)
        self.packet_logger.debug(info_string)
        info_string_2 = 'Database - Nodes currently ON: '+ str(self.override_off_poll_list)
        self.simple_msg_logger.debug(info_string_2)
        self.packet_logger.debug(info_string_2)
    
    def set_GPS_confirmed_list(self):
        '''Resets the historical GPS data received on this day. Aligns with the new daily-generated KML map file.'''
        self.GPS_confirmed_list = []
        self.GPS_varying_list = []
    
    def insert_GPS_confirmed_list(self, old_node_list):
        '''Inherits the historical GPS data received on this day. Aligns with the old daily-generated KML map file.'''
        self.GPS_confirmed_list.extend(old_node_list)
    
    def force_continue_loop(self):
        self.force_cont_flag = True
        
    def freeze_monitor_clock(self):
        '''Pauses the internal clock that calculates the polling cycle time that is triggered due to the port status.'''
        if self.monitor_clock is not None:
            self.monitor_clock.stop()
    
    def status(self):
        return self.stop_event.is_set()        
    
    def clone(self):
        return MainPollingThread(*self.arguments)
    
    def run(self):
        '''
        Functions to be executed once the MainPollingThread is started.
        After carrying out queue and list operations during the start of each polling cycle (changes according to current time), the Thread enters a nested While loop in which the polling cycle is emulated.
        The polling cycle consists of 3 layers of polling - heart beat, GPS and override OFF, depending on the current condition of the node monitoring by the queue-list operations.
        Also computes GPS_varying_list and GPS_confirmed_list as a memory feedback to the main loop for register only unique map data into the KML file.
        At the end of the cycle, if the full loop still has some time before exhausting over the predefined polling cycle time, it will go to sleep at that moment.
        '''
        while not self.stop_event.is_set():
            if self.interval_sec > 0:
                time.sleep(self.interval_sec)
            if self.aggressive_poll_ongoing_flag:
                if self.stop_event.is_set():
                    continue
                self.force_cont_flag = False
                poll_count = self.refresh_aggressive_poll_list(self.active_datetimenow, self.aggressivepoll_datetimenow)
                if poll_count == 0:
                    self.aggressive_poll_ongoing_flag = False
                while self.polling_queue.qsize() > 0:
                    if self.stop_event.is_set():
                        break
                    timenow = time.strftime('%H:%M', time.localtime())
                    current_marker = int(timenow[0:2])*60 + int(timenow[3:5])
                    if not self.force_cont_flag:
                        if self.interval_sec > 0:
                            time.sleep(self.interval_sec/6)
                    if self.pause_flag:
                        # read from somewhere to validate self.pause_flag
                        continue
                    msg = self.polling_queue.get()
                    if self.force_cont_flag:
                        if self.interval_sec > 0:
                            time.sleep(self.interval_sec/30)
                        self.polling_queue.task_done()
                        continue
                    nodeID_searcher = msg.find(b'\r\n')
                    try:
                        if nodeID_searcher == -1:
                            raise
                        node_ID = msg[3:nodeID_searcher].decode('utf-8')
#                         spec_string = 'polling node ' + node_ID
#                         self.packet_logger.debug(spec_string)
                        for _ in range(0, 3):
                            self.serial_obj.write(msg)
                            time.sleep(self.interval_sec/6)
                    except:
                        self.polling_queue.task_done()
                        spec_string = 'Failed to send command ' + msg.decode('utf-8') + '.'
                        self.packet_logger.debug(spec_string)
                        self.problem_logger.info(spec_string)
                        try:
                            fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
                        except:
                            continue
                        self.pause_flag = True
                        continue
                    if self.residual_polling_queue.qsize() > 0:
                        residual_msg = self.residual_polling_queue.get()
                        LP_nodeID_searcher = residual_msg.find(b'\r\n')
                        try:
                            if LP_nodeID_searcher == -1:
                                raise
#                             LP_node_ID = residual_msg[3:LP_nodeID_searcher].decode('utf-8')
#                             spec_string = 'low priority polling node ' + LP_node_ID
#                             self.packet_logger.debug(spec_string)
                            self.serial_obj.write(residual_msg)
                            time.sleep(self.interval_sec/6)
                        except:
                            pass
                        if self.interval_sec > 0:
                            time.sleep(self.interval_sec/6)
                        self.residual_polling_queue.task_done()
                    else:
                        if self.interval_sec > 0:
                            time.sleep(self.interval_sec/3)
                    self.polling_queue.task_done()
                self.all_poll_loop_count += 0.5
            else:
                self.poll_pulse_flag = False
                if self.interval_sec > 0:
                    time.sleep(self.interval_sec)
                self.monitor_clock = Clock()
                self.monitor_clock.start()
                if self.stop_event.is_set():
                    continue
                self.force_cont_flag = False
                self.refresh_override_off_list(self.LMactive_datetimenow, self.nodeoff_datetimenow)
                self.data_snip()
                while self.polling_queue.qsize() > 0:
                    if self.stop_event.is_set():
                        break
                    timenow = time.strftime('%H:%M', time.localtime())
                    current_marker = int(timenow[0:2])*60 + int(timenow[3:5])
                    if not self.force_cont_flag:
                        if self.interval_sec > 0:
                            time.sleep(self.interval_sec/4)
                    if self.pause_flag:
                        # read from somewhere to validate self.pause_flag
                        continue
                    msg = self.polling_queue.get()
                    if self.force_cont_flag:
                        if self.interval_sec > 0:
                            time.sleep(self.interval_sec/30)
                        self.polling_queue.task_done()
                        continue
                    nodeID_searcher = msg.find(b'\r\n')
                    if nodeID_searcher == -1:
                        self.polling_queue.task_done()
                        continue
                    node_ID = msg[3:nodeID_searcher].decode('utf-8')
                    try:
#                         spec_string = 'polling node ' + node_ID
#                         self.simple_msg_logger.debug(spec_string)
                        self.serial_obj.write(msg)
                    except:
                        self.polling_queue.task_done()
                        spec_string = 'Failed to send command ' + msg.decode('utf-8') + '.'
                        self.packet_logger.debug(spec_string)
                        self.problem_logger.info(spec_string)
                        try:
                            fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
                        except:
                            continue
                        self.pause_flag = True
                        continue
                    if self.interval_sec > 0:
                        time.sleep(self.interval_sec/4)
                    if GPS_between_flag == 2:
                        pass
                    elif GPS_between_flag == 1:
                        if current_marker >= GPS_start_marker and current_marker < end_marker:
                            if node_ID in self.GPS_poll_list:
                                try:
                                    GPSpollcommand = b'+TGQ' + node_ID.encode('utf-8') + b'\r\n'
                                    self.serial_obj.write(GPSpollcommand)
                                except:
                                    self.polling_queue.task_done()
                                    spec_string = 'Failed to send command ' + GPSpollcommand.decode('utf-8') + '.'
                                    self.packet_logger.debug(spec_string)
                                    self.problem_logger.info(spec_string)
                                    try:
                                        fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
                                    except:
                                        continue
                                    self.pause_flag = True
                                    continue
                    elif GPS_between_flag == 0:
                        if current_marker >= end_marker and current_marker < GPS_start_marker:
                            pass
                        else:
                            if node_ID in self.GPS_poll_list:
                                try:
                                    GPSpollcommand = b'+TGQ' + node_ID.encode('utf-8') + b'\r\n'
                                    self.serial_obj.write(GPSpollcommand)
                                except:
                                    self.polling_queue.task_done()
                                    spec_string = 'Failed to send command ' + GPSpollcommand.decode('utf-8') + '.'
                                    self.packet_logger.debug(spec_string)
                                    self.problem_logger.info(spec_string)
                                    try:
                                        fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
                                    except:
                                        continue
                                    self.pause_flag = True
                                    continue
                    if self.interval_sec > 0:
                        time.sleep(self.interval_sec/4)
                    if LM_between_flag == 2:
                        pass
                    elif LM_between_flag == 1:
                        if current_marker >= LM_start_marker and current_marker < end_marker:
                            pass
                        else:
                            if OF_between_flag == 0:
                                if current_marker >= end_marker and current_marker < node_end_marker:
                                    try:
                                        widecommand = b'+LM0FFFF\r\n'
                                        self.serial_obj.write(widecommand)
                                        spec_string = 'Actively sending command to override OFF ALL nodes.'
                                        self.simple_msg_logger.debug(spec_string)
                                        self.packet_logger.debug(spec_string)
                                    except:
                                        self.polling_queue.task_done()
                                        spec_string = 'Failed to send command ' + widecommand.decode('utf-8') + '.'
                                        self.packet_logger.debug(spec_string)
                                        self.problem_logger.info(spec_string)
                                        try:
                                            fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
                                        except:
                                            continue
                                        self.pause_flag = True
                                        continue
                                else:
                                    if node_ID in self.override_off_poll_list:
                                        try:
                                            overridecommand = b'+LM1' + node_ID.encode('utf-8') + b'\r\n'
                                            self.serial_obj.write(overridecommand)
                                            offcommand = b'+LCC' + node_ID.encode('utf-8') + b'\r\n'
                                            self.serial_obj.write(offcommand)
                                            spec_string = 'Actively sending command to override OFF' + node_ID + '.'
                                            self.simple_msg_logger.debug(spec_string)
                                            self.packet_logger.debug(spec_string)
                                        except:
                                            self.polling_queue.task_done()
                                            spec_string = 'Failed to send command ' + overridecommand.decode('utf-8') + '.'
                                            self.packet_logger.debug(spec_string)
                                            self.problem_logger.info(spec_string)
                                            spec_string = 'Failed to send command ' + offcommand.decode('utf-8') + '.'
                                            self.packet_logger.debug(spec_string)
                                            self.problem_logger.info(spec_string)
                                            try:
                                                fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
                                            except:
                                                continue
                                            self.pause_flag = True
                                            continue
                    elif LM_between_flag == 0:
                        if current_marker >= end_marker and current_marker < LM_start_marker:
                            if OF_between_flag == 0:
                                if current_marker >= end_marker and current_marker < node_end_marker:
                                    try:
                                        widecommand = b'+LM0FFFF\r\n'
                                        self.serial_obj.write(widecommand)
                                        spec_string = 'Actively sending command to override OFF ALL nodes.'
                                        self.simple_msg_logger.debug(spec_string)
                                        self.packet_logger.debug(spec_string)
                                    except:
                                        self.polling_queue.task_done()
                                        spec_string = 'Failed to send command ' + widecommand.decode('utf-8') + '.'
                                        self.packet_logger.debug(spec_string)
                                        self.problem_logger.info(spec_string)
                                        try:
                                            fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
                                        except:
                                            continue
                                        self.pause_flag = True
                                        continue
                                else:
                                    if node_ID in self.override_off_poll_list:
                                        try:
                                            overridecommand = b'+LM1' + node_ID.encode('utf-8') + b'\r\n'
                                            self.serial_obj.write(overridecommand)
                                            offcommand = b'+LCC' + node_ID.encode('utf-8') + b'\r\n'
                                            self.serial_obj.write(offcommand)
                                            spec_string = 'Actively sending command to override OFF' + node_ID + '.'
                                            self.simple_msg_logger.debug(spec_string)
                                            self.packet_logger.debug(spec_string)
                                        except:
                                            self.polling_queue.task_done()
                                            spec_string = 'Failed to send command ' + overridecommand.decode('utf-8') + '.'
                                            self.packet_logger.debug(spec_string)
                                            self.problem_logger.info(spec_string)
                                            spec_string = 'Failed to send command ' + offcommand.decode('utf-8') + '.'
                                            self.packet_logger.debug(spec_string)
                                            self.problem_logger.info(spec_string)
                                            try:
                                                fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
                                            except:
                                                continue
                                            self.pause_flag = True
                                            continue
                    if self.GPS_confirmed_queue.qsize() > 0:
                        msg, condition = self.GPS_confirmed_queue.get()
                        if condition == 'A':
                            self.GPS_confirmed_list.append(msg)
                            if msg in self.GPS_varying_list:
                                self.GPS_varying_list.remove(msg)
                        else:
                            if msg in self.GPS_varying_list:
                                pass
                            else:
                                self.GPS_varying_list.append(msg)
                        self.GPS_confirmed_queue.task_done()
                    if self.interval_sec > 0:
                        time.sleep(self.interval_sec/4)
                    self.polling_queue.task_done()
                process_time = float(self.monitor_clock)
                self.monitor_clock.stop()
                if process_time > self.cycle_sec:
                    if self.stop_event.is_set():
                        continue
                    warning_string = 'Total polling cycle time more than preset cycle time! Packet return times are now unpredictable.'
                    self.packet_logger.debug(warning_string)
                    self.simple_msg_logger.warning(warning_string)
                    self.all_poll_loop_count += 1.0
                    if self.interval_sec > 0:
                        time.sleep(self.interval_sec)
                else:
                    if self.stop_event.is_set():
                        continue
                    time_remaining = self.cycle_sec - process_time
                    if self.interval_sec > 0:
                        for_cycles = round(time_remaining/self.interval_sec)
                    else:
                        for_cycles = round(time_remaining)
                    spec_string = 'Network free time: ' + str(time_remaining)
                    self.packet_logger.debug(spec_string)
                    self.simple_msg_logger.debug(spec_string)
                    self.all_poll_loop_count += 1.0
                    if self.interval_sec > 0:
                        for _ in range(0, for_cycles):
                            if self.stop_event.is_set():
                                break
                            time.sleep(self.interval_sec)
                    else:
                        for _ in range(0, for_cycles):
                            if self.stop_event.is_set():
                                break
    def stop(self):
        '''Functions to be executed if an unexpected exit has occurred, to both the super thread or the overall script. Stop event is set to cleanly exit the super thread.'''
        self.stop_event.set()

