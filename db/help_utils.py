import os
from threading import local

from django.conf import settings
from django.db.utils import load_backend, ConnectionDoesNotExist
from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module

from help_base import pgServerSideCurorDBWrapper


class PostgresConnectionHandler(object):
    def __init__(self, databases, user_server_side_cursor = True):
        self.user_server_side_cursor = True
        self.databases = databases
        self._connections = local()

    def ensure_defaults(self, alias):
        """
        Puts the defaults into the settings dictionary for a given connection
        where no settings is provided.
        """
        try:
            conn = self.databases[alias]
        except KeyError:
            raise ConnectionDoesNotExist("The connection %s doesn't exist" % alias)

        conn.setdefault('ENGINE', 'django.db.backends.dummy')
        if conn['ENGINE'] == 'django.db.backends.' or not conn['ENGINE']:
            conn['ENGINE'] = 'django.db.backends.dummy'
        conn.setdefault('OPTIONS', {})
        conn.setdefault('TIME_ZONE', 'UTC' if settings.USE_TZ else settings.TIME_ZONE)
        for setting in ['NAME', 'USER', 'PASSWORD', 'HOST', 'PORT']:
            conn.setdefault(setting, '')
        for setting in ['TEST_CHARSET', 'TEST_COLLATION', 'TEST_NAME', 'TEST_MIRROR']:
            conn.setdefault(setting, None)

    def __getitem__(self, alias):
        if hasattr(self._connections, alias):
            return getattr(self._connections, alias)

        self.ensure_defaults(alias)
        db = self.databases[alias]
        backend = load_backend(db['ENGINE'])
        # this allows system to create a different type of SQL
        if backend.__name__.split(".")[3] == "postgresql_psycopg2" and \
                                                   self.user_server_side_cursor:
            conn = pgServerSideCurorDBWrapper(db, alias)
        else:
            conn = backend.DatabaseWrapper(db, alias)
        setattr(self._connections, alias, conn)
        return conn

    def __setitem__(self, key, value):
        setattr(self._connections, key, value)

    def __iter__(self):
        return iter(self.databases)

    def all(self):
        return [self[alias] for alias in self]