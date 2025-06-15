from sqlalchemy import create_engine
import psycopg2
import boto3
import json
from botocore.exceptions import ClientError
from psycopg2 import sql

def get_db_secret():

    secret_name = "my-pg-db-access"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        print(e)
        raise e

    secret = get_secret_value_response['SecretString']
    
    return json.loads(secret)


def connect_to_db():
    try:
        cred = get_db_secret()
        connection = psycopg2.connect(
             # PostgreSQL credentials
            user = cred['username'],
            password = cred['password'],
            host = cred['host'],
            port = cred['port'],
            database = cred['dbname']
        )

        # Create a cursor object
        cursor = connection.cursor()

        return connection, cursor

    except psycopg2.Error as e:
        print(f"Error while connecting to PostgreSQL: {e}")
        return None, None

    
def close_connection(conn):

    conn.close()
    return


def get_db_engine():

    # PostgreSQL credentials
    cred = get_secret()
    username = cred['username']
    password = cred['password']
    host = cred['host']
    port = cred['port']
    database = crd['dbname']
   
    # Create SQLAlchemy engine
    engine = create_engine(f'postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}')
    
    return engine

