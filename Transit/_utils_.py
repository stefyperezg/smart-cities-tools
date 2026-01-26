"""
Utility functions for GTFS and GTFS-RT data processing, analysis, and visualization.
"""
import geopandas as gpd
import json
import contextily as ctx
import matplotlib.pyplot as plt
import folium
from typing import List, Dict, Optional, Tuple, Any
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from haversine import haversine, Unit
import time
import requests
import gtfs_realtime_pb2
from collections import deque
from shapely.geometry import LineString, Point

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_gtfs_rt_feed(url: str) -> Optional[gtfs_realtime_pb2.FeedMessage]:
    """
    Fetch GTFS-RT feed from URL.
    
    Args:
        url: GTFS-RT feed URL
        
    Returns:
        FeedMessage object or None if failed
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        return feed
    except Exception as e:
        print(f"Error fetching feed from {url}: {e}")
        return None


def plot_map(
    dfs: List[pd.DataFrame],
    lon_col: str,
    lat_col: str,
    colour_column: str,
    cmap: str,
    title: str,
    vehicle_id_col: Optional[str] = None,
    time_threshold_minutes: int = 30
) -> Dict[str, Any]:
    """
    Plot multiple DataFrames as points on a map with basemap.
    Optionally connects points from the same vehicle with lines (within time threshold).
    
    Args:
        dfs: List of DataFrames to plot
        lon_col: Column name for longitude
        lat_col: Column name for latitude
        colour_column: Column to use for coloring points
        cmap: Colormap name
        title: Plot title
        vehicle_id_col: Optional column name for vehicle_id to connect points with lines
        time_threshold_minutes: Maximum time difference in minutes to connect points (default: 30)
        
    Returns:
        Dictionary with information about plotted connections
    """
    fig, ax = plt.subplots(figsize=(9, 9))
    
    connection_info = {
        'vehicles_with_connections': 0,
        'vehicles_with_one_pair': 0,
        'total_connections': 0
    }

    # First, draw lines connecting points from the same vehicle (if vehicle_id_col provided)
    if vehicle_id_col and len(dfs) >= 2:
        # Combine all dataframes to find vehicle connections
        all_dfs = [df for df in dfs if not df.empty and vehicle_id_col in df.columns]
        if len(all_dfs) >= 2:
            # Create combined dataframe
            combined = pd.concat(all_dfs, ignore_index=True)
            
            # Filter by time threshold if timestamp columns exist
            if 'capture_timestamp' in combined.columns:
                combined['timestamp'] = pd.to_datetime(combined['capture_timestamp'])
                current_time = combined['timestamp'].max()
                time_threshold = timedelta(minutes=time_threshold_minutes)
                combined = combined[combined['timestamp'] >= (current_time - time_threshold)].copy()
            elif 'timestamp' in combined.columns:
                combined['timestamp'] = pd.to_datetime(combined['timestamp'])
                current_time = combined['timestamp'].max()
                time_threshold = timedelta(minutes=time_threshold_minutes)
                combined = combined[combined['timestamp'] >= (current_time - time_threshold)].copy()
            
            # Convert to GeoDataFrame for projection
            gdf_combined = gpd.GeoDataFrame(
                combined,
                geometry=gpd.points_from_xy(combined[lon_col], combined[lat_col]),
                crs="EPSG:4326"
            )
            gdf_combined = gdf_combined.to_crs("EPSG:3857")
            
            # Draw lines between consecutive positions for each vehicle
            for vehicle_id in gdf_combined[vehicle_id_col].unique():
                vehicle_data = gdf_combined[gdf_combined[vehicle_id_col] == vehicle_id].copy()
                if len(vehicle_data) >= 2:
                    # Sort by timestamp if available, otherwise by index
                    if 'timestamp' in vehicle_data.columns:
                        vehicle_data = vehicle_data.sort_values('timestamp')
                    
                    # Get coordinates
                    coords = list(zip(vehicle_data.geometry.x, vehicle_data.geometry.y))
                    
                    # Draw line connecting points
                    ax.plot(
                        [c[0] for c in coords],
                        [c[1] for c in coords],
                        color='gray',
                        linewidth=1,
                        alpha=0.5,
                        linestyle='--'
                    )
                    
                    # Track connection info
                    connection_info['vehicles_with_connections'] += 1
                    connection_info['total_connections'] += len(coords) - 1
                    if len(vehicle_data) == 2:
                        connection_info['vehicles_with_one_pair'] += 1

    # Now plot the points
    for df in dfs:
        if df.shape[0] == 0:
            continue

        gdf = gpd.GeoDataFrame(
            df, 
            geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
            crs="EPSG:4326"
        )

        gdf = gdf.to_crs("EPSG:3857")
        gdf.plot(
            ax=ax,
            alpha=1, 
            edgecolor='k',
            column=colour_column,
            cmap=cmap,
            legend=True,
            legend_kwds={'fontsize': 5, 'markerscale': 0.4, 'ncol': 2},
            markersize=20
        )
        
    ctx.add_basemap(ax)

    minx, miny, maxx, maxy = gdf.total_bounds
    center_x = (minx + maxx) / 2
    width_x = maxx - minx

    ax.set_xlim(center_x - width_x, center_x + width_x)
    ax.set_ylim(miny, maxy)
    ax.set_aspect('equal', adjustable='datalim')
    ax.set_aspect('equal')

    plt.title(title)
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.show()

    return connection_info


def plot_route_shapes_and_stops(
    shapes_df: pd.DataFrame,
    stops_df: pd.DataFrame,
    route_id: Optional[str] = None,
    trips_df: Optional[pd.DataFrame] = None,
    routes_df: Optional[pd.DataFrame] = None,
    title: str = "Route Shapes and Stops",
    figsize: Tuple[int, int] = (12, 8)
) -> None:
    """
    Plot route shapes and stops on a static map.
    
    Args:
        shapes_df: DataFrame with shape points (must have 'shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence')
        stops_df: DataFrame with stops (must have 'stop_lat', 'stop_lon')
        route_id: Optional route ID to filter shapes (requires trips_df and routes_df)
        trips_df: Optional trips DataFrame to link shapes to routes
        routes_df: Optional routes DataFrame
        title: Plot title
        figsize: Figure size tuple
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Filter shapes by route if route_id provided
    if route_id and trips_df is not None and routes_df is not None:
        # Get route_id from routes_df
        route_info = routes_df[routes_df['route_id'] == str(route_id)]
        if not route_info.empty:
            # Get trips for this route
            route_trips = trips_df[trips_df['route_id'] == str(route_id)]
            if not route_trips.empty:
                # Get shape_ids for these trips
                shape_ids = route_trips['shape_id'].dropna().unique()
                shapes_df = shapes_df[shapes_df['shape_id'].isin(shape_ids)]
                logger.info(f"Filtered to {len(shape_ids)} shapes for route {route_id}")
    
    # Convert shapes to LineString geometries
    shapes_gdf = None
    if not shapes_df.empty:
        # Group by shape_id and create LineString for each shape
        shapes_gdf_list = []
        for shape_id in shapes_df['shape_id'].unique():
            shape_points = shapes_df[shapes_df['shape_id'] == shape_id].sort_values('shape_pt_sequence')
            if len(shape_points) >= 2:
                coords = list(zip(shape_points['shape_pt_lon'], shape_points['shape_pt_lat']))
                line = LineString(coords)
                shapes_gdf_list.append({'shape_id': shape_id, 'geometry': line})
        
        if shapes_gdf_list:
            shapes_gdf = gpd.GeoDataFrame(shapes_gdf_list, crs="EPSG:4326")
            shapes_gdf = shapes_gdf.to_crs("EPSG:3857")
            
            # Plot shapes
            shapes_gdf.plot(ax=ax, color='blue', linewidth=2, alpha=0.6, label='Route Shapes')
    
    # Plot stops
    stops_gdf = None
    if not stops_df.empty:
        stops_gdf = gpd.GeoDataFrame(
            stops_df,
            geometry=gpd.points_from_xy(stops_df['stop_lon'], stops_df['stop_lat']),
            crs="EPSG:4326"
        )
        stops_gdf = stops_gdf.to_crs("EPSG:3857")
        
        stops_gdf.plot(ax=ax, color='red', markersize=20, alpha=0.7, label='Stops', edgecolor='black')
    
    # Add basemap
    if shapes_gdf is not None:
        try:
            ctx.add_basemap(ax, crs=shapes_gdf.crs)
        except:
            ctx.add_basemap(ax)
    elif stops_gdf is not None:
        try:
            ctx.add_basemap(ax, crs=stops_gdf.crs)
        except:
            ctx.add_basemap(ax)
    else:
        logger.warning("No shapes or stops to plot")
        return
    
    # Set bounds
    if shapes_gdf is not None:
        bounds = shapes_gdf.total_bounds
    elif stops_gdf is not None:
        bounds = stops_gdf.total_bounds
    else:
        return
    
    minx, miny, maxx, maxy = bounds
    width_x = maxx - minx
    height_y = maxy - miny
    padding_x = width_x * 0.1
    padding_y = height_y * 0.1
    
    ax.set_xlim(minx - padding_x, maxx + padding_x)
    ax.set_ylim(miny - padding_y, maxy + padding_y)
    ax.set_aspect('equal')
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel("Longitude (Web Mercator)", fontsize=10)
    ax.set_ylabel("Latitude (Web Mercator)", fontsize=10)
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()


