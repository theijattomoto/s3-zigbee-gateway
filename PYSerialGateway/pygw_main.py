'''
Created on 30 Jul 2021

@author: ljyee
'''

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pyserialgateway.PYGatewayListener as running_main

options_string = ''.join(str(elements) for elements in sys.argv[1:])

if __name__ == '__main__':
    try:
        running_main.main(options_string)
    except Exception as error:
        print(error)
    finally:
        sys.exit(0)
    