#! /usr/bin/python3
'''
Created on 23 Sep 2020

@author: -
@version: 1.3.3
@change:
Kickstart 24-5-2021, 11-6-2021, 1-7-2021 -
Comparison to v1.3.2:
1) [Attempt stage] Uniformly output single-versions of .kml file for mapping feature with different instances of GW script. (DONE, TESTED 16/6)
2) Bug fixes on DBUP and DB checking to remove multiple-registered or corrupted registers should there be any. (DONE, TESTED 25/5)
3) HTTP Connection added with NOAUTH options for Authentication and TEST options for target-sending according to requirements from Selmos. (DONE, TESTED 30/6)
4) Remove all hard coding of base resources such as socket, etc. (DONE, TESTED 25/5)
5) Standardise clearer logging features to print out full error descriptions for future reference. (DONE, TESTED 28/5)
6) Addition of ExceptionAPI to standardise error-checking. (DONE)
7) Code minimisation for main() and its dependent classes to remove cache usage and redundancy of code. (DONE)
8) Minimise configuration declaration requirements, including hard-coding pathnames and removing unwanted/hidden/unchanged variables. (DONE)
9) Placeholder for server-gateway DB insert on CSV/local POSTGRESQL resources. (DONE, 17/6)
10) Encrypted data required-*parliamentname* is now needed to run data that requires encrypted info. (DONE)
'''
import argparse

desp_parser = argparse.ArgumentParser(description='Process house for Serial data in gateways.')
desp_parser.add_argument('test_gps_flag', metavar='GPSUP', type=str, nargs='?', help='Enable GPS node mapping function.')
desp_parser.add_argument('test_db_refresh_flag', metavar='DBUP', type=str, nargs='?', help='Enable local DB refresh function.')
desp_parser.add_argument('test_demo_flag', metavar='DEMOUP', type=str, nargs='?', help='Enable non-recovery static demo mode.')
desp_parser.add_argument('test_nopoll_flag', metavar='NOPOLL', type=str, nargs='?', help='Disable active data polling feature.')
desp_parser.add_argument('test_noselmos_flag', metavar='NOSELMOS', type=str, nargs='?', help='Disable all data sending features to main server.')
desp_parser.add_argument('test_noauth_flag', metavar='NOAUTH', type=str, nargs='?', help='Disable \'level 1 security feature\'.')
desp_parser.add_argument('test_uptest_flag', metavar='TESTUP', type=str, nargs='?', help='Redirect data to only backup server.')
args = desp_parser.parse_args()

import time
import sys, os, subprocess, errno
import serial, serial.tools.list_ports as srl_tools
import re, collections, random
import datetime
import psycopg2
import threading, multiprocessing
import logging, logging.handlers as handlers
import csv, xml.dom.minidom
import urllib, requests, flask, wsgiserver, ssl
import lxml.etree, pykml.parser
import zipfile, cryptography.fernet as fcrypto
import fcntl, psutil
try:
    import pygw_conf
except:
    import pyserialgateway.config_PYproperties as pygw_conf
import pyserialgateway
location_mod = []
location_mod += pyserialgateway.__path__
obs_instance = [str(p.info['pid']) for p in psutil.process_iter(attrs=['pid','name','cmdline']) if str(sys.argv[0]) in p.info['cmdline']]


class Clock:
    '''Internal clock object similar to stop-watch functions, used to record process time'''                                                                                                    # stopwatch function to act as the internal clock
    def __init__(self):
        self._start = time.perf_counter()
        self._end = None
        
    @property
    def duration(self):
        return self._end - self._start if self._end else time.perf_counter() - self._start
    
    @property
    def running(self):
        return not self._end
    
    def start(self):
        if not self.running:
            self._start = time.perf_counter() - self.duration
            self._end = None
        return self
    
    def stop(self):
        if self.running:
            self._end = time.perf_counter()
            
    def __float__(self):
        time = self.duration * 1000
        if time >= 1000:
            return round(time/1000, 2)
        if time >= 1:
            return round(round(time, 0)/1000,3)
        return 0.000
        
    def __str__(self):
        time = self.duration * 1000
        if time >= 1000:
            return '{:.2f}s'.format(time/1000)
        if time >= 1:
            return '{:.2f}ms'.format(time)
        return '{:.2f}\u03BCs'.format(time*1000)

class StatObjectExceptionAPI():
    def __init__(self,wrapped_class,my_logger,my_logger_problem,*args,**kwargs):
        self.wrapped_class = wrapped_class(*args, **kwargs)
        self.my_logger = my_logger
        self.my_logger_problem = my_logger_problem
        
    def __getattr__(self,attr):
        orig_attr = self.wrapped_class.__getattribute__(attr)
        if callable(orig_attr):
            def wrapper(*args, **kwargs):
                l = str(orig_attr.__qualname__).split('.')
                if l[0] == 'DatabaseAligner':
                    try:
                        return orig_attr(*args, **kwargs)
                    except (Exception, psycopg2.Error) as error:
                        if l[1].find('csv_check') != -1:
                            if error.__class__.__name__.find('FileNotFoundError') == -1:
                                info_string = 'NodeDatabase - Excel content error, local file database corrupted.'
                                self.my_logger.debug(info_string)
                                self.my_logger_problem.debug(info_string)
                            else:
                                self.my_logger_problem.debug(error)
                            return (False, 0, {}, [])
                        elif l[1].find('static_read') != -1:
                            self.problem_logger.debug(error)
                            return (0, None)
                        elif l[1].find('final_read') != -1:
                            self.problem_logger.error(error)
                            return ([], [])
                        elif l[1].find('select') != -1:
                            self.problem_logger.error(error)
                            return ([], [])
                        elif l[1].find('run') != -1:
                            self.problem_logger.warning(error)
                            return []
                        else:
                            self.my_logger_problem.debug(error)
                            return False
                elif l[0] == 'KMLMapManager':
                    try:
                        return orig_attr(*args, **kwargs)
                    except Exception as error:
                        self.my_logger_problem.debug(error)
                        if l[1].find('add_placemark') != -1:
                            return None
                        elif l[1].find('remove') != -1:
                            return args[0]
                        elif l[1].find('inherit') != -1:
                            return (None, [])
                        elif l[1].find('run') != -1:
                            sys.exit(str(error))
                        else:
                            pass
            return wrapper
        else:
            return orig_attr                    

class DatabaseAligner():
    '''Object that contains all Database-type commands needed'''
    def basic_exec(self, *args):
        '''Delete data entry for a particular node in PostgreSQL node list.'''
        data, query_string = args
        try:
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
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
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
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
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
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
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
            connection.set_session(autocommit=True)
            cursor = connection.cursor()
            query = '''select * from node_database where node = %s'''
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
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
            cursor = connection.cursor()
            query = '''select * from node_database'''
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
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
            cursor = connection.cursor()
            query = '''select * from node_database where pan_id = %s and channel = %s'''
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
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
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
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
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
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
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

