from django.db import DEFAULT_DB_ALIAS
from django.db import DatabaseError
from django.db.models.sql.query import RawQuery

from pyserver.common.db import connections


class SmartRawQuery(RawQuery):
    def get_columns(self):
        if self.cursor is None:
            self._execute_query()
        converter = connections[self.using].introspection.table_name_converter
        # dynamically calculate the column names
        if not hasattr(self, "_column_names"):
            try:
                self.cursor.fetchone()
                self._column_names = [converter(column_meta[0])
                    for column_meta in self.cursor.description]
                self.cursor.scroll(-1)
            except:
                raise DatabaseError("resolving query column error...")
        return self._column_names

    def _execute_query(self):
        if self.using is None:
            self.using = DEFAULT_DB_ALIAS
        self.cursor = connections[self.using].cursor()
        self.cursor.execute(self.sql, self.params)

    def _get_counter_cursor(self):
        if self.using is None:
            self.using = DEFAULT_DB_ALIAS
        self.counter_cursor = connections[self.using].cursor()
        return self.counter_cursor

    def __getitem__(self, k):
        if not isinstance(k, (slice, int, long)):
            raise TypeError
        assert ((not isinstance(k, slice) and (k >= 0))
                or (isinstance(k, slice) and (k.start is None or k.start >= 0)
                    and (k.stop is None or k.stop >= 0))), \
                "Negative indexing is not supported for %s." % self.__class__

        if self.cursor is None:
            self._execute_query()

        if isinstance(k, (int, long)):
            if k > 0:
                self.cursor.scroll(k)
            #else:
            #    self.cursor.scroll(k)
            res = self.cursor.fetchone()
            # scroll back to the original location.
            #if k == 0:
            #    self.cursor.scroll(-1)
            #else:
            #    self.cursor.scroll(-k)
        else:
            # here we really don't support the concpet of step in a slice
            # a slice(start, stop, step)
            start = 0 if k.start is None else k.start
            stop = 9999*25 if k.stop is None else k.stop
            if start > 0:
                self.cursor.scroll(start)
            res = self.cursor.fetchmany(stop - start)
            # scroll back to the original location.
            #self.cursor.scroll(1-k.stop)
        # if in pscopg2.5 we can do this.
        self.cursor.scroll(0, mode='absolute')
        return res
