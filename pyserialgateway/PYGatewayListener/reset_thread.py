'''
MainResetThread: sends reset commands to nodes flagged as faulty, and
forwards commands received from the REST controller queue to the serial
port.
'''
import time
import threading
import fcntl

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