class KMLMapManager():
    '''XML format document object containing functions to generate KML-type map file on Google Earth'''
    def __init__(self):    
        self.map_file = xml.dom.minidom.Document()
        self.name_iter_start = b'<name>'
        self.name_iter_end = b'</name>'
        
    def add_style_to_placemark(self, *args):
        '''
        Should be called only in the ini_run INIT stage.
        Includes one icon style and shape into the inventory of the main Document.
        '''
        self.docElement, self.styleID, self.stylehref = args
        styleElement = self.map_file.createElementNS(self.styleID, 'Style')
        styleElement.setAttribute('id', self.styleID)
        self.docElement.appendChild(styleElement)
        iconstyleElement = self.map_file.createElement('IconStyle')
        styleElement.appendChild(iconstyleElement)
        iconlinkElement = self.map_file.createElement('Icon')
        iconstyleElement.appendChild(iconlinkElement)
        iconlinkText = self.map_file.createTextNode(self.stylehref)
        iconlinkElement.appendChild(iconlinkText)
    
    def add_placemark(self, *args):
        '''
        Includes one node data under the Coordinates writing pointer of the Document.
        Should only be called after the ini_run INIT stage has been completed. 
        '''
        node_name, node_description, node_lat, node_long = args
        placemarkElement = self.map_file.createElement('Placemark')
        nameElement = self.map_file.createElement('name')
        placemarkElement.appendChild(nameElement)
        nameText = self.map_file.createTextNode(node_name)
        nameElement.appendChild(nameText)
        
        typeElement = self.map_file.createElement('description')
        placemarkElement.appendChild(typeElement)
        node_description_str = node_description + ' - geolocation'
        typeText = self.map_file.createTextNode(node_description_str)
        typeElement.appendChild(typeText)
        
        styleURL = None
        if node_description == '#G0':
            pass
        elif node_description == '#G0!':
            styleURL = self.stylelist[0][0]
        elif node_description == '#G0-':
            styleURL = self.stylelist[1][0]
        elif node_description == '#G0|V|':
            styleURL = self.stylelist[2][0]
            
        if styleURL != None:
            styleElement = self.map_file.createElement('styleUrl')
            placemarkElement.appendChild(styleElement)
            styledescription = '#' + styleURL
            styleText = self.map_file.createTextNode(styledescription)
            styleElement.appendChild(styleText)
        
        pointElement = self.map_file.createElement('Point')
        placemarkElement.appendChild(pointElement)
        coordinates = node_long+','+node_lat+','+'0'
        coorElement = self.map_file.createElement('coordinates')
        coorElement.appendChild(self.map_file.createTextNode(coordinates))
        pointElement.appendChild(coorElement)
        
        return placemarkElement
    
    def writetokmlfile(self):
        '''
        Calling this function will commit any data that is written under any writing pointer of the Document into the KML physical file.
        '''
        kmlFile = open(self.kmlpathname, 'wb')
        kmlFile.write(self.map_file.toprettyxml(encoding='utf-8'))
    
    def remove_whitespace_nodes(self, documentFile, unlink=False):
        '''
        Recursive function to remove all text-type whitespace when reassembling existing data within a pre-existing Document object.
        '''
        remove_list = []
        for child in documentFile.childNodes:
            if child.nodeType == xml.dom.Node.TEXT_NODE and not child.data.strip():
                remove_list.append(child)
            elif child.hasChildNodes:
                _ = self.remove_whitespace_nodes(child,unlink)
        for node in remove_list:
            node.parentNode.removeChild(node)
            if unlink:
                node.unlink()
        return documentFile
    
    def inherit_old_document_info(self, *args):
        old_data_list = []
        self.kmlpathname, self.stylelist = args
        existingDocumentFile = xml.dom.minidom.parse(self.kmlpathname)
        self.map_file = self.remove_whitespace_nodes(existingDocumentFile,False)
        newDocumentElement = self.map_file.getElementsByTagName('Document')[0]
        with open(self.kmlpathname) as f:
            doc = pykml.parser.parse(f)
        data_string = lxml.etree.tostring(doc)
        while data_string.find(self.name_iter_start) != -1:
            data_index_start = data_string.find(self.name_iter_start)
            data_index_end = data_string.find(self.name_iter_end)
            node_data = (data_string[data_index_start:data_index_end+len(self.name_iter_end)]).replace(self.name_iter_start, b'').replace(self.name_iter_end, b'')
            data_string = data_string[data_index_end+len(self.name_iter_end):]
            try:
                _ = int(node_data.decode('utf-8'), 16)
                old_data_list.append(node_data.decode('utf-8'))
            except:
                pass
        return newDocumentElement, old_data_list
                
    def ini_run(self, *args):
        '''
        Call-able INIT process for KMLMapManager. Creates the document headers and formats required to insert coordinates data.
        It then returns the Coordinates writing pointer for the Document to the caller. 
        '''
        self.kmlpathname, self.stylelist = args
        kmlElement = self.map_file.createElementNS('http://earth.google.com/kml/2.0', 'kml')
        kmlElement.setAttribute('xmlns','http://earth.google.com/kml/2.0')
        self.map_file.appendChild(kmlElement)
        documentElement = self.map_file.createElement('Document')
        kmlElement.appendChild(documentElement)
        for i in range(0, len(self.stylelist)):
            self.add_style_to_placemark(documentElement, self.stylelist[i][0], self.stylelist[i][1])
        return documentElement

