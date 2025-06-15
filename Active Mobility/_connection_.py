from sqlalchemy import create_engine
import pandas as pd
import boto3
from botocore.exceptions import ClientError


def get_secret():

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
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret = get_secret_value_response['SecretString']
    return secret


def insert_data (dataframe, table_name):
    # PostgreSQL credentials
    cred = get_secret()
    username = cred['username']
    password = cred['password']
    host = cred['host']
    port = cred['port']
    database = crd['dbname']

    # Create SQLAlchemy engine
    engine = create_engine(f'postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}')

    # add columns required in database
    # Get the columns of the target PostgreSQL table
    with engine.connect() as connection:
        table_columns = pd.read_sql_query(f'SELECT column_name FROM information_schema.columns WHERE table_name = \'{table_name}\'', connection)
        table_columns = table_columns['column_name'].tolist()

    # Filter the DataFrame to include only columns present in the PostgreSQL table
    filtered_df = dataframe[table_columns]

    # Insert the filtered DataFrame into PostgreSQL
    filtered_df.to_sql(table_name, con=engine, if_exists='append', index=False)

    return

