# config.py
import mysql.connector
from mysql.connector import Error

# Database connection configuration
def create_db_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",  # Replace with your MySQL host
            user="root",       # Replace with your MySQL username
            password="Kk@1234859",       # Replace with your MySQL password
            database="sqcb_db"  # Replace with your database name
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None