class SerialObjectManager(serial.Serial):
    '''Serial object containing functions to dynamically execute read-write functions over its designated port.'''
    def serial_open_gateway(self):
        '''
        Internal function specially called by ini_run INIT, repeatedly according to the number of different self.gateway_name.
        If the following serial port settings can be set and the port can be open and used, this function will return a True logic which saves the serial port changes.
        It's up to the caller's job to identify the returned logic and stop the execution of this function to retain the serial port changes.
        '''
        self.port = self.gateway_name
        if self.is_open:
            return False
        else:
            self.baudrate = 115200
            self.bytesize = serial.EIGHTBITS
            self.parity = serial.PARITY_NONE
            self.stopbits = serial.STOPBITS_ONE
            self.timeout = self.per_packet_cd
            try:
                self.open()
                fcntl.flock(self.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                info_string = 'SerialManager - Connected to port ' + self.gateway_name
                self.logger.debug(info_string)
                self.simple_logger.debug(info_string)
            except:
                # error_string = 'SerialManager -' + self.port + ' cannot be opened: resources busy.'
                # self.problem_logger.error(error_string)
                try:
                    self.close()
                except:
                    pass
                return False
            return True
    
    def force_close(self):
        try:
            fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
        except:
            pass
        self.close()
            
    def gw_initial(self, final_ports_ind, final_ports_len):
        '''
        Set the ID configurations of the gateway node which are determined in the startup script. Can be called externally. 
        '''
        hang_timeout_cnt = 0
        self.DS_info = None
        self.write(b'+DS\r\n')
        while True:
            i = self.read_until('\r\n')
            if b'SN' in i and b'HW' in i and b'NodeID' in i and b'PanID' in i and b'ZM-FW' in i:
                self.DS_info = i
                break
            else:
                hang_timeout_cnt += 1
            if hang_timeout_cnt > 5:
                break
        if self.DS_info is None:
            return (False, None)
        try:
            pending_SN_info = self.DS_info[self.DS_info.find(b'SN'):self.DS_info.find(b'HW')].replace(b'SN: ', b'')
            if pending_SN_info != self.SN_info:
                self.SN_info = pending_SN_info
                if self.lastportindex is None:
                    if 'USB0' in self.gateway_name:
                        self.lastportindex = 0
                    else:
                        self.lastportindex = 1
                else:
                    self.lastportindex += 1
        except:
            self.SN_info = self.DS_info[self.DS_info.find(b'SN'):self.DS_info.find(b'HW')].replace(b'SN: ', b'')
            if not final_ports_len or final_ports_len != 1:
                self.lastportindex = final_ports_ind
            else:
                if 'USB0' in self.gateway_name:
                    self.lastportindex = 0
                else:
                    self.lastportindex = 1
        data = self.GW_datalist[self.lastportindex]
        info_string = 'SerialManager - Configuring port with Setting ' + str(self.lastportindex)
        self.logger.debug(info_string)
        self.simple_logger.debug(info_string)
        cmd = '+ZC' + data[0] + data[1] + data[2] + '\r\n'
        self.write(cmd.encode('utf-8'))
        return (True, data)
    
    def gateway_reset_stop2bits(self):
        '''
        Using the same serial port, restart the serial port using the same Serial port settings as used in serial_open_gateway.
        '''
        self.close()
        self.baudrate = 115200
        self.bytesize = serial.EIGHTBITS
        self.parity = serial.PARITY_NONE
        self.stopbits = serial.STOPBITS_TWO
        self.timeout = self.per_packet_cd
        self.open()
        cmd = '+DR\r\n'
        self.write(cmd.encode('utf-8'))
        self.close()
    
    def ini_run(self, *args):
        '''
        Call-able INIT process for SerialObjectManager.
        By using the system utilities tools to list down all possible USB COM ports, each USB COM port is tested of its status.
        The first identifiable USB port will then be started and used.
        This function returns the serial port opening flag, port name and port ID configurations back to the caller.
        '''
        self.status = False
        self.logger, self.simple_logger, self.problem_logger, self.per_packet_cd, self.GW_datalist, self.lastportindex = args
        if self.lastportindex is None:
            self.SN_info = None
        ports = []
        true_ports_index_list = []
        final_ports = []
        for port_info in srl_tools.comports():
            ports.append(port_info[0])
        remove_list = []
        for port in ports:
            if port.find('USB') == -1:
                remove_list.append(port)
        for item in remove_list:
            ports.remove(item)
        for true_port in ports:
            ind = true_port.find('USB')
            true_port_index = true_port[ind+len('USB'):len(true_port)]
            true_ports_index_list.append((int(true_port_index), len(true_ports_index_list)))
        true_ports_index_list.sort()
        for j in range(0, len(true_ports_index_list)):
            final_ports.append(ports[true_ports_index_list[j][1]])
        self.final_gateway_name = None
        data = None
        ind = None
        for i in range(0, len(final_ports)):
            self.gateway_name = final_ports[i]
            open_status = self.serial_open_gateway()
            if open_status:
                cfg_flag, data = self.gw_initial(i, len(final_ports))
                if cfg_flag:
                    self.final_gateway_name = final_ports[i]
                    ind = i
                    self.status = True
                    break
                else:
                    try:
                        self.force_close()
                    except:
                        pass
        return (self.status, self.final_gateway_name, data, ind)

class RESTAPI(object):
    '''
    HTTP REST Server API object that shapes the properties of a Server around its communicating actions when a Web Servlet creates and hosts the Server.
    All functions below structures the Serial commands from the different types of data received in the Server, and sends it to be executed in the Serial port.
    All functions also return a application/json (not text/json) response with an accompanying OK query status back to the sending Web Client.
    '''
    bundle_breaker = '-'    
    def pollNode(self, nodeIdbundle):
        serverTime = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
        try:
            index_start_list = [0]
            index_end_list = []
            for i in re.finditer(self.bundle_breaker, nodeIdbundle):
                if i.start() != i.end():
                    index_start_list.append(i.end())
                    index_end_list.append(i.start())
            index_end_list.append(len(nodeIdbundle))
            if len(index_start_list) != len(index_end_list):
                resp = {'id': 0, 'result': 'Query string truncated, unable to interpret command', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=400,mimetype='application/json')
            else:
                for j in range(0, len(index_start_list)):
                    cmd = '+PM' + str(nodeIdbundle[index_start_list[j]:index_end_list[j]]) + '\r\n'
                    spec_string = 'Main Controller command: ' + cmd
                    self.logger.debug(spec_string)
                    self.simple_logger.debug(spec_string)
                    self.active_send_queue.put(cmd.encode('utf-8'))
                resp = {'id': 1, 'result': 'Query successfully sent', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=200,mimetype='application/json')
        except:
            resp = {'id': 0, 'result': 'Internal server processing error', 'dtime': serverTime}
            json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=500,mimetype='application/json')
        finally:
            return json_resp
    
    def findMeNode(self, nodeIdbundle):
        serverTime = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
        try:
            index_start_list = [0]
            index_end_list = []
            for i in re.finditer(self.bundle_breaker, nodeIdbundle):
                if i.start() != i.end():
                    index_start_list.append(i.end())
                    index_end_list.append(i.start())
            index_end_list.append(len(nodeIdbundle))
            if len(index_start_list) != len(index_end_list):
                resp = {'id': 0, 'result': 'Query string truncated, unable to interpret command', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=400,mimetype='application/json')
            else:
                for j in range(0, len(index_start_list)):
                    cmd = '+TFM' + str(nodeIdbundle[index_start_list[j]:index_end_list[j]]) + '\r\n'
                    spec_string = 'Main Controller command: ' + cmd
                    self.logger.debug(spec_string)
                    self.simple_logger.debug(spec_string)
                    self.active_send_queue.put(cmd.encode('utf-8'))
                resp = {'id': 1, 'result': 'Query successfully sent', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=200,mimetype='application/json')
        except:
            resp = {'id': 0, 'result': 'Internal server processing error', 'dtime': serverTime}
            json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=500,mimetype='application/json')
        finally:
            return json_resp
    
    def enableManualOverrideNode(self, nodeIdbundle):
        serverTime = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
        try:
            index_start_list = [0]
            index_end_list = []
            for i in re.finditer(self.bundle_breaker, nodeIdbundle):
                if i.start() != i.end():
                    index_start_list.append(i.end())
                    index_end_list.append(i.start())
            index_end_list.append(len(nodeIdbundle))
            if len(index_start_list) != len(index_end_list):
                resp = {'id': 0, 'result': 'Query string truncated, unable to interpret command', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=400,mimetype='application/json')
            else:
                for j in range(0, len(index_start_list)):
                    cmd = '+LM1' + str(nodeIdbundle[index_start_list[j]:index_end_list[j]]) + '\r\n'
                    spec_string = 'Main Controller command: ' + cmd
                    self.logger.debug(spec_string)
                    self.simple_logger.debug(spec_string)
                    self.active_send_queue.put(cmd.encode('utf-8'))
                resp = {'id': 1, 'result': 'Query successfully sent', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=200,mimetype='application/json')
        except:
            resp = {'id': 0, 'result': 'Internal server processing error', 'dtime': serverTime}
            json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=500,mimetype='application/json')
        finally:
            return json_resp
    
    def disableManualOverrideNode(self, nodeIdbundle):
        serverTime = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
        try:
            index_start_list = [0]
            index_end_list = []
            for i in re.finditer(self.bundle_breaker, nodeIdbundle):
                if i.start() != i.end():
                    index_start_list.append(i.end())
                    index_end_list.append(i.start())
            index_end_list.append(len(nodeIdbundle))
            if len(index_start_list) != len(index_end_list):
                resp = {'id': 0, 'result': 'Query string truncated, unable to interpret command', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=400,mimetype='application/json')
            else:
                for j in range(0, len(index_start_list)):
                    cmd = '+LM0' + str(nodeIdbundle[index_start_list[j]:index_end_list[j]]) + '\r\n'
                    spec_string = 'Main Controller command: ' + cmd
                    self.logger.debug(spec_string)
                    self.simple_logger.debug(spec_string)
                    self.active_send_queue.put(cmd.encode('utf-8'))
                resp = {'id': 1, 'result': 'Query successfully sent', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=200,mimetype='application/json')
        except:
            resp = {'id': 0, 'result': 'Internal server processing error', 'dtime': serverTime}
            json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=500,mimetype='application/json')
        finally:
            return json_resp
    
    def onNode(self, nodeIdbundle):
        serverTime = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
        try:
            index_start_list = [0]
            index_end_list = []
            for i in re.finditer(self.bundle_breaker, nodeIdbundle):
                if i.start() != i.end():
                    index_start_list.append(i.end())
                    index_end_list.append(i.start())
            index_end_list.append(len(nodeIdbundle))
            if len(index_start_list) != len(index_end_list):
                resp = {'id': 0, 'result': 'Query string truncated, unable to interpret command', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=400,mimetype='application/json')
            else:
                for j in range(0, len(index_start_list)):
                    cmd = '+LCB' + str(nodeIdbundle[index_start_list[j]:index_end_list[j]]) + '\r\n'
                    spec_string = 'Main Controller command: ' + cmd
                    self.logger.debug(spec_string)
                    self.simple_logger.debug(spec_string)
                    self.active_send_queue.put(cmd.encode('utf-8'))
                resp = {'id': 1, 'result': 'Query successfully sent', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=200,mimetype='application/json')
        except:
            resp = {'id': 0, 'result': 'Internal server processing error', 'dtime': serverTime}
            json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=500,mimetype='application/json')
        finally:
            return json_resp
    
    def offNode(self, nodeIdbundle):
        serverTime = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
        try:
            index_start_list = [0]
            index_end_list = []
            for i in re.finditer(self.bundle_breaker, nodeIdbundle):
                if i.start() != i.end():
                    index_start_list.append(i.end())
                    index_end_list.append(i.start())
            index_end_list.append(len(nodeIdbundle))
            if len(index_start_list) != len(index_end_list):
                resp = {'id': 0, 'result': 'Query string truncated, unable to interpret command', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=400,mimetype='application/json')
            else:
                for j in range(0, len(index_start_list)):
                    cmd = '+LCC' + str(nodeIdbundle[index_start_list[j]:index_end_list[j]]) + '\r\n'
                    spec_string = 'Main Controller command: ' + cmd
                    self.logger.debug(spec_string)
                    self.simple_logger.debug(spec_string)
                    self.active_send_queue.put(cmd.encode('utf-8'))
                resp = {'id': 1, 'result': 'Query successfully sent', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=200,mimetype='application/json')
        except:
            resp = {'id': 0, 'result': 'Internal server processing error', 'dtime': serverTime}
            json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=500,mimetype='application/json')
        finally:
            return json_resp
    
    def dimNode(self, nodeIdbundle):
        serverTime = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
        try:
            index_start_list = [0]
            index_end_list = []
            for i in re.finditer(self.bundle_breaker, nodeIdbundle):
                if i.start() != i.end():
                    index_start_list.append(i.end())
                    index_end_list.append(i.start())
            index_end_list.append(len(nodeIdbundle))
            if len(index_start_list) != len(index_end_list):
                resp = {'id': 0, 'result': 'Query string truncated, unable to interpret command', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=400,mimetype='application/json')
            else:
                for j in range(0, len(index_start_list)):
                    cmd = '+LCD' + str(nodeIdbundle[index_start_list[j]:index_end_list[j]]) + '\r\n'
                    spec_string = 'Main Controller command: ' + cmd
                    self.logger.debug(spec_string)
                    self.simple_logger.debug(spec_string)
                    self.active_send_queue.put(cmd.encode('utf-8'))
                resp = {'id': 1, 'result': 'Query successfully sent', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=200,mimetype='application/json')
        except:
            resp = {'id': 0, 'result': 'Internal server processing error', 'dtime': serverTime}
            json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=500,mimetype='application/json')
        finally:
            return json_resp
    
    def dimlevelNode(self, dimLvl, nodeIdbundle):
        serverTime = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
        try:
            index_start_list = [0]
            index_end_list = []
            for i in re.finditer(self.bundle_breaker, nodeIdbundle):
                if i.start() != i.end():
                    index_start_list.append(i.end())
                    index_end_list.append(i.start())
            index_end_list.append(len(nodeIdbundle))
            if len(index_start_list) != len(index_end_list):
                resp = {'id': 0, 'result': 'Query string truncated, unable to interpret command', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=400,mimetype='application/json')
            else:
                for j in range(0, len(index_start_list)):
                    cmd = '+LC' + str(dimLvl) + str(nodeIdbundle[index_start_list[j]:index_end_list[j]]) + '\r\n'
                    spec_string = 'Main Controller command: ' + cmd
                    self.logger.debug(spec_string)
                    self.simple_logger.debug(spec_string)
                    self.active_send_queue.put(cmd.encode('utf-8'))
                resp = {'id': 1, 'result': 'Query successfully sent', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=200,mimetype='application/json')
        except:
            resp = {'id': 0, 'result': 'Internal server processing error', 'dtime': serverTime}
            json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=500,mimetype='application/json')
        finally:
            return json_resp
    
    def softwareNode(self, actionType, nodeIdbundle):
        serverTime = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
        actionInterpreter = {
            'on': 'X1',
            'off': 'X2',
            'fault': 'X3',
            'cut': 'X4',
            'new': 'X5',
            'maintenanceNo': 'Y0',
            'maintenanceYes': 'Y1',
            'pole': 'Z',
        }
        actioncmdlist = actionType.split('-')
        strstr = ''
        for items in actioncmdlist:
            strstr += actionInterpreter.get(items,items)
        try:
            index_start_list = [0]
            index_end_list = []
            for i in re.finditer(self.bundle_breaker, nodeIdbundle):
                if i.start() != i.end():
                    index_start_list.append(i.end())
                    index_end_list.append(i.start())
            index_end_list.append(len(nodeIdbundle))
            if len(index_start_list) != len(index_end_list):
                resp = {'id': 0, 'result': 'Query string truncated, unable to interpret command', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=400,mimetype='application/json')
            else:
                for j in range(0, len(index_start_list)):
                    ind_node_ID = str(nodeIdbundle[index_start_list[j]:index_end_list[j]])
                    cmd = '#' + strstr + '|' + ind_node_ID + '|' + '00000'
                    spec_string = 'Main Controller software command: ' + cmd
                    self.logger.debug(spec_string)
                    self.simple_logger.debug(spec_string)
                    self.msg_queue.put((ind_node_ID,cmd.encode('utf-8'),'None'))
                resp = {'id': 1, 'result': 'Query successfully sent', 'dtime': serverTime}
                json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=200,mimetype='application/json')
        except:
            resp = {'id': 0, 'result': 'Internal server processing error', 'dtime': serverTime}
            json_resp = flask.Response(response=flask.json.dumps(resp),headers={'Access-Control-Allow-Origin':'*'},status=500,mimetype='application/json')
        finally:
            return json_resp
        
    def ini_run(self, *args):
        self.logger, self.simple_logger, self.active_send_queue, self.msg_queue = args
    
