'''
SerialObjectManager: wraps serial.Serial to discover, open, and manage the
USB/COM gateway serial port.
'''
import serial
import serial.tools.list_ports as srl_tools
import fcntl

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

