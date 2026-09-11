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
import logging
import logging.handlers


class NonRotatingFileHandler(logging.FileHandler):
    """Compatibility handler for legacy RotatingFileHandler call sites.

    Rotation and retention are owned by the host logrotate policy. The
    maxBytes and backupCount arguments are accepted only to preserve the
    legacy constructor signature while preventing application-side .1/.2
    rotations.
    """

    def __init__(
        self,
        filename,
        mode='a',
        maxBytes=0,
        backupCount=0,
        encoding=None,
        delay=False,
        errors=None,
    ):
        super().__init__(
            filename,
            mode=mode,
            encoding=encoding,
            delay=delay,
            errors=errors,
        )


# Keep the large legacy main module unchanged while making Linux logrotate the
# sole owner of daily rotation. This can be removed once the legacy logger
# setup is refactored to instantiate FileHandler directly.
logging.handlers.RotatingFileHandler = NonRotatingFileHandler

from .main import main