class RESTMainControllerThread(threading.Thread):
    '''
    A super-type Thread designed to grant it the ability to manage its variables and resources within a MULTIthreading environment.
    This thread focuses on running the WSGI HTTP Web Servlet, hosting its Server while handling requests using definitions of its API.
    Since the Clients are meant to exist externally in the World Wide Web, it listens to valid requests coming from all iPv4 connections.
    '''
    def __init__(self, *args):
        '''Start up variables taken from INIT arguments. Also starts up Event control functions and Flask Web Servlet.'''
        super(RESTMainControllerThread, self).__init__()
        self.arguments = args
        self.name = args[0]
        self.serverlink = args[1]
        self.packet_logger = args[2]
        self.simple_packet_logger = args[3]
        self.problem_logger = args[4]
        self.interval_sec = args[5]
        self.stop_event = threading.Event()
        self.app = flask.Flask(self.name)
        self.status_error_reasoning = None
        self.status_error_description = None
    
    def config_API(self):
        '''
        Ties in all the functions in the API object and connects it into specific internal URL addresses.
        The process is not dynamic, thus any new functions introduced in the API Object must be manually tied and added here for it to be usable.
        A 404 Not Found error will be issued back to the Client if a specific URL is not declared.
        '''
        self.app.add_url_rule('/gateway-serial-listener/poll-node/<string:nodeIdbundle>', view_func=self.serverlink.pollNode)
        self.app.add_url_rule('/gateway-serial-listener/find-me/<string:nodeIdbundle>', view_func=self.serverlink.findMeNode)
        self.app.add_url_rule('/gateway-serial-listener/enable-manual-override/<string:nodeIdbundle>', view_func=self.serverlink.enableManualOverrideNode)
        self.app.add_url_rule('/gateway-serial-listener/disable-manual-override/<string:nodeIdbundle>', view_func=self.serverlink.disableManualOverrideNode)
        self.app.add_url_rule('/gateway-serial-listener/on-node/<string:nodeIdbundle>', view_func=self.serverlink.onNode)
        self.app.add_url_rule('/gateway-serial-listener/off-node/<string:nodeIdbundle>', view_func=self.serverlink.offNode)
        self.app.add_url_rule('/gateway-serial-listener/dim-node/<string:nodeIdbundle>', view_func=self.serverlink.dimNode)
        self.app.add_url_rule('/gateway-serial-listener/dim-level-node/<string:dimLvl>/<string:nodeIdbundle>', view_func=self.serverlink.dimlevelNode)
        self.app.add_url_rule('/gateway-serial-listener/software/<string:actionType>/<string:nodeIdbundle>', view_func=self.serverlink.softwareNode)
    
    def status(self):
        return self.stop_event.is_set()        
    
    def status_error_reason(self):
        return (self.status_error_reasoning, self.status_error_description)
        
    def clone(self):
        return RESTMainControllerThread(*self.arguments)
    
    def run(self):
        '''
        Functions to be executed once the RESTMainControllerThread is started.
        An instance of the WSGI HTTP Server will be run at the specific port. Requests will be handled by the Servlet via parallel threading.
        '''
        self.config_API()
        spec_string = 'Running REST SERVER at port 9090.'
        self.packet_logger.debug(spec_string)
        self.simple_packet_logger.debug(spec_string)
        self.servlet = wsgiserver.WSGIServer(self.app,host='0.0.0.0',port=9090)
        try:
            self.servlet.start()
        except Exception as e:
            self.status_error_reasoning = e.__class__.__name__
            self.status_error_description = e.args[0]
            self.packet_logger.debug(e)
            self.problem_logger.error(e)
            self.servlet.stop()
            self.stop()
        finally:
            self.servlet.stop()
            self.stop()
    
    def stop(self):
        '''Functions to be executed if an unexpected exit has occurred, to both the super thread or the overall script. Stop event is set to cleanly exit the super thread.'''
        spec_string = self.name + ' - REST SERVER halted.'
        self.packet_logger.debug(spec_string)
        self.simple_packet_logger.debug(spec_string)
        self.stop_event.set()
        
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

        
class MainRecordThread(threading.Thread):
    '''
    A super-type Thread designed to grant it the ability to manage its variables and resources within a MULTIthreading environment.
    This thread focuses on logging all problems detected in node data packets along with their error description, which is tagged in messages sent to the record_queue.
    The reason behind dedicating a Thread to only write data to one file (which can same be done using logger.error) is due to the fact that file writing is slow.
    In order for the Listening-Recovery Thread to execute as fast as possible, whilst avoiding any data lost from crashes that can arise from I/O file writing, it's better for the system to store these problems in a queue.
    This method also allows the user to dynamically change the error recording format as data is not tied to one string received by the logger - just like how you can associate the error tag along with its error data. 
    '''
    def __init__(self, *args):
        '''Start up variables taken from INIT arguments. Also starts up Event control functions.'''
        super(MainRecordThread, self).__init__()
        self.arguments = args
        self.problem_logger = args[0]
        self.record_queue = args[1]
        self.stop_event = threading.Event()
        self.interval_sec = args[2]
        self.name = 'MainRecord'
    
    def status(self):
        return self.stop_event.is_set()    
    
    def clone(self):
        return MainRecordThread(*self.arguments)
    
    def run(self):
        '''
        Functions to be executed once the MainRecordThread is started.
        Records the error in a format defined by spec_string.
        '''
        while not self.stop_event.is_set():
            if self.interval_sec > 0:
                time.sleep(self.interval_sec/2)
            if self.record_queue.qsize() > 0:
                label_ID, description = self.record_queue.get()
                spec_string = label_ID.encode('utf-8') + b' : ' + description
                self.problem_logger.error(spec_string)
                if self.interval_sec > 0:
                    time.sleep(self.interval_sec/2)
                self.record_queue.task_done()
                
    def stop(self):
        '''Functions to be executed if an unexpected exit has occurred, to both the super thread or the overall script. Stop event is set to cleanly exit the super thread.'''
        self.stop_event.set()