def create_interactive_map(
    vehicle_df: pd.DataFrame,
    stops_df: Optional[pd.DataFrame] = None,
    shapes_gdf: Optional[gpd.GeoDataFrame] = None,
    previous_positions: Optional[pd.DataFrame] = None,
    route_id_col: Optional[str] = None,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    zoom_start: int = 12
) -> folium.Map:
    """
    Create an interactive Folium map with vehicle positions, trails, and stops.
    
    Args:
        vehicle_df: DataFrame with vehicle positions (must have 'latitude', 'longitude')
        stops_df: Optional DataFrame with stop locations
        shapes_gdf: Optional GeoDataFrame with route shapes
        previous_positions: Optional DataFrame with previous vehicle positions for trails
        route_id_col: Optional column name for route ID (for color coding)
        center_lat: Center latitude (auto-calculated if None)
        center_lon: Center longitude (auto-calculated if None)
        zoom_start: Initial zoom level
        
    Returns:
        folium.Map object
    """
    if vehicle_df.empty:
        logger.warning("Vehicle DataFrame is empty, cannot create map")
        return folium.Map()

    # Calculate center if not provided
    if center_lat is None or center_lon is None:
        center_lat = vehicle_df['latitude'].mean()
        center_lon = vehicle_df['longitude'].mean()

    # Create base map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start)

    # Add route shapes if provided
    if shapes_gdf is not None:
        for idx, row in shapes_gdf.iterrows():
            folium.GeoJson(
                row.geometry,
                style_function=lambda x: {
                    'color': 'blue',
                    'weight': 2,
                    'opacity': 0.5
                }
            ).add_to(m)

    # Add stops if provided
    if stops_df is not None and not stops_df.empty:
        for idx, row in stops_df.iterrows():
            folium.CircleMarker(
                location=[row['stop_lat'], row['stop_lon']],
                radius=3,
                popup=f"Stop: {row.get('stop_name', row.get('stop_id', 'Unknown'))}",
                color='black',
                fill=True,
                fillColor='gray',
                fillOpacity=0.7
            ).add_to(m)

    # Add previous positions as trails
    if previous_positions is not None and not previous_positions.empty:
        # Group by vehicle_id to create trails
        for vehicle_id in previous_positions['vehicle_id'].unique():
            vehicle_prev = previous_positions[
                previous_positions['vehicle_id'] == vehicle_id
            ].sort_values('timestamp')
            
            if len(vehicle_prev) > 1:
                trail_coords = [
                    [row['latitude'], row['longitude']]
                    for _, row in vehicle_prev.iterrows()
                ]
                folium.PolyLine(
                    trail_coords,
                    color='gray',
                    weight=2,
                    opacity=0.3,
                    popup=f"Trail: {vehicle_id}"
                ).add_to(m)

    # Add current vehicle positions
    color_map = {}
    if route_id_col and route_id_col in vehicle_df.columns:
        unique_routes = vehicle_df[route_id_col].unique()
        colors = plt.cm.Set3(np.linspace(0, 1, len(unique_routes)))
        color_map = {route: f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
                    for route, (r, g, b, _) in zip(unique_routes, colors)}

    for idx, row in vehicle_df.iterrows():
        color = 'red'
        if route_id_col and route_id_col in vehicle_df.columns:
            color = color_map.get(row[route_id_col], 'red')

        popup_text = f"Vehicle: {row.get('vehicle_id', 'Unknown')}"
        if 'speed' in row:
            popup_text += f"<br>Speed: {row['speed']:.1f} m/s"
        if 'timestamp' in row:
            popup_text += f"<br>Time: {row['timestamp']}"

        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=5,
            popup=folium.Popup(popup_text, max_width=200),
            color='black',
            fill=True,
            fillColor=color,
            fillOpacity=0.8
        ).add_to(m)

    return m


