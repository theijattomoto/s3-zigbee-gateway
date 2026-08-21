'''
MainRecordThread: drains the record_queue and logs faulty/unrecognised
packets to the error log.
'''
import time
import threading

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