class MainResetThread(threading.Thread):
    '''
    A super-type Thread designed to grant it the ability to manage its variables and resources within a MULTIthreading environment.
    This thread focuses on handling commands meant to be sent via 4 different queues, each with different functionality as described in __main__.
    Indirectly, the thread also handles Serial port writing resources, which can crash abruptly due to various types of errors, or occupied due to the common usage from other Main Threads.
    The auto port recovery function is not triggered here, but this Thread should consistently signal the one responsible for port recovery functions in order for this Thread functionality to be maximised.
    On top of the auto-DB node insert function, this Thread also plays a important role by triggering a reset and remembering the node ID, which is vital in the H2-E1-G0 validation process.
    '''
    def __init__(self, *args):
        '''Start up variables taken from INIT arguments. Also starts up Event control functions and port control variables.'''
        super(MainResetThread, self).__init__()
        self.arguments = args
        self.packet_logger = args[0]
        self.problem_logger = args[1]
        self.reset_queue = args[2]
        self.REST_controller_queue = args[3]
        self.reset_G0_confirmed_queue = args[4]
        self.TT_query_queue = args[5]
        self.stop_event = threading.Event()
        self.interval_sec = args[6]
        self.cooldown_sec = args[7]
        self.serial_obj = args[8]
        self.name = 'MainReset'
        self.pause_flag = False
        self.awaiting_E1_list = []
    
    def get_awaiting_E1_list(self):
        '''Returns to the caller on a list that records all the invalid node IDs which should emit E1s after being reset in the H2-E1-G0 validation process.'''
        return self.awaiting_E1_list
    
    def set_awaiting_E1_list(self):
        '''Resets the list that records all the historical, invalid node IDs which should emit E1s after being reset in the H2-E1-G0 validation process.'''
        self.awaiting_E1_list = []
    
    def get_pause_status(self):
        '''Returns to the caller on the pausing status of the whole command sending loop that is triggered due to the port status.'''
        return self.pause_flag
    
    def set_pause_status(self, *args):
        '''Resumes the command sending loop by correcting the pausing status. In the process, the serial port used is reloaded from the caller after the port recovery action is done.'''
        self.pause_flag = False
        self.serial_obj.close()
        self.serial_obj = args[0]
    
    def status(self):
        return self.stop_event.is_set()
    
    def clone(self):
        return MainResetThread(*self.arguments)    
    
    def run(self):
        '''
        Functions to be executed once the MainResetThread is started.
        While waiting for the data in the queues, this thread will consistently go into sleep.
        reset_G0_confirmed_queue is the only queue that is solely used for memory purposes in the node DB validation process.
        Other than that, TT_query_queue, REST_controller_queue and reset_queue are used to obtain commands from Threads and sent through the Serial port at a fixed number of times.
        (These 3 queues can also be commonly used in other MULTI-processes which requires command sending in the Serial port.) 
        '''
        while not self.stop_event.is_set():
            if self.cooldown_sec > 0:
                time.sleep(self.cooldown_sec/2)
            if self.stop_event.is_set():
                continue
            if self.reset_G0_confirmed_queue.qsize():
                if self.cooldown_sec > 0:
                    time.sleep(self.cooldown_sec/4)
                msg = self.reset_G0_confirmed_queue.get()
                if msg in self.awaiting_E1_list:
                    pass
                else:
                    self.awaiting_E1_list.append(msg)
                self.reset_G0_confirmed_queue.task_done()
            while self.TT_query_queue.qsize() > 0:
                if self.stop_event.is_set():
                    break
                if self.cooldown_sec > 0:
                    time.sleep(self.cooldown_sec/4)
                if self.pause_flag:
                    # read from somewhere to validate self.pause_flag
                    continue
                msg = self.TT_query_queue.get()
                try:
                    for _ in range(0, 2):
                        self.serial_obj.write(msg)
                        time.sleep(self.interval_sec)
                except:
                    self.TT_query_queue.task_done()
                    self.TT_query_queue.put(msg)
                    spec_string = 'Failed to send command ' + msg.decode('utf-8') + '.'
                    self.problem_logger.info(spec_string)
                    try:
                        fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
                    except:
                        pass
                    self.pause_flag = True
                    continue
                spec_string = 'Sending ' + msg.decode('utf-8') + ' to output.'
                self.packet_logger.debug(spec_string)
                self.TT_query_queue.task_done()
            while self.REST_controller_queue.qsize() > 0:
                if self.stop_event.is_set():
                    break
                if self.cooldown_sec > 0:
                    time.sleep(self.cooldown_sec/4)
                if self.pause_flag:
                    # read from somewhere to validate self.pause_flag
                    continue
                msg = self.REST_controller_queue.get()
                try:
                    for _ in range(0, 2):
                        self.serial_obj.write(msg)
                        time.sleep(self.interval_sec)
                except:
                    self.reset_queue.task_done()
                    self.reset_queue.put(msg)
                    spec_string = 'Failed to send command ' + msg.decode('utf-8') + '.'
                    self.problem_logger.info(spec_string)
                    try:
                        fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
                    except:
                        pass
                    self.pause_flag = True
                    continue
                spec_string = 'Sending ' + msg.decode('utf-8') + ' to output.'
                self.packet_logger.debug(spec_string)
                self.REST_controller_queue.task_done()
            while self.reset_queue.qsize() > 0:
                if self.stop_event.is_set():
                    break
                if self.cooldown_sec > 0:
                    time.sleep(self.cooldown_sec/4)
                if self.pause_flag:
                    # read from somewhere to validate self.pause_flag
                    continue
                msg = self.reset_queue.get()
                try:
                    for _ in range(0, 3):
                        self.serial_obj.write(msg)
                        time.sleep(self.interval_sec)
                except:
                    self.reset_queue.task_done()
                    self.reset_queue.put(msg)
                    spec_string = 'Failed to send command ' + msg.decode('utf-8') + '.'
                    self.problem_logger.info(spec_string)
                    try:
                        fcntl.flock(self.serial_obj.fileno(), fcntl.LOCK_UN | fcntl.LOCK_NB)
                    except:
                        pass
                    self.pause_flag = True
                    continue
                spec_string = 'Sending ' + msg.decode('utf-8') + ' to output.'
                self.packet_logger.debug(spec_string)
                self.reset_queue.task_done()
            if self.cooldown_sec > 0:
                time.sleep(self.cooldown_sec/2)
    
    def stop(self):
        '''Functions to be executed if an unexpected exit has occurred, to both the super thread or the overall script. Stop event is set to cleanly exit the super thread.'''
        self.stop_event.set()

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

