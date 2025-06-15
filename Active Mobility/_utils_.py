import geopandas as gpd
import contextily as ctx
import matplotlib.pyplot as plt


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


