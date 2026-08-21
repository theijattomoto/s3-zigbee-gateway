'''
GPSThread: parses G0 GPS packets, filters/deduplicates them, and dispatches
confirmed fixes to GPSDatabaseThread.
'''
import threading

from .gps_database_thread import GPSDatabaseThread

class GPSThread(threading.Thread):
    def __init__(self, packet_logger, problem_logger, GPS_confirmed_queue, record_queue, basiclabel, node_database_list, port_data, poll_thread_obj, node_list, node_data_list, kml_map_manager, kml_doc_element):
        super(GPSThread, self).__init__()
        self.packet_logger = packet_logger
        self.problem_logger = problem_logger
        self.GPS_confirmed_queue = GPS_confirmed_queue
        self.record_queue = record_queue
        self.node_database_list = node_database_list
        self.port_data = port_data
        self.poll_t = poll_thread_obj
        self.node_list = node_list
        self.node_data_list = node_data_list
        self.kml_map_manager = kml_map_manager
        self.kml_doc_element = kml_doc_element
        self.stop_event = threading.Event()
        self.name = 'NodeMapper'
        self.basiclabel = basiclabel
        self.GPS_V_list = []
        self.GPS_cfm_list = []
    
    def description_validation(self, basiclabel, selfgenlabel):
        return basiclabel == selfgenlabel
    
    def raw_to_value(self, partpacket):
        val_sep = (partpacket.decode('utf-8')).find(' ')
        value = str(float(partpacket[0:val_sep].decode('utf-8')) + float(partpacket[val_sep+1:-1].decode('utf-8'))/60)
        return value    
    
    def packet_data_conversion(self, nodeID, packet, index, condition):
        searcher_5 = packet.find(b' N')
        if (searcher_5 == -1):
            searcher_6 = packet.find(b' S')
            if (searcher_6 == -1):
                node_lat = '3.069900'
                node_long = '101.692244'
                note = '#G0!'
                info_string = 'GPS packet structure irregular for node ' + nodeID + ', setting all values at reference zero.'
                self.problem_logger.info(info_string)
                self.packet_logger.debug(info_string)
            else:
                lat_raw = packet[index+11:searcher_6]
                node_lat = self.raw_to_value(lat_raw)
                node_lat = str(float(node_lat) * (-1))
                searcher_7 = packet.find(b' E#')
                if (searcher_7 == -1):
                    searcher_8 = packet.find(b' W#')
                    if (searcher_8 == -1):
                        node_lat = '3.069900'
                        node_long = '101.692244'
                        note = '#G0!'
                        info_string = 'Longitude not found for node ' + nodeID + ', setting all values at reference zero.'
                        self.problem_logger.info(info_string)
                        self.packet_logger.debug(info_string)
                    else:
                        long_raw = packet[searcher_5+3:searcher_8]
                        node_long = self.raw_to_value(long_raw)
                        node_long = str(float(node_long) * (-1))
                        if condition == 'V':
                            note = '#G0|V|'
                        elif condition == 'A':
                            if nodeID in self.node_database_list:
                                note = '#G0'
                            else:
                                note = '#G0-'
                else:
                    long_raw = packet[searcher_5+3:searcher_7]
                    node_long = self.raw_to_value(long_raw)
                    if condition == 'V':
                        note = '#G0|V|'
                    elif condition == 'A':
                        if nodeID in self.node_database_list:
                            note = '#G0'
                        else:
                            note = '#G0-'
        else:
            lat_raw = packet[index+11:searcher_5]
            node_lat = self.raw_to_value(lat_raw)
            searcher_7 = packet.find(b' E#')
            if (searcher_7 == -1):
                searcher_8 = packet.find(b' W#')
                if (searcher_8 == -1):
                    node_lat = '3.069900'
                    node_long = '101.692244'
                    note = '#G0!'
                    info_string = 'Longitude not found for node ' + nodeID + ', setting all values at reference zero.'
                    self.problem_logger.info(info_string)
                    self.packet_logger.debug(info_string)
                else:
                    long_raw = packet[searcher_5+3:searcher_8]
                    node_long = self.raw_to_value(long_raw)
                    node_long = str(float(node_long) * (-1))
                    if condition == 'V':
                        note = '#G0|V|'
                    elif condition == 'A':
                        if nodeID in self.node_database_list:
                            note = '#G0'
                        else:
                            note = '#G0-'
            else:
                long_raw = packet[searcher_5+3:searcher_7]
                node_long = self.raw_to_value(long_raw)
                if condition == 'V':
                    note = '#G0|V|'
                elif condition == 'A':
                    if nodeID in self.node_database_list:
                        note = '#G0'
                    else:
                        note = '#G0-'
        data = [note, node_lat, node_long]
        return data
    
    def duplicate_filtering(self, nodelist, labellist):
        try:
            accepted_indices = []
            new_labellist = []
            all_index_list = []
            if len(nodelist) != len(labellist):
                raise
            else:
                for x in range(0, len(nodelist)):
                    new_label = nodelist[x] + '/' + labellist[x]
                    new_labellist.append(new_label)
                new_labellist = list(enumerate(new_labellist))
                for y in range(0, len(new_labellist)):
                    reference = new_labellist[y][1]
                    index_list = []
                    for z in range(0, len(new_labellist)):
                        if new_labellist[z][1] == reference:
                            index_list.append(new_labellist[z][0])
                        else:
                            pass
                    if index_list != []:
                        all_index_list.append(index_list)
                if len(all_index_list) >= 1:
                    for q in range(0, len(all_index_list)):
                        if len(all_index_list[q]) == 1:
                            accepted_indices.append(all_index_list[q][0])
                        else:
                            accepted_indices.append(min(all_index_list[q]))
                    accepted_indices = list(set(accepted_indices))
                    accepted_indices.sort()
        except:
            return None
        return accepted_indices
    
    def pinpoint_filtering(self, nodelist, nodedatalist):
        try:
            KMLdatalist = []
            dict_log = {}
            poll_feedback_log = {}
            if len(nodelist) != len(nodedatalist):
                raise
            else:
                for x in range(0, len(nodelist)):
                    kml_label = '#' + self.basiclabel
                    log_label = self.basiclabel + '/' + nodelist[x]
                    searcher_V = nodedatalist[x].find(b'|V|')
                    searcher_A = nodedatalist[x].find(b'|A|')
                    if searcher_V == -1 and searcher_A == -1:
                        error_string = b'Geolocation string corrupted, ' + nodedatalist[x]
                        dict_log[log_label] = error_string
                        continue
                    else:
                        if searcher_A == -1 and searcher_V != -1:
                            if nodelist[x] in self.GPS_V_list:
                                try:
                                    locationlist = self.packet_data_conversion(nodelist[x], nodedatalist[x], searcher_V, 'V')
                                    kml_label = locationlist[0]
                                    G0_data_lat = locationlist[1]
                                    G0_data_long = locationlist[2]
                                except:
                                    kml_label = kml_label + '!'
                                    G0_data_lat = 3.069900
                                    G0_data_long = 101.692244
                                poll_feedback_log[nodelist[x]] = 'A'
                            else:
                                try:
                                    locationlist = self.packet_data_conversion(nodelist[x], nodedatalist[x], searcher_V, 'V')
                                    info_string = b'Geolocation data not fixed, retrying for one more cycle - ' + nodedatalist[x]
                                    dict_log[log_label] = info_string
                                    poll_feedback_log[nodelist[x]] = 'V'
                                    continue
                                except:
                                    info_string = b'Geolocation data zero, data rejected,' + nodedatalist[x]
                                    dict_log[log_label] = info_string
                                    continue
                        elif searcher_A != -1 and searcher_V == -1:
                            try:
                                locationlist = self.packet_data_conversion(nodelist[x], nodedatalist[x], searcher_A, 'A')
                                if self.description_validation(self.basiclabel, locationlist[0]):
                                    pass
                                else:
                                    kml_label = locationlist[0]
                                G0_data_lat = locationlist[1]
                                G0_data_long = locationlist[2]
                            except:
                                kml_label = kml_label + '!'
                                G0_data_lat = 3.069900
                                G0_data_long = 101.692244
                            poll_feedback_log[nodelist[x]] = 'A'
                    KMLdatalist.append((nodelist[x], kml_label, G0_data_lat, G0_data_long))
            GPS_dict_items = list(poll_feedback_log.items())
            if self.GPS_confirmed_queue is not None and len(GPS_dict_items) >= 1:
                for y in range(0, len(GPS_dict_items)):
                    self.GPS_confirmed_queue.put(GPS_dict_items[y])        
            dict_items = list(dict_log.items())
            if self.record_queue is not None and len(dict_items) >= 1:
                for z in range(0, len(dict_items)):
                    self.record_queue.put(dict_items[z])
        except:
            return None
        return KMLdatalist
    
    def run(self):
        try:
            GPS_DB_threads_list = []
            final_node_list = []
            final_label_list = []
            final_lat_list = []
            final_long_list = []
            if self.poll_t.is_alive():
                self.GPS_V_list = self.poll_t.get_GPS_varying_list()
                self.GPS_cfm_list = self.poll_t.get_GPS_confirmed_list()
            KMLdatalist = self.pinpoint_filtering(self.node_list, self.node_data_list)
            if KMLdatalist is None:
                raise 
            else:
                for i in range(0, len(KMLdatalist)):
                    final_node_list.append(KMLdatalist[i][0])
                    final_label_list.append(KMLdatalist[i][1])
                    final_lat_list.append(KMLdatalist[i][2])
                    final_long_list.append(KMLdatalist[i][3])