class GPSDatabaseThread(threading.Thread):
    def __init__(self, packet_logger, problem_logger, node_ID, description, latitude, longitude, port_data, node_database_list):
        super(GPSDatabaseThread, self).__init__()
        self.packet_logger = packet_logger
        self.problem_logger = problem_logger
        self.node_ID = node_ID
        self.description = description
        self.latitude = latitude
        self.longitude = longitude
        self.port_data = port_data
        self.node_database_list = node_database_list
        self.stop_event = threading.Event()
        self.name = 'GPSDatabase'
        self.DB_flag = True
    
    def postgres_update(self, sp_data, sp_query):
        try:
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
            connection.set_session(autocommit=True)
            cursor = connection.cursor()
            cursor.execute(sp_query, sp_data)
        except (Exception, psycopg2.Error) as error:
            if sp_data[3].find('TBD-AUTO') == -1:
                error_string = 'PostgreSQL database update from local interrupted, exiting UPDATE...' + str(error)
                self.problem_logger.error(error_string)
                self.packet_logger.debug(error_string)
            else:
                pass
        finally:
            if(connection):
                cursor.close()
                connection.close()
    
    def run(self):
        try:
            _ = int(self.node_ID, 16)
        except:
            self.stop()
        if self.node_ID in self.node_database_list:
            tuple_data = (self.latitude, self.longitude, self.description, self.node_ID)
            query = '''update node_database set latitude = %s, longitude = %s, description = %s where node = %s'''
            debug_string = 'Updating node ' + str(tuple_data)
        else:
            tuple_data = (self.latitude, self.longitude, self.description, 'TBD-AUTO', self.node_ID, self.port_data[1], self.port_data[2])
            query = '''insert into node_database (latitude,longitude,description,pole_node,node,pan_id,channel) values (%s, %s, %s, %s, %s, %s, %s)'''
            debug_string = 'AUTO INSERTING into DB node list ' + str(tuple_data)
            self.problem_logger.info(debug_string)
        self.postgres_update(tuple_data, query)
        self.packet_logger.info(debug_string)
        self.stop()
    
    def stop(self):
        self.stop_event.set()
        
class DatabaseThread(threading.Thread):
    def __init__(self, packet_logger, problem_logger, msg_queue, node_ID_list, node_ID_datalist, ack, dtime_list, message_ID_list, override_flag_list, lamp_status_list):
        super(DatabaseThread, self).__init__()
        self.packet_logger = packet_logger
        self.problem_logger = problem_logger
        self.msg_queue = msg_queue
        self.dtime_stamp_list = dtime_list
        self.ack = ack
        self.node_ID_list = node_ID_list
        self.node_ID_datalist = node_ID_datalist
        self.message_ID_list = message_ID_list
        self.override_flag_list = override_flag_list
        self.lamp_status_list = lamp_status_list
        self.stop_event = threading.Event()
        self.name = 'Database'
    
    def postgres_fetch(self, node_ID, ack):
        try:
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
            cursor = connection.cursor()
            fetch_query = '''select dtime, msgid, dec_count, rollover_count, miss_count from filter_time_py where node = %s and ack = %s'''
            cursor.execute(fetch_query, (node_ID, ack))
            record = cursor.fetchall()
            return record
        except (Exception, psycopg2.Error) as error:
            error_string = 'Cannot update filter_time_py data without initial reference,' + str(error)
            self.problem_logger.error(error_string)
            self.packet_logger.debug(error_string)
        finally:
            if(connection):
                cursor.close()
                connection.close()
    
    def postgres_timecheck(self, data_time, packet_time):
        try:
            data_time_dt = data_time
            packet_time_dt = datetime.datetime.strptime(packet_time, '%Y-%m-%d %H:%M:%S')
            if data_time_dt < packet_time_dt:
                deltatime = packet_time_dt - data_time_dt
                return (True, deltatime)
            elif data_time_dt > packet_time_dt:
                deltatime = data_time_dt - packet_time_dt
                return (False, deltatime)
            else:
                raise
        except:
            return (-1, -1)
    
    def postgres_update(self, sp_data, sp_query):
        try:
            connection = psycopg2.connect(user='pi', port='5432', database='serial-gateway-program')
            connection.set_session(autocommit=True)
            cursor = connection.cursor()
            cursor.execute(sp_query, sp_data)
