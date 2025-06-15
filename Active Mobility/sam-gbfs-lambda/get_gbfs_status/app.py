import json
import requests
import uuid
import pandas as pd
import _utils_ as utils

def lambda_handler(event, context):
    
    gbfs_url='https://bogota.publicbikesystem.net/customer/gbfs/v2/gbfs.json'
    stations_file_name = "selected_stations 2024-12-04.csv"

    all_data_links = requests.get(gbfs_url).json()
    feeds_dict = {feed['name']: feed['url'] for feed in all_data_links['data']['en']['feeds']}
    request_url = feeds_dict['station_status']

    station_status_df = utils.request_gbfs_data(request_url)

    filtered_station_status_df = utils.format_filter_df (station_status_df, stations_file_name)
    utils.insert_with_on_conflict(filtered_station_status_df, 'gbfs_station_status' )
    print("data inserted")
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Success"
        }),
    }