def get_veh_positions_geojson(feed_entity: List) -> Dict[str, Any]:
    """
    Convert GTFS-RT vehicle position feed entities to GeoJSON format.
    
    Args:
        feed_entity: List of FeedEntity objects from GTFS-RT feed
        
    Returns:
        GeoJSON FeatureCollection dictionary
    """
    geojson = {
        "type": "FeatureCollection",
        "features": []
    } 
    
    for entity in feed_entity:
        if entity.HasField('vehicle'):
            vehicle = entity.vehicle
            pos = vehicle.position

            properties = {
                "vehicle_id": vehicle.vehicle.id,
                "bearing": pos.bearing,
                "speed": pos.speed
            }
            
            # Add trip information if available
            if vehicle.HasField('trip'):
                trip = vehicle.trip
                if trip.HasField('trip_id'):
                    properties["trip_id"] = trip.trip_id
                if trip.HasField('route_id'):
                    properties["route_id"] = trip.route_id
                if trip.HasField('direction_id'):
                    properties["direction_id"] = trip.direction_id
            
            # Add timestamp if available (timestamp is in vehicle, not position)
            if vehicle.HasField('timestamp'):
                properties["timestamp"] = vehicle.timestamp

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [pos.longitude, pos.latitude]
                },
                "properties": properties
            }

            geojson["features"].append(feature)
    
    return geojson


