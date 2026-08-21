'''
GPSDatabaseThread: writes a confirmed GPS fix for a single node to
PostgreSQL.
'''
import psycopg2
import threading

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
        

