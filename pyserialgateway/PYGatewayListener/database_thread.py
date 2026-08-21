'''
DatabaseThread: validates and commits an incoming node data packet (ack,
timestamps, message ID, override/lamp status) to PostgreSQL.
'''
import datetime
import psycopg2
import threading

from .config import msgID, msgID_vers, max_msgID_count

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

