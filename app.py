from flask import Flask, render_template, jsonify, request
import os, json
import pandas as pd
import geopandas as gpd

from shapely.geometry import Point, MultiLineString, shape, mapping
try:
    # shapely 2.x
    from shapely import from_wkb
except Exception:
    # shapely <2.0 fallback
    from shapely.wkb import loads as from_wkb

app = Flask(__name__, static_folder="static", template_folder="templates")

# ---------- Paths ----------
PARQUET_PATH = os.getenv("BIKE_PARQUET", os.path.join(app.root_path, "data", "bicycle_infra.parquet"))
FACILITIES_XLSX_PATH = os.path.join(app.root_path, "data", "facilities.xlsx")
PT_FILE = os.path.join(app.root_path, "static", "public_transport_stops.geojson")


# ---------- Loaders ----------
def load_bike_parquet(path: str) -> gpd.GeoDataFrame:
    """Load bike lines from a Parquet file regardless of geometry encoding."""
    if not os.path.exists(path):
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    # Try GeoParquet first
    try:
        gdf = gpd.read_parquet(path)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        return gdf
    except Exception:
        pass

    # Generic parquet -> infer geometry
    df = pd.read_parquet(path)

    if "geometry" in df.columns and isinstance(df["geometry"].iloc[0], (bytes, bytearray)):
        geom = df["geometry"].apply(from_wkb)
        gdf = gpd.GeoDataFrame(df.drop(columns=["geometry"]), geometry=geom, crs="EPSG:4326")
        return gdf

    if "geometry" in df.columns:
        def to_geom(g):
            if isinstance(g, str):
                g = json.loads(g)
            return shape(g)
        geom = df["geometry"].apply(to_geom)
        gdf = gpd.GeoDataFrame(df.drop(columns=["geometry"]), geometry=geom, crs="EPSG:4326")
        return gdf

    if {"type", "coordinates"}.issubset(df.columns):
        def row_to_geom(row):
            if row["type"] == "MultiLineString":
                return MultiLineString([[(x, y) for x, y in seg] for seg in row["coordinates"]])
            return shape({"type": row["type"], "coordinates": row["coordinates"]})
        geom = df.apply(row_to_geom, axis=1)
        gdf = gpd.GeoDataFrame(df.drop(columns=["type", "coordinates"]), geometry=geom, crs="EPSG:4326")
        return gdf

    raise ValueError("Unrecognized geometry format in Parquet")


def load_facilities_xlsx(path: str) -> gpd.GeoDataFrame:
    """Load facilities points from the FIRST sheet of an XLSX file."""
    if not os.path.exists(path):
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    cols_lower = {c.lower(): c for c in df.columns}
    lat_col = next((cols_lower.get(k) for k in ["latitude", "lat", "y"]), None)
    lon_col = next((cols_lower.get(k) for k in ["longitude", "long", "lon", "x"]), None)
    if not lat_col or not lon_col:
        raise ValueError("facilities.xlsx must contain Latitude/Longitude (or Lat/Lon or X/Y) columns.")

    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])

    # Light dedupe
    dedupe_keys = [k for k in ["Facility ID", "Facility Name", lat_col, lon_col] if k in df.columns]
    if dedupe_keys:
        df = df.drop_duplicates(subset=dedupe_keys)

    # Friendly names (optional)
    if "Facility Name" not in df.columns:
        for c in ["Facility", "Name", "FACILITY_NAME", "Facility_Name"]:
            if c in df.columns:
                df = df.rename(columns={c: "Facility Name"})
                break
    if "LGA Name" not in df.columns:
        for c in ["LGA", "Council", "LGA_Name"]:
            if c in df.columns:
                df = df.rename(columns={c: "LGA Name"})
                break

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
        crs="EPSG:4326"
    )
    return gdf


# ---------- Load datasets once ----------
BIKES = load_bike_parquet(PARQUET_PATH)
if not BIKES.empty:
    # Normalize/confirm WGS84 to avoid OGC:CRS84/EPSG:4326 mismatch warnings
    BIKES = BIKES.to_crs("EPSG:4326")
    _ = BIKES.sindex

FAC = load_facilities_xlsx(FACILITIES_XLSX_PATH)
if not FAC.empty:
    _ = FAC.sindex


