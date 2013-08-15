from django.conf import settings
from django.core import signals
from django.core.exceptions import ImproperlyConfigured

from django.db.utils import (ConnectionRouter, load_backend,
                                DEFAULT_DB_ALIAS, DatabaseError, IntegrityError)

from help_utils import PostgresConnectionHandler
from help_base import pgServerSideCurorDBWrapper


if DEFAULT_DB_ALIAS not in settings.DATABASES:
    raise ImproperlyConfigured("You must define a '%s' database" % DEFAULT_DB_ALIAS)

#here use a different connection handler
connections = PostgresConnectionHandler(settings.DATABASES)

router = ConnectionRouter(settings.DATABASE_ROUTERS)

class DefaultConnectionProxy(object):
    """
    Proxy for accessing the default DatabaseWrapper object's attributes. If you
    need to access the DatabaseWrapper object itself, use
    connections[DEFAULT_DB_ALIAS] instead.
    """
    def __getattr__(self, item):
        return getattr(connections[DEFAULT_DB_ALIAS], item)

    def __setattr__(self, name, value):
        return setattr(connections[DEFAULT_DB_ALIAS], name, value)

connection = DefaultConnectionProxy()
backend = load_backend(connection.settings_dict['ENGINE'])
backend.DatabaseWrapper = pgServerSideCurorDBWrapper

# Register an event that closes the database connection
# when a Django request is finished.
def close_connection(**kwargs):
    for conn in connections.all():
        conn.close()
signals.request_finished.connect(close_connection)

# Register an event that resets connection.queries
# when a Django request is started.
def reset_queries(**kwargs):
    for conn in connections.all():
        conn.queries = []
signals.request_started.connect(reset_queries)

# Register an event that rolls back the connections
# when a Django request has an exception.
def _rollback_on_exception(**kwargs):
    from django.db import transaction
    for conn in connections:
        try:
            transaction.rollback_unless_managed(using=conn)
        except DatabaseError:
            pass
signals.got_request_exception.connect(_rollback_on_exception)