'''
Created on 30 Jul 2021

@author: ljyee
'''

import sys
import pyserialgateway.PYGatewayListener as running_main

options_string = ''.join(str(elements) for elements in sys.argv[1:])

if __name__ == '__main__':
    try:
        running_main.main(options_string)
    except Exception as error:
        print(error)
    finally:
        sys.exit(0)
    