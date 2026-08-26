'''
Centralized PostgreSQL connection helper.

Every module that used to call psycopg2.connect(user='radxa', port='5432',
database='serial-gateway-program') directly now calls get_connection()
from here instead. Connection details (host, port, user, password,
database name) are read once from config.py (which in turn reads them
from pygw_conf.py), so deploying this code on a different machine - a
different OS user, a remote Postgres host, a different database name -
only ever requires editing pygw_conf.py, not hunting through the code.

Backward compatible by default: if pygw_conf.py doesn't define any of the
db_* settings (an older config file that predates this), get_connection()
falls back to exactly what was hardcoded before (local socket, user
'radxa', port 5432, database 'serial-gateway-program', no password) - see
config.py for the defaults.
'''
import psycopg2

from .config import db_host, db_port, db_user, db_password, db_name


def get_connection():
    '''
    Returns a new psycopg2 connection using the configured db_* settings.
    host/password are only included if actually set, so the default
    (unset) case connects via the local Unix socket with peer
    authentication - identical to every psycopg2.connect(...) call this
    replaces.
    '''
    kwargs = {'user': db_user, 'port': db_port, 'database': db_name}
    if db_host:
        kwargs['host'] = db_host
    if db_password:
        kwargs['password'] = db_password
    return psycopg2.connect(**kwargs)