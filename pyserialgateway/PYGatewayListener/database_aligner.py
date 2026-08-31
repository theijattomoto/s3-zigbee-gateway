'''
DatabaseAligner: PostgreSQL/local-CSV alignment logic for the node database.
'''
import time
import os
import errno
import collections
import random
import datetime
import csv

from .config import updating_database_localpath, first_GW_data, second_GW_data
from .db_connection import get_connection

class DatabaseAligner():
    '''Object that contains all Database-type commands needed'''
    def basic_exec(self, *args):
        '''Delete data entry for a particular node in PostgreSQL node list.'''
        data, query_string = args
        try:
            connection = get_connection()
            connection.set_session(autocommit=True)
            cursor = connection.cursor()
            cursor.execute(query_string, data)
            return True
        finally:
            if(connection):
                cursor.close()
                connection.close()
    
    def DB_delete_node_DB(self, *args):
        '''Delete data entry for a particular node in PostgreSQL node list.'''
        data = args
        try:
            connection = get_connection()
            connection.set_session(autocommit=True)
            cursor = connection.cursor()
            query = '''delete from node_database where node = %s'''
            cursor.execute(query, data)
            return True
        finally:
            if(connection):
                cursor.close()
                connection.close()
    
    def DB_delete_filter_time(self, *args):
        '''Delete data entry for a particular node in PostgreSQL data packets list.'''
        data = args
        try:
            connection = get_connection()
            connection.set_session(autocommit=True)
            cursor = connection.cursor()
            query = '''delete from filter_time_py where node = %s and ack = %s'''
            cursor.execute(query, data)
            return True
        finally:
            if(connection):
                cursor.close()
                connection.close()
    
    def DB_register(self, data, data_header):
        '''
        Insert data entry for a particular node in PostgreSQL node list.
        17/6/2021 - Dynamic data entry into database according to input header enabled.
        '''
        insert_header = '('
        for ind,items in enumerate(data_header):
            if items == 'node':
                select_ind = ind
            if ind == len(data_header)-1:
                insert_header += str(items)
                insert_header += ')'
            else:
                insert_header += str(items) + ','
        try:
            connection = get_connection()
            connection.set_session(autocommit=True)
            cursor = connection.cursor()
            query = '''select pole_node, node, pan_id, channel, latitude, longitude, description from node_database where node = %s'''
            cursor.execute(query, (data[select_ind],))
            record = cursor.fetchall()
            if len(record) == 0:
                in_query = '''insert into node_database''' + str(insert_header) + ''' values %s'''
                cursor.execute(in_query, (tuple(data),))
            elif len(record) == 1:
                q_string = ''
                d_list = []
                for ind,item_string in enumerate(data_header):
                    if item_string != 'node':
                        if data[ind] != None:
                            if q_string.find('= %s') == -1:
                                q_string += str(item_string) + ' = %s'
                            else:
                                q_string += ', ' + str(item_string) + ' = %s'
                            d_list.append(data[ind])
                    else:
                        end_string = ' where node = %s'
                        end_data = data[ind]
                q_string += end_string
                d_list += (end_data,)
                up_query = '''update node_database set ''' + q_string
                cursor.execute(up_query, tuple(d_list))
            else:
                _ = self.DB_delete_node_DB(data[1])
                time.sleep(0.5)
                re_in_query = '''insert into node_database''' + str(insert_header) + ''' values %s'''
                cursor.execute(re_in_query, (tuple(data),))
            return True
        finally:
            if(connection):
                cursor.close()
                connection.close()
    
    def csv_check(self):
        '''Load and return data recorded in particular headers in the static Excel CSV file using lists.'''
        if os.path.isfile(updating_database_localpath):
            csv_entries = 0
            node_templist = {}
            csv_status_flag = True
            local_reader = csv.DictReader(open(updating_database_localpath), ['pole_node', 'node', 'pan_id', 'channel'])
            csv_header = list(next(local_reader).keys())
            for row in local_reader:
                if not row['node'] == None or not row['pole_node'] == None:
                    node_templist[row['node']] = list(row.values())
                    csv_entries += 1
            return (csv_status_flag, csv_entries, node_templist, csv_header)
        else:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), updating_database_localpath)
    
    def static_read(self):
        '''Load all data from PostgreSQL node list.'''
        try:
            empty_nodelist = []
            connection = get_connection()
            cursor = connection.cursor()
            query = '''select pole_node, node, pan_id, channel, latitude, longitude, description from node_database'''
            cursor.execute(query)
            all_records = cursor.fetchall()
            entries = cursor.rowcount
            for row in all_records:
                empty_nodelist.append(row[1])
            info_string = 'NodeDatabase - Check: '+ str(len(all_records)) + ' existing entries in node_database table...'
            self.logger.debug(info_string)
            self.simple_logger.debug(info_string)
            return (entries, empty_nodelist)
        finally:
            if(connection):
                cursor.close()
                connection.close()
        
    def final_read(self, port_data):
        '''
        Check all lines, and load data into two specific lists from PostgreSQL node list.
        empty_nodelist :- full node list under specific pan id + channel.
        poll_exempt_nodelist :- full auto-inserted node list under specific pole_node ID.
        # With the updated node_database table, compute empty_nodelist
        '''
        try:
            empty_nodelist = []
            poll_exempt_nodelist = []
            node_temp_sortlist = {}
            sorted_nodelist = {}
            connection = get_connection()
            cursor = connection.cursor()
            query = '''select pole_node, node, pan_id, channel, latitude, longitude, description from node_database where pan_id = %s and channel = %s'''
            cursor.execute(query, (port_data[1], port_data[2]))
            all_records = cursor.fetchall()
            for row in all_records:
                if row[0] == 'TBD-AUTO':
                    poll_exempt_nodelist.append(row[1])
                try:
                    dec_value = int(row[1], 16)
                    node_temp_sortlist[row[1]] = dec_value
                except:
                    _ = self.DB_delete_node_DB(row[1])
            sorted_nodelist = collections.OrderedDict(sorted(node_temp_sortlist.items(), key=lambda t:t[0]))
            for g in sorted_nodelist:
                empty_nodelist.append(g)
            return empty_nodelist, poll_exempt_nodelist
        finally:
            if(connection):
                cursor.close()
                connection.close()
    
    def select_override_OFF_list(self, LMactive_datetime, nodeoff_datetime):
        '''
        Using the currently selected node list, filter out the most recent data entry for the nodes in the PostgreSQL data packets list.
        Using timing checkpoints of the POWER active hours (typically 7pm - 7am), determine if the lanterns are currently ON, and needs to be turned OFF.
        This function will also include all data packets recorded ON which are out of the timing loop (last entry before the POWER active hours on the day before).
        In that case, you will need to manually modify/delete the data in the PostgreSQL data packets list - with permission granted by the system.
        Current script implementation:
        This function is called externally only during SYSTEM inactive hours on the CURRENT day for the filter logic to work.
        The script will load in the POWER active hours from the previous cycle, overriding only nodes which have updated ON during inactive hours.
        This arrangement effectively accommodates all possible ON conditions on-site, including the uncertainty on not receiving the correct TRUE last packet from each node, due to network limitations.
        '''
        try:
            out_of_timerange_nodelist = []
            empty_nodelist = []
            latest_status_tuple_list = []
            connection = get_connection()
            cursor = connection.cursor()
            for i in range(0, len(self.node_database_list)):
                if self.node_database_list[i] in self.poll_exempt_list or self.node_database_list[i] in self.gatewaynode_idlist:
                    continue
                mini_time_list = []
                query = '''select dtime, override_flag, lamp_status from filter_time_py where node = %s'''
                cursor.execute(query, (self.node_database_list[i],))
                all_records = cursor.fetchall()
                if len(all_records) <= 0:
                    continue
                else:
                    for row in all_records:
                        mini_time_list.append(row[0])
                    data_index = mini_time_list.index(max(mini_time_list))
                    gmt8_time = max(mini_time_list) + datetime.timedelta(hours=8)
                    latest_status_tuple_list.append((int(self.node_database_list[i], 16), self.node_database_list[i], all_records[data_index][1], all_records[data_index][2], gmt8_time))
            latest_status_tuple_list = sorted(latest_status_tuple_list, key=lambda tup: tup[0])
            '''
            9-7-2021: Such override_off list should check latest node status as well with latest_status_tuple_list[m][2]
            '''
            if len(latest_status_tuple_list) >= 1:
                for m in range(0, len(latest_status_tuple_list)):
                    time_diff = latest_status_tuple_list[m][4] - LMactive_datetime
                    if time_diff.days < 0:
                        out_of_timerange_nodelist.append(latest_status_tuple_list[m][1])
                        continue
                    LM_active_flag = not self.DB_timecheck(latest_status_tuple_list[m][4], LMactive_datetime)
                    nodeoff_flag = self.DB_timecheck(latest_status_tuple_list[m][4], nodeoff_datetime)
                    if LM_active_flag & nodeoff_flag is True:
                        if latest_status_tuple_list[m][2] & latest_status_tuple_list[m][3] is True:
                            empty_nodelist.append(latest_status_tuple_list[m][1])
                    else:
                        if nodeoff_flag is False:
                            if latest_status_tuple_list[m][2] is False & latest_status_tuple_list[m][3] is True:
                                empty_nodelist.append(latest_status_tuple_list[m][1])
            return (out_of_timerange_nodelist, empty_nodelist)
        finally:
            if(connection):
                cursor.close()
                connection.close()
    
    def select_aggressive_poll_list(self, active_datetime, aggressivepoll_datetime):
