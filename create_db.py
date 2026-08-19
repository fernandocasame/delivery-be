import os
import pymysql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

db_name = os.environ.get('MYSQL_DATABASE', 'delivery')
db_user = os.environ.get('MYSQL_USER', 'fcasame')
db_password = os.environ.get('MYSQL_PASSWORD', 'Cdarfgvn3004!')
db_host = os.environ.get('MYSQL_HOST', '192.168.20.80')
db_port = int(os.environ.get('MYSQL_PORT', '3306'))

print(f"Checking if database '{db_name}' already exists and is accessible...")
try:
    conn = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name,
        port=db_port
    )
    conn.close()
    print(f"Database '{db_name}' already exists and is fully accessible! No need to create.")
except pymysql.err.OperationalError as e:
    # 1049 is ER_BAD_DB_ERROR (Unknown database)
    if e.args[0] == 1049:
        print(f"Database '{db_name}' does not exist. Connecting to MySQL server to create it...")
        try:
            conn = pymysql.connect(
                host=db_host,
                user=db_user,
                password=db_password,
                port=db_port
            )
            cursor = conn.cursor()
            print(f"Creating database '{db_name}'...")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.close()
            conn.close()
            print("Database check/creation complete.")
        except Exception as create_err:
            print(f"Error creating database: {create_err}")
            raise create_err
    else:
        print(f"Operational error connecting to database: {e}")
        raise e
except Exception as e:
    print(f"Error connecting to database: {e}")
    raise e

