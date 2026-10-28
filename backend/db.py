from contextlib import contextmanager

from mysql.connector import pooling

import config

_pool = pooling.MySQLConnectionPool(
    pool_name="transitiq_pool",
    pool_size=5,
    **config.DB_CONFIG,
)


def query(sql, params=(), one=False):
    # Run a SELECT and return rows as dictionaries.
    conn = _pool.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
        if one:
            return rows[0] if rows else None
        return rows
    finally:
        conn.close()


@contextmanager
def transaction():
    # Yield a cursor; commit if the block succeeds, roll back if it fails.
    conn = _pool.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        yield cursor
        conn.commit()
        cursor.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()