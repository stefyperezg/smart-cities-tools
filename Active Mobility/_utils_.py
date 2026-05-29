import geopandas as gpd
import contextily as ctx
import matplotlib.pyplot as plt
import numpy as np


def plot_map(df, colour_column, cmap, title):
    # Plotting latitudes and longitudes as points
    plt.figure(figsize=(8,8))

    # Convert DataFrame to GeoDataFrame
    gdf = gpd.GeoDataFrame(
        df, 
        geometry=gpd.points_from_xy(df['lon'], df['lat']),
        crs="EPSG:4326"  # Set the coordinate reference system to WGS84
    )

    # # Plot with a basemap
    gdf = gdf.to_crs("EPSG:3857")  # Project to Web Mercator for compatibility with basemap tiles
    ax = gdf.plot(figsize=(8, 8), alpha=1, edgecolor='k',
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


def haversine(lat1, lon1, lat2, lon2):
    # Calculate the great circle distance between two points on the earth (in meters)
    R = 6371000  # Earth radius in meters
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def select_stations_far_apart(df, n=10, min_dist_m=500):
    selected = []
    for idx, row in df.iterrows():
        if not selected:
            selected.append(idx)
        else:
            too_close = False
            for sel_idx in selected:
                dist = haversine(row['lat'], row['lon'], df.loc[sel_idx, 'lat'], df.loc[sel_idx, 'lon'])
                if dist < min_dist_m:
                    too_close = True
                    break
            if not too_close:
                selected.append(idx)
        if len(selected) == n:
            break
    return df.loc[selected]