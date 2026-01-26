"""
Performance metrics calculations for GTFS and GTFS-RT data.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
import logging
from haversine import haversine, Unit

logger = logging.getLogger(__name__)


def calculate_on_time_performance(
    trip_updates_df: pd.DataFrame,
    stop_times_df: pd.DataFrame,
    stops_df: pd.DataFrame,
    on_time_threshold_minutes: int = 2
) -> Dict[str, any]:
    """
    Calculate on-time performance metrics.
    
    Args:
        trip_updates_df: DataFrame with trip updates (arrival/departure times)
        stop_times_df: DataFrame with scheduled stop times
        stops_df: DataFrame with stop information
        on_time_threshold_minutes: Minutes tolerance for "on-time" (default: ±2 minutes)
        
    Returns:
        Dictionary with OTP metrics
    """
    if trip_updates_df.empty or stop_times_df.empty:
        logger.warning("Empty DataFrames provided for OTP calculation")
        return {}
    
    # Convert merge keys to same type (string) to avoid type mismatch errors
    trip_updates_df = trip_updates_df.copy()
    stop_times_df = stop_times_df.copy()
    
    for col in ['trip_id', 'stop_id', 'stop_sequence']:
        if col in trip_updates_df.columns:
            trip_updates_df[col] = trip_updates_df[col].astype(str)
        if col in stop_times_df.columns:
            stop_times_df[col] = stop_times_df[col].astype(str)
    
    # Merge trip updates with scheduled times
    merged = pd.merge(
        trip_updates_df,
        stop_times_df,
        on=['trip_id', 'stop_id', 'stop_sequence'],
        how='inner',
        suffixes=('_actual', '_scheduled')
    )
    
    if merged.empty:
        logger.warning("No matching trips found for OTP calculation")
        return {}
    
    # Check if we have delay information directly from trip updates (preferred)
    if 'arrival_delay' in merged.columns:
        # Use delay directly from trip updates (in seconds, convert to minutes)
        merged['arrival_delay_minutes'] = merged['arrival_delay'] / 60
        # Filter out rows with no delay data
        merged = merged[merged['arrival_delay_minutes'].notna()].copy()
    elif 'arrival_time_actual' in merged.columns and 'arrival_time_scheduled' in merged.columns:
        # Convert time columns to datetime
        merged['arrival_time_actual'] = pd.to_datetime(merged['arrival_time_actual'], errors='coerce')
        merged['arrival_time_scheduled'] = pd.to_datetime(merged['arrival_time_scheduled'], format='%H:%M:%S', errors='coerce')
        
        # If scheduled time parsing failed, try without format
        if merged['arrival_time_scheduled'].isna().any():
            merged['arrival_time_scheduled'] = pd.to_datetime(merged['arrival_time_scheduled'], errors='coerce')
        
        # Filter out rows with invalid dates
        valid_rows = merged['arrival_time_actual'].notna() & merged['arrival_time_scheduled'].notna()
        if not valid_rows.any():
            logger.warning("No valid datetime pairs found for delay calculation")
            return {}
        
        merged = merged[valid_rows].copy()
        merged['arrival_delay_minutes'] = (
            merged['arrival_time_actual'] - merged['arrival_time_scheduled']
        ).dt.total_seconds() / 60
    else:
        logger.warning("No arrival time or delay information available")
        return {}
    
    if merged.empty:
        logger.warning("No data available after processing delays")
        return {}
    
    # Calculate on-time percentage
    on_time = merged[
        abs(merged['arrival_delay_minutes']) <= on_time_threshold_minutes
    ]
    otp_percentage = (len(on_time) / len(merged)) * 100 if len(merged) > 0 else 0
    
    # Aggregate metrics
    metrics = {
        'total_stops': len(merged),
        'on_time_stops': len(on_time),
        'otp_percentage': otp_percentage,
        'average_delay_minutes': merged['arrival_delay_minutes'].mean(),
        'median_delay_minutes': merged['arrival_delay_minutes'].median(),
        'max_delay_minutes': merged['arrival_delay_minutes'].max(),
        'min_delay_minutes': merged['arrival_delay_minutes'].min(),
        'early_stops': len(merged[merged['arrival_delay_minutes'] < -on_time_threshold_minutes]),
        'late_stops': len(merged[merged['arrival_delay_minutes'] > on_time_threshold_minutes])
    }
    
    # By route
    if 'route_id' in merged.columns:
        route_otp = merged.groupby('route_id').apply(
            lambda x: (abs(x['arrival_delay_minutes']) <= on_time_threshold_minutes).sum() / len(x) * 100
        ).to_dict()
        metrics['otp_by_route'] = route_otp
    
    return metrics
    
    return {}


def calculate_headways(
    vehicle_positions_df: pd.DataFrame,
    trips_df: pd.DataFrame,
    route_id: Optional[str] = None,
    direction_id: Optional[int] = None
) -> Dict[str, any]:
    """
    Calculate headways (time between consecutive vehicles) on routes.
    
    Args:
        vehicle_positions_df: DataFrame with vehicle positions and timestamps
        trips_df: DataFrame with trip information (route_id, direction_id)
        route_id: Optional route ID to filter by
        direction_id: Optional direction ID to filter by
        
    Returns:
        Dictionary with headway metrics
    """
    if vehicle_positions_df.empty:
        return {}
    
    # Merge with trip information
    if 'trip_id' in vehicle_positions_df.columns and not trips_df.empty:
        # Convert trip_id to same type
        vehicle_positions_df = vehicle_positions_df.copy()
        trips_df = trips_df.copy()
        vehicle_positions_df['trip_id'] = vehicle_positions_df['trip_id'].astype(str)
        trips_df['trip_id'] = trips_df['trip_id'].astype(str)
        
        merged = pd.merge(
            vehicle_positions_df,
            trips_df[['trip_id', 'route_id', 'direction_id']],
            on='trip_id',
            how='left'
        )
    else:
        merged = vehicle_positions_df.copy()
    
    # Check if route_id column exists and has valid data
    if 'route_id' not in merged.columns:
        logger.warning("No route_id column found after merge - trip IDs may not match between static and real-time data")
        return {}
    
    # Filter by route/direction if specified
    if route_id:
        merged = merged[merged['route_id'] == route_id]
    if direction_id is not None and 'direction_id' in merged.columns:
        merged = merged[merged['direction_id'] == direction_id]
    
    # Filter out rows where route_id is NaN (no match found)
    merged = merged[merged['route_id'].notna()].copy()
    
    if merged.empty:
        logger.warning("No matching trips found after merge and filtering")
        return {}
    
    # Convert timestamp
    merged['timestamp'] = pd.to_datetime(merged['capture_timestamp'])
    merged = merged.sort_values(['route_id', 'direction_id', 'timestamp'])
    
    # Calculate headways by route and direction
    headways = []
    for (route, direction), group in merged.groupby(['route_id', 'direction_id']):
        group = group.sort_values('timestamp')
        if len(group) > 1:
            time_diffs = group['timestamp'].diff().dt.total_seconds() / 60  # minutes
            for hw in time_diffs.dropna():
                headways.append({
                    'route_id': route,
                    'direction_id': direction,
                    'headway_minutes': hw
                })
    
    if not headways:
        return {}
    
    headways_df = pd.DataFrame(headways)
    
    metrics = {
        'total_headways': len(headways_df),
        'average_headway_minutes': headways_df['headway_minutes'].mean(),
        'median_headway_minutes': headways_df['headway_minutes'].median(),
        'min_headway_minutes': headways_df['headway_minutes'].min(),
        'max_headway_minutes': headways_df['headway_minutes'].max(),
        'headway_std_minutes': headways_df['headway_minutes'].std()
    }
    
    # By route
    if 'route_id' in headways_df.columns:
        route_headways = headways_df.groupby('route_id')['headway_minutes'].agg([
            'mean', 'median', 'std', 'count'
        ]).to_dict('index')
        metrics['headways_by_route'] = route_headways
    
    # Detect bunching (headways < 50% of average) and gaps (headways > 200% of average)
    avg_hw = headways_df['headway_minutes'].mean()
    metrics['bunching_events'] = len(headways_df[headways_df['headway_minutes'] < avg_hw * 0.5])
    metrics['gap_events'] = len(headways_df[headways_df['headway_minutes'] > avg_hw * 2.0])
    
    return metrics


def calculate_service_frequency(
    vehicle_positions_df: pd.DataFrame,
    trips_df: pd.DataFrame,
    time_window_minutes: int = 60
) -> Dict[str, any]:
    """
    Calculate service frequency (vehicles per hour) by route.
    
    Args:
        vehicle_positions_df: DataFrame with vehicle positions
        trips_df: DataFrame with trip information
        time_window_minutes: Time window for frequency calculation (default: 60 minutes)
        
    Returns:
        Dictionary with service frequency metrics
    """
    if vehicle_positions_df.empty:
        return {}
    
    # Merge with trip information
    if 'trip_id' in vehicle_positions_df.columns and not trips_df.empty:
        # Convert trip_id to same type
        vehicle_positions_df = vehicle_positions_df.copy()
        trips_df = trips_df.copy()
        vehicle_positions_df['trip_id'] = vehicle_positions_df['trip_id'].astype(str)
        trips_df['trip_id'] = trips_df['trip_id'].astype(str)
        
        merged = pd.merge(
            vehicle_positions_df,
            trips_df[['trip_id', 'route_id', 'direction_id']],
            on='trip_id',
            how='left'
        )
    else:
        merged = vehicle_positions_df.copy()
    
    # Check if route_id column exists and filter out NaN values
    if 'route_id' not in merged.columns:
        logger.warning("No route_id column found after merge - trip IDs may not match")
        return {}
    
    # Filter out rows where route_id is NaN (no match found)
    merged = merged[merged['route_id'].notna()].copy()
    
    if merged.empty:
        logger.warning("No matching trips found after merge")
        return {}
    
    merged['timestamp'] = pd.to_datetime(merged['capture_timestamp'])
    
    # Calculate frequency by route
    frequency_by_route = {}
    for route_id in merged['route_id'].dropna().unique():
        route_data = merged[merged['route_id'] == route_id]
        
        # Count unique vehicles in time window
        time_range = (
            route_data['timestamp'].max() - timedelta(minutes=time_window_minutes),
            route_data['timestamp'].max()
        )
        window_data = route_data[
            (route_data['timestamp'] >= time_range[0]) &
            (route_data['timestamp'] <= time_range[1])
        ]
        
        unique_vehicles = window_data['vehicle_id'].nunique()
        frequency_per_hour = (unique_vehicles / time_window_minutes) * 60
        
        frequency_by_route[route_id] = {
            'vehicles_per_hour': frequency_per_hour,
            'unique_vehicles': unique_vehicles,
            'time_window_minutes': time_window_minutes
        }
    
    overall_frequency = np.mean([v['vehicles_per_hour'] for v in frequency_by_route.values()]) if frequency_by_route else 0
    
    return {
        'overall_frequency_per_hour': overall_frequency,
        'frequency_by_route': frequency_by_route,
        'total_routes_with_service': len(frequency_by_route)
    }


def calculate_speed_and_travel_time(
    vehicle_positions_df: pd.DataFrame,
    shapes_df: Optional[pd.DataFrame] = None,
    trips_df: Optional[pd.DataFrame] = None
) -> Dict[str, any]:
    """
    Calculate speed and travel time metrics from vehicle positions.
    
    Args:
        vehicle_positions_df: DataFrame with vehicle positions (must have multiple timestamps per vehicle)
        shapes_df: Optional DataFrame with route shapes
        trips_df: Optional DataFrame with trip information
        
    Returns:
        Dictionary with speed and travel time metrics
    """
    if vehicle_positions_df.empty:
        return {}
    
    # Ensure timestamp column exists
    if 'timestamp' not in vehicle_positions_df.columns:
        logger.warning("No timestamp column found for speed calculation")
        return {}
    
    vehicle_positions_df = vehicle_positions_df.copy()
    vehicle_positions_df['timestamp'] = pd.to_datetime(vehicle_positions_df['timestamp'])
    
    # Calculate speeds for each vehicle
    speeds = []
    travel_times = []
    
    for vehicle_id in vehicle_positions_df['vehicle_id'].unique():
        vehicle_data = vehicle_positions_df[
            vehicle_positions_df['vehicle_id'] == vehicle_id
        ].sort_values('timestamp')
        
        if len(vehicle_data) < 2:
            continue
        
        # Calculate speed between consecutive positions
        for i in range(1, len(vehicle_data)):
            pos1 = vehicle_data.iloc[i-1]
            pos2 = vehicle_data.iloc[i]
            
            try:
                distance = haversine(
                    (pos1['latitude'], pos1['longitude']),
                    (pos2['latitude'], pos2['longitude']),
                    unit=Unit.METERS
                )
                
                time_delta = (pos2['timestamp'] - pos1['timestamp']).total_seconds()
                
                if time_delta > 0:
                    speed_mps = distance / time_delta
                    speeds.append({
                        'vehicle_id': vehicle_id,
                        'speed_mps': speed_mps,
                        'speed_kmh': speed_mps * 3.6,
                        'distance_meters': distance,
                        'time_seconds': time_delta
                    })
                    
                    travel_times.append({
                        'vehicle_id': vehicle_id,
                        'travel_time_seconds': time_delta,
                        'distance_meters': distance
                    })
            except Exception as e:
                logger.warning(f"Error calculating speed for vehicle {vehicle_id}: {e}")
    
    if not speeds:
        return {}
    
    speeds_df = pd.DataFrame(speeds)
    travel_times_df = pd.DataFrame(travel_times)
    
    metrics = {
        'average_speed_mps': speeds_df['speed_mps'].mean(),
        'average_speed_kmh': speeds_df['speed_kmh'].mean(),
        'median_speed_kmh': speeds_df['speed_kmh'].median(),
        'max_speed_kmh': speeds_df['speed_kmh'].max(),
        'min_speed_kmh': speeds_df['speed_kmh'].min(),
        'speed_std_kmh': speeds_df['speed_kmh'].std(),
        'average_travel_time_seconds': travel_times_df['travel_time_seconds'].mean(),
        'total_measurements': len(speeds_df)
    }
    
    # By vehicle
    vehicle_speeds = speeds_df.groupby('vehicle_id')['speed_kmh'].agg(['mean', 'max', 'count']).to_dict('index')
    metrics['speed_by_vehicle'] = vehicle_speeds
    
    # By route if available
    if trips_df is not None and not trips_df.empty and 'trip_id' in vehicle_positions_df.columns:
        # Convert trip_id to same type
        vehicle_positions_df = vehicle_positions_df.copy()
        trips_df = trips_df.copy()
        vehicle_positions_df['trip_id'] = vehicle_positions_df['trip_id'].astype(str)
        trips_df['trip_id'] = trips_df['trip_id'].astype(str)
        
        merged = pd.merge(
            vehicle_positions_df[['vehicle_id', 'trip_id']].drop_duplicates(),
            trips_df[['trip_id', 'route_id']],
            on='trip_id',
            how='left'
        )
        speeds_with_route = speeds_df.merge(
            merged[['vehicle_id', 'route_id']],
            on='vehicle_id',
            how='left'
        )
        if 'route_id' in speeds_with_route.columns:
            route_speeds = speeds_with_route.groupby('route_id')['speed_kmh'].agg(['mean', 'median']).to_dict('index')
            metrics['speed_by_route'] = route_speeds
    
    return metrics


def calculate_spatial_coverage(
    vehicle_positions_df: pd.DataFrame,
    routes_df: pd.DataFrame,
    shapes_df: Optional[pd.DataFrame] = None,
    stops_df: Optional[pd.DataFrame] = None
) -> Dict[str, any]:
    """
    Calculate spatial coverage metrics (route coverage, stop coverage, service gaps).
    
    Args:
        vehicle_positions_df: DataFrame with vehicle positions
        routes_df: DataFrame with route information
        shapes_df: Optional DataFrame with route shapes
        stops_df: Optional DataFrame with stop locations
        
    Returns:
        Dictionary with spatial coverage metrics
    """
    if vehicle_positions_df.empty or routes_df.empty:
        return {}
    
    metrics = {}
    
    # Route coverage
    if 'route_id' in vehicle_positions_df.columns:
        active_routes = vehicle_positions_df['route_id'].dropna().nunique()
        total_routes = routes_df['route_id'].nunique()
        route_coverage_pct = (active_routes / total_routes * 100) if total_routes > 0 else 0
        
        metrics['route_coverage'] = {
            'active_routes': int(active_routes),
            'total_routes': int(total_routes),
            'coverage_percentage': route_coverage_pct,
            'active_route_ids': vehicle_positions_df['route_id'].dropna().unique().tolist()
        }
    
    # Stop coverage (if stops data available)
    if stops_df is not None and not stops_df.empty:
        # This is a simplified version - would need to calculate distance from vehicles to stops
        # For now, just report total stops
        metrics['stop_coverage'] = {
            'total_stops': len(stops_df),
            'note': 'Distance-based coverage calculation requires spatial analysis'
        }
    
    # Service density (vehicles per route)
    if 'route_id' in vehicle_positions_df.columns:
        vehicles_per_route = vehicle_positions_df.groupby('route_id')['vehicle_id'].nunique().to_dict()
        metrics['vehicles_per_route'] = vehicles_per_route
        metrics['average_vehicles_per_route'] = np.mean(list(vehicles_per_route.values())) if vehicles_per_route else 0
    
    # Geographic bounds
    if 'latitude' in vehicle_positions_df.columns and 'longitude' in vehicle_positions_df.columns:
        metrics['geographic_bounds'] = {
            'min_lat': float(vehicle_positions_df['latitude'].min()),
            'max_lat': float(vehicle_positions_df['latitude'].max()),
            'min_lon': float(vehicle_positions_df['longitude'].min()),
            'max_lon': float(vehicle_positions_df['longitude'].max())
        }
    
    return metrics
