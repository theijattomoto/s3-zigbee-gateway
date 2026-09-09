'''
RESTAPI: Flask view functions for the incoming REST commands (poll, find-me,
override, on/off, dim, software update).
RESTMainControllerThread: runs the Flask/WSGI server for RESTAPI in its own
thread.
'''
import time
import re
import threading
import flask
import wsgiserver

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
        '''Stop the REST server and allow the controller thread to exit cleanly.'''
        spec_string = self.name + ' - REST SERVER halted.'
        self.packet_logger.debug(spec_string)
        self.simple_packet_logger.debug(spec_string)
        self.stop_event.set()
        try:
            if hasattr(self, 'servlet') and self.servlet is not None:
                self.servlet.stop()
        except Exception as error:
            self.problem_logger.error(
                self.name + ' - REST server shutdown error: ' + str(error)
            )
        

