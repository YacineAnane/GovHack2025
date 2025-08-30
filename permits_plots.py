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
        domestic_count=('BASIS_Building_Use', lambda x: (x=='Domestic').sum()),
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
        center={"lat": -37.0, "lon": 144.0},
        zoom=6,
        hover_name='name',
        hover_data={'permit_count': True, 'total_cost': True},
        opacity=0.6,
    )
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    return fig

# ---------- new plotting helpers ----------

def plot_permit_sunburst(
    levels=('BASIS_Building_Use', 'BASIS_NOW', 'BASIS_Ownership_Sector'),
    unknown_label='Unknown'
):
    """
    Sunburst showing hierarchy: Building Use -> Nature Of Works -> Ownership Sector.
    Groups by the provided levels and uses counts as the value.
    Returns a plotly.express.sunburst figure.
    """
    # load permits
    df = pd.read_excel(permits_file_path, sheet_name="Sheet1", engine="pyxlsb")

    # keep only columns that exist, replace missing columns with filler levels
    used_levels = []
    for l in levels:
        if l in df.columns:
            used_levels.append(l)
        else:
            # create an artificial column with 'Unknown' so sunburst still works
            df[l] = unknown_label
            used_levels.append(l)

    # Normalise missing values for grouping
    df[used_levels] = df[used_levels].fillna(unknown_label).astype(str)

    # Group and count
    grouped = df.groupby(used_levels).size().reset_index(name='count')

    # build sunburst
    fig = px.sunburst(
        grouped,
        path=used_levels,
        values='count',
        title='Distribution of Permits: Use → Nature of Works → Ownership Sector',
        hover_data={'count': True}
    )
    fig.update_layout(margin={"r":0,"t":30,"l":0,"b":0})
    return fig


def plot_distributions(
    permits_file_path,
    metrics=None,
    bins=60,
    log_scale=False,
    dropna=True
):
    """
    Create distributions (histogram + boxplot) for selected numeric columns.
    Returns a list of tuples (metric_name, hist_fig, box_fig).
    metrics: list of column names (defaults to common cost/area columns)
    log_scale: if True, apply log10 to data for plotting (useful for costs).
    """
    if metrics is None:
        metrics = [
            'Reported_Cost_of_works',
            'Total_Estimated_Cost_of_Works__c',
            'Total_Floor_Area__c'
        ]

    df = pd.read_excel(permits_file_path, sheet_name="Sheet1", engine="pyxlsb")
    out = []

    for metric in metrics:
        if metric not in df.columns:
            # skip absent columns but keep user informed
            print(f"[plot_distributions] skipped missing column: {metric}")
            continue

        # coerce to numeric; many datasets have strings/commas
        col = pd.to_numeric(df[metric].astype(str).str.replace(',', ''), errors='coerce')

        if dropna:
            col = col.dropna()

        if col.empty:
            print(f"[plot_distributions] no numeric data for: {metric}")
            continue

        plot_series = col.copy()
        if log_scale:
            # add small positive offset to avoid log(0)
            plot_series = plot_series[plot_series > 0]  # remove non-positive values for log
            plot_series = np.log10(plot_series)

        plot_df = plot_series.to_frame(name=metric)

        # Histogram
        hist_title = f"Histogram of {metric}" + (" (log10)" if log_scale else "")
        hist_fig = px.histogram(
            plot_df,
            x=metric,
            nbins=bins,
            marginal="rug",
            title=hist_title,
            labels={metric: metric}
        )
        hist_fig.update_layout(margin={"r":0,"t":30,"l":0,"b":0})

        # Boxplot (vertical)
        box_title = f"Boxplot of {metric}" + (" (log10)" if log_scale else "")
        box_fig = px.box(
            plot_df,
            y=metric,
            points="outliers",
            title=box_title,
            labels={metric: metric}
        )
        box_fig.update_layout(margin={"r":0,"t":30,"l":0,"b":0})

        out.append((metric, hist_fig, box_fig))

    return out

