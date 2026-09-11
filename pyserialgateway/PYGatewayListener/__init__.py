'''
pyserialgateway.PYGatewayListener package.

This is the S5 serial gateway listener, split out of the original
single-file PYGatewayListener.py into one module per class (plus a config
module for the argparse/pygw_conf-derived settings) for readability.

pygw_main.py runs this as:

    import pyserialgateway.PYGatewayListener as running_main
    running_main.main(options_string)

so `main` is re-exported here at package level to keep that call site
working unchanged.
'''

from .main import main
