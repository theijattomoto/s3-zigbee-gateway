'''
Small shared helper classes: the process-time Clock stopwatch, and the
StatObjectExceptionAPI wrapper that standardises error handling for
DatabaseAligner and KMLMapManager method calls.
'''
import time
import sys
import psycopg2

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

