import geopandas as gpd
import json
import contextily as ctx
import matplotlib.pyplot as plt


def plot_map(dfs, lon_col, lat_col, colour_column, cmap, title):

    # Plotting latitudes and longitudes as points
    # plt.figure(figsize=(8,5))

    # Create figure and axis once
    fig, ax = plt.subplots(figsize=(8, 5))

    for df in dfs:
        if df.shape[0]==0:
            continue

        # Convert DataFrame to GeoDataFrame
        gdf = gpd.GeoDataFrame(
            df, 
            geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
            crs="EPSG:4326"  # Set the coordinate reference system to WGS84
        )

        # # Plot with a basemap
        gdf = gdf.to_crs("EPSG:3857")  # Project to Web Mercator for compatibility with basemap tiles
        gdf.plot(
            ax = ax,
            alpha=1, 
            edgecolor='k',
            column = colour_column,
            cmap=cmap,
            legend=True,
            markersize=30)
        
    ctx.add_basemap(ax)  # Adds a basemap

    # Calculate bounds and center the x-axis with twice the width
    minx, miny, maxx, maxy = gdf.total_bounds
    center_x = (minx + maxx) / 2  # Center x-coordinate
    width_x = maxx - minx          # Width of the original data bounds

    # Set new x-axis limits for twice the original width, keeping data centered
    ax.set_xlim(center_x - width_x, center_x + width_x)
    ax.set_ylim(miny, maxy)

    # Set aspect ratio to equal for a square map with expanded x-axis
    ax.set_aspect('equal', adjustable='datalim')

    ax.set_aspect('equal')

    plt.title(title)
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.show()


def get_veh_positions_geojson (feed_entity):
    geojson = {
        "type": "FeatureCollection",
        "features": []
    } 
    for entity in feed_entity:
        if entity.HasField('vehicle'):
            vehicle = entity.vehicle
            pos = vehicle.position

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [pos.longitude, pos.latitude]
                },
                "properties": {
                    "vehicle_id": vehicle.vehicle.id,
                    "bearing": pos.bearing,
                    "speed": pos.speed
                }
            }

            geojson["features"].append(feature)
    return geojson


def get_veh_positions_dict (feed_entity):

    dict_list = []
    for entity in feed_entity:
        if entity.HasField('vehicle'):
            vehicle = entity.vehicle
            pos = vehicle.position

            dict_object = {
                "vehicle_id": vehicle.vehicle.id,
                "bearing": pos.bearing,
                "speed": pos.speed,
                "longitude": pos.longitude, 
                "latitude": pos.latitude
                }

            dict_list.append(dict_object)

    return dict_list


def df_to_geojson(df, lat_col, lon_col, geometry_type="Point", output_file=None, group_by=None):
    features = []

    if geometry_type == "Point":
        for _, row in df.iterrows():

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row[lon_col], row[lat_col]]
                },
                "properties": {k: v for k, v in row.items() if k not in [lat_col, lon_col]}
            })

    elif geometry_type == "LineString":
        if not group_by:
            raise ValueError("For LineString, you must provide a group_by column (e.g., 'shape_id').")

        grouped = df.sort_values(by=['shape_id', 'shape_pt_sequence']).groupby(group_by)
        for name, group in grouped:
            coords = list(zip(group[lon_col], group[lat_col]))
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords
                },
                "properties": {"id": name}
            })

    else:
        raise ValueError("geometry_type must be 'Point' or 'LineString'")

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    if output_file:
        with open(output_file, "w") as f:
            json.dump(geojson, f, indent=2)

    return geojson

