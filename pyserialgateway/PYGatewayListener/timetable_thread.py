'''
TimetableThread: verifies node timezone/timetable configuration against
listened packets.
'''
import datetime
import threading

class TimetableThread(threading.Thread):
    def __init__(self, packet_logger, problem_logger, reset_queue_obj, record_queue_obj, TT_query_queue_obj, label, node_list, node_datalist):
        super(TimetableThread, self).__init__()
        self.packet_logger = packet_logger
        self.problem_logger = problem_logger
        self.reset_queue = reset_queue_obj
        self.record_queue = record_queue_obj
        self.TT_query_queue = TT_query_queue_obj
        self.label = label
        self.node_list = node_list
        self.node_datalist = node_datalist
        self.stop_event = threading.Event()
        self.name = 'TimetableConfig'
        self.EOF_string = b'+'
        self.alt_EOF_string = b'-'
    
    def timezone_verification(self, nodelist, nodedatalist):
        try:
            next_datalist = []
            final_problem_node_list = []
            final_reset_node_list = []
            dict_log = {}
            if len(nodelist) != len(nodedatalist):
                raise
            else:
                for x in range(0, len(nodelist)):
                    # GPS time check on packet data
                    log_label = self.label + '/' + nodelist[x]
                    packet_data_list = nodedatalist[x].split(b'|')
                    temp_dict_pkt_time = {}
                    temp_list_pkt_time = []
                    time_runoff_conf_count = 0
                    for ind,info in enumerate(packet_data_list[3].split(b'-')):
                        temp_dict_pkt_time[ind] = list(map(int,info.split(b':')))
                    for items in list(temp_dict_pkt_time.values()):
                        temp_list_pkt_time += items
                    packet_TP = list(datetime.datetime.utcnow().timetuple())[2:6]
                    for ind,time_item in enumerate(temp_list_pkt_time):
                        temp_list_pkt_time[ind] = abs(packet_TP[ind] - time_item)
                    for threshold_val in temp_list_pkt_time:
                        if threshold_val > 0:
                            time_runoff_conf_count += 1
                    if time_runoff_conf_count > 3:
                        final_reset_node_list.append(nodelist[x])
                        info_string = b'GPS time not updated, ' + nodedatalist[x]
                        dict_log[log_label] = info_string
                        continue
                    # Timezone check on packet data
                    TT_EOF_packet_searcher = nodedatalist[x].find(self.EOF_string)
                    TT_alt_EOF_packet_searcher = nodedatalist[x].find(self.alt_EOF_string)
                    if TT_EOF_packet_searcher != -1:
                        try:
                            timezone = (nodedatalist[x][TT_EOF_packet_searcher:TT_EOF_packet_searcher+3]).decode('utf-8')
                            info_string = 'TT data for node ' + nodelist[x] + ': ' + timezone   
                            self.packet_logger.info(info_string)
                            timezone_PN = timezone[0:1]
                            timezone_VAL = int(timezone[1:len(timezone)])
                        except:
                            info_string = 'Time zone values corrupt - unreadable packet' + nodedatalist[x]
                            self.problem_logger.info(info_string)
                            continue
                        if timezone_PN != '+' or timezone_VAL != 8:
                            final_problem_node_list.append(nodelist[x])
                            info_string = b'Time zone configuration incorrect, resetting to GMT+08: ' + nodedatalist[x]
                            dict_log[log_label] = info_string
                            continue
                        next_datalist.append((nodelist[x], nodedatalist[x]))
                    else:
                        if TT_alt_EOF_packet_searcher != -1:
                            try:
                                timezone = (nodedatalist[x][TT_alt_EOF_packet_searcher:TT_alt_EOF_packet_searcher+3]).decode('utf-8')
                                info_string = 'TT data for node ' + nodelist[x] + ': ' + timezone   
                                self.packet_logger.info(info_string)
                                timezone_PN = timezone[0:1]
                                timezone_VAL = int(timezone[1:len(timezone)])
                            except:
                                info_string = 'Time zone values corrupt - unreadable packet'
                                self.problem_logger.info(info_string)
                                continue
                            if timezone_PN != '-' or timezone_VAL != 8:
                                final_problem_node_list.append(nodelist[x])
                                info_string = b'Time zone configuration incorrect, resetting to GMT+08: ' + nodedatalist[x]
                                dict_log[log_label] = info_string
                                continue
                            next_datalist.append((nodelist[x], nodedatalist[x]))
            # Reset and record data placements
            dict_items = list(dict_log.items())
            final_problem_node_list = list(set(final_problem_node_list))
            if self.record_queue is not None and len(dict_items) >= 1:
                for z in range(0, len(dict_items)):
                    self.record_queue.put(dict_items[z])
            if len(final_problem_node_list) >= 1:
                for y in range(0, len(final_problem_node_list)):
                    settings_cmd = '+CA50CD66E76060B00' + final_problem_node_list[y] + '0018' + '7FFE5A' + '\r\n'
                    self.TT_query_queue.put(settings_cmd.encode('utf-8'))
            if len(final_reset_node_list) >= 1:
                for x in range(0, len(final_reset_node_list)):
                    reset_cmd = '+TRS' + final_reset_node_list[x] + '\r\n'
                    self.reset_queue.put(reset_cmd.encode('utf-8'))
        except:
            return None
        return next_datalist
    
    def run(self):
        try:
            for g in range(0, len(self.node_datalist)):
                self.packet_logger.info(self.node_datalist[g])
            _ = self.timezone_verification(self.node_list, self.node_datalist)
        except:
            self.stop()
    
    def stop(self):
        self.stop_event.set()
        

