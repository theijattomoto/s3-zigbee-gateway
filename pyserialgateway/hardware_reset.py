#! /usr/bin/python3

import os
import subprocess
import fcntl
import logging
from logging import handlers
import sys
import time
try:
	import config_PYproperties
except:
	print('Script configurations not set, script is not executed.')
	sys.exit(1)

file_pathname = str(os.path.abspath(os.path.dirname(sys.argv[0])))
problemlogpath = file_pathname + '/' + config_PYproperties.problemlogpath
logfilepath = file_pathname + '/' + config_PYproperties.logfilepath
CONST_USB_DEV_FS_RESET_CODE = ord('U') << (4*2) | 20
USB_CONVERTER_NAME = 'CP210x'
if __name__ == '__main__':
	my_logger = logging.getLogger('PacketListener')
	my_logger.setLevel(logging.DEBUG)
	my_logger_problem = logging.getLogger('MainReset')
	my_logger_problem.setLevel(logging.DEBUG)
	formatter_simplelog = logging.Formatter('%(threadName)s:%(asctime)s - %(message)s\n', datefmt='%Y-%m-%d,%H:%M:%S')
	formatter_stdo = logging.Formatter('%(asctime)s  %(threadName)s:%(lineno)d - %(message)s\n', datefmt='%Y-%m-%d,%H:%M:%S')
	stdoh = logging.StreamHandler(sys.stdout)
	stdoh.setLevel(logging.INFO)
	stdoh.setFormatter(formatter_stdo)
	my_logger.addHandler(stdoh)
	simple_fh = handlers.RotatingFileHandler(logfilepath+'/gateway.log', maxBytes=5000000, backupCount=100)
	simple_fh.setLevel(logging.DEBUG)
	simple_fh.setFormatter(formatter_simplelog)
	my_logger.addHandler(simple_fh)
	problem_fh = handlers.RotatingFileHandler(problemlogpath+'/error.log', maxBytes=500000, backupCount=25)
	problem_fh.setLevel(logging.INFO)
	problem_fh.setFormatter(formatter_simplelog)
	my_logger_problem.addHandler(problem_fh)
	
	final_usb_path_list = []
	proc_1 = subprocess.Popen(['lsusb'], stdout=subprocess.PIPE)
	cmd_output_1 = proc_1.communicate()[0]
	usb_device_list = cmd_output_1.split(b'\n')
	for items in usb_device_list:
		if USB_CONVERTER_NAME.encode('utf-8') in items:
			usb_dev_details = items.split()
			usb_bus = usb_dev_details[1]
			usb_dev = usb_dev_details[3][:3]
			device_path_name = '/dev/bus/usb/' + usb_bus.decode('utf-8') + '/' + usb_dev.decode('utf-8')
			final_usb_path_list.append(device_path_name)
			spec_string = '[HWRESET] - Invoking hardware refresh on bus device ' + device_path_name
			my_logger.debug(spec_string)
	for usb_devices in final_usb_path_list:
		try:
			device_file = os.open(usb_devices, os.O_WRONLY)
			fcntl.ioctl(device_file, CONST_USB_DEV_FS_RESET_CODE, 0)
		except Exception as err:
			my_logger.debug(err)
			my_logger_problem.info(err)
		finally:
			try:
				os.close(device_file)
			except:
				pass
			time.sleep(1)
