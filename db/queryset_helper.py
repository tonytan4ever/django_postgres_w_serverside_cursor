from django.db import models
from django.db.models.query import RawQuerySet
from django.db.utils import DEFAULT_DB_ALIAS
from django.db.models.query_utils import (deferred_class_factory, InvalidQuery)

from pyserver.common.db import connections
from pyserver.common.db import sql_query_helper
import psycopg2


class SmartPaginatableRawQuerySet(RawQuerySet):
    """
    Provides an iterator which converts the results of raw SQL queries into
    annotated model instances.
    """
    def __init__(self, raw_query, model=None, query=None, params=None,
        translations=None, using=None, page_count_mode = 'NORMAL'):
        self.raw_query = raw_query
        self.model = model
        self._db = using
        self.query = query or sql_query_helper.SmartRawQuery(sql=raw_query, using=self.db, params=params)
        self.params = params or ()
        self.translations = translations or {}
        if self.model is None:
            self.model = self.create_model("fake_model_name")
        self.page_count_mode = page_count_mode
        self.count_sql = 'select count(*) from (' + raw_query + ') as prq1'

    @property
    def db(self):
        """Return the database that will be used if this query is executed now
        this provides a chance to user router, for right now just return the 
        default database
        """
        return self._db or DEFAULT_DB_ALIAS

    def create_model(self, name):
        fields = {}
        title_list = self.query.get_columns()
        for title in title_list:
            fields[title] = models.CharField(max_length=255)

        class Meta:
            pass

        setattr(Meta, 'app_label', 'fake')
        fields['__module__'] = 'fake'
        fields['Meta'] = Meta

        model = type(name, (models.Model,), fields)
        return model

    def __getitem__(self, k):
        # Mapping of attrnames to row column positions. Used for constructing
        # the model using kwargs, needed when not all model's fields are present
        # in the query.
        model_init_field_names = {}
        # A list of tuples of (column name, column position). Used for
        # annotation fields.
        annotation_fields = []

        # Cache some things for performance reasons outside the loop.
        db = self.db
        compiler = connections[db].ops.compiler('SQLCompiler')(
            self.query, connections[db], db
        )
        need_resolv_columns = hasattr(compiler, 'resolve_columns')

        query = self.query.__getitem__(k)
        # if it is not a slicing make a list out of it
        if not isinstance(k, slice):
            query = [query]

        # Find out which columns are model's fields, and which ones should be
        # annotated to the model.
        for pos, column in enumerate(self.columns):
            if column in self.model_fields:
                model_init_field_names[self.model_fields[column].attname] = pos
            else:
                annotation_fields.append((column, pos))

        # Find out which model's fields are not present in the query.
        skip = set()
        for field in self.model._meta.fields:
            if field.attname not in model_init_field_names:
                skip.add(field.attname)
        if skip:
            if self.model._meta.pk.attname in skip:
                raise InvalidQuery('Raw query must include the primary key')
            model_cls = deferred_class_factory(self.model, skip)
        else:
            model_cls = self.model
            # All model's fields are present in the query. So, it is possible
            # to use *args based model instantation. For each field of the model,
            # record the query column position matching that field.
            model_init_field_pos = []
            for field in self.model._meta.fields:
                model_init_field_pos.append(model_init_field_names[field.attname])
        if need_resolv_columns:
            fields = [self.model_fields.get(c, None) for c in self.columns]
        # Begin looping through the query values.
        res = []
        for values in query:
            if need_resolv_columns:
                values = compiler.resolve_columns(values, fields)
            # Associate fields to values
            if skip:
                model_init_kwargs = {}
                for attname, pos in model_init_field_names.iteritems():
                    model_init_kwargs[attname] = values[pos]
                instance = model_cls(**model_init_kwargs)
            else:
                model_init_args = [values[pos] for pos in model_init_field_pos]
                instance = model_cls(*model_init_args)
            if annotation_fields:
                for column, pos in annotation_fields:
                    setattr(instance, column, values[pos])

            instance._state.db = db
            instance._state.adding = False

            res.append(instance)
        # depending on k value's type return different result
        return res if isinstance(k, slice) else res[0]

    def count(self):
        """Here we implementing just a estimation length of the result set"""
        if self.page_count_mode == 'ALL': return -1   # forces all rows on one page; be very careful using this
        if self.page_count_mode == 'NOCOUNT': return 249975   # 9999*25. shows up as 9999 pages when using default rows per page
        cursor = self.query.cursor
        if cursor is None:
            self.query._execute_query()
        # this logic defaults the count to 249975 if the result set is longer than
        # 249975
        try:
            cursor.scroll(249975)
            record = cursor.fetchone()
            if record is None:
                raise IndexError("Curor scrolling out of bound...")
            numrows = 249975
        except (psycopg2.ProgrammingError, IndexError):
            counter_cursor = self.query._get_counter_cursor()
            counter_cursor.execute(self.count_sql)
            numrows = 0
            row = counter_cursor.fetchone()
            if row:
                numrows = row[0]
            counter_cursor.close()
        cursor.scroll(0, mode="absolute")
        return numrows