#         LMactive_datetime = args[2]
        try:
            residual_nodelist = []
            empty_nodelist = []
            latest_status_tuple_list = []
            connection = get_connection()
            cursor = connection.cursor()
            for i in range(0, len(self.node_database_list)):
                if self.node_database_list[i] in self.poll_exempt_list or self.node_database_list[i] in self.gatewaynode_idlist:
                    continue
                mini_time_list = []
                query = '''select dtime, ack from filter_time_py where node = %s'''
                cursor.execute(query, (self.node_database_list[i],))
                all_records = cursor.fetchall()
                if len(all_records) <= 0:
                    continue
                else:
                    for row in all_records:
                        mini_time_list.append(row[0])
                    data_index = mini_time_list.index(max(mini_time_list))
                    gmt8_time = max(mini_time_list) + datetime.timedelta(hours=8)
                    latest_status_tuple_list.append((int(self.node_database_list[i], 16), self.node_database_list[i], all_records[data_index][1], gmt8_time))
            latest_status_tuple_list = sorted(latest_status_tuple_list, key=lambda tup: tup[0])
            if len(latest_status_tuple_list) >= 1:
                for m in range(0, len(latest_status_tuple_list)):
#                     time_diff = latest_status_tuple_list[m][3] - LMactive_datetime
#                     if time_diff.days < 0:
#                         continue
                    LM_active_flag = not self.DB_timecheck(latest_status_tuple_list[m][3], active_datetime)
                    nodeoff_flag = self.DB_timecheck(latest_status_tuple_list[m][3], aggressivepoll_datetime)
                    if LM_active_flag & nodeoff_flag is False:
                        empty_nodelist.append(latest_status_tuple_list[m][1])
                    else:
                        if latest_status_tuple_list[m][2].find('E2') != -1:
                            empty_nodelist.append(latest_status_tuple_list[m][1])
                        else:
                            residual_nodelist.append(latest_status_tuple_list[m][1])
            if len(residual_nodelist) > len(empty_nodelist):
                residual_nodelist = random.sample(residual_nodelist, len(empty_nodelist))
            return (residual_nodelist, empty_nodelist)
        finally:
            if(connection):
                cursor.close()
                connection.close()
    
    def dtime_active_check(self):
        '''Deletes all corrupted data entries with its entry time stamp being beyond the current time.'''
        try:
            delete_tuple_list = []
            connection = get_connection()
            cursor = connection.cursor()
            sp_query = '''select dtime, node, ack from filter_time_py'''
            cursor.execute(sp_query)
            all_records = cursor.fetchall()
            if len(all_records) <= 0:
                pass
            else:
                for row in all_records:
                    dtime_data = row[0]
                    if self.DB_timecheck(datetime.datetime.utcnow(), dtime_data):
                        delete_tuple_list.append((row[1], row[2]))
            if len(delete_tuple_list) >= 1:
                info_string = 'RTDatabase - Sync: '+ str(len(delete_tuple_list)) + ' existing entries in filter_time_py table...'
                self.logger.debug(info_string)
                self.simple_logger.debug(info_string)
                for i in range(0, len(delete_tuple_list)):
                    process_status = self.DB_delete_filter_time(delete_tuple_list[i][0], delete_tuple_list[i][1],)
                    if process_status == False:
                        error_string = 'RTDatabase - Error occurred, data SYNC incomplete from local to postgresql.'
                        self.logger.debug(error_string)
                        self.problem_logger.error(error_string)
        finally:
            if(connection):
                cursor.close()
                connection.close()
    
    def DB_timecheck(self, data_time_1, data_time_2):
        '''Time comparison logic used by select_override_off_list'''
        if data_time_1 < data_time_2:
            return True
        elif data_time_1 >= data_time_2:
            return False
        
    def run(self, *args):
        '''
        Call-able INIT process for DatabaseAligner. Depending on self.DB_check_flag, it will optionally execute one block of code which is used to replicate data in local Excel file.
        If not, it will load in all the valid nodes from the PostgreSQL DB node list to create a node database list and poll database list that can be used locally in self-type functions.
        It then returns the node database list to the caller. 
        '''
        self.logger, self.simple_logger, self.problem_logger, self.portdata, self.port_datalist, self.DB_check_flag = args
        self.gatewaynode_idlist = [GWnodeid for (GWnodeid,_,_) in self.port_datalist]
        port_data = self.portdata
        if self.DB_check_flag:
            self.entries, self.node_database_list = self.static_read()
            if self.node_database_list is None:
                error_string = 'DBUP - PostgreSQL database cannot be accessed while reading node DB.'
                self.logger.debug(error_string)
                raise Exception(error_string)
            '''
            16/6/2021 - Changed designation of separate dicts node_csv_dict, node_pan_dict, node_ch_dict to single dict node_data_dict
            - Expanded capabilities on data registration to local DB.
            '''
            self.csv_flag, self.csv_entries, self.node_data_dict, self.csv_header = self.csv_check()
            if self.csv_flag == False:
                pass
            else:
                keylist = []
                if self.entries == 0:
                    if self.csv_entries == 0:
                        error_string = 'DBUP - No subjected nodes in database to be checked.'
                        self.logger.debug(error_string)
                        raise Exception(error_string)
                    else:
                        for x in self.node_data_dict:
                            keylist.append(x)
                        info_string = 'DBUP - Inserting ' + str(self.csv_entries) + ' lines of data into node database.'
                        self.logger.debug(info_string)
                        self.simple_logger.debug(info_string)
                        status_flag = True
                        for i in range(0, self.csv_entries):
                            status_flag = status_flag & self.DB_register(self.node_data_dict[keylist[i]][0:4], self.csv_header)
                        if status_flag == False:
                            error_string = 'DBUP - Error occurred, partial data INSERT incomplete from local to postgresql.'
                            self.logger.debug(error_string)
                            self.problem_logger.error(error_string)
                else:
                    if self.csv_entries == 0:
                        info_string = 'DBUP - no reference local csv present to update postgresql.'
                        self.logger.debug(error_string)
                        self.problem_logger.error(error_string)
                    else:
                        for x in self.node_data_dict:
                            keylist.append(x)
                        delete_list = list(set(self.node_database_list) - set(keylist))
                        new_list = list(set(keylist) - set(self.node_database_list))
                        update_list = list(set(keylist) & set(self.node_database_list))
                        if len(delete_list) > 0:
                            info_string = 'DBUP - Deleting ' + str(len(delete_list)) + ' unwanted existing keys from node database.'
                            self.logger.debug(info_string)
                            self.simple_logger.debug(info_string)
                            status_flag = True
                            for i in range(0, len(delete_list)):
                                status_flag = status_flag & self.DB_delete_node_DB(delete_list[i],)
                            if status_flag == False:
                                error_string = 'DBUP - Error occurred, data DELETE incomplete from local to postgresql.'
                                self.logger.debug(error_string)
                                self.problem_logger.error(error_string)
                        if len(new_list) > 0:
                            info_string = 'DBUP - Inserting ' + str(len(new_list)) + ' lines of data into node database.'
                            self.logger.debug(info_string)
                            self.simple_logger.debug(info_string)
                            status_flag = True
                            for i in range(0, len(new_list)):
                                status_flag = status_flag & self.DB_register(self.node_data_dict[new_list[i]][0:4], self.csv_header)
                            if status_flag == False:
                                error_string = 'DBUP - Error occurred, data INSERT incomplete from local to postgresql.'
                                self.logger.debug(error_string)
                                self.problem_logger.error(error_string)
                        if len(update_list) > 0:
                            info_string = 'DBUP - Updating ' + str(len(update_list)) + ' existing keys in the node database.'
                            self.logger.debug(info_string)
                            self.simple_logger.debug(info_string)
                            status_flag = True
                            for i in range(0, len(update_list)):
                                status_flag = status_flag & self.DB_register(self.node_data_dict[update_list[i]][0:4], self.csv_header)
                            if status_flag == False:
                                error_string = 'DBUP - Error occurred, data UPDATE incomplete from local to postgresql.'
                                self.logger.debug(error_string)
                                self.problem_logger.error(error_string)
        running_flag = True
        try:
            flag = running_flag & self.DB_register(['GW-1']+list(first_GW_data), ['pole_node','node','pan_id','channel'])
            flag = flag & self.DB_register(['GW-2']+list(second_GW_data), ['pole_node','node','pan_id','channel'])
            if flag is False:
                raise
        except:
            error_string = 'DBUP - PostgreSQL database cannot be accessed while updating GW nodes.'
            self.logger.debug(error_string)
            self.problem_logger.error(error_string)
        self.node_database_list, self.poll_exempt_list = self.final_read(port_data)
        total_records = len(self.node_database_list) + len(self.poll_exempt_list)
        info_string = 'NodeDatabase - Sync: '+ str(total_records) + ' existing entries in node_database table...'
        self.logger.debug(info_string)
        self.simple_logger.debug(info_string)
        return self.node_database_list