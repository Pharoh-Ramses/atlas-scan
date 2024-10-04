import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_db_connection():
    try:
        connection = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', 5432)
        )
        return connection
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        return None

def close_db_connection(connection):
    if connection:
        connection.close()
        print("PostgreSQL connection is closed")

def create_atlas_files_table():
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            create_table_query = '''
            CREATE TABLE IF NOT EXISTS atlas_files (
                id SERIAL PRIMARY KEY,
                patient_name TEXT,
                date_of_birth TEXT,
                gender TEXT,
                mrn TEXT,
                test_name TEXT,
                test_device TEXT,
                specimen_type TEXT,
                collection_date TEXT,
                tested_pathogen TEXT,
                test_result TEXT,
                reported_date TEXT
            )
            '''
            cursor.execute(create_table_query)
            connection.commit()
            print("Table 'atlas_files' created successfully")
        except (Exception, psycopg2.Error) as error:
            print("Error creating table:", error)
        finally:
            close_db_connection(connection)