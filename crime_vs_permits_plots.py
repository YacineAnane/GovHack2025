import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import re

# Load data
crime = pd.read_excel('data/Data_Tables_LGA_Victim_Reports_Year_Ending_March_2025.xlsx', sheet_name='Table 02')
suburb = pd.read_csv('data/geojson/australian-suburbs-master/data/suburbs.csv')


# --- Create base LGA name in suburbs for merging ---
suburb['local_goverment_area_base'] = suburb['local_goverment_area'].apply(
    lambda x: re.sub(r"\s*\(.*?\)$", "", x).strip()
)

crime_by_local_gov = crime.groupby(by=['Local Government Area']).agg(
    victim_reports=('Victim Reports', 'sum')
)

suburb_by_local_gov = suburb.groupby('local_goverment_area_base').agg(
    population=('population', 'sum'),
    lat=('lat', "mean"),
    lon=('lng', 'mean'),
    postcode=('postcode', 'first')
).reset_index()

suburb_by_local_gov = suburb.groupby('local_goverment_area_base').agg(
    population=('population', 'sum'),
    lat=('lat', "mean"),
    lon=('lng', 'mean'),
    postcode=('postcode', 'first')
).reset_index()

merged_df = suburb_by_local_gov.merge(crime_by_local_gov, left_on='local_goverment_area_base', right_on='Local Government Area')
# Make sure your lat/lon columns are numeric
merged_df['lat'] = pd.to_numeric(merged_df['lat'])
merged_df['lon'] = pd.to_numeric(merged_df['lon'])
merged_df['population'] = pd.to_numeric(merged_df['population'])
merged_df['victim_reports'] = pd.to_numeric(merged_df['victim_reports'])


def plot_crimes_map():
    fig = px.scatter_mapbox(
        merged_df,
        lat='lat',
        lon='lon',
        size='population',                 # bubble size = population
        color='victim_reports',            # bubble color = victim reports
        hover_name='local_goverment_area_base',
        hover_data={'population': True, 'victim_reports': True, 'lat': False, 'lon': False},
        color_continuous_scale='Reds',
        size_max=50,
        zoom=6,
        mapbox_style='carto-positron'      # nice clean basemap
    )

    fig.update_layout(
        title="Population and Victim Reports in Victoria, Australia",
        margin={"r":0,"t":50,"l":0,"b":0}
    )
    return fig