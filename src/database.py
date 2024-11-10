import mysql.connector
from mysql.connector import pooling

db_config = {
    'user': 'root',
    'password': 'Solomia1997/',
    'host': 'localhost',
    'database': 'birthdays_db',
    'port': 3306,
    'use_pure': True
}

connection_pool = mysql.connector.pooling.MySQLConnectionPool(**db_config)

def get_connection():
    return connection_pool.get_connection()