# ---------- Geo helpers ----------
def clip_radius_lines(gdf: gpd.GeoDataFrame, lat: float, lon: float, radius_km: float) -> gpd.GeoDataFrame:
    """Clip line/polygon features to a circular buffer (overlay), matching CRS."""
    if gdf.empty:
        return gdf
    center_wgs84 = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
    buf_3857 = center_wgs84.to_crs(3857).buffer(radius_km * 1000.0)
    buf_in_layer_crs = buf_3857.to_crs(gdf.crs).geometry.iloc[0]
    idx = gdf.sindex.query(buf_in_layer_crs, predicate="intersects") if hasattr(gdf, "sindex") else gdf.index
    sub = gdf.iloc[idx]
    return gpd.overlay(sub, gpd.GeoDataFrame(geometry=[buf_in_layer_crs], crs=gdf.crs), how="intersection")


def clip_radius_points(gdf: gpd.GeoDataFrame, lat: float, lon: float, radius_km: float) -> gpd.GeoDataFrame:
    """Robust point-in-radius selection using metric distance."""
    if gdf.empty:
        return gdf
    center_wgs84 = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
    center_3857 = center_wgs84.to_crs(3857).geometry.iloc[0]
    radius_m = radius_km * 1000.0

    # Optional prefilter
    try:
        buf_3857 = center_wgs84.to_crs(3857).buffer(radius_m)
        buf_wgs84 = buf_3857.to_crs(4326).iloc[0]
        idx = gdf.sindex.query(buf_wgs84, predicate="intersects")
        cand = gdf.iloc[idx]
    except Exception:
        cand = gdf

    cand_3857 = cand.to_crs(3857)
    dists = cand_3857.geometry.distance(center_3857)
    return cand.loc[dists <= radius_m]


def to_feature_collection(gdf: gpd.GeoDataFrame) -> dict:
    """Serialize a GeoDataFrame to GeoJSON FeatureCollection."""
    if gdf.empty:
        return {"type": "FeatureCollection", "features": []}

    def _jsonable(v):
        if pd.isna(v):
            return None
        if hasattr(v, "item"):
            try:
                return v.item()
            except Exception:
                pass
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    keep = [c for c in gdf.columns if c != "geometry"]
    feats = []
    for _, row in gdf.iterrows():
        props = {k: _jsonable(row[k]) for k in keep}
        feats.append({"type": "Feature", "properties": props, "geometry": mapping(row.geometry)})
    return {"type": "FeatureCollection", "features": feats}


# ---------- Routes ----------
@app.route("/")
def root():
    return render_template("housing-stress.html")

@app.route("/housing-stress")
def housing_stress():
    return render_template("housing-stress.html")

@app.get("/api/public_transport")
def api_public_transport():
    with open(PT_FILE, "r") as f:
        data = json.load(f)
    return jsonify(data)

@app.get("/api/bikes_radius")
def api_bikes_radius():
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
        radius_km = float(request.args.get("radius_km", 2.0))
    except Exception:
        return jsonify({"error": "Provide lat, lon and optional radius_km"}), 400

    if BIKES.empty:
        return jsonify({"type": "FeatureCollection", "features": []})

    clipped = clip_radius_lines(BIKES, lat, lon, radius_km)
    return jsonify(to_feature_collection(clipped))

@app.get("/api/facilities_radius")
def api_facilities_radius():
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
        radius_km = float(request.args.get("radius_km", 2.0))
    except Exception as e:
        return jsonify({"error": f"Bad params: {e}"}), 400

    sub = clip_radius_points(FAC, lat, lon, radius_km)

    # Optional text filter
    q = (request.args.get("q") or "").strip()
    if q and not sub.empty:
        ql = q.lower()
        candidate_cols = ["Facility Name", "Facility ID", "LGA Name", "Suburb/Town", "Street Name", "Name", "Facility", "Council"]
        search_cols = [c for c in candidate_cols if c in sub.columns]
        if search_cols:
            hay = sub[search_cols].astype(str).apply(lambda r: " ".join(r.values.tolist()), axis=1).str.lower()
        else:
            fallback = next((c for c in ["Facility Name", "Name", "LGA Name", "Suburb/Town"] if c in sub.columns), None)
            hay = sub[fallback].astype(str).str.lower() if fallback else pd.Series([""] * len(sub), index=sub.index)
        sub = sub[hay.str.contains(ql, na=False)]

    return jsonify(to_feature_collection(sub))

@app.get("/health")
def health():
    return {
        "ok": True,
        "bike_features": int(len(BIKES)),
        "bike_crs": str(BIKES.crs) if not BIKES.empty else None,
        "facilities_rows": int(len(FAC)),
        "facilities_crs": str(FAC.crs) if not FAC.empty else None
    }


# ---------- Main ----------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