#             connection.commit()
            debug_string = 'Updating node ' + str(sp_data)
            self.packet_logger.info(debug_string)
        except (Exception, psycopg2.Error) as error:
            error_string = 'PostgreSQL database update from local interrupted, exiting UPDATE...' + str(error)
            self.problem_logger.error(error_string)
            self.packet_logger.debug(error_string)
        finally:
            if(connection):
                cursor.close()
                connection.close()        
    
    def run(self):
        for p in range(0, len(self.node_ID_list)):
            ini_record = self.postgres_fetch(self.node_ID_list[p], self.ack)
            if len(ini_record) == 1:
                for row in ini_record:
                    msg_ID_int = int(self.message_ID_list[p][1:len(msgID)])
                    version_num = int(self.message_ID_list[p][0:1])
                    if version_num > msgID_vers:
                        continue
                    msg_ID_pg = int(row[1][1:len(msgID)])
                    if msg_ID_int != msg_ID_pg:
                        entry_diff = msg_ID_int - msg_ID_pg
                        dtime_pg = row[0]
                        if entry_diff < 0:
                            if entry_diff >= -5:
                                flag = self.postgres_timecheck(dtime_pg, self.dtime_stamp_list[p])
                                if flag[0] == -1:
                                    self.stop()
                                if flag[1] == -1:
                                    continue
                                if self.ack.find('E4') == -1:
                                    try:
                                        if flag[1].days == 0 and flag[1].seconds <= 30:
                                            continue
                                    except:
                                        if flag[1].seconds <= 30:
                                            continue
                                dec_count_pg = int(row[2])
                                new_dec_count = dec_count_pg + 1
                                query = '''update filter_time_py set dtime = %s, msgid = %s, oo_msgid = %s, dec_count = %s where node = %s and ack = %s'''
                                tuple_data = (self.dtime_stamp_list[p], self.message_ID_list[p], msg_ID_pg, new_dec_count, self.node_ID_list[p], self.ack)
                                self.postgres_update(tuple_data, query)
                                self.msg_queue.put((self.node_ID_list[p], self.node_ID_datalist[p], 0))
                                # increment dec_count, overwrite data entry in DB, record fault as oo_msgid
                            else:
                                flag = self.postgres_timecheck(dtime_pg, self.dtime_stamp_list[p])
                                if flag[0] == -1:
                                    self.stop()
                                if flag[0]:
                                    if flag[1] == -1:
                                        continue
                                    if self.ack.find('E4') == -1:
                                        try:
                                            if flag[1].days == 0 and flag[1].seconds <= 30:
                                                continue
                                        except:
                                            if flag[1].seconds <= 30:
                                                continue
                                    ro_count_pg = int(row[3])
                                    new_ro_count = ro_count_pg + 1
                                    if entry_diff <= -max_msgID_count+6 and entry_diff > -max_msgID_count+1:
                                        ms_count = max_msgID_count + entry_diff
                                        query = '''update filter_time_py set dtime = %s, msgid = %s, rollover_count = %s, miss_count = %s, override_flag = %s, lamp_status = %s where node = %s and ack = %s'''
                                        tuple_data = (self.dtime_stamp_list[p], self.message_ID_list[p], new_ro_count, ms_count, self.override_flag_list[p], self.lamp_status_list[p], self.node_ID_list[p], self.ack)
                                        self.postgres_update(tuple_data, query)
                                        self.msg_queue.put((self.node_ID_list[p], self.node_ID_datalist[p], 0))
                                        # upload dtime, msgid; increment rollover_count and update miss_count
                                    else:
                                        query = '''update filter_time_py set dtime = %s, msgid = %s, rollover_count = %s, override_flag = %s, lamp_status = %s where node = %s and ack = %s'''
                                        tuple_data = (self.dtime_stamp_list[p], self.message_ID_list[p], new_ro_count, self.override_flag_list[p], self.lamp_status_list[p], self.node_ID_list[p], self.ack)
                                        self.postgres_update(tuple_data, query)
                                        self.msg_queue.put((self.node_ID_list[p], self.node_ID_datalist[p], 0))
                                        # upload dtime, msgid and increment rollover_count
                                else:
                                    if flag[1] == -1:
                                        continue
                                    if self.ack.find('E4') == -1:
                                        try:
                                            if flag[1].days == 0 and flag[1].seconds <= 30:
                                                continue
                                        except:
                                            if flag[1].seconds <= 30:
                                                continue
                                    dec_count_pg = int(row[2])
                                    new_dec_count = dec_count_pg + 1
                                    query = '''update filter_time_py set dtime = %s, msgid = %s, oo_msgid = %s, dec_count = %s where node = %s and ack = %s'''
                                    tuple_data = (self.dtime_stamp_list[p], self.message_ID_list[p], msg_ID_pg, new_dec_count, self.node_ID_list[p], self.ack)
                                    self.postgres_update(tuple_data, query)
                                    self.msg_queue.put((self.node_ID_list[p], self.node_ID_datalist[p], 0))
                                    # increment dec_count, overwrite data entry in DB, record fault as oo_msgid
                        elif entry_diff == 0:
                            continue
                        elif entry_diff > 0:
                            flag = self.postgres_timecheck(dtime_pg, self.dtime_stamp_list[p])
                            if flag[0] == -1:
                                self.stop()
                            if flag[0]:
                                if flag[1] == -1:
                                    continue
                                if self.ack.find('E4') == -1:
                                    try:
                                        if flag[1].days == 0 and flag[1].seconds <= 30:
                                            continue
                                    except:
                                        if flag[1].seconds <= 30:
                                            continue
                                query = '''update filter_time_py set dtime = %s, msgid = %s, override_flag = %s, lamp_status = %s where node = %s and ack = %s'''
                                tuple_data = (self.dtime_stamp_list[p], self.message_ID_list[p], self.override_flag_list[p], self.lamp_status_list[p], self.node_ID_list[p], self.ack)
                                self.postgres_update(tuple_data, query)
                                self.msg_queue.put((self.node_ID_list[p], self.node_ID_datalist[p], 0))
                                # upload dtime, msgid
                            else:
                                if flag[1] == -1:
                                    continue
                                if self.ack.find('E4') == -1:
                                    try:
                                        if flag[1].days == 0 and flag[1].seconds <= 30:
                                            continue
                                    except:
                                        if flag[1].seconds <= 30:
                                            continue
                                dec_count_pg = int(row[2])
                                new_dec_count = dec_count_pg + 1
                                query = '''update filter_time_py set dtime = %s, msgid = %s, oo_msgid = %s, dec_count = %s where node = %s and ack = %s'''
                                tuple_data = (self.dtime_stamp_list[p], self.message_ID_list[p], msg_ID_pg, new_dec_count, self.node_ID_list[p], self.ack)
                                self.postgres_update(tuple_data, query)
                                self.msg_queue.put((self.node_ID_list[p], self.node_ID_datalist[p], 0))
                                # increment dec_count, overwrite data entry in DB, record fault as oo_msgid
                    else:
                        dtime_pg = row[0]
                        flag = self.postgres_timecheck(dtime_pg, self.dtime_stamp_list[p])
                        if flag[0] == -1:
                            self.stop()
                        if flag[0]:
                            if flag[1] == -1:
                                continue
                            if self.ack.find('E4') == -1:
                                try:
                                    if flag[1].days == 0 and flag[1].seconds <= 30:
                                        continue
                                except:
                                    if flag[1].seconds <= 30:
                                        continue
                            if msg_ID_int == 0 and msg_ID_pg == 0:
                                query = '''update filter_time_py set dtime = %s, msgid = %s, override_flag = %s, lamp_status = %s where node = %s and ack = %s'''
                                tuple_data = (self.dtime_stamp_list[p], self.message_ID_list[p], self.override_flag_list[p], self.lamp_status_list[p], self.node_ID_list[p], self.ack)
                                self.postgres_update(tuple_data, query)
                                self.msg_queue.put((self.node_ID_list[p], self.node_ID_datalist[p], 0))
                            else:
                                if self.ack.find('E4') == -1:
                                    continue
                                else:
                                    query = '''update filter_time_py set dtime = %s, msgid = %s, override_flag = %s, lamp_status = %s where node = %s and ack = %s'''
                                    tuple_data = (self.dtime_stamp_list[p], self.message_ID_list[p], self.override_flag_list[p], self.lamp_status_list[p], self.node_ID_list[p], self.ack)
                                    self.postgres_update(tuple_data, query)
                                    self.msg_queue.put((self.node_ID_list[p], self.node_ID_datalist[p], 0))
            else:
                query = '''insert into filter_time_py (node,ack,dtime,msgid,override_flag,lamp_status) values (%s, %s, %s, %s, %s, %s)'''
                tuple_data = (self.node_ID_list[p], self.ack, self.dtime_stamp_list[p], self.message_ID_list[p], self.override_flag_list[p], self.lamp_status_list[p])
                self.postgres_update(tuple_data, query)
                self.msg_queue.put((self.node_ID_list[p], self.node_ID_datalist[p], 0))
        self.stop()
        
    def stop(self):
        self.stop_event.set()

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

