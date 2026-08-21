'''
RecoveryThread: filters/validates a batch of packets by node ID, timing,
and duplicates, then hands confirmed data off to DatabaseThread.
'''
import time
import datetime
import threading

from .database_thread import DatabaseThread
from .config import (
    msgID, max_msgID_count, off_state_wattage,
    LM_between_flag, LM_start_marker, end_marker,
    between_flag, start_marker,
)

class RecoveryThread(threading.Thread):
    def __init__(self, demo_flag, packet_logger, problem_logger, queue_obj, record_queue_obj, message_queue_obj, reset_G0_confirmed_queue_obj, node_database_list, gatewaynode_idlist, label, poll_thread_obj, reset_thread_obj, node_list, node_datalist):
        super(RecoveryThread, self).__init__()
        self.demo_flag = demo_flag
        self.packet_logger = packet_logger
        self.problem_logger = problem_logger
        self.reset_queue = queue_obj
        self.record_queue = record_queue_obj
        self.msg_queue = message_queue_obj
        self.reset_G0_confirmed_queue = reset_G0_confirmed_queue_obj
        self.node_database_list = node_database_list
        self.gatewaynode_idlist = gatewaynode_idlist
        self.label = label
        self.poll_t = poll_thread_obj
        self.reset_t = reset_thread_obj
        self.node_list = node_list
        self.node_datalist = node_datalist
        self.stop_event = threading.Event()
        self.name = 'Recovery'
        self.pending_verify_E1_list = []
        self.GPS_cfm_list = []
    
    def ID_filtering(self, nodelist, nodedatalist):
        try:
            next_datalist = []
            dict_log = {}
            mini_problem_list = []
            try_new_install_list = []
            if len(nodelist) != len(nodedatalist):
                raise
            else:
                for x in range(0, len(nodelist)):
                    log_label = self.label + '/' + nodelist[x]
                    # node ID checking
                    try:
                        int_pktnodeID = int(nodelist[x],16)
                    except ValueError:
                        continue
                    if nodelist[x] in self.node_database_list:
                        pass
                    else:
                        if int_pktnodeID == 0:
                            error_string = b'Node ID zero, ' + nodedatalist[x]
                            dict_log[log_label] = error_string
                        else:
                            error_string = b'Node ID invalid, ' + nodedatalist[x]
                            dict_log[log_label] = error_string
                            try_new_install_list.append(nodelist[x])
                        mini_problem_list.append(nodelist[x])
                        continue
                    # message ID (first layer) checking
                    searcher_msgID = nodedatalist[x].find(nodelist[x].encode('utf-8') + b'|')
                    if searcher_msgID == -1:
                        continue
                    else:
                        try:
                            int_pktmsgID_vers = int(nodedatalist[x][searcher_msgID+len(nodelist[x])+1:searcher_msgID+len(nodelist[x])+1+len(msgID[0])], 16)
                            int_pktmsgID = int(nodedatalist[x][searcher_msgID+len(nodelist[x])+1+len(msgID[0]):searcher_msgID+len(nodelist[x])+1+len(msgID)])
                        except ValueError:
                            continue
                        if int_pktmsgID_vers == 0:
                            next_datalist.append((nodelist[x], nodedatalist[x]))
                        elif int_pktmsgID_vers > 0 and int_pktmsgID <= max_msgID_count:
                            next_datalist.append((nodelist[x], nodedatalist[x]))
                        else:
                            error_string = b'Message ID corrupted, ' + nodedatalist[x]
                            dict_log[log_label] = error_string
                            mini_problem_list.append(nodelist[x])
                    # Packet length check according to msgID version will be implemented post decryption
            # Reset and error message placements
            dict_items = list(dict_log.items())
            mini_problem_list = list(set(mini_problem_list))
            try_new_install_list = list(set(try_new_install_list))
            # For new installations, poll for G0 when a new node ID (out of DB) is detected - takes place in self.TT_query_queue
            if len(try_new_install_list) >= 1 and self.label.find('E1') != -1:
                for x in range(0, len(try_new_install_list)):
                    if try_new_install_list[x] in self.pending_verify_E1_list:
                        if try_new_install_list[x] not in self.GPS_cfm_list:
                            LP_echolocation_cmd = '+TGQ' + try_new_install_list[x] + '\r\n'
                            self.reset_queue.put(LP_echolocation_cmd.encode('utf-8'))
            if len(mini_problem_list) >= 1 and self.label.find('H') != -1:
                for y in range(0, len(mini_problem_list)):
                    if self.label.find('H2') != -1:
                        self.reset_G0_confirmed_queue.put(mini_problem_list[y])
                    reset_cmd = '+TRS' + mini_problem_list[y] + '\r\n'
                    self.reset_queue.put(reset_cmd.encode('utf-8'))
            if self.record_queue is not None and len(dict_items) >= 1:
                for z in range(0, len(dict_items)):
                    self.record_queue.put(dict_items[z])
        except:
            return None
        return next_datalist
    
    def time_filtering(self, nodelist, nodedatalist):
        try:
            next_datalist = []
            dict_log = {}
            mini_problems_list = []
            override_control_list = []
            timetable_problem_list = []
            packet_date_index = [31, 23, 59, 59]
            if len(nodelist) != len(nodedatalist):
                raise 
            else:
                for x in range(0, len(nodelist)):
                    log_label = self.label + '/' + nodelist[x]
                    # day-hour time checking
                    searcher_timestamp = nodedatalist[x].find(nodelist[x].encode('utf-8') + b'|')
                    searcher_day = nodedatalist[x].find(b'-')
                    searcher_hr = nodedatalist[x].find(b':')
                    if searcher_timestamp == -1 or searcher_day == -1 or searcher_hr == -1:
                        mini_problems_list.append(nodelist[x])
                        dict_log[log_label] = b'Day-hour time index not found, ' + nodedatalist[x]
                        continue
                    elif searcher_day-(searcher_timestamp+len(nodelist[x])+1+len(msgID)+1) != 2 or searcher_hr-(searcher_day+1) != 2:
                        mini_problems_list.append(nodelist[x])
                        dict_log[log_label] = b'Day/hour time values corrupted, ' + nodedatalist[x]
                        continue
                    try:
                        pktmsgID = (nodedatalist[x][searcher_timestamp+len(nodelist[x])+1:searcher_timestamp+len(nodelist[x])+1+len(msgID)]).decode('utf-8')
                        day = int(nodedatalist[x][searcher_timestamp+len(nodelist[x])+1+len(msgID)+1:searcher_day])
                        hr = int(nodedatalist[x][searcher_day+1:searcher_hr])
                    except:
                        mini_problems_list.append(nodelist[x])
                        dict_log[log_label] = b'Day/hour time values not integer, ' + nodedatalist[x]
                        continue
                    # minute-second time checking
                    nodedatalist_cut1 = nodedatalist[x][searcher_hr+1:len(nodedatalist[x])+1]
                    searcher_min = nodedatalist_cut1.find(b':')
                    searcher_sec = nodedatalist_cut1.find(b'|')
                    if searcher_min == -1 or searcher_sec == -1:
                        mini_problems_list.append(nodelist[x])
                        dict_log[log_label] = b'Min-sec time index not found, ' + nodedatalist[x]
                        continue
                    elif searcher_min != 2 or searcher_sec != 5:
                        mini_problems_list.append(nodelist[x])
                        dict_log[log_label] = b'Min/sec time values corrupted, ' + nodedatalist[x]
                        continue
                    try:
                        mnt = int(nodedatalist_cut1[0:searcher_min])
                        sec = int(nodedatalist_cut1[searcher_min+1:searcher_sec])
                    except:
                        mini_problems_list.append(nodelist[x])
                        dict_log[log_label] = b'Min/sec time values not integer, ' + nodedatalist[x]
                        continue
                    # Overall time checking
                    packet_TP = [day, hr, mnt, sec]
                    TP_checksum = 0
                    for y in range(0, len(packet_TP)):
                        if packet_TP[y] > packet_date_index[y]:
                            pass
                        else:
                            TP_checksum += 1
                    if TP_checksum != len(packet_TP):
                        mini_problems_list.append(nodelist[x])
                        dict_log[log_label] = b'Time value corrupted (beyond time range), ' + nodedatalist[x]
                        continue
                    # Generate dtime for DB return
                    if packet_TP[0] == 0:
                        packet_TP = list(datetime.datetime.utcnow().timetuple())[2:6]
                        hr = packet_TP[1]
                        mnt = packet_TP[2]
                        sec = packet_TP[3]
                        dtime = datetime.datetime.fromtimestamp(time.mktime(time.localtime())+time.timezone).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        time_runoff_conf_count = 0
                        datestamp_y = str(datetime.datetime.utcnow().timetuple().tm_year)
                        datestamp_m = str(datetime.datetime.utcnow().timetuple().tm_mon)
                        temp_list_pkt_time = list(datetime.datetime.utcnow().timetuple())[2:6]
                        for ind,time_item in enumerate(temp_list_pkt_time):
                            temp_list_pkt_time[ind] = abs(packet_TP[ind] - time_item)
                        for threshold_val in temp_list_pkt_time:
                            if threshold_val > 0:
                                time_runoff_conf_count += 1
                        if time_runoff_conf_count > 3:
                            tt_index = int(nodedatalist[x].split(b'|')[13])
                            timetable_problem_list.append((nodelist[x], tt_index))
                            dict_log[log_label] = b'Lamp auto-off - verifying TT and time, ' + nodedatalist[x]
                        while len(datestamp_m) != 2:
                            datestamp_m = '0' + datestamp_m
                        for p in range(0, len(packet_TP)):
                            packet_TP[p] = str(packet_TP[p])
                            while len(packet_TP[p]) != 2:
                                packet_TP[p] = '0' + packet_TP[p]
                        dtime = datestamp_y + '-' + datestamp_m + '-' + packet_TP[0] + ' ' + packet_TP[1] + ':' + packet_TP[2] + ':' + packet_TP[3]
                    # lantern status check
                    MY_timediff = int((-1)*(time.timezone/3600))
                    hr += MY_timediff
                    if hr > 24:
                        hr = hr-24
                    current_marker = hr*60 + mnt
                    try:
                        raw_byte_back_data = nodedatalist_cut1.replace(b'#',b'')
                        split_raw_byte_back_data = raw_byte_back_data.split(b'|')
                        ctrl_mode = int(split_raw_byte_back_data[11])
                        lamp_effstatus = int(split_raw_byte_back_data[12])
                        node_DC5V_string = split_raw_byte_back_data[14]
                        node_voltage_string = split_raw_byte_back_data[15]
                        node_current_string = split_raw_byte_back_data[16]
                        node_wattage_string = split_raw_byte_back_data[17]
                        node_pf_string = split_raw_byte_back_data[18]
                        if len(node_DC5V_string) > 5 or len(node_voltage_string) > 6 or len(node_current_string) > 5 or len(node_wattage_string) > 5 or len(node_pf_string) > 5:
                            raise
                        else:
                            node_wattage = float(node_wattage_string)
                    except:
                        mini_problems_list.append(nodelist[x])
                        dict_log[log_label] = b'Lamp status unreadable - packet corrupt, ' + nodedatalist[x]
                        continue
                    if self.demo_flag == False:
                        if self.label.find('H') != -1:
                            if LM_between_flag == 2:
                                pass
                            elif LM_between_flag == 1:
                                try:
                                    if current_marker >= LM_start_marker and current_marker < end_marker:
                                        if ctrl_mode == 1:
                                            if lamp_effstatus == 1:
                                                override_control_list.append('+LM0' + nodelist[x])
                                                dict_log[log_label] = b'Disabling lamp override since GPS is found.'
                                            elif lamp_effstatus == 0:
                                                override_control_list.append('+LCB' + nodelist[x])
                                                dict_log[log_label] = b'Lamp override previously, turning ON lamp.'
                                                continue
                                            elif lamp_effstatus == 2 and day == 0:
                                                override_control_list.append('+LCB' + nodelist[x])
                                                dict_log[log_label] = b'Lamp override previously, turning ON lamp.'
                                    else:
                                        if day == 0:
                                            if lamp_effstatus == 2:
                                                override_control_list.append('+LCC' + nodelist[x])
                                                override_control_list.append('+LM1' + nodelist[x])
                                                dict_log[log_label] = b'GPS time sync fail, initiating lamp override + OFF.'
                                            elif lamp_effstatus == 1:
                                                override_control_list.append('+LCC' + nodelist[x])
                                                override_control_list.append('+LM1' + nodelist[x])
                                                dict_log[log_label] = b'GPS time sync fail, initiating lamp override + OFF.'
                                                continue
                                        else:
                                            if ctrl_mode == 1:
                                                if lamp_effstatus == 0:
                                                    override_control_list.append('+LM0' + nodelist[x])
                                                    dict_log[log_label] = b'Disabling lamp override since GPS is found.'
                                                elif lamp_effstatus == 1:
                                                    override_control_list.append('+LCC' + nodelist[x])
                                                    dict_log[log_label] = b'Lamp override previously, turning OFF lamp.'
                                                    continue
                                                elif lamp_effstatus == 2:
                                                    override_control_list.append('+LCC' + nodelist[x])
                                                    dict_log[log_label] = b'Lamp override previously, turning OFF lamp.'
                                except:
                                    pass
                            elif LM_between_flag == 0:
                                try:
                                    if current_marker >= end_marker and current_marker < LM_start_marker:
                                        if day == 0:
                                            if lamp_effstatus == 2:
                                                override_control_list.append('+LCC' + nodelist[x])
                                                override_control_list.append('+LM1' + nodelist[x])
                                                dict_log[log_label] = b'GPS time sync fail, initiating lamp override + OFF.'
                                            elif lamp_effstatus == 1:
                                                override_control_list.append('+LCC' + nodelist[x])
                                                override_control_list.append('+LM1' + nodelist[x])
                                                dict_log[log_label] = b'GPS time sync fail, initiating lamp override + OFF.'
                                                continue
                                        else:
                                            if ctrl_mode == 1:
                                                if lamp_effstatus == 0:
                                                    override_control_list.append('+LM0' + nodelist[x])
                                                    dict_log[log_label] = b'Disabling lamp override since GPS is found.'
                                                elif lamp_effstatus == 1:
                                                    override_control_list.append('+LCC' + nodelist[x])
                                                    dict_log[log_label] = b'Lamp override previously, turning OFF lamp.'
                                                    continue
                                                elif lamp_effstatus == 2:
                                                    override_control_list.append('+LCC' + nodelist[x])
                                                    dict_log[log_label] = b'Lamp override previously, turning OFF lamp.'
                                    else:
                                        if ctrl_mode == 1:
                                            if lamp_effstatus == 1:
                                                override_control_list.append('+LM0' + nodelist[x])
                                                dict_log[log_label] = b'Disabling lamp override since GPS is found.'
                                            elif lamp_effstatus == 0:
                                                override_control_list.append('+LCB' + nodelist[x])
                                                dict_log[log_label] = b'Lamp override previously, turning ON lamp.'
                                                continue
                                            elif lamp_effstatus == 2 and day == 0:
                                                override_control_list.append('+LCB' + nodelist[x])
                                                dict_log[log_label] = b'Lamp override previously, turning ON lamp.'
                                except:
                                    pass    
                    # lantern active timetable/time zone & power check
                    try:
                        if between_flag == 2:
                            pass
                        elif between_flag == 1:
                            if current_marker >= start_marker and current_marker < end_marker:
                                if lamp_effstatus == 0:
                                    if nodelist[x] in self.gatewaynode_idlist:
                                        pass
                                    else:
                                        if node_wattage < off_state_wattage and ctrl_mode == 0:
                                            searcher_msgID = nodedatalist[x].find(nodelist[x].encode('utf-8') + b'|')
                                            try:
    #                                             int_pktmsgID_vers = int(nodedatalist[x][searcher_msgID+len(nodelist[x])+1:searcher_msgID+len(nodelist[x])+1+len(msgID[0])], 16)
                                                int_pktmsgID = int(nodedatalist[x][searcher_msgID+len(nodelist[x])+1+len(msgID[0]):searcher_msgID+len(nodelist[x])+1+len(msgID)])
                                                if int_pktmsgID != 0:
                                                    tt_index = int(nodedatalist[x].split(b'|')[13])
                                                    timetable_problem_list.append((nodelist[x], tt_index))
                                                    dict_log[log_label] = b'Lamp auto-off - verifying TT, ' + nodedatalist[x]
                                                else:
                                                    mini_problems_list.append(nodelist[x])
                                                    dict_log[log_label] = b'Lamp auto-off - resetting node, ' + nodedatalist[x]
                                            except ValueError:
                                                pass
                                elif lamp_effstatus == 1 or lamp_effstatus == 2:
                                    pass
                                else:
                                    mini_problems_list.append(nodelist[x])
                                    dict_log[log_label] = b'Lamp status not OFF nor ON/DIM - packet corrupt, ' + nodedatalist[x]
                                    continue
                            else:
                                pass
                        elif between_flag == 0:
                            if current_marker >= end_marker and current_marker < start_marker:
                                pass
                            else:
                                if lamp_effstatus == 0:
                                    if nodelist[x] in self.gatewaynode_idlist:
                                        pass
                                    else:
                                        if node_wattage < off_state_wattage and ctrl_mode == 0:
                                            searcher_msgID = nodedatalist[x].find(nodelist[x].encode('utf-8') + b'|')
                                            try:
    #                                             int_pktmsgID_vers = int(nodedatalist[x][searcher_msgID+len(nodelist[x])+1:searcher_msgID+len(nodelist[x])+1+len(msgID[0])], 16)
                                                int_pktmsgID = int(nodedatalist[x][searcher_msgID+len(nodelist[x])+1+len(msgID[0]):searcher_msgID+len(nodelist[x])+1+len(msgID)])
                                                if int_pktmsgID != 0:
                                                    tt_index = int(nodedatalist[x].split(b'|')[13])
                                                    timetable_problem_list.append((nodelist[x], tt_index))
                                                    dict_log[log_label] = b'Lamp auto-off - verifying TT, ' + nodedatalist[x]
                                                else:
                                                    mini_problems_list.append(nodelist[x])
                                                    dict_log[log_label] = b'Lamp auto-off - resetting node, ' + nodedatalist[x]
                                            except ValueError:
                                                pass
                                elif lamp_effstatus == 1 or lamp_effstatus == 2:
                                    pass
                                else:
                                    mini_problems_list.append(nodelist[x])
                                    dict_log[log_label] = b'Lamp status not OFF nor ON/DIM - packet corrupt, ' + nodedatalist[x]
                                    continue
                    except:
                        pass
                    next_datalist.append((nodelist[x], nodedatalist[x], pktmsgID, dtime, bool(ctrl_mode), bool(lamp_effstatus)))
            # Reset and error message placements
            dict_items = list(dict_log.items())
            mini_problems_list = list(set(mini_problems_list))
            override_control_list = list(set(override_control_list))
            timetable_problem_list = list(set(timetable_problem_list))
            if len(mini_problems_list) >= 1 and self.label.find('H') != -1:
                for x in range(0, len(mini_problems_list)):
                    reset_cmd = '+TRS' + mini_problems_list[x] + '\r\n'
                    self.reset_queue.put(reset_cmd.encode('utf-8'))
            if len(override_control_list) >= 1 and self.label.find('H') != -1:
                for y in range(0, len(override_control_list)):
                    override_cmd = override_control_list[y] + '\r\n'
                    self.reset_queue.put(override_cmd.encode('utf-8'))
            if len(timetable_problem_list) >= 1 and self.label.find('H') != -1:
                for w in range(0, len(timetable_problem_list)):
                    TT_cmd = '+STQ' + str(timetable_problem_list[w][1]) + timetable_problem_list[w][0] + '\r\n'
                    self.reset_queue.put(TT_cmd.encode('utf-8'))
            if self.record_queue is not None and len(dict_items) >= 1:
                for z in range(0, len(dict_items)):
                    self.record_queue.put(dict_items[z])
        except:
            return None
        return next_datalist
    
    def packet_timecheck(self, earliest_time, new_time):
        earliest_time_dt = earliest_time
        new_time_dt = new_time
        if earliest_time_dt <= new_time_dt:
            return True
        else:
            return False
    
    def duplicate_filtering(self, nodelist, msgIDlist, dtimelist):
        try:
            accepted_indices = []
            msgID_labellist = []
            all_index_list = []
            if len(nodelist) != len(msgIDlist) or len(msgIDlist) != len(dtimelist):
                raise
            else:
                for x in range(0, len(nodelist)):
                    msgID_label = nodelist[x] + '/' + msgIDlist[x]
                    msgID_labellist.append(msgID_label)
                msgID_labellist = list(enumerate(msgID_labellist))
                for y in range(0, len(msgID_labellist)):
                    reference = msgID_labellist[y][1]
                    index_list = []
                    for z in range(0, len(msgID_labellist)):
                        if msgID_labellist[z][1] == reference:
                            index_list.append(msgID_labellist[z][0])
                        else:
                            pass
                    if index_list != []:
                        all_index_list.append(index_list)
                if len(all_index_list) >= 1:
                    for q in range(0, len(all_index_list)):
                        if len(all_index_list[q]) == 1:
                            accepted_indices.append(all_index_list[q][0])
                        else:
                            for w in range(0, len(all_index_list[q])):
                                inner_index = 0
                                flag = self.packet_timecheck(dtimelist[inner_index], dtimelist[w])
                                if flag:
                                    inner_index = w
                                else:
                                    pass
                            accepted_indices.append(inner_index)
                    accepted_indices = list(set(accepted_indices))
                    accepted_indices.sort()
        except:
            return None
        return accepted_indices
        
    def run(self):
        try:
            DB_threads_list = []
            final_msgIDlist = []
            final_dtimelist = []
            final_overridelist = []
            final_lamplist = []
            if self.label.find('E1') != -1:
                if self.poll_t.is_alive():
                    self.GPS_cfm_list = self.poll_t.get_GPS_confirmed_list()
                if self.reset_t.is_alive():
                    self.pending_verify_E1_list = self.reset_t.get_awaiting_E1_list()
            next_datalist = self.ID_filtering(self.node_list, self.node_datalist)
            if next_datalist is None:
                raise
            else:
                self.node_list = []
                self.node_datalist = []
                for i in range(0, len(next_datalist)):
                    self.node_list.append(next_datalist[i][0])
                    self.node_datalist.append(next_datalist[i][1])
            next_datalist = self.time_filtering(self.node_list, self.node_datalist)
            if next_datalist is None:
                raise
            else:
                next_datalist = list(set(next_datalist))
                self.node_list = []
                self.node_datalist = []
                for i in range(0, len(next_datalist)):
                    self.node_list.append(next_datalist[i][0])
                    self.node_datalist.append(next_datalist[i][1])
                    final_msgIDlist.append(next_datalist[i][2])
                    final_dtimelist.append(next_datalist[i][3])
                    final_overridelist.append(next_datalist[i][4])
                    final_lamplist.append(next_datalist[i][5])
