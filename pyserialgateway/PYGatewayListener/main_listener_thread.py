'''
MainListenerThread: reads and snips one raw serial packet, then dispatches
it to GPSThread, RecoveryThread, and/or TimetableThread depending on its
label.
'''
import re
import threading

from .gps_thread import GPSThread
from .recovery_thread import RecoveryThread
from .timetable_thread import TimetableThread

class MainListenerThread(threading.Thread):
    '''
    The only super-type Thread which is spawned by the Main loop, and can be created in multiples asynchronously with the ability to manage its own variables and resources.
    A threading manager is also dedicated to the main loop to monitor each MainListenerThread's status and helps to close and exit the thread safely via the Main loop.
    The manager is required because this MainListenerThread will spawn more sub-threads according to message type listened here. 
    These are described as sub-processes which flows as below:-
                         +---------------------+ -> G0 packets --> GPSThread       -> good data --> GPSDatabaseThread -> requires action --> +--------------------+
    Raw data packets --> | MainListenerThreads | -> P0 packets --> TimetableThread -> ---------------------------------> requires action --> | Other Main Threads |
                         +---------------------+ -> all others --> RecoveryThread  -> good data --> DatabaseThread    -> requires action --> +--------------------+
                                                                  (Recovery Stage)                    (DB Stage)                                    (Feedback Control Action)
    Functionalities:-
    1. Serial node hang checker, where it will prompt the Main loop to reassign serial port once a node hang condition is detected from its listening packets.
    2. Data filter, removes all duplicated data within an instance to create unique, good data that is to be processed in the DB stage.
    3. Threading manager for sub-threads in the Recovery stage and subsequently the DB stage.
    '''
    def __init__(self, demo_flag, packet_logger, problem_logger, queue_obj, record_queue_obj, message_queue_obj, GPS_confirmed_queue_obj, reset_G0_confirmed_queue_obj, TT_query_queue_obj, node_database_list, gatewaynode_idlist, port_data, raw_data, serial_port, reject_labels, accept_labels, kml_doc, kml_doc_element, poll_thread_obj, reset_thread_obj):
        '''Start up variables taken from INIT arguments. Also starts up Event control functions and port control variables.'''
        super(MainListenerThread, self).__init__()
        self.demo_flag = demo_flag
        self.packet_logger = packet_logger
        self.problem_logger = problem_logger
        self.reset_queue = queue_obj
        self.record_queue = record_queue_obj
        self.msg_queue = message_queue_obj
        self.GPS_confirmed_queue = GPS_confirmed_queue_obj
        self.reset_G0_confirmed_queue = reset_G0_confirmed_queue_obj
        self.TT_query_queue = TT_query_queue_obj
        self.node_database_list = node_database_list
        self.gatewaynode_idlist = gatewaynode_idlist
        self.port_data = port_data
        self.packet = raw_data
        self.serial_obj = serial_port
        self.reject_labels = reject_labels
        self.accept_labels = accept_labels
        self.kml_doc = kml_doc
        self.kml_doc_element = kml_doc_element
        self.poll_t = poll_thread_obj
        self.reset_t = reset_thread_obj
        self.stop_event = threading.Event()
        self.EOF_string = b'\r\n#'
        self.EOF_packet = b'#\r\n'
        self.name = 'MainListener'
        self.pause_flag = False
    
    def status(self):
        '''Returns the Thread current status to the caller so that the caller can clean all inactive MainListenerThreads when needed.'''
        return self.stop_event.is_set()
    
    def get_pause_status(self):
        '''Returns to the caller on the pausing status of the whole command sending loop that is triggered due to the port status.'''
        return self.pause_flag
    
    def checkserialhang(self):
        '''
        Filters out part of packet which contains active sending commands when available.
        If that part of the packet is cannot be decoded by standard means, it returns the Serial port reset prompt back to the caller.
        '''
        hang_flag = False
        command_searcher = self.packet.find(b'+')
        if command_searcher == -1:
            pass
        else:
            packet_portion = self.packet[command_searcher:len(self.packet)+1]
            searcher_stringend = packet_portion.find(self.EOF_string)
            if searcher_stringend == -1:
                pass
            else:
                packet_portion = packet_portion[0:searcher_stringend]
            try:
                _ = packet_portion.decode('utf-8')
            except:
                hang_flag = True
        return hang_flag
    
    def data_headerfilter(self):
        '''
        Filter starts from the start of the packet. Dumps packet data until it reaches the header of one of the known accepted labels.
        Helps to remove possible truncated/cross-appended packets in which its data structure is abnormal. 
        '''
        try:
            searcher_list = []
            if len(self.accept_labels) >= 1:
                for i in range(0, len(self.accept_labels)):
                    full_label = '#' + self.accept_labels[i] + '|'
                    searcher_label = self.packet.find(full_label.encode('utf-8'))
                    if searcher_label == -1:
                        searcher_label = 50000
                    searcher_list.append(searcher_label)
            else:
                raise
            if min(searcher_list) == 50000:
                raise
            else:
                packet_frontcut = self.packet[min(searcher_list):len(self.packet)+1]
                return packet_frontcut
        except:
            return None
            self.stop()
    
    def data_endfilter(self, packet_cut, verified_rawpacket):
        '''
        Using all known rejected labels, if such data are still present and not filtered within data_headerfilter, will be filtered out from the packet, remaining with only the valid data packets. 
        '''
        try:
            reject_indices_list = []
            if len(self.reject_labels) >= 1:
                for i in range(0, len(self.reject_labels)):
                    full_label = '#' + self.reject_labels[i] + '|'
                    searcher_label = packet_cut.find(full_label.encode('utf-8'))
                    if searcher_label == -1:
                        pass
                    else:
                        reject_indices_list.append(searcher_label)
                if len(reject_indices_list) == 0:
                    verified_rawpacket = packet_cut
                    packet_cut = b''
                elif len(reject_indices_list) > 0:
                    if min(reject_indices_list) == 0:
                        searcher_stringend = packet_cut.find(self.EOF_string)
                        if searcher_stringend == -1:
                            packet_cut = b''
                        else:
                            packet_cut = packet_cut[searcher_stringend+2:len(packet_cut)+1]
                    else:
                        verified_rawpacket += packet_cut[0:reject_indices_list[0]-2]
                        packet_cut = packet_cut[reject_indices_list[0]:len(packet_cut)+1]
                else:
                    raise                # impossible condition
            else:
                verified_rawpacket = packet_cut
                packet_cut = b''
        except:
            self.stop()
        return (packet_cut, verified_rawpacket)
    
    def packet_snipping(self, target_string, full_label):
        '''
        Using all known accepted labels, if such label and end-of-string is present in the data packet, the data will be taken out of the full data packet structure.
        These data are then extracted of their node IDs, and tagged alongside its data at indices in separate lists. 
        '''
        j_list = []
        k_list = []
        j_index = 0
        k_index = 0
        node_list = []
        node_datalist = []
        for j in re.finditer(full_label.encode('utf-8'), target_string):
            if j.start() != j.end():
                j_list.append(j.start())
        for k in re.finditer(self.EOF_packet , target_string):
            if k.start() != k.end():
                k_list.append(k.start())
        if len(j_list) >= len(k_list):
            if len(k_list) != 0:
                for m in range(0, len(k_list)):
                    for l in range(0, len(j_list)):
                        if j_list[l] < k_list[m]:
                            j_index += 1
                    target_string_cut1 = target_string[j_list[j_index-1]+4:len(target_string)+1]
                    searcher_ID_target_string = target_string_cut1.find(b'|')
                    if searcher_ID_target_string == -1:
                        continue
                    else:
                        node_ID = target_string_cut1[0:searcher_ID_target_string]
                        try:
                            node_list.append(node_ID.decode('utf-8'))
                            node_datalist.append(target_string[j_list[j_index-1]:k_list[m]+1])
                        except:
                            continue
                    j_index = 0
        else:
            if len(j_list) != 0:
                for l in range(0, len(j_list)):
                    for m in range(0, len(k_list)):
                        if k_list[m] < j_list[l]:
                            k_index += 1
                    target_string_cut1 = target_string[j_list[l]+4:len(target_string)+1]
                    searcher_ID_target_string = target_string_cut1.find(b'|')
                    if searcher_ID_target_string == -1:
                        continue
                    else:
                        node_ID = target_string_cut1[0:searcher_ID_target_string]
                        try:
                            node_list.append(node_ID.decode('utf-8'))
                            node_datalist.append(target_string[j_list[l]:k_list[k_index]+1])
                        except:
                            continue
                    k_index = 0
        return node_list, node_datalist
    
    def run(self):
        '''
        Functions to be executed once the MainListenerThread is started.
        Carries out the Serial port and data packet processes sequentially to generate a list of individual, valid data packets.
        All data packets are then redirected to sub-threads in the different branched processes. 
        '''
        try:
            analysis_threads = []
            GPS_threads = []
            hang_flag = self.checkserialhang()
            if hang_flag is True:
                self.serial_obj.gateway_reset_stop2bits()
                error_string = 'Node hang - resetting gateway node with 2 stop bits.'
                self.packet_logger.debug(error_string)
                self.problem_logger.info(error_string)
                self.pause_flag = True
                raise        
            packet_cut1 = self.data_headerfilter()
            if packet_cut1 is None:
                raise
            verified_rawpacket = b''
            while packet_cut1 != b'':            # recursive call to function until whole packet is verified
                packet_cut1, verified_rawpacket = self.data_endfilter(packet_cut1, verified_rawpacket)
            if verified_rawpacket != b'':
                for i in range(0, len(self.accept_labels)):            # segregate full verified packet into different data lists (data lists MUST BE DECRYPTED)
                    if self.accept_labels[i].find('G0') != -1:
                        node_list, node_datalist = self.packet_snipping(verified_rawpacket, '#G0|')
                        if len(node_list) > 0:
                            GPS_analysis_t = GPSThread(self.packet_logger, self.problem_logger, self.GPS_confirmed_queue, self.record_queue, self.accept_labels[i], self.node_database_list, self.port_data, self.poll_t, node_list, node_datalist, self.kml_doc, self.kml_doc_element)
                            info_string = 'Running data analysis on received ' + self.accept_labels[i] + ' packets.'
                            self.packet_logger.info(info_string)
                            GPS_analysis_t.start()
                            GPS_threads.append(GPS_analysis_t)
                    elif self.accept_labels[i].find('P0') != -1:
                        node_list, node_datalist = self.packet_snipping(verified_rawpacket, '#P0|')
                        if len(node_list) > 0:
                            TT_analysis_t = TimetableThread(self.packet_logger, self.problem_logger, self.reset_queue, self.record_queue, self.TT_query_queue, self.accept_labels[i], node_list, node_datalist)
                            info_string = 'Running data analysis on received ' + self.accept_labels[i] + ' packets.'
                            self.packet_logger.info(info_string)
                            TT_analysis_t.start()
                            analysis_threads.append(TT_analysis_t)
                    else:
                        full_label = '#' + self.accept_labels[i] + '|'
                        node_list, node_datalist = self.packet_snipping(verified_rawpacket, full_label)
                        if len(node_list) > 0:
                            analysis_t = RecoveryThread(self.demo_flag, self.packet_logger, self.problem_logger, self.reset_queue, self.record_queue, self.msg_queue, self.reset_G0_confirmed_queue, self.node_database_list, self.gatewaynode_idlist, self.accept_labels[i], self.poll_t, self.reset_t, node_list, node_datalist)
                            info_string = 'Running data analysis on received ' + self.accept_labels[i] + ' packets.'
                            self.packet_logger.info(info_string)
                            analysis_t.start()
                            analysis_threads.append(analysis_t)
                for threads in analysis_threads:
                    threads.join()
                for threads in GPS_threads:
                    threads.join()
                self.stop()            
            else:
                raise
        except:
            self.stop()
    
    def stop(self):
        '''Functions to be executed if an unexpected exit has occurred, to both the super thread or the overall script. Stop event is set to cleanly exit the super thread.'''
        self.stop_event.set()