'''[External configuration file user-defined variables]'''
file_pathname = str(os.path.abspath(os.path.dirname(sys.argv[0])))
updating_database_localpath = file_pathname + '/' + str(pygw_conf.localDBpath)
problemlogpath = file_pathname + '/' + str(pygw_conf.problemlogpath)
logfilepath = file_pathname + '/' + str(pygw_conf.logfilepath)
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
    # my_logger_* :- Different static file loggers for different occasions (usage details as below)        
    # formatter_* :- Different logging formats                                                            
    # options_string :- Startup argument string creation for declaration of extra functions    
    # all_other_main_threads :- Initial list of other Main-type threads that will be used for WATCHDOG monitoring
    # datenow, datein :- Startup reference dates for script startup and other variables                             
    # *_datetimenow :- Formation of time stamps according to times declared in config.properties                    
    # between_flag :- time profiles determined by active_time and inactive_time of config.properties                
    # *_fh :- File handlers to park formatter_* alongside repository properties                                        
    # my_logger_* :- (Usage details)                                                                                
    #    my_logger[debug] - Displays data in console only                                                            
    #    my_logger[info&+] - Displays data in console, records system time & data in 2-line format in gateway.log.*    
    #    my_logger_simple[debug&+] - Records system time & data in 1-line format in gateway.log.*                    
    #    my_logger_problem[debug&+] - Records system time & data in 1-line format in error.log.*            
    # kmlpathname :- Filename for .kml type map created using reference date                    
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
    
    
    '''
    [Creating dynamic/inheritable objects to support resources used by Threads]
    # DatabaseAligner :- Database-type actions, used to select/configure data in DB                        
    # SerialObjectManager :- USB/COM port actions, supports dynamic runtime usage                        
    # KMLMapManager :- Mapping actions, for .xml file type logging specific to Google Earth                
    # RESTAPI :- Properties for external Web REST Server application when receiving GET requests
    '''
    DBAligner = StatObjectExceptionAPI(DatabaseAligner,my_logger,my_logger_problem)
    KMLMapper = StatObjectExceptionAPI(KMLMapManager,my_logger,my_logger_problem)
    SerialProcessObject = SerialObjectManager()
    RESTAPIObject = RESTAPI()


    '''
    [Manually INIT dynamic/inheritable objects with start up variables]
    # KMLDocumentElement :- File pointer to write map data that points back to KMLMapper
    # port_* :- Port resources pointer that points back to port determined by SerialProcessObject
    # node_database_list :- Main node list cross-checked by static database determined by DBAligner
    # options_status_dict (all flags are initially disabled)
    :- 'DBUP', enable function to auto-sync DB with Excel daily, or on every port switch
    :- 'GPSUP', enable GPS mapping feature
    :- 'DEMOUP', disable all node recovery actions during runtime
    :- 'TESTUP', disable data sending to main server, only to test server(s) listed in configuration
    :- 'NOSELMOS', disable uploading data to remote servers
    :- 'NOPOLL', disable cycle-based active polling actions for preset node list
    :- 'NOAUTH', disable basic authentication level on packet sent
    '''
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
    
    node_database_list = DBAligner.run(my_logger, my_logger_simple, my_logger_problem, port_data, [first_GW_data, second_GW_data], options_status_dict['DBUP'])
    if node_database_list == []:
        error_string = 'DBUP - PostgreSQL database has no target nodes, deactivating code.'
        my_logger.debug(error_string)
        my_logger_problem.error(error_string)
    '''
    [Starting up all Main-type threads, each with distinctive functions]
    # If no USB ports are found during startup, no threads will succeed and the script will exit.
    # If startup argument has 'NOPOLL', only the MainPollingThread is disabled. All other functions will be alive, and SerialPort occupied.
    # If startup argument has 'GPSUP', MainPollingThread will double poll for GPS data at a specific time, which will then be used by the KMLMapper object.
    # If startup argument has 'NOSELMOS', any updated packet data will not be uploaded to SELMOS. Only to be used in gateway in which its configuration has not been set up properly to not affect big data.
    # poll_t (MainPolling)        :-    1. Used to poll for node heart beat/GPS data when given a node list. 
    #                                2. Confirms GPS data from nodes in daily cycles to disable double recording.
    # reset_t (MainReset)        :-    1. Used to send reset commands for nodes who are deemed faulty at the time, determined by listened packets.
    #                                2. Forward commands sent from REST SELMOS application to the SerialPort.
    #                                3. Confirms Timetable queries for nodes who are deemed corrupted in its timetable configuration, determined by listened packets.
    #                                4. Confirms auto-DB insert node queries for nodes who completes the reactive reset sequence, determined by listened packets.
    # record_t (MainRecord)        :-    1. Tags faulty packets with different error types and records them. Dedicated to error log.
    # mqtt_t (MQTT, unused)        :-    1. Client central to publish data via MQTT link to message broker.
    #                                 2. Accepts all data asynchronously from all client sources in the message broker.
    # REST_t (MainController)    :-    1. Server central to accept data via HTTP link from all valid client sources.
    # http_t (MainHTTPURL)        :-    1. Client central to send data via HTTP link to rest_location
    '''
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
        record_t = MainRecordThread(my_logger_problem, record_queue, 1)
        record_t.start()
        record_flag = True
        all_other_main_threads.append((record_t.name, record_t))
    except:
        record_flag = False
        my_logger.warning('Record thread disabled.')
    try:
        if port_status == False:
            raise
        REST_t = RESTMainControllerThread('MainController', RESTAPIObject, my_logger, my_logger_simple, my_logger_problem, 0.5)
        REST_t.start()
        REST_flag = True
        all_other_main_threads.append((REST_t.name, REST_t))
    except:
        REST_t = RESTMainControllerThread('MainController', RESTAPIObject, my_logger, my_logger_simple, my_logger_problem, 0.5)
        REST_t.stop()
        REST_flag = False
        my_logger.warning('REST server thread disabled.')
    try:
        if port_status == False:
            raise
        http_t = MainHTTPURLThread(my_logger, my_logger_simple, my_logger_problem, msg_queue, full_URLstring, 0.5, options_status_dict, test_align_flag)
        http_t.start()
        http_flag = True
        all_other_main_threads.append((http_t.name, http_t))
    except:
        http_t = MainHTTPURLThread(my_logger, my_logger_simple, my_logger_problem, msg_queue, full_URLstring, 0.5, options_status_dict, test_align_flag)
        http_t.stop()
        http_flag = False
        my_logger.warning('HTTP-URL thread disabled.')
    '''
    [Main Listener loop start-up variables]
    # *_threads :- Since multiple Listener processing threads can be created at the same time, these variables help to cleanly execute and kill threads as the main loop iterates.
    # read_port_status :- Defaults to the current port status. Must be True at start. Used for dynamic port switching in code runtime.
    # msg_recv :- Total number of received ACKs via HTTP/MQTT link, fetched from Main-type thread. Resets daily. Defaults to None if http_t/mqtt_t is not alive.
    # msg_publish :- Total number of sent packets via HTTP/MQTT link, fetched from Main-type thread. Resets daily. Defaults to None if http_t/mqtt_t is not alive.
    # hoursoffset :- Defaults & resets daily to 24 hours, as an increment to dynamic time checkpoints. Mainly used within active hours to record hourly statistics.
    # If startup argument has 'DEMOUP', all manual control lantern options are allowed from various sources, and will not be reset or re-overwritten by autonomous control. Ideal for DEMO mode only. 
    '''  
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
    '''
    [Start of Main Listener loop]
    '''
    try:
        spec_string = '[START] PYGATEWAY LISTENER @ ' + time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
        my_logger.info(spec_string)
        portcheck_datetimenow = datetime.datetime(*time.localtime()[:6]) + datetime.timedelta(hours=1)
        while True:
            datetimenow = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())
            dt_datetimenow = datetime.datetime(*time.localtime()[:6])
            '''Main threads (excluding loop) internal WATCHDOG manager'''
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
                if len(inactive_other_main_threads)    >= 1:
                    for l in range(0, len(inactive_other_main_threads)):
                        all_other_main_threads.remove(inactive_other_main_threads[l])
                    inactive_other_main_threads.clear()
                if len(new_other_main_threads) >= 1:
                    for m in range(0, len(new_other_main_threads)):
                        all_other_main_threads.append(new_other_main_threads[m])
                    new_other_main_threads.clear()
            '''Full database & poll list manager'''
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
            '''Daily parameters refresh'''
            portchecktimedelta = portcheck_datetimenow - dt_datetimenow
            if portchecktimedelta.days < 0:
                portcheck_datetimenow += datetime.timedelta(hours=1)
                read_port_status, port_data = SerialProcessObject.gw_initial(port_index, None)
            '''
            8/6/2021 - Moved poll_t.set_GPS_confirmed_list() to daily repositories refresh section due to changes in output only single .kml file
            - However, reset_t.set_awaiting_E1_list() remains on-date, due to node not being recognised on-time before new GPS polling cycle.
            '''
            GPStimedelta = GPSactive_datetimenow - dt_datetimenow
            if GPStimedelta.days < 0:
                GPSactive_datetimenow += datetime.timedelta(days=1)
                if reset_flag:
                    reset_t.set_awaiting_E1_list()
            if between_flag == 2:
                pass
            else:
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
                else:
                    pass
            '''Daily repositories refresh'''
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
                packet = SerialProcessObject.read_until('#\r\n ')
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
            '''Listener thread manager for packet listeners'''
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
            '''Serial port manager'''
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
                        node_database_list = DBAligner.run(my_logger, my_logger_simple, my_logger_problem, port_data, [first_GW_data, second_GW_data], options_status_dict['DBUP'])
                        if poll_flag:
                            if forced_port_switch_flag:#reset poll loop count, reset all polling param, forced port flag False
                                port_index = retry_port_index
                                forced_port_switch_flag = False
                                last_port_index = None
                                poll_t.set_pause_status(spo_2)
                                _ , poll_exempt_list = DBAligner.final_read(port_data)
                                if last_port_index != retry_port_index:
                                    poll_t.set_check_override_off_status()
                                    poll_t.set_poll_list(node_database_list, poll_exempt_list)
                                else:
                                    poll_t.set_poll_list(None, poll_exempt_list)
                            else:
                                poll_t.set_pause_status(spo_2)
                                _ , poll_exempt_list = DBAligner.final_read(port_data)
                                if port_index != retry_port_index:
                                    port_index = retry_port_index
                                    poll_t.set_check_override_off_status()
                                    poll_t.force_continue_loop()
                                    poll_t.set_poll_list(node_database_list, poll_exempt_list)
                                else:
                                    poll_t.set_poll_list(None, poll_exempt_list)
                        else:
                            if options_status_dict['NOPOLL']:
                                all_other_main_threads.append((poll_t.name, poll_t))
                        if not http_flag:
                            all_other_main_threads.append((http_t.name, http_t))
                        if not REST_flag:
                            all_other_main_threads.append((REST_t.name, REST_t))
                    else:
                        if abs(dt_datetimenow.second) == 0:
                            my_logger.debug('All serial ports cannot be opened: reconnecting...')
                            my_logger_simple.debug('All serial ports cannot be opened: reconnecting...')
                            time.sleep(0.5)
                except serial.SerialException as error:
                    if abs(dt_datetimenow.second) == 0:
                        my_logger.debug(error)
                        my_logger_simple.debug(error)
                        time.sleep(0.5)
    finally:
        if poll_flag:
            poll_t.stop()
            poll_t.join()
        if reset_flag:
            reset_t.stop()
            reset_t.join()
        if record_flag:
            record_t.stop()
            record_t.join()
        if http_flag:
            http_t.stop()
            http_t.join()
        if REST_flag:
            REST_t.stop()
            REST_t.join()
        for threads in listener_threads:
            threads.stop()
            threads.join()
        my_logger.debug('All threading processes stopped.')
        my_logger_simple.debug('All threading processes stopped.')
    
if __name__ == '__main__':
    main() 
