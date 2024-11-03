import psycopg2
import pandas as pd
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()


class PostgreSQLConnector:
    def __init__(self):
        self.host = os.environ.get('HOST')
        self.database = os.environ.get('DATABASE')
        self.user = os.environ.get('USERSQL')
        self.password = os.environ.get('PASSWORD')

    def _open_connection(self):
        self.conn = psycopg2.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password
        )
        self.cur = self.conn.cursor()

    def _close_connection(self):
        if hasattr(self, 'cur') and self.cur:
            self.cur.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def with_connection(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                self._open_connection()
                return func(self, *args, **kwargs)
            except Exception as e:
                print(f"An error occurred: {e}")
                raise
            finally:
                self._close_connection()

        return wrapper

    @with_connection
    def read_data_to_dataframe(self, query):
        return pd.read_sql_query(query, self.conn)

    @with_connection
    def read_data(self, query, params=None):
        self.cur.execute(query, params)
        return self.cur.fetchall()

    @with_connection
    def insert_data_from_dataframe(self, df, table_name):
        columns = ', '.join(df.columns)
        values = ', '.join(['%s'] * len(df.columns))
        insert_query = f"INSERT INTO {table_name} ({columns}) VALUES ({values})"

        data = [tuple(row) for row in df.to_numpy()]
        self.cur.executemany(insert_query, data)
        self.conn.commit()

    @with_connection
    def insert_data(self, data, table_name, columns):
        values = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join(columns)
        insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({values})"

        self.cur.executemany(insert_query, data)
        self.conn.commit()

    @with_connection
    def update_data(self, table_name, condition_column, condition_value, update_column, new_value):
        update_query = f"""
        UPDATE {table_name}
        SET {update_column} = %s
        WHERE {condition_column} = %s
        """

        self.cur.execute(update_query, (new_value, condition_value))
        self.conn.commit()
