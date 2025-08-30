import os
import json
from glob import glob
from pathlib import Path

import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
import json
import plotly.express as px

permits_file_path = r"data/20251496-Rawdata-July-20251.xlsb"

# Step 1: Check sheet names
xls = pd.ExcelFile(permits_file_path, engine="pyxlsb")

# Step 2: Load the sheet that actually contains the planning history data
# Replace 'SheetName' with the correct one after checking
permits_df = pd.read_excel(permits_file_path, sheet_name="Sheet1", engine="pyxlsb")

postcodes_folder = 'data/geojson/australian-suburbs-master/GeoJSON/postcodes'
suburbs_folder = 'data/geojson/australian-suburbs-master/GeoJSON/suburbs'
suburbs_csv = 'data/australian-suburbs-master/data/suburbs.csv'

# ---------- helper: load many small geojson files into a GeoDataFrame ----------
def load_geojson_folder(folder, filename_filter_set=None, filename_digits=4, name_prop='name'):
    """
    folder: path to folder containing many .json files (each a single Feature with properties.name)
    filename_filter_set: set of filenames WITHOUT extension to keep (e.g. {'0800','3142'}). If None -> load all.
    filename_digits: number of digits if you want to zero-pad numeric names (e.g. 4 -> '0800')
    name_prop: property key in geojson to use as 'name' column (default 'name')
    """
    rows = []
    folder = Path(folder)
    for p in folder.glob("*.json"):
        key = p.stem  # filename without .json
        if filename_filter_set is not None and key not in filename_filter_set:
            continue
        with open(p, 'r', encoding='utf8') as fh:
            j = json.load(fh)
        # handle case where file is a Feature (as in your samples)
        feature = j if j.get('type') == 'Feature' else j.get('features', [None])[0]
        if feature is None:
            continue
        geom = shape(feature['geometry'])
        props = feature.get('properties', {})
        rows.append({
            'filename': key,
            'geometry': geom,
            'name': props.get(name_prop, key),
            **props
        })
    gdf = gpd.GeoDataFrame(rows, geometry='geometry', crs="EPSG:4326")
    return gdf

postcodes_gdf = load_geojson_folder(suburbs_folder, filename_filter_set=None, name_prop='name')

# Normalize postcode column to 4-digit strings matching the geojson filenames
def normalize_postcode_col(series):
    # remove NaN, convert to int then zero-pad to 4 digits
    out = []
    for v in series.fillna("").astype(str):
        v = v.strip()
        if v == "" or v.upper() == "NAN":
            out.append(None)
            continue
        try:
            iv = int(float(v))
            out.append(f"{iv:04d}")
        except Exception:
            # if it's already like '0800' or contains letters, keep raw
            out.append(v.zfill(4) if v.isdigit() else v)
    return pd.Series(out)

perm = permits_df.copy()
perm['postcode_4'] = normalize_postcode_col(perm['site_postcode__c'])

# build the set of postcodes we actually need
needed = set(perm['postcode_4'].dropna().unique())

# load only those postcode GeoJSONs (fast)
postcodes_gdf = load_geojson_folder(postcodes_folder, filename_filter_set=needed, name_prop='name')
# make sure 'name' is zero-padded strings too (some datasets store it as int)
postcodes_gdf['name'] = postcodes_gdf['name'].astype(str).str.zfill(4)

# aggregate permits by postcode
agg = perm.groupby('postcode_4').agg(
    permit_count=('permit_stage_number','count'),
    total_cost=('Reported_Cost_of_works','sum'),
    mean_cost=('Reported_Cost_of_works','mean'),
    dommestic_count=('BASIS_Building_Use', lambda x: (x=='Domestic').sum()),
    public_count=('BASIS_Building_Use', lambda x: (x=='Public Buildings').sum()),
    industrial_count=('BASIS_Building_Use', lambda x: (x=='Industrial').sum()),
    commercial_count=('BASIS_Building_Use', lambda x: (x=='Commercial').sum()),
    retail_count=('BASIS_Building_Use', lambda x: (x=='Retail').sum()),
    residential_count=('BASIS_Building_Use', lambda x: (x=='Residential').sum()),
    healthcare_count=('BASIS_Building_Use', lambda x: (x=='Hospital/Healthcare').sum())
).reset_index().rename(columns={'postcode_4': 'name'})

# merge onto the postcode polygons
pc_merged = postcodes_gdf.merge(agg, on='name', how='left').fillna({'permit_count':0, 'total_cost':0})


# prepare geojson from the merged GeoDataFrame
geojson_pc = json.loads(pc_merged.to_json())

def plot_permits_choropleth(permits_category='All'):
    """
    Arguments:
    permits_category enum: ['All', 'Domestic', 'Public Buildings', 'Industrial', 'Commercial',
       'Retail', 'Residential', 'Hospital/Healthcare']
    """
    # Choropleth: color by the selected category count
    if permits_category not in ['All', 'Domestic', 'Public Buildings', 'Industrial', 'Commercial',
       'Retail', 'Residential', 'Hospital/Healthcare']:
        raise ValueError("Invalid permits_category")

    color_col = 'permit_count' if permits_category == 'All' else f"{permits_category.lower().replace(' ','_')}_count"

    fig = px.choropleth_mapbox(
        pc_merged,
        geojson=geojson_pc,
        locations='name',                    # matches properties.name in geojson
        color=color_col,               # column to color by
        featureidkey="properties.name",
        mapbox_style="open-street-map",
        center={"lat": -25.0, "lon": 133.0}, # sensible center for Australia (or compute from your data)
        zoom=4,
        hover_name='name',
        hover_data={'permit_count': True, 'total_cost': True},
        opacity=0.6,
    )
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    return fig


