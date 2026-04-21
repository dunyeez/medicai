import sqlite3

def query_db(query, args=(), one=False):
    with sqlite3.connect('database.db') as con:
        cur = con.cursor()
        cur.execute(query, args)
        rv = cur.fetchall()
        return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    with sqlite3.connect('database.db') as con:
        cur = con.cursor()
        cur.execute(query, args)
        con.commit()