def get_veh_positions_dict(feed_entity: List, capture_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    Convert GTFS-RT vehicle position feed entities to list of dictionaries.
    
    Args:
        feed_entity: List of FeedEntity objects from GTFS-RT feed
        capture_timestamp: Optional timestamp when data was captured
        
    Returns:
        List of dictionaries with vehicle position data
    """
    dict_list = []
    capture_ts = capture_timestamp or datetime.now()
    
    for entity in feed_entity:
        if entity.HasField('vehicle'):
            vehicle = entity.vehicle
            pos = vehicle.position

            dict_object = {
                "vehicle_id": vehicle.vehicle.id,
                "bearing": pos.bearing if pos.HasField('bearing') else None,
                "speed": pos.speed if pos.HasField('speed') else None,
                "longitude": pos.longitude, 
                "latitude": pos.latitude,
                "capture_timestamp": capture_ts.isoformat()
            }
            
            # Add trip information if available
            if vehicle.HasField('trip'):
                trip = vehicle.trip
                dict_object["trip_id"] = trip.trip_id if trip.HasField('trip_id') else None
                dict_object["route_id"] = trip.route_id if trip.HasField('route_id') else None
                dict_object["direction_id"] = trip.direction_id if trip.HasField('direction_id') else None
            
            # Add position timestamp (timestamp is in vehicle, not position)
            if vehicle.HasField('timestamp'):
                dict_object["position_timestamp"] = datetime.fromtimestamp(vehicle.timestamp).isoformat()
            else:
                dict_object["position_timestamp"] = capture_ts.isoformat()

            dict_list.append(dict_object)

    return dict_list


def get_trip_updates_dict(feed_entity: List, capture_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    Convert GTFS-RT trip update feed entities to list of dictionaries.
    
    Args:
        feed_entity: List of FeedEntity objects from GTFS-RT feed
        capture_timestamp: Optional timestamp when data was captured
        
    Returns:
        List of dictionaries with trip update data
    """
    dict_list = []
    capture_ts = capture_timestamp or datetime.now()
    
    for entity in feed_entity:
        if entity.HasField('trip_update'):
            trip_update = entity.trip_update
            trip = trip_update.trip
            
            base_dict = {
                "entity_id": entity.id,
                "trip_id": trip.trip_id if trip.HasField('trip_id') else None,
                "route_id": trip.route_id if trip.HasField('route_id') else None,
                "direction_id": trip.direction_id if trip.HasField('direction_id') else None,
                "capture_timestamp": capture_ts.isoformat()
            }
            
            # Add vehicle information if available
            if trip_update.HasField('vehicle'):
                base_dict["vehicle_id"] = trip_update.vehicle.id
            
            # Add stop time updates
            if trip_update.stop_time_update:
                for stop_update in trip_update.stop_time_update:
                    stop_dict = base_dict.copy()
                    stop_dict["stop_id"] = stop_update.stop_id if stop_update.HasField('stop_id') else None
                    stop_dict["stop_sequence"] = stop_update.stop_sequence if stop_update.HasField('stop_sequence') else None
                    
                    # Arrival time
                    if stop_update.HasField('arrival'):
                        arr = stop_update.arrival
                        stop_dict["arrival_delay"] = arr.delay if arr.HasField('delay') else None
                        stop_dict["arrival_time"] = datetime.fromtimestamp(arr.time).isoformat() if arr.HasField('time') else None
                    
                    # Departure time
                    if stop_update.HasField('departure'):
                        dep = stop_update.departure
                        stop_dict["departure_delay"] = dep.delay if dep.HasField('delay') else None
                        stop_dict["departure_time"] = datetime.fromtimestamp(dep.time).isoformat() if dep.HasField('time') else None
                    
                    dict_list.append(stop_dict)
            else:
                # No stop updates, just add base trip info
                dict_list.append(base_dict)
    
    return dict_list


def calculate_speed_from_positions(
    positions_df: pd.DataFrame,
    vehicle_id: str,
    time_col: str = 'capture_timestamp',
    lat_col: str = 'latitude',
    lon_col: str = 'longitude'
) -> Optional[float]:
    """
    Calculate speed (m/s) from a series of positions for a vehicle.
    
    Args:
        positions_df: DataFrame with vehicle positions
        vehicle_id: Vehicle ID to calculate speed for
        time_col: Column name for timestamp
        lat_col: Column name for latitude
        lon_col: Column name for longitude
        
    Returns:
        Speed in m/s, or None if insufficient data
    """
    vehicle_positions = positions_df[
        positions_df['vehicle_id'] == vehicle_id
    ].sort_values(time_col)
    
    if len(vehicle_positions) < 2:
        return None
    
    # Calculate distance and time between last two positions
    pos1 = vehicle_positions.iloc[-2]
    pos2 = vehicle_positions.iloc[-1]
    
    try:
        distance = haversine(
            (pos1[lat_col], pos1[lon_col]),
            (pos2[lat_col], pos2[lon_col]),
            unit=Unit.METERS
        )
        
        time1 = pd.to_datetime(pos1[time_col])
        time2 = pd.to_datetime(pos2[time_col])
        time_delta = (time2 - time1).total_seconds()
        
        if time_delta > 0:
            return distance / time_delta
    except Exception as e:
        logger.warning(f"Error calculating speed for vehicle {vehicle_id}: {e}")
    
    return None


def calculate_time_deltas(df: pd.DataFrame, time_col: str = 'capture_timestamp') -> pd.DataFrame:
    """
    Calculate time deltas between consecutive records.
    
    Args:
        df: DataFrame with timestamps
        time_col: Column name for timestamp
        
    Returns:
        DataFrame with added 'time_delta_seconds' column
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col)
    df['time_delta_seconds'] = df[time_col].diff().dt.total_seconds()
    return df


def df_to_geojson(
    df: pd.DataFrame,
    lat_col: str,
    lon_col: str,
    geometry_type: str = "Point",
    output_file: Optional[str] = None,
    group_by: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convert DataFrame to GeoJSON format.
    
    Args:
        df: DataFrame with geographic data
        lat_col: Column name for latitude
        lon_col: Column name for longitude
        geometry_type: "Point" or "LineString"
        output_file: Optional file path to save GeoJSON
        group_by: Column to group by for LineString (e.g., 'shape_id')
        
    Returns:
        GeoJSON FeatureCollection dictionary
    """
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

        grouped = df.sort_values(by=[group_by, 'shape_pt_sequence']).groupby(group_by)
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


def save_position_history(position_history: Dict[str, deque], file_path: str = "geojson_layers/position_history.json") -> None:
    """
    Save position history to JSON file.
    
    Args:
        position_history: Dictionary mapping vehicle_id to deque of positions
        file_path: Path to save the JSON file
    """
    data = {
        vehicle_id: list(positions)
        for vehicle_id, positions in position_history.items()
    }
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def dict_to_multiindex_df(data: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert a nested dictionary to a multi-index DataFrame.
    
    Args:
        data: Nested dictionary with structure like:
            {
                'route_coverage': {'active_routes': 10, 'total_routes': 20, ...},
                'vehicles_per_route': {'route_1': 5, 'route_2': 3, ...},
                'simple_key': value
            }
    
    Returns:
        DataFrame with MultiIndex (outer_key, inner_key) and Value column
    """
    rows = []
    
    for outer_key, outer_value in data.items():
        if isinstance(outer_value, dict):
            # Nested dictionary - create second level index
            for inner_key, inner_value in outer_value.items():
                rows.append({
                    'outer_index': outer_key,
                    'inner_index': inner_key,
                    'Value': inner_value
                })
        else:
            # Simple value - only outer index
            rows.append({
                'outer_index': outer_key,
                'inner_index': '',
                'Value': outer_value
            })
    
    if not rows:
        return pd.DataFrame()
    
    df = pd.DataFrame(rows)
    df = df.set_index(['outer_index', 'inner_index'])
    df.index.names = [None, None]  # Remove index names for cleaner display
    
    return df