#             print('Before: \r\n', final_node_list, final_label_list, final_lat_list, final_long_list)
            accepted_indices = self.duplicate_filtering(final_node_list, final_label_list)
            if accepted_indices is None:
                raise 
            else:
                pop_indexlist = []
                for i in range(0, len(final_node_list)):
                    try:
                        _ = accepted_indices.index(i)
                    except ValueError:
                        pop_indexlist.append(i)
                if len(pop_indexlist) >= 1:
                    for j in range(len(pop_indexlist)-1, -1, -1):
                        pop_index = pop_indexlist[j]
                        final_node_list.pop(pop_index)
                        final_label_list.pop(pop_index)
                        final_lat_list.pop(pop_index)
                        final_long_list.pop(pop_index)
#             print('After: \r\n', final_node_list, final_label_list, final_lat_list, final_long_list)
            if len(final_node_list) >= 1:
                for k in range(0, len(final_node_list)):
                    if final_node_list[k] in self.GPS_cfm_list:
                        pass
                    else:
                        debug_string = 'Mapping node (' + final_node_list[k] + ', ' + final_label_list[k] + ', ' + final_lat_list[k] + ', ' + final_long_list[k] + ')'
                        self.packet_logger.info(debug_string)
                        placemarkElement = self.kml_map_manager.add_placemark(final_node_list[k], final_label_list[k], final_lat_list[k], final_long_list[k])
                        if placemarkElement is not None:
                            self.kml_doc_element.appendChild(placemarkElement)
                            GPS_DB_t = GPSDatabaseThread(self.packet_logger, self.problem_logger, final_node_list[k], final_label_list[k], final_lat_list[k], final_long_list[k], self.port_data, self.node_database_list)
                            GPS_DB_t.start()
                            GPS_DB_threads_list.append(GPS_DB_t)
                self.kml_map_manager.writetokmlfile()
            for threads in GPS_DB_threads_list:
                threads.join()
        except:
            self.stop()
            
    def stop(self):
        self.stop_event.set()        

