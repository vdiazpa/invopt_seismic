#in_polygon.py
"""Module to determine if points are inside a polygon.Feed two csv files in specific format. Returns df with points inside polygon. Assumes points that make up polygon are in order surrounding the perimeter of the polygon."""

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon

path_to_data = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data" #path to data folder

roi_df = pd.read_csv(fr"{path_to_data}\sgmd_boundaries.csv")
buses = pd.read_csv(fr"{path_to_data}\bus_locations_data.csv")

roi_poly = Polygon(zip(roi_df.longitude, roi_df.latitude))

roi = gpd.GeoDataFrame(geometry=[roi_poly], crs="EPSG:4326")
bus_gdf = gpd.GeoDataFrame(buses,geometry=gpd.points_from_xy(buses.lng, buses.lat), crs="EPSG:4326")

utm = roi.estimate_utm_crs()
roi_p = roi.to_crs(utm).geometry.iloc[0]
bus_p = bus_gdf.to_crs(utm)

inside = bus_p.within(roi_p) | bus_p.touches(roi_p)
inside_buses = bus_p.loc[inside, ["Bus_ID", "lat", "lng"]]

print(f"There are {inside_buses.shape[0]} buses inside the polygon:")
print(inside_buses)
print(type(inside_buses))

inside_buses.to_csv(fr"{path_to_data}\buses_inside_polygon.csv", index=False)