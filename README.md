A Implementation of Django's psycopg2 backend utilizing Postgres Server Side Cursor

Dependencies:
   postgresql
   psycopg2 >= 2.5

This is just quote from psycopg2 documentation
"
When a PostgresSQL database query is executed, the Psycopg cursor usually fetches all the records returned by the backend, 
transferring them to the client process. If the query returned an huge amount of data, a proportionally large amount of
 memory will be allocated by the client.
 
If the dataset is too large to be practically handled on the client side, it is possible to create a server side cursor. Using
 this kind of cursor it is possible to transfer to the client only a controlled amount of data, so that a large dataset can be 
 examined without keeping it entirely in memory"
 

 So Here I implemented the server side cursor backend for django. The Aim for this project is to benefit the large database
 query and paging a large database result set, without over-writing the default Django's postgres_psycopg2 base class.
 
 Usage:
 1. Check out the folder under your project
 2. Use the following code idiom:
 
    ```
    from <yourproject>.db import connection
    cur = connection.cursor()
    cur.execute(<your_raw_query_statement>)
    ```


 3. There is also a re-written paginatable QuerySet that works with django's default Paginator:
 
    ```
    from <yourproject>.db.queryset_helper import SmartPaginatableRawQuerySet
    qr = SmartPaginatableRawQuerySet(<your_raw_query_statement>) 
    pgt = Paginator(qr, <row_per_page>)
    pg = pgt.page(<page_number>)
    ```
    
 If you have any comments && feature suggests, feel free to leave me an email or message.
