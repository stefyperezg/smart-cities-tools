import pandas as pd
import uuid
import _connection_ as con
from sqlalchemy import text
import requests

def request_gbfs_data (request_url):
    station_status= requests.get(request_url).json()
    station_status_df = pd.DataFrame(station_status['data']['stations'])
    station_status_df = station_status_df.sort_values(by="station_id")
    
    return station_status_df


def format_filter_df (station_status_df, stations_file_name):
    station_status_df['status_uuid'] = [uuid.uuid4() for _ in range(len(station_status_df))]
    station_status_df['city'] = 'bogota_co'
    selected_stations = pd.read_csv(f"selected_stations/{stations_file_name}")
    filtered_stations_status = station_status_df[station_status_df['station_id'].apply(lambda x: int(x) in selected_stations['station_id'])]
    
    return filtered_stations_status

    
def get_table_columns (table_name):
    # Query to get the columns of the target table
    engine = con.get_db_engine()
    select_sql = f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
    """
    # Get the columns in the PostgreSQL table
    with engine.connect() as connection:
        table_columns = pd.read_sql_query(select_sql, connection)
        table_columns = table_columns['column_name'].tolist()
    
    return table_columns


def insert_with_on_conflict(dataframe, table_name):
    
    table_columns = get_table_columns(table_name)

    # Filter the DataFrame to include only columns present in the PostgreSQL table
    filtered_df = dataframe[table_columns]
    
    # Build INSERT query dynamically
    column_names = ", ".join(filtered_df.columns)  # Columns for the INSERT statement
 
    values = []
    for _, row in filtered_df.iterrows():
        formatted_row = tuple(format_value(val) for val in row)
        values.append(formatted_row)
    
    print(len(values), "  inserted values")

    # Create the dynamic query for bulk insert
    query = f"""
    INSERT INTO {table_name} ({column_names})
    VALUES {', '.join([f'({", ".join(row)})' for row in values])}
    ON CONFLICT ON CONSTRAINT unique_station_lastreported DO NOTHING;
    """
    
    conn, cur = con.connect_to_db()
    cur.execute(query)
    conn.commit()
    
    return


def format_value(val):
    if isinstance(val, str):  # Check if the value is a string
        return f"'{val}'"  # Add single quotes around strings
    elif isinstance(val, uuid.UUID):  # If the value is a UUID
        return f"'{str(val)}'"  # Convert the UUID to a string and wrap it in single quotes
    else:
        return str(val)  # For non-strings and non-UUIDs, just return the value as is
