# permits_plots.py
import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
from pathlib import Path
import plotly.express as px

permits_file_path = r"data/20251496-Rawdata-July-20251.xlsb"
postcodes_folder = 'data/geojson/australian-suburbs-master/GeoJSON/postcodes'


# ---------- helpers ----------
def load_geojson_folder(folder, filename_filter_set=None, name_prop='name'):
    rows = []
    folder = Path(folder)
    for p in folder.glob("*.json"):
        key = p.stem
        if filename_filter_set is not None and key not in filename_filter_set:
            continue
        with open(p, 'r', encoding='utf8') as fh:
            j = json.load(fh)
        feature = j if j.get('type') == 'Feature' else j.get('features', [None])[0]
        if feature is None:
            continue
        geom = shape(feature['geometry'])
        props = feature.get('properties', {})
        rows.append({'filename': key, 'geometry': geom, 'name': props.get(name_prop, key), **props})
    return gpd.GeoDataFrame(rows, geometry='geometry', crs="EPSG:4326")


def normalize_postcode_col(series):
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
            out.append(v.zfill(4) if v.isdigit() else v)
    return pd.Series(out)


# ---------- cached globals ----------
_pc_merged = None
_geojson_pc = None


def prepare_data():
    global _pc_merged, _geojson_pc
    if _pc_merged is not None:
        return _pc_merged, _geojson_pc  # reuse cached version

    permits_df = pd.read_excel(permits_file_path, sheet_name="Sheet1", engine="pyxlsb")
    permits_df['postcode_4'] = normalize_postcode_col(permits_df['site_postcode__c'])
    needed = set(permits_df['postcode_4'].dropna().unique())

    postcodes_gdf = load_geojson_folder(postcodes_folder, filename_filter_set=needed, name_prop='name')
    postcodes_gdf['name'] = postcodes_gdf['name'].astype(str).str.zfill(4)

    agg = permits_df.groupby('postcode_4').agg(
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

    _pc_merged = postcodes_gdf.merge(agg, on='name', how='left').fillna({'permit_count':0, 'total_cost':0})
    _geojson_pc = json.loads(_pc_merged.to_json())

    return _pc_merged, _geojson_pc


# ---------- plotting ----------
def plot_permits_choropleth(permits_category='All'):
    pc_merged, geojson_pc = prepare_data()

    if permits_category not in ['All', 'Domestic', 'Public Buildings', 'Industrial', 'Commercial',
                                'Retail', 'Residential', 'Hospital/Healthcare']:
        raise ValueError("Invalid permits_category")

    color_col = 'permit_count' if permits_category == 'All' else f"{permits_category.lower().replace(' ','_')}_count"

    fig = px.choropleth_mapbox(
        pc_merged,
        geojson=geojson_pc,
        locations='name',
        color=color_col,
        featureidkey="properties.name",
        mapbox_style="open-street-map",
        center={"lat": -25.0, "lon": 133.0},
        zoom=4,
        hover_name='name',
        hover_data={'permit_count': True, 'total_cost': True},
        opacity=0.6,
    )
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    return fig
