# config.py
import mysql.connector
from mysql.connector import Error

# Database connection configuration
def create_db_connection():
    try:
        connection = mysql.connector.connect(
            host="Attakan.mysql.pythonanywhere-services.com",  # Replace with AwardSpace MySQL host
            user="Attakan",   # Replace with AwardSpace MySQL username
            password="Kk@1234859",   # Replace with AwardSpace MySQL password
            database="Attakan$sqcbdb"  # Replace with your AwardSpace database name
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None