#             print('Before: \r\n', self.node_list, self.node_datalist, final_msgIDlist, final_dtimelist, final_overridelist, final_lamplist)
            accepted_indices = self.duplicate_filtering(self.node_list, final_msgIDlist, final_dtimelist)
            if accepted_indices is None:
                raise 
            else:
                pop_indexlist = []
                for i in range(0, len(self.node_datalist)):
                    try:
                        _ = accepted_indices.index(i)
                    except ValueError:
                        pop_indexlist.append(i)
                if len(pop_indexlist) >= 1:
                    for j in range(0, len(pop_indexlist)):
                        pop_index = pop_indexlist[j]
                        self.node_list.pop(pop_index)
                        self.node_datalist.pop(pop_index)
                        final_msgIDlist.pop(pop_index)
                        final_dtimelist.pop(pop_index)
                        final_overridelist.pop(pop_index)
                        final_lamplist.pop(pop_index)
#             print('After: \r\n', self.node_list, self.node_datalist, final_msgIDlist, final_dtimelist, final_overridelist, final_lamplist)
            if len(self.node_list) >= 1:
                DB_t = DatabaseThread(self.packet_logger, self.problem_logger, self.msg_queue, self.node_list, self.node_datalist, self.label, final_dtimelist, final_msgIDlist, final_overridelist, final_lamplist)
                DB_t.start()
                DB_threads_list.append(DB_t)
            for threads in DB_threads_list:
                threads.join()
            for g in range(0, len(self.node_datalist)):
                self.packet_logger.info(self.node_datalist[g])
#                 self.msg_queue.put((self.node_list[g], self.node_datalist[g]))
        except:
            self.stop()
    
    def stop(self):
        self.stop_event.set()

